// Code Reviewer — AGNT5 worker.
package main

import (
	"context"
	"log"

	"agnt5.dev/sdk-go/agnt5"

	code_reviewer "code-reviewer/src/code_reviewer"
)

const serviceName = "code-reviewer"

func must(err error) {
	if err != nil {
		log.Fatal(err)
	}
}

func main() {
	log.Printf("Starting %s worker...", serviceName)

	cfg := code_reviewer.LoadConfig()
	if err := cfg.Validate(); err != nil {
		log.Fatal(err)
	}

	model := agnt5.NewOpenAIModel(agnt5.OpenAIConfig{
		APIKey: cfg.OpenAIAPIKey,
		Model:  "gpt-4.1-mini",
	})

	if err := code_reviewer.NewAgents(model, cfg); err != nil {
		log.Fatal(err)
	}

	worker := agnt5.NewWorker(serviceName,
		agnt5.WithServiceVersion("1.0.0"),
	)

	must(agnt5.RegisterAgent(worker, code_reviewer.ContextBuilderAgent))
	must(agnt5.RegisterAgent(worker, code_reviewer.ReviewerAgent))
	must(agnt5.RegisterWorkflow(worker, "code_reviewer_workflow", func(ctx *agnt5.Context, in code_reviewer.CodeReviewInput) (code_reviewer.CodeReviewOutput, error) {
		return code_reviewer.CodeReviewerWorkflow(ctx, in, model, cfg)
	}))

	log.Println("Starting worker and registering with coordinator...")
	if err := worker.Run(context.Background()); err != nil {
		log.Fatal(err)
	}
}
