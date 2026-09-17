// Functions that drive each stage of the research pipeline. Each wraps a
// single agent call with a stage-specific prompt.
//
// Every stage is exposed twice: an unexported helper holding the prompt and
// agent call, and an exported `func(*agnt5.Context, In) (Out, error)` wrapper
// with a typed input struct. The wrapper is the shape both agnt5.RegisterFunction
// (main.go) and agnt5.Task (workflows.go) require, so each stage shows up as a
// real Function component — independently invocable, retryable, and rendered as
// its own node in Studio traces, matching the Python and TypeScript siblings.
package hitl_deep_research

import (
	"fmt"
	"strings"
	"time"

	"github.com/agnt5dev/sdk-go/agnt5"
)

type PlanResearchInput struct {
	Topic string `json:"topic"`
}

type ConductResearchInput struct {
	Topic        string `json:"topic"`
	ResearchPlan string `json:"research_plan"`
}

type WriteReportInput struct {
	Topic            string `json:"topic"`
	ResearchPlan     string `json:"research_plan"`
	ResearchFindings string `json:"research_findings"`
}

// PlanResearch is the registered Function wrapper around planResearch.
func PlanResearch(ctx *agnt5.Context, in PlanResearchInput) (string, error) {
	return planResearch(ctx, in.Topic)
}

// ConductResearch is the registered Function wrapper around conductResearch.
func ConductResearch(ctx *agnt5.Context, in ConductResearchInput) (string, error) {
	return conductResearch(ctx, in.Topic, in.ResearchPlan)
}

// WriteReport is the registered Function wrapper around writeReport.
func WriteReport(ctx *agnt5.Context, in WriteReportInput) (string, error) {
	return writeReport(ctx, in.Topic, in.ResearchPlan, in.ResearchFindings)
}

func planResearch(ctx *agnt5.Context, topic string) (string, error) {
	currentDate := time.Now().UTC().Format("2006-01-02")
	prompt := fmt.Sprintf(`Today's date is %s.

Research topic: %s

Create a structured research plan for this topic:
1. Break it into 3-6 manageable subtopics
2. Define the research strategy for each subtopic
3. Make reasonable assumptions if the topic is vague or ambiguous
4. Start your response with "PLAN:" followed by the structured plan`, currentDate, topic)

	result, err := ScopingAgent.Run(ctx, agnt5.AgentInput{Message: prompt})
	if err != nil {
		return "", err
	}

	plan := strings.TrimSpace(result.Response)
	if strings.HasPrefix(plan, "PLAN:") {
		plan = strings.TrimSpace(strings.TrimPrefix(plan, "PLAN:"))
	}
	ctx.Logger().Info("Research plan created successfully")
	return plan, nil
}

func conductResearch(ctx *agnt5.Context, topic, researchPlan string) (string, error) {
	prompt := fmt.Sprintf(`Execute systematic research for the following topic:

Topic: %s

Research Plan:
%s

Instructions:
1. Research each subtopic thoroughly using Wikipedia as your primary source
2. Supplement with web searches for additional context when needed
3. Organize your findings by subtopic
4. Cite all sources clearly (include titles and URLs)
5. Focus on factual information and verifiable details

Use the wikipedia_search_tool and fetch_webpage_tool to gather comprehensive information.`, topic, researchPlan)

	result, err := ResearchAgent.Run(ctx, agnt5.AgentInput{Message: prompt})
	if err != nil {
		// A tool-happy model can burn through WithAgentMaxTurns before it ever
		// produces a tool-free answer, and the SDK returns an error with no
		// partial result in that case (agent.go: "agent max turns exceeded").
		// Failing here would throw away a plan the human already approved at
		// the HITL gate, so salvage the research instead of propagating.
		//
		// The SDK returns a bare errors.New, so there is no sentinel to match
		// on — string matching is the only option until it exports one.
		if !strings.Contains(err.Error(), "max turns exceeded") {
			return "", err
		}
		findings := RecordedFindings(ctx)
		ctx.Logger().Warn("Research agent hit its turn limit, synthesizing from findings so far",
			"gathered_chars", len(findings))
		return synthesizePartialResearch(ctx, topic, researchPlan, findings)
	}
	ctx.Logger().Info("Research completed", "chars", len(result.Response))
	return result.Response, nil
}

// synthesizePartialResearch runs one final tool-free pass so the pipeline can
// continue with whatever the research agent managed to gather before running
// out of turns. WritingAgent has no tools, so it cannot hit the turn limit in
// turn and is guaranteed to terminate.
func synthesizePartialResearch(ctx *agnt5.Context, topic, researchPlan, findings string) (string, error) {
	// The tools record what they retrieved (tools.go: recordFinding), so the
	// writer works from the material the run actually gathered. Without it this
	// asked a tool-free agent to "summarize" a topic it had been told nothing
	// about, and labelled the result partial research (AGNT5-1160).
	gathered := strings.TrimSpace(findings)
	if gathered == "" {
		// Nothing to write from, so nothing is written by a model: asking one
		// to "summarize" with no material invites it to supply the research
		// from memory, which is the failure this path exists to prevent. The
		// report says what happened and which subtopics are uncovered -- all
		// of them.
		ctx.Logger().Warn("No findings were gathered before the turn limit; returning a fixed no-evidence report")
		return fmt.Sprintf(`PARTIAL RESEARCH — coverage is incomplete.

No sources were retrieved before the research agent ran out of turns, so there
are no findings to report for "%s".

Uncovered subtopics (all of them):
%s`, topic, researchPlan), nil
	}

	prompt := fmt.Sprintf(`Research on the topic below was cut short before it could be completed.

Topic: %s

Research Plan:
%s

Material gathered before research stopped:
%s

Instructions:
1. Write up only what the gathered material supports, organized by subtopic
2. Do NOT invent sources, URLs, citations or facts — if the material does not cover a subtopic, say so
3. Explicitly list which subtopics remain uncovered

Begin your response with "PARTIAL RESEARCH — coverage is incomplete."`, topic, researchPlan, gathered)

	result, err := WritingAgent.Run(ctx, agnt5.AgentInput{Message: prompt})
	if err != nil {
		return "", err
	}
	ctx.Logger().Info("Partial research synthesized", "chars", len(result.Response))
	return result.Response, nil
}

func writeReport(ctx *agnt5.Context, topic, researchPlan, researchFindings string) (string, error) {
	prompt := fmt.Sprintf(`Create a comprehensive academic report based on the research findings.

Topic: %s

Research Plan:
%s

Research Findings:
%s

Instructions:
1. Synthesize the findings into a well-structured academic report
2. Follow the report structure: Executive Summary, Introduction, Main Sections, Conclusion, References
3. Use proper citations in [Source Name](URL) format
4. Create a coherent narrative that connects different aspects of the research
5. Ensure the report answers the original research question comprehensively
6. End your report with the References section`, topic, researchPlan, researchFindings)

	result, err := WritingAgent.Run(ctx, agnt5.AgentInput{Message: prompt})
	if err != nil {
		return "", err
	}
	ctx.Logger().Info("Report synthesized successfully")
	return result.Response, nil
}
