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
