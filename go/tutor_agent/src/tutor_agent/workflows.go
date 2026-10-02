// Tutor workflow for educational interactions.
//
// Demonstrates the agent handoff pattern: a triage agent delegates to
// specialized tutors (see agents.go) based on the subject of the question.
package tutor_agent

import (
	"context"
	"fmt"

	"github.com/agnt5dev/sdk-go/agnt5"
)

type TutorChatInput struct {
	Message string `json:"message"`
}

type TutorChatOutput struct {
	Output string `json:"output"`
}

func TutorChatWorkflow(ctx *agnt5.Context, in TutorChatInput) (TutorChatOutput, error) {
	ctx.Logger().Info("Tutor chat workflow", "message", in.Message)

	// Wrapped in a Step so the model call is checkpointed. The triage agent may
	// hand off to a specialist tutor, which costs a second model round-trip;
	// without this a worker restart would re-run and re-bill both.
	result, err := agnt5.Step(ctx, "tutor_triage", func(context.Context) (agnt5.AgentResult, error) {
		return TriageAgent.Run(ctx, agnt5.AgentInput{Message: in.Message})
	})
	if err != nil {
		// Return the error so the run fails with it (no OPENAI_API_KEY, a
		// provider outage) rather than returning a canned answer as a success.
		return TutorChatOutput{}, fmt.Errorf("tutor agent: %w", err)
	}

	return TutorChatOutput{Output: result.Response}, nil
}
