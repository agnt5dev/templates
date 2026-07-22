// Agent tools: PR fetch, Jira/Linear ticket fetch, and ticket-source
// detection, wrapping GitHub REST, Jira REST v3, and Linear GraphQL.
package code_reviewer

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"time"

	"agnt5.dev/sdk-go/agnt5"
)

var apiClient = &http.Client{Timeout: 30 * time.Second}

var (
	prURLPattern     = regexp.MustCompile(`^https://github\.com/([^/]+)/([^/]+)/pull/(\d+)`)
	jiraKeyPattern   = regexp.MustCompile(`/browse/([A-Z0-9\-]+)`)
	linearKeyPattern = regexp.MustCompile(`/issue/([A-Z0-9\-]+)`)
)

func doJSON(req *http.Request, out any) error {
	resp, err := apiClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
	}
	return json.NewDecoder(resp.Body).Decode(out)
}

// callGitHubAPI fetches one GitHub API URL with retry (matches the Python
// template's call_github_api function, which has its own RetryPolicy).
func callGitHubAPI(ctx context.Context, url, token string, out any) error {
	return retryWithBackoff(ctx, 3, func() error {
		req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
		if err != nil {
			return err
		}
		req.Header.Set("Authorization", "token "+token)
		req.Header.Set("Accept", "application/vnd.github.v3+json")
		return doJSON(req, out)
	})
}

// fetchAllPRFiles paginates through every changed file on a PR (GitHub caps
// at 30/page by default), following the Link response header.
func fetchAllPRFiles(ctx context.Context, filesURL, token string) ([]PRFile, error) {
	var allFiles []PRFile
	pageURL := filesURL + "?per_page=100&page=1"

	for pageURL != "" {
		req, err := http.NewRequestWithContext(ctx, http.MethodGet, pageURL, nil)
		if err != nil {
			return nil, err
		}
		req.Header.Set("Authorization", "token "+token)
		req.Header.Set("Accept", "application/vnd.github.v3+json")

		var resp *http.Response
		err = retryWithBackoff(ctx, 3, func() error {
			var doErr error
			resp, doErr = apiClient.Do(req)
			return doErr
		})
		if err != nil {
			return nil, err
		}

		var page []struct {
			Filename  string `json:"filename"`
			Status    string `json:"status"`
			Additions int    `json:"additions"`
			Deletions int    `json:"deletions"`
			Patch     string `json:"patch"`
		}
		decodeErr := json.NewDecoder(resp.Body).Decode(&page)
		linkHeader := resp.Header.Get("Link")
		resp.Body.Close()
		if decodeErr != nil {
			return nil, decodeErr
		}

		for _, f := range page {
			allFiles = append(allFiles, PRFile{
				Filename: f.Filename, Status: f.Status,
				Additions: f.Additions, Deletions: f.Deletions,
				Patch: f.Patch, HasPatch: f.Patch != "",
			})
		}

		pageURL = ""
		for _, part := range strings.Split(linkHeader, ",") {
			part = strings.TrimSpace(part)
			if strings.Contains(part, `rel="next"`) {
				if i := strings.Index(part, ";"); i > 0 {
					pageURL = strings.Trim(strings.TrimSpace(part[:i]), "<>")
				}
				break
			}
		}
	}
	return allFiles, nil
}

// fetchPR fetches PR metadata and ALL changed files (paginated) from the
// GitHub REST API.
func fetchPR(ctx context.Context, prURL, githubToken string) (PRData, error) {
	match := prURLPattern.FindStringSubmatch(prURL)
	if match == nil {
		return PRData{}, fmt.Errorf("invalid PR URL: %s", prURL)
	}
	owner, repo, prNumberStr := match[1], match[2], match[3]
	prNumber, _ := strconv.Atoi(prNumberStr)

	apiURL := fmt.Sprintf("https://api.github.com/repos/%s/%s/pulls/%s", owner, repo, prNumberStr)
	var meta struct {
		Title string `json:"title"`
		User  struct {
			Login string `json:"login"`
		} `json:"user"`
		State        string `json:"state"`
		Body         string `json:"body"`
		ChangedFiles int    `json:"changed_files"`
		Additions    int    `json:"additions"`
		Deletions    int    `json:"deletions"`
	}
	if err := callGitHubAPI(ctx, apiURL, githubToken, &meta); err != nil {
		return PRData{}, err
	}

	filesURL := fmt.Sprintf("https://api.github.com/repos/%s/%s/pulls/%s/files", owner, repo, prNumberStr)
	files, err := fetchAllPRFiles(ctx, filesURL, githubToken)
	if err != nil {
		return PRData{}, err
	}

	return PRData{
		Repo: owner + "/" + repo, PRNumber: prNumber,
		Title: meta.Title, Author: meta.User.Login, State: meta.State,
		Description: meta.Body, ChangedFiles: meta.ChangedFiles,
		Additions: meta.Additions, Deletions: meta.Deletions, Files: files,
	}, nil
}

