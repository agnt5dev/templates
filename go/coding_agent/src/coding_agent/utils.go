// Shared helpers: markdown-fence stripping, a lightweight third-party
// import scanner, and structured-output generation (the Go SDK has no
// response_format/schema field on GenerateRequest, so this prompts for JSON
// and retries once on a parse failure).
package coding_agent

import (
	"encoding/json"
	"fmt"
	"regexp"
	"strings"

	"agnt5.dev/sdk-go/agnt5"
)

var codeFencePattern = regexp.MustCompile("(?s)^```(?:python)?\\s*\\n(.*?)\\n```$")

// cleanCode strips markdown code fences the LLM sometimes wraps around a
// generated code value.
func cleanCode(code string) string {
	code = strings.TrimSpace(code)
	if m := codeFencePattern.FindStringSubmatch(code); m != nil {
		return strings.TrimSpace(m[1])
	}
	lines := strings.Split(code, "\n")
	if len(lines) > 0 && strings.HasPrefix(strings.TrimSpace(lines[0]), "```") {
		lines = lines[1:]
	}
	if len(lines) > 0 && strings.TrimSpace(lines[len(lines)-1]) == "```" {
		lines = lines[:len(lines)-1]
	}
	return strings.TrimSpace(strings.Join(lines, "\n"))
}

var (
	importPattern     = regexp.MustCompile(`(?m)^\s*import\s+([a-zA-Z_][\w.]*)`)
	fromImportPattern = regexp.MustCompile(`(?m)^\s*from\s+([a-zA-Z_][\w.]*)\s+import`)
)

// stdlibModules is a partial list of Python standard library top-level
// module names, enough to filter common cases out of the generated
// requirements. The Go SDK has no equivalent to Python's
// sys.stdlib_module_names, so this is a hand-maintained approximation —
// good enough for a demo template, not exhaustive.
var stdlibModules = map[string]bool{
	"os": true, "sys": true, "re": true, "json": true, "typing": true,
	"time": true, "datetime": true, "math": true, "random": true,
	"collections": true, "itertools": true, "functools": true,
	"pathlib": true, "subprocess": true, "asyncio": true, "unittest": true,
	"logging": true, "abc": true, "io": true, "enum": true, "dataclasses": true,
	"contextlib": true, "copy": true, "string": true, "traceback": true,
	"pytest": true, "__future__": true, "typing_extensions": true,
}

// extractThirdPartyImports gets non-stdlib top-level module names imported
// by Python source code, so install_deps_node knows what to pip install.
func extractThirdPartyImports(code string) []string {
	seen := map[string]bool{}
	add := func(name string) {
		root := strings.SplitN(name, ".", 2)[0]
		if root != "" && !stdlibModules[root] && !strings.HasPrefix(root, "_") {
			seen[root] = true
		}
	}
	for _, m := range importPattern.FindAllStringSubmatch(code, -1) {
		add(m[1])
	}
	for _, m := range fromImportPattern.FindAllStringSubmatch(code, -1) {
		add(m[1])
	}

	names := make([]string, 0, len(seen))
	for n := range seen {
		names = append(names, n)
	}
	return names
}

const jsonOnlyInstruction = "\n\nRespond with ONLY a single valid JSON object matching the required shape — no prose, no markdown code fences, no explanation."

// GenerateStructured prompts the model for JSON matching T and unmarshals
// the response, retrying once with an error-correction follow-up if the
// first response doesn't parse.
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

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
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
