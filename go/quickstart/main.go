// AGNT5 Hacker News digest — worker entry point.
package main

import (
	"context"
	"log"
	"os"

	"github.com/agnt5dev/sdk-go/agnt5"

	"quickstart/src/quickstart"
)

// newSummarizerModel picks Anthropic when ANTHROPIC_API_KEY is set and OpenAI
// otherwise. Go takes the bare model name, without a "provider/" prefix.
func newSummarizerModel() agnt5.LanguageModel {
	if key := os.Getenv("ANTHROPIC_API_KEY"); key != "" {
		return agnt5.NewAnthropicModel(agnt5.AnthropicConfig{
			APIKey: key,
			Model:  "claude-haiku-4-5-20251001",
		})
	}
	return agnt5.NewOpenAIModel(agnt5.OpenAIConfig{
		APIKey: os.Getenv("OPENAI_API_KEY"),
		Model:  "gpt-4o-mini",
	})
}

func must(err error) {
	if err != nil {
		log.Fatal(err)
	}
}

func main() {
	var err error
	quickstart.Summarizer, err = agnt5.NewAgent("hn_summarizer",
		agnt5.WithAgentModel(newSummarizerModel()),
		agnt5.WithAgentInstructions(quickstart.SummarizerPrompt),
	)
	if err != nil {
		log.Fatal(err)
	}

	worker := agnt5.NewWorker("quickstart",
		agnt5.WithServiceVersion("0.2.0"),
	)

	// The Go SDK has no auto-register equivalent: every agent, function, and
	// workflow has to be listed here explicitly.
	must(agnt5.RegisterAgent(worker, quickstart.Summarizer))

	// The three functions that touch the network get a retry policy; the
	// digest assembly is pure string formatting, so it has nothing to retry.
	must(agnt5.RegisterFunction(worker, "fetch_top_ids", quickstart.FetchTopIDsFunction,
		agnt5.WithRetry(3, 500, 10000),
		agnt5.WithBackoff("exponential", 2.0),
	))
	must(agnt5.RegisterFunction(worker, "fetch_story", quickstart.FetchStoryFunction,
		agnt5.WithRetry(3, 500, 10000),
		agnt5.WithBackoff("exponential", 2.0),
	))
	must(agnt5.RegisterFunction(worker, "summarize", quickstart.SummarizeFunction,
		agnt5.WithRetry(3, 1000, 30000),
		agnt5.WithBackoff("exponential", 2.0),
	))
	must(agnt5.RegisterFunction(worker, "assemble_digest", quickstart.AssembleDigestFunction))
	must(agnt5.RegisterWorkflow(worker, "digest", quickstart.DigestWorkflow))

	log.Println("Worker created. Connecting to AGNT5 runtime...")
	if err := worker.Run(context.Background()); err != nil {
		log.Fatal(err)
	}
}
