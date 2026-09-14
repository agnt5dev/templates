// Configuration loaded from environment variables.
//
// Create a .env file with these variables:
//
//	GITHUB_TOKEN=your_github_token_here (required)
//	OPENAI_API_KEY=your_openai_key_here (required)
//
//	# Optional — set one only if you pass ticket_url to the workflow:
//	LINEAR_API_TOKEN=your_linear_api_key_here (optional)
//	# OR
//	JIRA_EMAIL=your_jira_email_here (optional, requires all 3 Jira vars)
//	JIRA_DOMAIN=your_jira_domain_here (optional, requires all 3 Jira vars)
//	JIRA_API_TOKEN=your_jira_api_token_here (optional, requires all 3 Jira vars)
package code_reviewer

import (
	"fmt"
	"os"
)

type AppConfig struct {
	GitHubToken  string
	LinearKey    string
	JiraEmail    string
	JiraDomain   string
	JiraAPIToken string
	OpenAIAPIKey string
}

func LoadConfig() AppConfig {
	return AppConfig{
		GitHubToken:  os.Getenv("GITHUB_TOKEN"),
		LinearKey:    os.Getenv("LINEAR_API_TOKEN"),
		JiraEmail:    os.Getenv("JIRA_EMAIL"),
		JiraDomain:   os.Getenv("JIRA_DOMAIN"),
		JiraAPIToken: os.Getenv("JIRA_API_TOKEN"),
		OpenAIAPIKey: os.Getenv("OPENAI_API_KEY"),
	}
}

// validate checks that required API keys are present. At least one issue
// tracking system (Jira or Linear) must be configured.
func (c AppConfig) Validate() error {
	var missing []string
	if c.GitHubToken == "" {
		missing = append(missing, "GITHUB_TOKEN")
	}
	if c.OpenAIAPIKey == "" {
		missing = append(missing, "OPENAI_API_KEY")
	}
	if len(missing) > 0 {
		return fmt.Errorf("missing required environment variables: %v; please create a .env file with these variables", missing)
	}

	// An issue tracker is optional: ticket_url is an optional workflow input,
	// and a PR-only review is a legitimate use. When a ticket URL is supplied
	// without the matching credential, the fetch tool reports that instead —
	// refusing to start meant the whole worker died over a review that never
	// needed a ticket (AGNT5-1161).
	return nil
}
