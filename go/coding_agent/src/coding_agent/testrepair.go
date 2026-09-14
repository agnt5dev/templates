// Guardrails for correcting generated tests.
//
// The suite is written before any code, so it can be wrong. When the error
// analysis flags a test whose expected value contradicts the task, the
// workflow lets the model correct that test — but only within the limits
// checked here, so the agent cannot make a failing run pass by deleting,
// weakening or rewriting tests it was not asked to touch.
package coding_agent

import (
	"fmt"
	"regexp"
	"sort"
	"strings"
)

// baseTestName reduces a pytest id such as test.py::test_x[P3Y-9.0] to test_x.
func baseTestName(name string) string {
	parts := strings.Split(name, "::")
	last := parts[len(parts)-1]
	return strings.TrimSpace(strings.SplitN(last, "[", 2)[0])
}

func indentOf(line string) int { return len(line) - len(strings.TrimLeft(line, " \t")) }

func bracketDelta(line string) int {
	return strings.Count(line, ")") + strings.Count(line, "]") + strings.Count(line, "}") -
		strings.Count(line, "(") - strings.Count(line, "[") - strings.Count(line, "{")
}

var testDefRe = regexp.MustCompile(`^([ \t]*)(?:async[ \t]+)?def[ \t]+(test\w*)[ \t]*\(`)

type lineSpan struct{ start, end int }

// testFunctionSpans maps each test function to its [start, end) line range,
// decorators included.
//
// Go cannot parse Python (the Python template uses ast), so blocks are found
// by indentation and bracket balance, as the TypeScript template does: the
// decorators above a `def test…` line — including multi-line ones such as
// @pytest.mark.parametrize(...), where expectations often live — then the
// signature, then every following line indented deeper or blank. That covers
// the plain top-level and class-level functions the generator writes.
func testFunctionSpans(code string) map[string]lineSpan {
	lines := strings.Split(code, "\n")
	spans := map[string]lineSpan{}
	for i := 0; i < len(lines); i++ {
		m := testDefRe.FindStringSubmatch(lines[i])
		if m == nil {
			continue
		}
		indent := len(m[1])

		// Walk up through decorators; a positive depth means we are inside one
		// that opened further up.
		start, depth := i, 0
		for j := i - 1; j >= 0; j-- {
			text := strings.TrimSpace(lines[j])
			delta := bracketDelta(text)
			if depth == 0 {
				if strings.HasPrefix(text, "@") && indentOf(lines[j]) == indent {
					start = j
					continue
				}
				if delta > 0 && text != "" {
					depth += delta
					start = j
					continue
				}
				break
			}
			depth += delta
			if depth < 0 {
				depth = 0
			}
			start = j
		}

		// The signature may span lines; then the body is everything deeper.
		end := i + 1
		for sig := -bracketDelta(lines[i]); sig > 0 && end < len(lines); end++ {
			sig -= bracketDelta(lines[end])
		}
		for end < len(lines) && (strings.TrimSpace(lines[end]) == "" || indentOf(lines[end]) > indent) {
			end++
		}
		for end > i+1 && strings.TrimSpace(lines[end-1]) == "" {
			end--
		}
		spans[m[2]] = lineSpan{start, end}
	}
	return spans
}

func testSources(code string) map[string]string {
	lines := strings.Split(code, "\n")
	out := map[string]string{}
	for name, span := range testFunctionSpans(code) {
		out[name] = strings.TrimSpace(strings.Join(lines[span.start:span.end], "\n"))
	}
	return out
}

// codeOutsideTests returns the file with every test function removed, blank
// lines ignored.
func codeOutsideTests(code string) string {
	lines := strings.Split(code, "\n")
	inside := map[int]bool{}
	for _, span := range testFunctionSpans(code) {
		for k := span.start; k < span.end; k++ {
			inside[k] = true
		}
	}
	var kept []string
	for k, l := range lines {
		if !inside[k] && strings.TrimSpace(l) != "" {
			kept = append(kept, strings.TrimRight(l, " \t"))
		}
	}
	return strings.Join(kept, "\n")
}

// validatePythonSource catches the shapes a model actually returns wrong:
// nothing, or a markdown fence that survived cleaning.
func validatePythonSource(code string) error {
	if strings.TrimSpace(code) == "" {
		return fmt.Errorf("code is empty")
	}
	if strings.HasPrefix(strings.TrimSpace(code), "```") {
		return fmt.Errorf("code still contains markdown fence markers")
	}
	return nil
}

// checkTestRepair accepts a repaired suite only if it corrects flagged tests
// and nothing else. It returns the tests that changed.
func checkTestRepair(original, candidate string, targets map[string]bool) (bool, string, []string) {
	if err := validatePythonSource(candidate); err != nil {
		return false, fmt.Sprintf("repaired tests are invalid: %v", err), nil
	}
	before, after := testSources(original), testSources(candidate)

	var removed, added []string
	for name := range before {
		if _, ok := after[name]; !ok {
			removed = append(removed, name)
		}
	}
	for name := range after {
		if _, ok := before[name]; !ok {
			added = append(added, name)
		}
	}
	if len(removed) > 0 || len(added) > 0 {
		sort.Strings(removed)
		sort.Strings(added)
		return false, fmt.Sprintf("test set changed (removed [%s], added [%s])",
			strings.Join(removed, ", "), strings.Join(added, ", ")), nil
	}

	var changed, unflagged []string
	for name, src := range before {
		if after[name] != src {
			changed = append(changed, name)
			if !targets[name] {
				unflagged = append(unflagged, name)
			}
		}
	}
	if len(unflagged) > 0 {
		sort.Strings(unflagged)
		return false, fmt.Sprintf("changed tests that were not flagged: [%s]", strings.Join(unflagged, ", ")), nil
	}
	if codeOutsideTests(original) != codeOutsideTests(candidate) {
		return false, "changed code outside the flagged tests", nil
	}
	if len(changed) == 0 {
		return false, "no flagged test was changed", nil
	}
	sort.Strings(changed)
	return true, "", changed
}
