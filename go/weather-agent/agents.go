// Weather agent definition.
package main

import "agnt5.dev/sdk-go/agnt5"

// weatherAgent is assigned once in newWeatherAgent() before the worker starts
// registering components.
var weatherAgent *agnt5.Agent

// newWeatherAgent builds the weather agent and its tool.
//
// Note: the Go SDK has no temperature option on NewAgent (Python's
// Agent(temperature=0.1) has no equivalent here yet) — omitted rather than
// faked.
func newWeatherAgent(model agnt5.LanguageModel) error {
	weatherTool, err := newGetWeatherDataTool()
	if err != nil {
		return err
	}

	weatherAgent, err = agnt5.NewAgent("weather-agent",
		agnt5.WithAgentModel(model),
		agnt5.WithAgentInstructions("Get weather data for a location, if a generic question is posed, just answer the question with your knowledge"),
		agnt5.WithAgentTools(weatherTool),
		agnt5.WithAgentMaxTurns(3),
	)
	return err
}
