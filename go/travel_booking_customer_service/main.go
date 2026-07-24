// Customer Service (Travel Booking) — AGNT5 worker.
package main

import (
	"context"
	"log"
	"os"

	"agnt5.dev/sdk-go/agnt5"

	travel_booking_customer_service "travel-booking-customer-service/src/travel_booking_customer_service"
)

const serviceName = "customer-service"

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

	if err := travel_booking_customer_service.NewTravelBookingAgent(model); err != nil {
		log.Fatal(err)
	}

	worker := agnt5.NewWorker(serviceName,
		agnt5.WithServiceVersion("1.0.0"),
	)

	must(agnt5.RegisterAgent(worker, travel_booking_customer_service.TravelBookingAgent))
	must(agnt5.RegisterWorkflow(worker, "travel_booking_workflow", travel_booking_customer_service.TravelBookingWorkflow))

	if err := worker.Run(context.Background()); err != nil {
		log.Fatal(err)
	}
}
