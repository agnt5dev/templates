// Travel booking workflow.
package main

import "agnt5.dev/sdk-go/agnt5"

type TravelBookingInput struct {
	Message string `json:"message"`
}

type TravelBookingOutput struct {
	Status string `json:"status"`
	Output string `json:"output"`
}

// travelBookingWorkflow is a chat-based travel booking workflow. Conversation
// history is kept in session-scoped memory so the agent never asks for
// information the user already gave earlier in the session.
func travelBookingWorkflow(ctx *agnt5.Context, in TravelBookingInput) (TravelBookingOutput, error) {
	ctx.Logger().Info("Travel booking workflow", "message", truncate(in.Message, 100))

	conversation := ctx.Memory().Conversation()
	history, err := conversation.Messages(ctx)
	if err != nil {
		return TravelBookingOutput{}, err
	}
	messages := make([]agnt5.Message, len(history))
	for i, m := range history {
		messages[i] = agnt5.Message{Role: agnt5.MessageRole(m.Role), Content: m.Content}
	}

	result, err := travelBookingAgent.Run(ctx, agnt5.AgentInput{Messages: messages, Message: in.Message})
	if err != nil {
		return TravelBookingOutput{}, err
	}

	if err := conversation.Append(ctx, agnt5.MemoryMessage{Role: "user", Content: in.Message}); err != nil {
		return TravelBookingOutput{}, err
	}
	if err := conversation.Append(ctx, agnt5.MemoryMessage{Role: "assistant", Content: result.Response}); err != nil {
		return TravelBookingOutput{}, err
	}

	ctx.Logger().Info("Travel booking agent completed")
	return TravelBookingOutput{Status: "completed", Output: result.Response}, nil
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
}
