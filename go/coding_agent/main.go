// Coding Agent — AGNT5 worker. Autonomous TDD agent running in an E2B
// sandbox.
package main

import (
	"context"
	"log"

	"agnt5.dev/sdk-go/agnt5"

	coding_agent "coding-agent/src/coding_agent"
)

const serviceName = "coding-agent"

func must(err error) {
	if err != nil {
		log.Fatal(err)
	}
}

func main() {
	log.Printf("Starting %s worker...", serviceName)

	cfg := coding_agent.LoadConfig()
	if err := cfg.Validate(); err != nil {
		log.Fatal(err)
	}

	model := agnt5.NewGroqModel(agnt5.OpenAIConfig{
		APIKey: cfg.GroqAPIKey,
		Model:  "meta-llama/llama-4-scout-17b-16e-instruct",
	})
	e2b := coding_agent.NewE2BClient(cfg.E2BAPIKey)

	worker := agnt5.NewWorker(serviceName,
		agnt5.WithServiceVersion("1.0.0"),
	)

	must(agnt5.RegisterWorkflow(worker, "coding_agent_workflow", func(ctx *agnt5.Context, in coding_agent.CodingAgentInput) (coding_agent.WorkflowResult, error) {
		return coding_agent.CodingAgentWorkflow(ctx, in, model, e2b)
	}))

	log.Println("Starting worker and registering with coordinator...")
	if err := worker.Run(context.Background()); err != nil {
		log.Fatal(err)
	}
}
