package coding_agent

import (
	"strings"
	"testing"
)

const originalSuite = `import pytest

from main import parse_duration

TOLERANCE = 1e-9


def test_simple():
    assert parse_duration("PT1H") == 3600.0


def test_years():
    # P0.5Y is half a year
    assert parse_duration("P0.5Y") == 1.5 * 365 * 86400


@pytest.mark.parametrize(
    "text,expected",
    [
        ("P1W", 7 * 86400),
        ("-PT15M", -900),
    ],
)
def test_table(text, expected):
    assert parse_duration(text) == expected
`

func targetSet(names ...string) map[string]bool {
	t := map[string]bool{}
	for _, n := range names {
		t[n] = true
	}
	return t
}

func TestBaseTestName(t *testing.T) {
	for in, want := range map[string]string{
		"test.py::test_x[P3Y-9.0]":   "test_x",
		"test.py::TestClass::test_y": "test_y",
		"test_z":                     "test_z",
		"  test.py::test_w[a-b]  ":   "test_w",
	} {
		if got := baseTestName(in); got != want {
			t.Errorf("baseTestName(%q) = %q, want %q", in, got, want)
		}
	}
}

// Spans must cover decorators, including a multi-line parametrize where the
// expectations usually live.
func TestTestFunctionSpansCoverDecorators(t *testing.T) {
	spans := testFunctionSpans(originalSuite)
	if len(spans) != 3 {
		t.Fatalf("found %d test functions, want 3: %v", len(spans), spans)
	}
	src := testSources(originalSuite)["test_table"]
	if !strings.HasPrefix(src, "@pytest.mark.parametrize(") || !strings.Contains(src, `("P1W", 7 * 86400)`) {
		t.Errorf("test_table source missed its decorator table:\n%s", src)
	}
	if outside := codeOutsideTests(originalSuite); strings.Contains(outside, "parse_duration(\"PT1H\")") ||
		!strings.Contains(outside, "TOLERANCE = 1e-9") {
		t.Errorf("codeOutsideTests kept the wrong lines:\n%s", outside)
	}
}

func TestCheckTestRepair(t *testing.T) {
	fixedYears := strings.Replace(originalSuite,
		`    # P0.5Y is half a year
    assert parse_duration("P0.5Y") == 1.5 * 365 * 86400`,
		`    # P0.5Y is half a year
    assert parse_duration("P0.5Y") == 0.5 * 365 * 86400`, 1)
	fixedTable := strings.Replace(originalSuite, `("P1W", 7 * 86400),`, `("P1W", 7 * 86400.0),`, 1)
	editedUnflagged := strings.Replace(originalSuite, `assert parse_duration("PT1H") == 3600.0`, `assert parse_duration("PT1H") == 3600`, 1)
	deleted := strings.Replace(originalSuite, `def test_simple():
    assert parse_duration("PT1H") == 3600.0


`, "", 1)
	added := originalSuite + `

def test_extra():
    assert parse_duration("PT2H") == 7200.0
`
	weakenedConstant := strings.Replace(originalSuite, "TOLERANCE = 1e-9", "TOLERANCE = 1.0", 1)

	cases := []struct {
		name      string
		candidate string
		targets   map[string]bool
		accepted  bool
		reason    string
		repaired  []string
	}{
		{"corrects the flagged test", fixedYears, targetSet("test_years"), true, "", []string{"test_years"}},
		{"corrects a parametrize table", fixedTable, targetSet("test_table"), true, "", []string{"test_table"}},
		{"rejects editing an unflagged test", editedUnflagged, targetSet("test_years"), false, "not flagged", nil},
		{"rejects a deleted test", deleted, targetSet("test_simple"), false, "test set changed", nil},
		{"rejects an added test", added, targetSet("test_years"), false, "test set changed", nil},
		{"rejects weakening a shared constant", weakenedConstant, targetSet("test_years"), false, "outside the flagged tests", nil},
		{"rejects unparseable output", "```python\n" + fixedYears, targetSet("test_years"), false, "invalid", nil},
		{"rejects a no-op", originalSuite, targetSet("test_years"), false, "no flagged test was changed", nil},
	}
	for _, tc := range cases {
		accepted, why, repaired := checkTestRepair(originalSuite, tc.candidate, tc.targets)
		if accepted != tc.accepted {
			t.Errorf("%s: accepted = %v, want %v (reason %q)", tc.name, accepted, tc.accepted, why)
			continue
		}
		if !accepted && !strings.Contains(why, tc.reason) {
			t.Errorf("%s: reason = %q, want it to mention %q", tc.name, why, tc.reason)
		}
		if accepted && strings.Join(repaired, ",") != strings.Join(tc.repaired, ",") {
			t.Errorf("%s: repaired = %v, want %v", tc.name, repaired, tc.repaired)
		}
	}
}

