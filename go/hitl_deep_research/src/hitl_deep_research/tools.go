// Research tools: generic webpage fetch and Wikipedia search.
package hitl_deep_research

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	"agnt5.dev/sdk-go/agnt5"
	"golang.org/x/net/html"
)

var researchHTTPClient = &http.Client{Timeout: 30 * time.Second}

// skipTags are elements whose text content is never useful for research
// extraction (scripts, ads, chrome).
var skipTags = map[string]bool{
	"script": true, "style": true, "nav": true, "footer": true,
	"header": true, "aside": true, "noscript": true, "iframe": true,
}

func extractText(n *html.Node, title *string, buf *strings.Builder) {
	if n.Type == html.ElementNode {
		if n.Data == "title" && n.FirstChild != nil && *title == "" {
			*title = strings.TrimSpace(n.FirstChild.Data)
		}
		if skipTags[n.Data] {
			return
		}
	}
	if n.Type == html.TextNode {
		text := strings.TrimSpace(n.Data)
		if text != "" {
			buf.WriteString(text)
			buf.WriteString(" ")
		}
	}
	for c := n.FirstChild; c != nil; c = c.NextSibling {
		extractText(c, title, buf)
	}
}

func NewFetchWebpageTool() (agnt5.Tool, error) {
	return agnt5.NewTool("fetch_webpage_tool", func(c context.Context, args map[string]any) (any, error) {
		pageURL, _ := args["url"].(string)
		logInfo(c, "Webpage fetch tool called", "url", truncate(pageURL, 100))

		req, err := http.NewRequestWithContext(c, http.MethodGet, pageURL, nil)
		if err != nil {
			return fmt.Sprintf("Invalid URL: %s", pageURL), nil
		}
		req.Header.Set("User-Agent", "Mozilla/5.0 (AGNT5-DeepResearch/1.0)")

		resp, err := researchHTTPClient.Do(req)
		if err != nil {
			logError(c, "Error fetching webpage", "url", pageURL, "error", err)
			return fmt.Sprintf("Error fetching content from %s: %s", pageURL, err), nil
		}
		defer resp.Body.Close()

		contentType := strings.ToLower(resp.Header.Get("Content-Type"))
		if !strings.Contains(contentType, "text/html") {
			return fmt.Sprintf("Content type %s is not supported for URL: %s", contentType, pageURL), nil
		}

		body, err := io.ReadAll(resp.Body)
		if err != nil {
			return fmt.Sprintf("Error reading content from %s: %s", pageURL, err), nil
		}

		doc, err := html.Parse(strings.NewReader(string(body)))
		if err != nil {
			return fmt.Sprintf("Error parsing HTML from %s: %s", pageURL, err), nil
		}

		var title string
		var buf strings.Builder
		extractText(doc, &title, &buf)
		if title == "" {
			title = "Untitled"
		}

		text := strings.Join(strings.Fields(buf.String()), " ")
		const maxChars = 8000
		if len(text) > maxChars {
			truncated := text[:maxChars]
			if lastSentence := strings.LastIndex(truncated, "."); lastSentence > int(float64(maxChars)*0.8) {
				text = truncated[:lastSentence+1] + " ... [truncated]"
			} else {
				text = truncated + " ... [truncated]"
			}
		}

		logInfo(c, "Successfully fetched webpage", "chars", len(text))
		return fmt.Sprintf("Title: %s\nURL: %s\n\nContent:\n%s", title, pageURL, text), nil
	},
		agnt5.WithToolDescription("Fetch and extract text content from a webpage for research purposes."),
		agnt5.WithToolSchema(map[string]any{
			"type": "object",
			"properties": map[string]any{
				"url": map[string]any{"type": "string", "description": "The webpage URL to fetch."},
			},
			"required": []string{"url"},
		}),
	)
}

