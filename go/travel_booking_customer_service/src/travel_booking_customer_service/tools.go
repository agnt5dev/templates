// Travel booking tools for flight and hotel search.
//
// Provides tools for searching flights, hotels, and creating itineraries
// using SerpAPI.
package travel_booking_customer_service

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"time"

	"agnt5.dev/sdk-go/agnt5"
)

var serpAPIClient = &http.Client{Timeout: 15 * time.Second}

func logInfo(c context.Context, msg string, kv ...any) {
	if ctx, ok := c.(*agnt5.Context); ok {
		ctx.Logger().Info(msg, kv...)
	}
}

func logError(c context.Context, msg string, kv ...any) {
	if ctx, ok := c.(*agnt5.Context); ok {
		ctx.Logger().Error(msg, kv...)
	}
}

func serpAPIGet(ctx context.Context, params url.Values) (map[string]any, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, "https://serpapi.com/search?"+params.Encode(), nil)
	if err != nil {
		return nil, err
	}
	resp, err := serpAPIClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var data map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		return nil, err
	}
	return data, nil
}

func NewSearchFlightsTool() (agnt5.Tool, error) {
	return agnt5.NewTool("search_flights", func(c context.Context, args map[string]any) (any, error) {
		departureID, _ := args["departure_id"].(string)
		arrivalID, _ := args["arrival_id"].(string)
		outboundDate, _ := args["outbound_date"].(string)
		returnDate, _ := args["return_date"].(string)
		adults := 1
		if a, ok := args["adults"].(float64); ok {
			adults = int(a)
		}

		logInfo(c, "Searching flights", "from", departureID, "to", arrivalID, "date", outboundDate)

		serpAPIKey := os.Getenv("SERPAPI_KEY")
		if serpAPIKey == "" {
			logError(c, "SERPAPI_KEY not set")
			return map[string]any{"error": "SERPAPI_KEY not configured", "status": "failed"}, nil
		}

		params := url.Values{
			"engine":        {"google_flights"},
			"departure_id":  {departureID},
			"arrival_id":    {arrivalID},
			"outbound_date": {outboundDate},
			"currency":      {"USD"},
			"hl":            {"en"},
			"adults":        {fmt.Sprint(adults)},
			"api_key":       {serpAPIKey},
		}
		if returnDate != "" {
			params.Set("return_date", returnDate)
			params.Set("type", "1") // Round trip
		} else {
			params.Set("type", "2") // One way
		}

		data, err := serpAPIGet(c, params)
		if err != nil {
			logError(c, "Flight search failed", "error", err)
			return map[string]any{"error": err.Error(), "status": "failed"}, nil
		}

		flights := []map[string]any{}
		if best, ok := data["best_flights"].([]any); ok {
			for i, f := range best {
				if i >= 3 { // top 3 flights
					break
				}
				flight, ok := f.(map[string]any)
				if !ok {
					continue
				}
				legs, _ := flight["flights"].([]any)
				if len(legs) == 0 {
					continue
				}
				leg, _ := legs[0].(map[string]any)
				dep, _ := leg["departure_airport"].(map[string]any)
				arr, _ := leg["arrival_airport"].(map[string]any)
				flights = append(flights, map[string]any{
					"price":          flight["price"],
					"airline":        leg["airline"],
					"departure_time": dep["time"],
					"arrival_time":   arr["time"],
					"duration":       leg["duration"],
					"flight_number":  leg["flight_number"],
				})
			}
		}

		logInfo(c, "Found flight options", "count", len(flights))
		return map[string]any{"flights": flights, "status": "success"}, nil
	},
		agnt5.WithToolDescription("Search for flights using SerpAPI Google Flights."),
		agnt5.WithToolSchema(map[string]any{
			"type": "object",
			"properties": map[string]any{
				"departure_id":  map[string]any{"type": "string", "description": "Departure airport code (e.g., JFK, LAX)"},
				"arrival_id":    map[string]any{"type": "string", "description": "Arrival airport code (e.g., LHR, CDG)"},
				"outbound_date": map[string]any{"type": "string", "description": "Departure date in YYYY-MM-DD format"},
				"return_date":   map[string]any{"type": "string", "description": "Return date in YYYY-MM-DD format (optional for one-way)"},
				"adults":        map[string]any{"type": "integer", "description": "Number of adult passengers"},
			},
			"required": []string{"departure_id", "arrival_id", "outbound_date"},
		}),
	)
}

