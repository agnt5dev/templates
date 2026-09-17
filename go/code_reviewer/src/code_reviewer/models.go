// Data models for structured review output.
package code_reviewer

import (
	"fmt"
	"strings"
)

// Severity levels for a Finding.
const (
	SeverityCritical = "critical"
	SeverityMajor    = "major"
	SeverityMinor    = "minor"
	SeverityNitpick  = "nitpick"
)

// Finding is one review comment.
type Finding struct {
	Severity      string `json:"severity"`       // critical, major, minor, or nitpick
	Category      string `json:"category"`       // correctness, performance, quality, standards, or security
	Description   string `json:"description"`    // clear description of the issue
	LineReference string `json:"line_reference"` // e.g. "auth.go:45-52", empty if not applicable
	Suggestion    string `json:"suggestion"`     // concrete fix suggestion
}

// FileReview is the structured result of reviewing one file's diff.
type FileReview struct {
	Filename string    `json:"filename"`
	Language string    `json:"language"`
	Findings []Finding `json:"findings"`
	Summary  string    `json:"summary"`
}

// SecurityReview is the structured result of the dedicated security pass.
type SecurityReview struct {
	Findings    []Finding `json:"findings"`
	OverallRisk string    `json:"overall_risk"` // low, medium, high, or critical
	Summary     string    `json:"summary"`
}

// TechStack is detected languages/frameworks/config from the PR's file list.
type TechStack struct {
	Languages        []string `json:"languages"`
	Frameworks       []string `json:"frameworks"`
	TestFilesPresent bool     `json:"test_files_present"`
	ConfigFiles      []string `json:"config_files"`
	Notes            string   `json:"notes"`
}

// PRFile is one changed file from a GitHub PR.
type PRFile struct {
	Filename  string `json:"filename"`
	Status    string `json:"status"`
	Additions int    `json:"additions"`
	Deletions int    `json:"deletions"`
	Patch     string `json:"patch"`
	HasPatch  bool   `json:"has_patch"`
}

// PRData is fetched PR metadata plus all changed files.
type PRData struct {
	Repo         string   `json:"repo"`
	PRNumber     int      `json:"pr_number"`
	Title        string   `json:"title"`
	Author       string   `json:"author"`
	State        string   `json:"state"`
	Description  string   `json:"description"`
	ChangedFiles int      `json:"changed_files"`
	Additions    int      `json:"additions"`
	Deletions    int      `json:"deletions"`
	Files        []PRFile `json:"files"`
}

// TicketData is normalized ticket info from Jira or Linear.
type TicketData struct {
	Available   bool   `json:"available"`
	Source      string `json:"source,omitempty"` // "jira" or "linear"
	Key         string `json:"key,omitempty"`
	Summary     string `json:"summary,omitempty"`
	Status      string `json:"status,omitempty"`
	Priority    string `json:"priority,omitempty"`
	Description string `json:"description,omitempty"`
	URL         string `json:"url,omitempty"`
	Reason      string `json:"reason,omitempty"` // set when Available is false
}

// structuredResult is implemented by the shapes GenerateStructured returns.
// json.Unmarshal succeeds on "{}", so without this a model that answered with
// an empty object produced a zero-value review that read as "no findings"
// (AGNT5-1160).
type structuredResult interface {
	Validate() error
}

// Validate reports whether the model answered at all. Only the empty shape
// is rejected: a response carrying findings is an answer even when the
// summary is missing, and discarding real findings over absent metadata
// would hide exactly the issues the review exists to surface. A clean file
// legitimately has no findings, so for that case the summary is the evidence.
func (r FileReview) Validate() error {
	if len(r.Findings) == 0 && strings.TrimSpace(r.Summary) == "" {
		return fmt.Errorf("file review has neither findings nor a summary")
	}
	return nil
}

// Validate is the same test for a security pass. A missing overall_risk with
// findings present is filled in from their severities by RiskOrFromFindings;
// it is not a reason to throw the findings away.
func (r SecurityReview) Validate() error {
	if len(r.Findings) == 0 && strings.TrimSpace(r.Summary) == "" && strings.TrimSpace(r.OverallRisk) == "" {
		return fmt.Errorf("security review has neither findings, a summary nor an overall_risk")
	}
	return nil
}

// RiskOrFromFindings returns the model's overall_risk, or derives one from the
// worst finding when the model left it out, so a batch that reported real
// findings still counts toward the merged rating.
func (r SecurityReview) RiskOrFromFindings() string {
	if risk := strings.TrimSpace(r.OverallRisk); risk != "" {
		return risk
	}
	worst := "low"
	for _, f := range r.Findings {
		var level string
		switch strings.ToLower(f.Severity) {
		case SeverityCritical:
			level = "critical"
		case SeverityMajor:
			level = "high"
		case SeverityMinor:
			level = "medium"
		default:
			continue
		}
		if riskRank(level) > riskRank(worst) {
			worst = level
		}
	}
	return worst
}