// TestCheckTestRepairRejectsNeuteredTests is the AGNT5-1160 regression. The
// package comment promised the agent could not "make a failing run pass by
// deleting, weakening or rewriting tests", and every check looked at which
// tests changed, never whether the changed test still claimed anything.
func TestCheckTestRepairRejectsNeuteredTests(t *testing.T) {
	original := `def test_add():
    assert add(2, 3) == 6


def test_sub():
    assert sub(3, 2) == 1
`
	targets := map[string]bool{"test_add": true}

	for name, candidate := range map[string]string{
		"body replaced with pass": `def test_add():
    pass


def test_sub():
    assert sub(3, 2) == 1
`,
		"assertion made vacuous": `def test_add():
    assert True


def test_sub():
    assert sub(3, 2) == 1
`,
	} {
		accepted, why, _ := checkTestRepair(original, candidate, targets)
		if accepted {
			t.Errorf("%s: repair accepted, want rejection", name)
		}
		if !strings.Contains(why, "no longer asserts") {
			t.Errorf("%s: reason = %q, want it to name the missing assertion", name, why)
		}
	}
}

// The guard must not block a genuine correction.
func TestCheckTestRepairAcceptsACorrectedExpectation(t *testing.T) {
	original := "def test_add():\n    assert add(2, 3) == 6\n"
	candidate := "def test_add():\n    assert add(2, 3) == 5\n"

	accepted, why, changed := checkTestRepair(original, candidate, map[string]bool{"test_add": true})

	if !accepted {
		t.Fatalf("corrected expectation rejected: %s", why)
	}
	if len(changed) != 1 || changed[0] != "test_add" {
		t.Errorf("changed = %v, want [test_add]", changed)
	}
}

// Malformed Python used to be accepted as long as the test names survived; Go
// cannot parse Python, so the structural checks stand in for the Python
// template's ast.parse.
func TestValidatePythonSourceRejectsMalformedCandidates(t *testing.T) {
	cases := map[string]string{
		"truncated call":   "def test_add():\n    assert add(2, 3 == 5\n",
		"unterminated doc": "def test_add():\n    \"\"\"unfinished\n    assert add(2, 3) == 5\n",
		"markdown fence":   "```python\ndef test_add():\n    assert add(2, 3) == 5\n```",
		"no tests at all":  "def helper():\n    return 1\n",
		"empty":            "   ",
	}
	for name, code := range cases {
		if err := validatePythonSource(code); err == nil {
			t.Errorf("%s: accepted, want an error", name)
		}
	}

	valid := "import pytest\n\n\ndef test_add():\n    assert add(2, 3) == 5  # (2, 3)\n"
	if err := validatePythonSource(valid); err != nil {
		t.Errorf("valid source rejected: %v", err)
	}
}

// The review's exact evasions: an assertion that survives only in a comment or
// a string must not count, and a real assertion that merely mentions True must.
func TestStillAssertsReadsSyntaxNotText(t *testing.T) {
	cases := map[string]struct {
		source string
		want   bool
	}{
		"pass with assertion in comment":    {"def test_x():\n    pass  # assert old == 5\n", false},
		"vacuous plus assertion in comment": {"def test_x():\n    assert True  # assert old == 5\n", false},
		"assertion in docstring only":       {"def test_x():\n    \"\"\"assert something\"\"\"\n    return\n", false},
		"vacuous with message":              {"def test_x():\n    assert True, \"fine\"\n", false},
		"True compared to a call":           {"def test_x():\n    assert True == predicate()\n", true},
		"real comparison":                   {"def test_x():\n    assert add(2, 3) == 5\n", true},
		"pytest.raises":                     {"def test_x():\n    with pytest.raises(ValueError):\n        add(2, 'x')\n", true},
		"unittest style":                    {"def test_x(self):\n    self.assertEqual(add(2, 3), 5)\n", true},
		"explicit raise":                    {"def test_x():\n    raise AssertionError('no')\n", true},
	}
	for name, tc := range cases {
		if got := stillAsserts(tc.source); got != tc.want {
			t.Errorf("%s: stillAsserts = %v, want %v", name, got, tc.want)
		}
	}
}

// Validation must see syntax, not bytes: delimiters inside strings are data.
func TestValidatePythonSourceDistinguishesDataFromSyntax(t *testing.T) {
	valid := map[string]string{
		"triple quote inside a string":   "def test_x():\n    expected = '\"\"\"'\n    assert render() == expected\n",
		"markdown fence inside a string": "def test_x():\n    sample = \"```python\\nprint(1)\\n```\"\n    assert parse(sample)\n",
		"bracket inside a string":        "def test_x():\n    assert f(\"(\") == \")\"\n",
		"bracket inside a comment":       "def test_x():\n    assert f(1) == 2  # (unbalanced\n",
	}
	for name, code := range valid {
		if err := validatePythonSource(code); err != nil {
			t.Errorf("%s: rejected valid code: %v", name, err)
		}
	}

	invalid := map[string]string{
		"mismatched brackets that cancel": "def test_x():\n    assert f([)]\n",
		"unterminated string":             "def test_x():\n    assert f(\"unterminated) == 1\n",
		"fence outside any string":        "```python\ndef test_x():\n    assert f(1) == 1\n```",
	}
	for name, code := range invalid {
		if err := validatePythonSource(code); err == nil {
			t.Errorf("%s: accepted, want an error", name)
		}
	}
}