func NewSearchHotelsTool() (agnt5.Tool, error) {
	return agnt5.NewTool("search_hotels", func(c context.Context, args map[string]any) (any, error) {
		location, _ := args["location"].(string)
		checkIn, _ := args["check_in_date"].(string)
		checkOut, _ := args["check_out_date"].(string)
		adults := 1
		if a, ok := args["adults"].(float64); ok {
			adults = int(a)
		}

		logInfo(c, "Searching hotels", "location", location, "check_in", checkIn, "check_out", checkOut)

		serpAPIKey := os.Getenv("SERPAPI_KEY")
		if serpAPIKey == "" {
			logError(c, "SERPAPI_KEY not set")
			return map[string]any{"error": "SERPAPI_KEY not configured", "status": "failed"}, nil
		}

		params := url.Values{
			"engine":         {"google_hotels"},
			"q":              {location},
			"check_in_date":  {checkIn},
			"check_out_date": {checkOut},
			"adults":         {fmt.Sprint(adults)},
			"currency":       {"USD"},
			"gl":             {"us"},
			"hl":             {"en"},
			"api_key":        {serpAPIKey},
		}

		data, err := serpAPIGet(c, params)
		if err != nil {
			logError(c, "Hotel search failed", "error", err)
			return map[string]any{"error": err.Error(), "status": "failed"}, nil
		}

		hotels := []map[string]any{}
		if props, ok := data["properties"].([]any); ok {
			for i, p := range props {
				if i >= 3 { // top 3 hotels
					break
				}
				hotel, ok := p.(map[string]any)
				if !ok {
					continue
				}
				rate, _ := hotel["rate_per_night"].(map[string]any)
				amenities, _ := hotel["amenities"].([]any)
				if len(amenities) > 5 {
					amenities = amenities[:5]
				}
				hotels = append(hotels, map[string]any{
					"name":        hotel["name"],
					"price":       rate["lowest"],
					"rating":      hotel["overall_rating"],
					"reviews":     hotel["reviews"],
					"description": hotel["description"],
					"amenities":   amenities,
				})
			}
		}

		logInfo(c, "Found hotel options", "count", len(hotels))
		return map[string]any{"hotels": hotels, "status": "success"}, nil
	},
		agnt5.WithToolDescription("Search for hotels using SerpAPI Google Hotels."),
		agnt5.WithToolSchema(map[string]any{
			"type": "object",
			"properties": map[string]any{
				"location":       map[string]any{"type": "string", "description": "City or location name (e.g., 'Paris, France', 'New York')"},
				"check_in_date":  map[string]any{"type": "string", "description": "Check-in date in YYYY-MM-DD format"},
				"check_out_date": map[string]any{"type": "string", "description": "Check-out date in YYYY-MM-DD format"},
				"adults":         map[string]any{"type": "integer", "description": "Number of guests"},
			},
			"required": []string{"location", "check_in_date", "check_out_date"},
		}),
	)
}

func NewCreateItineraryTool() (agnt5.Tool, error) {
	return agnt5.NewTool("create_itinerary", func(c context.Context, args map[string]any) (any, error) {
		destination, _ := args["destination"].(string)
		travelDates, _ := args["travel_dates"].(string)
		preferences, _ := args["preferences"].(string)

		logInfo(c, "Creating itinerary", "destination", destination, "dates", travelDates)

		return map[string]any{
			"destination": destination,
			"dates":       travelDates,
			"preferences": preferences,
			"status":      "created",
			"message":     "Itinerary framework created. Please search for flights and hotels to complete it.",
		}, nil
	},
		agnt5.WithToolDescription("Create a travel itinerary framework."),
		agnt5.WithToolSchema(map[string]any{
			"type": "object",
			"properties": map[string]any{
				"destination":  map[string]any{"type": "string", "description": "Travel destination"},
				"travel_dates": map[string]any{"type": "string", "description": "Travel date range"},
				"preferences":  map[string]any{"type": "string", "description": "Any special preferences or requirements"},
			},
			"required": []string{"destination", "travel_dates"},
		}),
	)
}
