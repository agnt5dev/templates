// Data models for structured review output.
package code_reviewer

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
