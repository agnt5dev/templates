// Research tools: generic webpage fetch and Wikipedia search.
package hitl_deep_research

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/agnt5dev/sdk-go/agnt5"
	"golang.org/x/net/html"
)

// The webpage tool fetches whatever URL the model hands it, so the transport
// enforces a destination policy rather than trusting the argument: a prompt
// that says "read http://169.254.169.254/latest/meta-data/" would otherwise
// make the worker fetch cloud credentials and hand them back as research
// (AGNT5-1160).
//
// The policy lives in DialContext, not in a check before the request: a
// hostname is resolved exactly once, every address is validated, and the
// connection goes to one of those addresses. Validating first and letting the
// default transport resolve again left a window for DNS rebinding -- a public
// answer for the check, a private one for the dial. Redirects dial through the
// same function, so each hop is held to the same rule.
var researchHTTPClient = &http.Client{
	Timeout: 30 * time.Second,
	Transport: &http.Transport{
		// No proxy: a proxy would connect on the worker's behalf and the
		// address policy would never see the real destination.
		Proxy:               nil,
		DialContext:         dialPublicAddressOnly,
		TLSHandshakeTimeout: 10 * time.Second,
	},
	CheckRedirect: func(req *http.Request, via []*http.Request) error {
		if len(via) >= 5 {
			return fmt.Errorf("stopped after 5 redirects")
		}
		return checkResearchScheme(req.URL)
	},
}

// dialPublicAddressOnly resolves the host, refuses if any answer is a private
// address, and dials only the addresses it validated. Rejecting on any private
// answer, rather than skipping it, closes the mixed-answer variant of
// rebinding where a public address is offered alongside a private one.
func dialPublicAddressOnly(ctx context.Context, network, addr string) (net.Conn, error) {
	host, port, err := net.SplitHostPort(addr)
	if err != nil {
		return nil, err
	}
	addrs, err := net.DefaultResolver.LookupIPAddr(ctx, host)
	if err != nil {
		return nil, fmt.Errorf("could not resolve %s: %w", host, err)
	}
	if len(addrs) == 0 {
		return nil, fmt.Errorf("%s resolved to no addresses", host)
	}
	for _, a := range addrs {
		if isPrivateAddress(a.IP) {
			return nil, fmt.Errorf("refusing to connect to %s: it resolves to the private address %s", host, a.IP)
		}
	}
	dialer := &net.Dialer{Timeout: 10 * time.Second}
	var lastErr error
	for _, a := range addrs {
		conn, err := dialer.DialContext(ctx, network, net.JoinHostPort(a.IP.String(), port))
		if err == nil {
			return conn, nil
		}
		lastErr = err
	}
	return nil, lastErr
}

const (
	findingsMemoryKey   = "research_findings"
	maxRecordedFindings = 24000
)

// findingsLocks holds one mutex per run ID for recordFinding.
var findingsLocks sync.Map

// recordFinding keeps what a tool actually retrieved in run-scoped memory, so a
// research pass that dies on its turn limit still has something to write from.
// The SDK's error carries no partial result, and the fallback used to call the
// writer with nothing but the plan — producing a "partial research" report
// containing no research at all (AGNT5-1160).
//
// Best effort on purpose: a memory write must never fail a tool call that
// otherwise succeeded.
func recordFinding(c context.Context, source, text string) {
	ctx, ok := c.(*agnt5.Context)
	if !ok || strings.TrimSpace(text) == "" {
		return
	}
	// One lock per run: the model can issue several tool calls at once, and
	// two of them reading the same prior value would each overwrite the
	// other's result. Serialized here since the KV store has no atomic append.
	lock, _ := findingsLocks.LoadOrStore(ctx.RunID(), &sync.Mutex{})
	mu := lock.(*sync.Mutex)
	mu.Lock()
	defer mu.Unlock()

	kv := ctx.Memory().KV(agnt5.MemoryScopeRun)
	existing, _ := kv.Get(ctx, findingsMemoryKey)
	prior, _ := existing.(string)

	entry := fmt.Sprintf("### From %s\n%s", source, text)
	combined := entry
	if prior != "" {
		combined = prior + "\n\n" + entry
	}
	// Bounded: findings feed a prompt, and an unbounded transcript would push
	// the writer past its context window.
	if len(combined) > maxRecordedFindings {
		combined = combined[len(combined)-maxRecordedFindings:]
	}
	if err := kv.Set(ctx, findingsMemoryKey, combined); err != nil {
		ctx.Logger().Warn("Could not record research finding", "error", err)
	}
}

// RecordedFindings returns whatever the tools gathered during this run.
func RecordedFindings(ctx *agnt5.Context) string {
	value, err := ctx.Memory().KV(agnt5.MemoryScopeRun).Get(ctx, findingsMemoryKey)
	if err != nil {
		return ""
	}
	text, _ := value.(string)
	return text
}

// maxWebpageBytes caps what a single page can pull into memory. Without it a
// large or endless response is read whole before parsing.
const maxWebpageBytes = 2 << 20 // 2 MiB

// checkResearchScheme rejects anything but http(s) with a host. Where the
// request may connect is decided by dialPublicAddressOnly at dial time, so a
// DNS answer cannot change between being checked and being used.
func checkResearchScheme(u *url.URL) error {
	if u.Scheme != "http" && u.Scheme != "https" {
		return fmt.Errorf("unsupported URL scheme %q: only http and https are fetched", u.Scheme)
	}
	if u.Hostname() == "" {
		return fmt.Errorf("URL has no host")
	}
	return nil
}

// isPrivateAddress reports whether an address belongs to the machine or its
// network rather than the public internet. Link-local covers the cloud metadata
// endpoints (169.254.169.254 and fd00:ec2::254).
func isPrivateAddress(ip net.IP) bool {
	return ip.IsLoopback() ||
		ip.IsPrivate() ||
		ip.IsLinkLocalUnicast() ||
		ip.IsLinkLocalMulticast() ||
		ip.IsInterfaceLocalMulticast() ||
		ip.IsUnspecified()
}

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

		parsed, err := url.Parse(pageURL)
		if err != nil {
			return fmt.Sprintf("Invalid URL: %s", pageURL), nil
		}
		if err := checkResearchScheme(parsed); err != nil {
			logError(c, "Refused webpage fetch", "url", truncate(pageURL, 100), "error", err)
			return fmt.Sprintf("Refused to fetch %s: %s", pageURL, err), nil
		}

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

		body, err := io.ReadAll(io.LimitReader(resp.Body, maxWebpageBytes))
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
		result := fmt.Sprintf("Title: %s\nURL: %s\n\nContent:\n%s", title, pageURL, text)
		recordFinding(c, pageURL, result)
		return result, nil
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
		// Tool arguments arrive as decoded JSON, so a model-supplied integer
		// lands here as a float64. Clamp both ends: the Wikipedia API rejects
		// srlimit above 50, and a model passing 0 would otherwise silently ask
		// for no results at all.
		maxResults := 3
		if m, ok := args["max_results"].(float64); ok {
			maxResults = int(m)
		}
		if maxResults < 1 {
			maxResults = 1
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
			result := fmt.Sprintf("Wikipedia search results for '%s':\n\n%s", query, strings.Join(results, "\n---\n"))
			recordFinding(c, "Wikipedia search: "+query, result)
			return result, nil
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