type wikipediaSearchResponse struct {
	Error *struct {
		Info string `json:"info"`
	} `json:"error"`
	Query struct {
		Search []struct {
			Title   string `json:"title"`
			Snippet string `json:"snippet"`
		} `json:"search"`
	} `json:"query"`
}

var htmlEntityReplacer = strings.NewReplacer(
	`<span class="searchmatch">`, "", "</span>", "",
	"&quot;", `"`, "&amp;", "&", "&lt;", "<", "&gt;", ">",
)

func NewWikipediaSearchTool() (agnt5.Tool, error) {
	return agnt5.NewTool("wikipedia_search_tool", func(c context.Context, args map[string]any) (any, error) {
		query, _ := args["query"].(string)
		maxResults := 3
		if m, ok := args["max_results"].(float64); ok {
			maxResults = int(m)
		}
		if maxResults > 50 {
			maxResults = 50
		}

		logInfo(c, "Wikipedia search tool called", "query", truncate(query, 100))

		params := url.Values{
			"action":   {"query"},
			"list":     {"search"},
			"srsearch": {query},
			"format":   {"json"},
			"srlimit":  {strconv.Itoa(maxResults)},
			"srwhat":   {"text"},
		}

		const maxRetries = 3
		for attempt := 0; attempt < maxRetries; attempt++ {
			req, err := http.NewRequestWithContext(c, http.MethodGet, "https://en.wikipedia.org/w/api.php?"+params.Encode(), nil)
			if err != nil {
				return nil, err
			}
			req.Header.Set("User-Agent", "AGNT5-DeepResearch/1.0")

			resp, err := researchHTTPClient.Do(req)
			if err != nil {
				logError(c, "Wikipedia search failed", "error", err)
				return fmt.Sprintf("Wikipedia search failed for '%s': %s", query, err), nil
			}

			if resp.StatusCode == http.StatusTooManyRequests {
				resp.Body.Close()
				wait := time.Duration(3*(1<<attempt)) * time.Second // 3s, 6s, 12s
				logWarn(c, "Wikipedia rate-limited, retrying", "wait_seconds", wait.Seconds(), "attempt", attempt+1, "max_retries", maxRetries)
				select {
				case <-time.After(wait):
				case <-c.Done():
					return nil, c.Err()
				}
				continue
			}

			var data wikipediaSearchResponse
			decodeErr := json.NewDecoder(resp.Body).Decode(&data)
			resp.Body.Close()
			if decodeErr != nil {
				return nil, decodeErr
			}

			if data.Error != nil {
				logError(c, "Wikipedia API error", "info", data.Error.Info)
				return fmt.Sprintf("Wikipedia search error: %s", data.Error.Info), nil
			}
			if len(data.Query.Search) == 0 {
				return fmt.Sprintf("No Wikipedia articles found for query: %s", query), nil
			}

			var results []string
			for _, r := range data.Query.Search {
				content := htmlEntityReplacer.Replace(r.Snippet)
				pageURL := "https://en.wikipedia.org/wiki/" + strings.ReplaceAll(r.Title, " ", "_")
				results = append(results, fmt.Sprintf("Title: %s\nURL: %s\nSnippet: %s\n", r.Title, pageURL, content))
			}

			logInfo(c, "Found Wikipedia articles", "count", len(data.Query.Search))
			return fmt.Sprintf("Wikipedia search results for '%s':\n\n%s", query, strings.Join(results, "\n---\n")), nil
		}

		return fmt.Sprintf("Wikipedia search failed after %d retries (rate limited) for query: %s", maxRetries, query), nil
	},
		agnt5.WithToolDescription("Search Wikipedia for articles related to the research query."),
		agnt5.WithToolSchema(map[string]any{
			"type": "object",
			"properties": map[string]any{
				"query":       map[string]any{"type": "string", "description": "Search term or phrase to look up on Wikipedia."},
				"max_results": map[string]any{"type": "integer", "description": "Maximum number of articles to return (default 3, max 50)."},
			},
			"required": []string{"query"},
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
