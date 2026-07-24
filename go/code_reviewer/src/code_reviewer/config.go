// Configuration loaded from environment variables.
//
// Create a .env file with these variables:
//
//	GITHUB_TOKEN=your_github_token_here (required)
//	OPENAI_API_KEY=your_openai_key_here (required)
//
//	# At least one issue tracking system is required:
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

	hasLinear := c.LinearKey != ""
	hasJira := c.JiraEmail != "" && c.JiraDomain != "" && c.JiraAPIToken != ""
	if !hasLinear && !hasJira {
		return fmt.Errorf("at least one issue tracking system must be configured: Linear (LINEAR_API_TOKEN) or Jira (JIRA_EMAIL, JIRA_DOMAIN, JIRA_API_TOKEN)")
	}
	return nil
}