func NewPRFetcherTool(cfg AppConfig) (agnt5.Tool, error) {
	return agnt5.NewTool("pr_fetcher", func(c context.Context, args map[string]any) (any, error) {
		prURL, _ := args["pr_url"].(string)
		logInfo(c, "Fetching PR", "url", prURL)
		data, err := fetchPR(c, prURL, cfg.GitHubToken)
		if err != nil {
			logError(c, "PR fetch failed", "error", err)
			return nil, err
		}
		logInfo(c, "PR fetched", "files", len(data.Files), "additions", data.Additions, "deletions", data.Deletions)
		return data, nil
	},
		agnt5.WithToolDescription("Fetch Pull Request metadata and ALL file diffs from GitHub REST API."),
		agnt5.WithToolSchema(map[string]any{
			"type": "object",
			"properties": map[string]any{
				"pr_url": map[string]any{"type": "string", "description": "Full GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)"},
			},
			"required": []string{"pr_url"},
		}),
	)
}

func NewJiraTicketFetcherTool(cfg AppConfig) (agnt5.Tool, error) {
	return agnt5.NewTool("jira_ticket_fetcher", func(c context.Context, args map[string]any) (any, error) {
		ticketURL, _ := args["ticket_url"].(string)
		data, err := fetchJiraTicket(c, ticketURL, cfg)
		if err != nil {
			logError(c, "Jira fetch failed", "error", err)
			return nil, err
		}
		return data, nil
	},
		agnt5.WithToolDescription("Fetch Jira issue details via REST API (v3)."),
		agnt5.WithToolSchema(map[string]any{
			"type": "object",
			"properties": map[string]any{
				"ticket_url": map[string]any{"type": "string", "description": "Full Jira ticket URL (e.g., https://company.atlassian.net/browse/PROJ-123)"},
			},
			"required": []string{"ticket_url"},
		}),
	)
}

func fetchJiraTicket(ctx context.Context, ticketURL string, cfg AppConfig) (TicketData, error) {
	if cfg.JiraEmail == "" || cfg.JiraAPIToken == "" || cfg.JiraDomain == "" {
		return TicketData{}, fmt.Errorf("missing Jira credentials (JIRA_EMAIL, JIRA_API_TOKEN, JIRA_DOMAIN)")
	}
	match := jiraKeyPattern.FindStringSubmatch(ticketURL)
	if match == nil {
		return TicketData{}, fmt.Errorf("invalid Jira ticket URL: %s", ticketURL)
	}
	ticketKey := match[1]
	apiURL := fmt.Sprintf("%s/rest/api/3/issue/%s", cfg.JiraDomain, ticketKey)

	var data struct {
		Key    string `json:"key"`
		Fields struct {
			Summary string `json:"summary"`
			Status  struct {
				Name string `json:"name"`
			} `json:"status"`
			Assignee struct {
				DisplayName string `json:"displayName"`
			} `json:"assignee"`
			Priority struct {
				Name string `json:"name"`
			} `json:"priority"`
			Project struct {
				Name string `json:"name"`
			} `json:"project"`
			Description any `json:"description"`
		} `json:"fields"`
	}

	err := retryWithBackoff(ctx, 3, func() error {
		req, err := http.NewRequestWithContext(ctx, http.MethodGet, apiURL, nil)
		if err != nil {
			return err
		}
		req.SetBasicAuth(cfg.JiraEmail, cfg.JiraAPIToken)
		req.Header.Set("Accept", "application/json")
		return doJSON(req, &data)
	})
	if err != nil {
		return TicketData{}, err
	}

	return TicketData{
		Available: true, Source: "jira", Key: data.Key,
		Summary: data.Fields.Summary, Status: data.Fields.Status.Name,
		Priority:    data.Fields.Priority.Name,
		Description: strings.TrimSpace(parseADF(data.Fields.Description)),
		URL:         ticketURL,
	}, nil
}

