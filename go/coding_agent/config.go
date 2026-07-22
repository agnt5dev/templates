// Configuration loaded from environment variables.
//
// Create a .env file with these variables:
//
//	GROQ_API_KEY=your_groq_api_key_here
//	E2B_API_KEY=your_e2b_api_key_here
//	OPENAI_API_KEY=your_openai_key_here  # Optional
package main

import (
	"fmt"
	"os"
)

type appConfig struct {
	GroqAPIKey   string
	E2BAPIKey    string
	OpenAIAPIKey string // Optional, for future use
}

func loadConfig() appConfig {
	return appConfig{
		GroqAPIKey:   os.Getenv("GROQ_API_KEY"),
		E2BAPIKey:    os.Getenv("E2B_API_KEY"),
		OpenAIAPIKey: os.Getenv("OPENAI_API_KEY"),
	}
}

func (c appConfig) validate() error {
	var missing []string
	if c.GroqAPIKey == "" {
		missing = append(missing, "GROQ_API_KEY")
	}
	if c.E2BAPIKey == "" {
		missing = append(missing, "E2B_API_KEY")
	}
	if len(missing) > 0 {
		return fmt.Errorf("missing required environment variables: %v; please create a .env file with these variables", missing)
	}
	return nil
}
