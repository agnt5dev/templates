// Tutor workflow for educational interactions.
//
// Demonstrates the agent handoff pattern: a triage agent delegates to
// specialized tutors (see agents.go) based on the subject of the question.
package main

import "agnt5.dev/sdk-go/agnt5"

type TutorChatInput struct {
	Message string `json:"message"`
}

type TutorChatOutput struct {
	Output string `json:"output"`
}

func tutorChatWorkflow(ctx *agnt5.Context, in TutorChatInput) (TutorChatOutput, error) {
	ctx.Logger().Info("Tutor chat workflow", "message", in.Message)

	result, err := triageAgent.Run(ctx, agnt5.AgentInput{Message: in.Message})
	if err != nil {
		ctx.Logger().Error("Error running tutor agent", "error", err)
		return TutorChatOutput{
			Output: "I apologize, but I'm having trouble processing your question right now. Could you please rephrase: " + in.Message,
		}, nil
	}

	return TutorChatOutput{Output: result.Response}, nil
}
