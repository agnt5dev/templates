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

// validatePythonSource rejects candidates that are not plausible Python.
//
// Go cannot parse Python, so this is structural where the Python template uses
// ast.parse -- the same template, stricter in one language than the other
// (AGNT5-1160). The checks run on the code with string and comment contents
// removed, so a fence or a bracket inside a string is data, not syntax: a
// text-processing task's tests legitimately contain both. What is caught is
// what a truncated or malformed model response actually looks like: nothing,
// a fence outside any string, an unterminated string, mismatched brackets. A
// syntax error that slips through still fails when the suite runs in the
// sandbox; checking here keeps a broken candidate from replacing working tests.
func validatePythonSource(code string) error {
	if strings.TrimSpace(code) == "" {
		return fmt.Errorf("code is empty")
	}
	stripped, err := stripPythonLiterals(code)
	if err != nil {
		return err
	}
	if strings.Contains(stripped, "```") {
		return fmt.Errorf("code still contains markdown fence markers")
	}
	if err := checkBrackets(stripped); err != nil {
		return err
	}
	if len(testFunctionSpans(code)) == 0 {
		return fmt.Errorf("code contains no test functions")
	}
	return nil
}

// stripPythonLiterals returns the code with every comment removed and every
// string literal's contents replaced by an empty literal, so later checks see
// only syntax. Newlines are kept so line-based logic still lines up. An
// unterminated string is an error: that is the truncated-response shape the
// old triple-quote count was trying to catch, without the false positive on a
// string that merely contains one.
func stripPythonLiterals(code string) (string, error) {
	var out strings.Builder
	runes := []rune(code)
	for i := 0; i < len(runes); {
		r := runes[i]
		switch {
		case r == '#':
			for i < len(runes) && runes[i] != '\n' {
				i++
			}
		case r == '\'' || r == '"':
			triple := i+2 < len(runes) && runes[i+1] == r && runes[i+2] == r
			quoteLen := 1
			if triple {
				quoteLen = 3
			}
			out.WriteString(strings.Repeat(string(r), quoteLen*2)) // an empty literal of the same kind
			i += quoteLen
			closed := false
			for i < len(runes) {
				if runes[i] == '\\' {
					i += 2
					continue
				}
				if runes[i] == '\n' {
					if !triple {
						break // a single-quoted string cannot span lines
					}
					out.WriteRune('\n')
				}
				if runes[i] == r && (!triple || (i+2 < len(runes) && runes[i+1] == r && runes[i+2] == r)) {
					i += quoteLen
					closed = true
					break
				}
				i++
			}
			if !closed {
				return "", fmt.Errorf("code has an unterminated string literal")
			}
		default:
			out.WriteRune(r)
			i++
		}
	}
	return out.String(), nil
}

// checkBrackets verifies delimiters open and close in matching pairs. A plain
// count let `f([)]` through because the totals cancelled; the stack does not.
func checkBrackets(stripped string) error {
	closers := map[rune]rune{')': '(', ']': '[', '}': '{'}
	var stack []rune
	for _, r := range stripped {
		switch r {
		case '(', '[', '{':
			stack = append(stack, r)
		case ')', ']', '}':
			if len(stack) == 0 || stack[len(stack)-1] != closers[r] {
				return fmt.Errorf("code has mismatched brackets near %q, so it is truncated or malformed", string(r))
			}
			stack = stack[:len(stack)-1]
		}
	}
	if len(stack) > 0 {
		return fmt.Errorf("code has %d unclosed bracket(s), so it is truncated or malformed", len(stack))
	}
	return nil
}

// vacuousAssertion matches an assert whose condition is a constant that always
// holds, with or without a message: `assert True`, `assert 1, "still fine"`.
// `assert True == predicate()` is not vacuous and does not match.
var vacuousAssertion = regexp.MustCompile(`^assert\s*\(?\s*(True|1|not\s+False)\s*\)?\s*(,.*)?$`)

// assertionCall matches the other ways a test states an expectation.
var assertionCall = regexp.MustCompile(`(^|[^\w.])(pytest\.raises|self\.assert[A-Za-z]+|self\.fail|raise)\b`)

// stillAsserts reports whether a test body claims anything at all. A test
// rewritten to `pass`, `return` or `assert True` turns a failing suite green
// without fixing the code -- the exact move the package comment above promises
// this file prevents, and did not (AGNT5-1160).
//
// It looks at the code with strings and comments stripped, so
// `pass  # assert old == 5` is seen for the empty test it is, and an assertion
// in a docstring counts for nothing.
func stillAsserts(testSource string) bool {
	stripped, err := stripPythonLiterals(testSource)
	if err != nil {
		return false
	}
	for _, line := range strings.Split(stripped, "\n") {
		stmt := strings.TrimSpace(line)
		if strings.HasPrefix(stmt, "assert") && (len(stmt) == len("assert") || !isIdentChar(rune(stmt[len("assert")]))) {
			if !vacuousAssertion.MatchString(stmt) {
				return true
			}
			continue
		}
		if assertionCall.MatchString(stmt) {
			return true
		}
	}
	return false
}

func isIdentChar(r rune) bool {
	return r == '_' || (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9')
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
	// A flagged test may be corrected, not neutered: rewriting it to `pass` or
	// `assert True` makes the suite green while the code stays broken. The
	// package comment above has always promised this; nothing checked it
	// (AGNT5-1160).
	sort.Strings(changed)
	for _, name := range changed {
		if !stillAsserts(after[name]) {
			return false, fmt.Sprintf("repaired test %s no longer asserts anything", name), nil
		}
	}
	return true, "", changed
}
