// AGNT5 Hacker News digest — worker entry point.
package main

import (
	"context"
	"log"
	"os"

	"agnt5.dev/sdk-go/agnt5"

	"quickstart/src/quickstart"
)

func newSummarizerModel() agnt5.LanguageModel {
	if key := os.Getenv("ANTHROPIC_API_KEY"); key != "" {
		return agnt5.NewAnthropicModel(agnt5.AnthropicConfig{
			APIKey: key,
			Model:  "claude-3-5-haiku-20241022",
		})
	}
	return agnt5.NewOpenAIModel(agnt5.OpenAIConfig{
		APIKey: os.Getenv("OPENAI_API_KEY"),
		Model:  "gpt-5-mini",
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
		agnt5.WithServiceVersion("0.1.0"),
	)

	must(agnt5.RegisterFunction(worker, "fetch_top_ids", quickstart.FetchTopIDsFunction))
	must(agnt5.RegisterFunction(worker, "fetch_story", quickstart.FetchStoryFunction))
	must(agnt5.RegisterFunction(worker, "summarize", quickstart.SummarizeFunction))
	must(agnt5.RegisterFunction(worker, "assemble_digest", quickstart.AssembleDigestFunction))
	must(agnt5.RegisterWorkflow(worker, "digest", quickstart.DigestWorkflow))

	log.Println("Worker created. Connecting to AGNT5 runtime...")
	if err := worker.Run(context.Background()); err != nil {
		log.Fatal(err)
	}
}
