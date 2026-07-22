// AGNT5 Tutor Agent worker — demonstrates agent handoffs.
package main

import (
	"context"
	"log"
	"os"

	"agnt5.dev/sdk-go/agnt5"

	tutor_agent "tutor-agent/src/tutor_agent"
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

	if err := tutor_agent.NewAgents(model); err != nil {
		log.Fatal(err)
	}
	log.Println("Agents created with handoff architecture")

	worker := agnt5.NewWorker(serviceName,
		agnt5.WithServiceVersion("1.0.0"),
	)

	must(agnt5.RegisterAgent(worker, tutor_agent.TriageAgent))
	must(agnt5.RegisterAgent(worker, tutor_agent.HistoryTutorAgent))
	must(agnt5.RegisterAgent(worker, tutor_agent.MathTutorAgent))
	must(agnt5.RegisterWorkflow(worker, "tutor_chat_workflow", tutor_agent.TutorChatWorkflow))

	log.Println("Starting worker and registering with coordinator...")
	if err := worker.Run(context.Background()); err != nil {
		log.Fatal(err)
	}
}
