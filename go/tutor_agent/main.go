// AGNT5 Tutor Agent worker — demonstrates agent handoffs.
package main

import (
	"context"
	"log"
	"os"

	"agnt5.dev/sdk-go/agnt5"
)

const serviceName = "agnt5-tutor-agent"

func must(err error) {
	if err != nil {
		log.Fatal(err)
	}
}

func main() {
	log.Printf("Starting %s worker...", serviceName)

	model := agnt5.NewOpenAIModel(agnt5.OpenAIConfig{
		APIKey: os.Getenv("OPENAI_API_KEY"),
		Model:  "gpt-5-mini",
	})

	if err := newAgents(model); err != nil {
		log.Fatal(err)
	}
	log.Println("Agents created with handoff architecture")

	worker := agnt5.NewWorker(serviceName,
		agnt5.WithServiceVersion("1.0.0"),
	)

	must(agnt5.RegisterAgent(worker, triageAgent))
	must(agnt5.RegisterAgent(worker, historyTutorAgent))
	must(agnt5.RegisterAgent(worker, mathTutorAgent))
	must(agnt5.RegisterWorkflow(worker, "tutor_chat_workflow", tutorChatWorkflow))

	log.Println("Starting worker and registering with coordinator...")
	if err := worker.Run(context.Background()); err != nil {
		log.Fatal(err)
	}
}
