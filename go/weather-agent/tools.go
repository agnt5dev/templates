// Tool wrapper so the weather agent can call fetchWeatherData.
package main

import (
	"context"

	"agnt5.dev/sdk-go/agnt5"
)

func newGetWeatherDataTool() (agnt5.Tool, error) {
	return agnt5.NewTool("get_weather_data_tool", func(c context.Context, args map[string]any) (any, error) {
		location, _ := args["location"].(string)

		if agntCtx, ok := c.(*agnt5.Context); ok {
			agntCtx.Logger().Info("Fetching weather data", "location", location)
		}

		weather, err := fetchWeatherData(c, location)
		if err != nil {
			return nil, err
		}

		if agntCtx, ok := c.(*agnt5.Context); ok {
			agntCtx.Logger().Info("Received weather", "temperature_c", weather.TemperatureC, "location", location)
		}
		return weather, nil
	},
		agnt5.WithToolDescription("Fetch weather data for a location."),
		agnt5.WithToolSchema(map[string]any{
			"type": "object",
			"properties": map[string]any{
				"location": map[string]any{"type": "string", "description": "City name"},
			},
			"required": []string{"location"},
		}),
	)
}
