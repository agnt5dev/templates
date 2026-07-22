// Weather Agent worker.
//
// Usage:
//
//	agnt5 dev up   # start the AGNT5 platform, if not already running
//	go run .       # start this worker
package main

import (
	"context"
	"log"
	"os"

	"agnt5.dev/sdk-go/agnt5"
)

func must(err error) {
	if err != nil {
		log.Fatal(err)
	}
}

func main() {
	log.Println("Weather Agent - Worker")

	model := agnt5.NewOpenAIModel(agnt5.OpenAIConfig{
		APIKey: os.Getenv("OPENAI_API_KEY"),
		Model:  "gpt-4o-mini",
	})

	if err := newWeatherAgent(model); err != nil {
		log.Fatal(err)
	}

	worker := agnt5.NewWorker(serviceName,
		agnt5.WithServiceVersion(serviceVersion),
		agnt5.WithMetadata(map[string]string{
			"description": "Simple weather agent for fetching weather data",
		}),
	)

	must(agnt5.RegisterFunction(worker, "get_weather_data", getWeatherData))
	must(agnt5.RegisterAgent(worker, weatherAgent))
	must(agnt5.RegisterWorkflow(worker, "get_weather", getWeatherWorkflow))
	must(agnt5.RegisterWorkflow(worker, "get_weather_interactive", getWeatherInteractiveWorkflow))

	log.Println("Connecting to AGNT5 Coordinator...")
	if err := worker.Run(context.Background()); err != nil {
		log.Fatal(err)
	}
}
