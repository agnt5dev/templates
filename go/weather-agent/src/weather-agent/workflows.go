// Weather agent workflows.
package weather_agent

import (
	"context"

	"github.com/agnt5dev/sdk-go/agnt5"
)

type GetWeatherInput struct {
	Location string `json:"location"`
}

// GetWeatherWorkflow fetches weather data for a location.
func GetWeatherWorkflow(ctx *agnt5.Context, in GetWeatherInput) (WeatherData, error) {
	// agnt5.Task rather than agnt5.Step: both checkpoint the result, but Task
	// takes the registered function directly and emits function.started /
	// function.completed around it, so the fetch renders as its own Function
	// node in Studio instead of an anonymous step.
	weather, err := agnt5.Task(ctx, "get_weather_data",
		GetWeatherDataInput{Location: in.Location}, GetWeatherData)
	if err != nil {
		return WeatherData{}, err
	}

	ctx.Logger().Info("Weather retrieved", "location", weather.Location, "temperature_c", weather.TemperatureC)
	return weather, nil
}

type GetWeatherInteractiveInput struct {
	Message string `json:"message"`
}

type GetWeatherInteractiveOutput struct {
	Response string `json:"response"`
}

// GetWeatherInteractiveWorkflow is a multi-turn chat workflow. Conversation
// history is kept in session-scoped memory (ctx.Memory().Conversation()) so
// follow-up questions in the same session have context from earlier turns.
func GetWeatherInteractiveWorkflow(ctx *agnt5.Context, in GetWeatherInteractiveInput) (GetWeatherInteractiveOutput, error) {
	conversation := ctx.Memory().Conversation()

	history, err := conversation.Messages(ctx)
	if err != nil {
		return GetWeatherInteractiveOutput{}, err
	}
	messages := make([]agnt5.Message, len(history))
	for i, m := range history {
		messages[i] = agnt5.Message{Role: agnt5.MessageRole(m.Role), Content: m.Content}
	}

	// Messages carries prior turns; Message is the new turn the agent appends.
	//
	// Wrapped in a Step so the model call is checkpointed: without it a worker
	// restart between here and the conversation.Append calls below would re-run
	// the whole agent turn, paying for the tokens twice.
	result, err := agnt5.Step(ctx, "weather_agent_turn", func(context.Context) (agnt5.AgentResult, error) {
		return WeatherAgent.Run(ctx, agnt5.AgentInput{Messages: messages, Message: in.Message})
	})
	if err != nil {
		return GetWeatherInteractiveOutput{}, err
	}

	// Recording the turn is idempotent by inspection, not by hoping the Step
	// runs once: Step execution is at least once, so a restart between the
	// user append and the assistant append, or before the Step's completion
	// is journaled, would otherwise write the user message a second time
	// (AGNT5-1160). The history is read back and only what is missing is
	// appended, so any number of replays converge on one user/assistant pair.
	if _, err := agnt5.Step(ctx, "record_weather_agent_turn", func(context.Context) (struct{}, error) {
		return struct{}{}, recordTurn(ctx, conversation, in.Message, result.Response)
	}); err != nil {
		return GetWeatherInteractiveOutput{}, err
	}

	ctx.Logger().Info("Weather agent response", "preview", truncate(result.Response, 100))
	return GetWeatherInteractiveOutput{Response: result.Response}, nil
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
}

// recordTurn appends the user message and the assistant reply unless the
// tail of the history already holds them, so a replayed append changes
// nothing.
func recordTurn(ctx *agnt5.Context, conversation *agnt5.ConversationMemory, userMessage, reply string) error {
	history, err := conversation.Messages(ctx)
	if err != nil {
		return err
	}
	n := len(history)
	userRecorded := n >= 1 && history[n-1].Role == "user" && history[n-1].Content == userMessage
	pairRecorded := n >= 2 && history[n-2].Role == "user" && history[n-2].Content == userMessage &&
		history[n-1].Role == "assistant" && history[n-1].Content == reply
	if pairRecorded {
		return nil
	}
	if !userRecorded {
		if err := conversation.Append(ctx, agnt5.MemoryMessage{Role: "user", Content: userMessage}); err != nil {
			return err
		}
	}
	return conversation.Append(ctx, agnt5.MemoryMessage{Role: "assistant", Content: reply})
}
