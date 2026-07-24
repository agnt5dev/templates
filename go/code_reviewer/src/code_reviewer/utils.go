// Shared helpers: Atlassian Document Format parsing, structured-output
// generation (the Go SDK has no response_format/schema field on
// GenerateRequest, so this prompts for JSON and retries once on a parse
// failure), and a simple exponential-backoff HTTP retry.
package code_reviewer

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"agnt5.dev/sdk-go/agnt5"
)

// parseADF recursively converts an Atlassian Document Format (ADF) node
// (from Jira's API response) into readable text.
func parseADF(node any) string {
	switch n := node.(type) {
	case map[string]any:
		nodeType, _ := n["type"].(string)
		content, _ := n["content"].([]any)

		switch nodeType {
		case "paragraph":
			var b strings.Builder
			for _, c := range content {
				b.WriteString(parseADF(c))
			}
			b.WriteString("\n")
			return b.String()
		case "text":
			text, _ := n["text"].(string)
			marks, _ := n["marks"].([]any)
			for _, m := range marks {
				mark, _ := m.(map[string]any)
				switch mark["type"] {
				case "strong":
					text = "**" + text + "**"
				case "code":
					text = "`" + text + "`"
				}
			}
			return text
		case "bulletList":
			var b strings.Builder
			for _, item := range content {
				b.WriteString("- " + parseADF(item))
			}
			return b.String()
		case "orderedList":
			var lines []string
			for i, item := range content {
				lines = append(lines, fmt.Sprintf("%d. %s", i+1, strings.TrimSpace(parseADF(item))))
			}
			return strings.Join(lines, "\n") + "\n"
		case "listItem":
			var b strings.Builder
			for _, c := range content {
				b.WriteString(parseADF(c))
			}
			return b.String()
		default:
			if content != nil {
				var b strings.Builder
				for _, c := range content {
					b.WriteString(parseADF(c))
				}
				return b.String()
			}
		}
	case []any:
		var b strings.Builder
		for _, c := range n {
			b.WriteString(parseADF(c))
		}
		return b.String()
	}
	return ""
}

// retryWithBackoff retries fn up to maxAttempts times with exponential
// backoff (starting at 1s, doubling each attempt), matching the retry/backoff
// policy the Python template applies to its external API calls.
func retryWithBackoff(ctx context.Context, maxAttempts int, fn func() error) error {
	var err error
	wait := time.Second
	for attempt := 0; attempt < maxAttempts; attempt++ {
		if err = fn(); err == nil {
			return nil
		}
		if attempt == maxAttempts-1 {
			break
		}
		select {
		case <-time.After(wait):
		case <-ctx.Done():
			return ctx.Err()
		}
		wait *= 2
	}
	return err
}

const jsonOnlyInstruction = "\n\nRespond with ONLY a single valid JSON object matching the required shape — no prose, no markdown code fences, no explanation."

// GenerateStructured prompts the model for JSON matching T and unmarshals
// the response. The Go SDK's GenerateRequest has no response_format/schema
// field, so this is the fallback: instruct, parse, and retry once with an
// error-correction follow-up if the first response doesn't parse.
func GenerateStructured[T any](ctx *agnt5.Context, model agnt5.LanguageModel, systemPrompt, userPrompt string) (T, error) {
	var zero T
	messages := []agnt5.Message{
		{Role: agnt5.MessageRoleSystem, Content: systemPrompt + jsonOnlyInstruction},
		{Role: agnt5.MessageRoleUser, Content: userPrompt},
	}

	var lastErr error
	for attempt := 0; attempt < 2; attempt++ {
		temperature := 0.0
		resp, err := model.Generate(ctx, agnt5.GenerateRequest{
			Messages:    messages,
			Temperature: &temperature,
		})
		if err != nil {
			return zero, err
		}

		var result T
		if err := json.Unmarshal([]byte(extractJSON(resp.Content)), &result); err == nil {
			return result, nil
		} else {
			lastErr = err
		}

		messages = append(messages,
			agnt5.Message{Role: agnt5.MessageRoleAssistant, Content: resp.Content},
			agnt5.Message{Role: agnt5.MessageRoleUser, Content: "That was not valid JSON matching the required shape. Respond again with ONLY the JSON object, no other text."},
		)
	}
	return zero, fmt.Errorf("model did not return valid JSON after retries: %w", lastErr)
}

// extractJSON strips markdown code fences and surrounding prose, returning
// the substring between the first '{' and the last '}'.
func extractJSON(s string) string {
	s = strings.TrimSpace(s)
	s = strings.TrimPrefix(s, "```json")
	s = strings.TrimPrefix(s, "```")
	s = strings.TrimSuffix(s, "```")
	start := strings.Index(s, "{")
	end := strings.LastIndex(s, "}")
	if start == -1 || end == -1 || end < start {
		return s
	}
	return s[start : end+1]
}
