// Deep Research Agent — AGNT5 worker.
package main

import (
	"context"
	"log"
	"os"

	"agnt5.dev/sdk-go/agnt5"

	hitl_deep_research "hitl-deep-research/src/hitl_deep_research"
)

const serviceName = "deep-research"

func must(err error) {
	if err != nil {
		log.Fatal(err)
	}
}

func main() {
	log.Printf("Starting %s worker...", serviceName)

	model := agnt5.NewOpenAIModel(agnt5.OpenAIConfig{
		APIKey: os.Getenv("OPENAI_API_KEY"),
		Model:  "gpt-4o-mini",
	})

	if err := hitl_deep_research.NewAgents(model); err != nil {
		log.Fatal(err)
	}
	log.Println("Worker created successfully with a 3-agent research pipeline:")
	log.Println("  - 3 specialized agents: Scoping, Research, Writing")
	log.Println("  - 1 main workflow: deep_research_workflow")

	worker := agnt5.NewWorker(serviceName,
		agnt5.WithServiceVersion("2.0.0"),
	)

	must(agnt5.RegisterAgent(worker, hitl_deep_research.ScopingAgent))
	must(agnt5.RegisterAgent(worker, hitl_deep_research.ResearchAgent))
	must(agnt5.RegisterAgent(worker, hitl_deep_research.WritingAgent))
	must(agnt5.RegisterWorkflow(worker, "deep_research_workflow", hitl_deep_research.DeepResearchWorkflow))

	log.Println("Starting worker and registering with coordinator...")
	if err := worker.Run(context.Background()); err != nil {
		log.Fatal(err)
	}
}
