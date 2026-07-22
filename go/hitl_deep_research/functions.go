// Functions that drive each stage of the research pipeline. Each wraps a
// single agent call with a stage-specific prompt.
package main

import (
	"fmt"
	"strings"
	"time"

	"agnt5.dev/sdk-go/agnt5"
)

func planResearch(ctx *agnt5.Context, topic string) (string, error) {
	currentDate := time.Now().UTC().Format("2006-01-02")
	prompt := fmt.Sprintf(`Today's date is %s.

Research topic: %s

Create a structured research plan for this topic:
1. Break it into 3-6 manageable subtopics
2. Define the research strategy for each subtopic
3. Make reasonable assumptions if the topic is vague or ambiguous
4. Start your response with "PLAN:" followed by the structured plan`, currentDate, topic)

	result, err := scopingAgent.Run(ctx, agnt5.AgentInput{Message: prompt})
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

	result, err := researchAgent.Run(ctx, agnt5.AgentInput{Message: prompt})
	if err != nil {
		return "", err
	}
	ctx.Logger().Info("Research completed", "chars", len(result.Response))
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

	result, err := writingAgent.Run(ctx, agnt5.AgentInput{Message: prompt})
	if err != nil {
		return "", err
	}
	ctx.Logger().Info("Report synthesized successfully")
	return result.Response, nil
}