func NewLinearTicketFetcherTool(cfg AppConfig) (agnt5.Tool, error) {
	return agnt5.NewTool("linear_ticket_fetcher", func(c context.Context, args map[string]any) (any, error) {
		ticketURL, _ := args["ticket_url"].(string)
		data, err := fetchLinearTicket(c, ticketURL, cfg)
		if err != nil {
			logError(c, "Linear fetch failed", "error", err)
			return nil, err
		}
		return data, nil
	},
		agnt5.WithToolDescription("Fetch Linear issue details using GraphQL API."),
		agnt5.WithToolSchema(map[string]any{
			"type": "object",
			"properties": map[string]any{
				"ticket_url": map[string]any{"type": "string", "description": "Full Linear ticket URL (e.g., https://linear.app/team/issue/PROJ-123)"},
			},
			"required": []string{"ticket_url"},
		}),
	)
}

func fetchLinearTicket(ctx context.Context, ticketURL string, cfg AppConfig) (TicketData, error) {
	if cfg.LinearKey == "" {
		return TicketData{}, fmt.Errorf("missing LINEAR_API_TOKEN in environment variables")
	}
	match := linearKeyPattern.FindStringSubmatch(ticketURL)
	if match == nil {
		return TicketData{}, fmt.Errorf("invalid Linear ticket URL: %s", ticketURL)
	}
	ticketKey := match[1]

	query := fmt.Sprintf(`{"query":"{ issue(id: \"%s\") { id identifier title description url state { name } assignee { name } team { name key } priority createdAt updatedAt dueDate } }"}`, ticketKey)

	var data struct {
		Data struct {
			Issue *struct {
				Identifier  string `json:"identifier"`
				Title       string `json:"title"`
				Description string `json:"description"`
				URL         string `json:"url"`
				State       struct {
					Name string `json:"name"`
				} `json:"state"`
				Assignee struct {
					Name string `json:"name"`
				} `json:"assignee"`
				Team struct {
					Name string `json:"name"`
				} `json:"team"`
				Priority float64 `json:"priority"`
			} `json:"issue"`
		} `json:"data"`
	}

	err := retryWithBackoff(ctx, 3, func() error {
		req, err := http.NewRequestWithContext(ctx, http.MethodPost, "https://api.linear.app/graphql", strings.NewReader(query))
		if err != nil {
			return err
		}
		req.Header.Set("Authorization", cfg.LinearKey)
		req.Header.Set("Content-Type", "application/json")
		return doJSON(req, &data)
	})
	if err != nil {
		return TicketData{}, err
	}
	if data.Data.Issue == nil {
		return TicketData{}, fmt.Errorf("no issue found for Linear key: %s", ticketKey)
	}
	issue := data.Data.Issue

	priority := ""
	if issue.Priority != 0 {
		priority = strconv.FormatFloat(issue.Priority, 'f', -1, 64)
	}

	return TicketData{
		Available: true, Source: "linear", Key: issue.Identifier,
		Summary: issue.Title, Status: issue.State.Name, Priority: priority,
		Description: issue.Description, URL: issue.URL,
	}, nil
}

func NewDetectTicketSourceTool() (agnt5.Tool, error) {
	return agnt5.NewTool("detect_ticket_source", func(c context.Context, args map[string]any) (any, error) {
		ticketURL, _ := args["ticket_url"].(string)
		switch {
		case strings.Contains(ticketURL, "atlassian.net"):
			logInfo(c, "Detected Jira ticket URL")
			return "jira", nil
		case strings.Contains(ticketURL, "linear.app"):
			logInfo(c, "Detected Linear ticket URL")
			return "linear", nil
		default:
			return nil, fmt.Errorf("unsupported ticketing platform URL: %s", ticketURL)
		}
	},
		agnt5.WithToolDescription("Determine ticketing platform (Jira or Linear) based on URL pattern."),
		agnt5.WithToolSchema(map[string]any{
			"type": "object",
			"properties": map[string]any{
				"ticket_url": map[string]any{"type": "string", "description": "Ticket URL to analyze"},
			},
			"required": []string{"ticket_url"},
		}),
	)
}

func logInfo(c context.Context, msg string, kv ...any) {
	if ctx, ok := c.(*agnt5.Context); ok {
		ctx.Logger().Info(msg, kv...)
	}
}

func logWarn(c context.Context, msg string, kv ...any) {
	if ctx, ok := c.(*agnt5.Context); ok {
		ctx.Logger().Warn(msg, kv...)
	}
}

func logError(c context.Context, msg string, kv ...any) {
	if ctx, ok := c.(*agnt5.Context); ok {
		ctx.Logger().Error(msg, kv...)
	}
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
}
