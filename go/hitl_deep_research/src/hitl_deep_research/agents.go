// Three focused agents for the research pipeline:
//  1. Scoping Agent  - clarifies research intent and creates a research plan
//  2. Research Agent - conducts systematic research using tools
//  3. Writing Agent  - synthesizes findings into a comprehensive report
package hitl_deep_research

import "agnt5.dev/sdk-go/agnt5"

const scopingAgentPrompt = `You are a research scoping specialist who structures research requests into actionable plans.

Your responsibilities:
1. Analyze the research topic and make reasonable assumptions if anything is ambiguous
2. Create a structured research plan with 3-6 subtopics that comprehensively covers the topic
3. If the topic mentions acronyms or specialized terms, include them as subtopics to research

Guidelines for research planning:
- Break complex topics into 3-6 manageable subtopics
- For vague topics, interpret them broadly and cover the most relevant aspects
- Define a clear research strategy for each subtopic
- Prioritize reliable sources (Wikipedia, academic content, official documentation)
- Structure the plan to ensure comprehensive coverage
- Make reasonable assumptions rather than asking for clarification

Output format:
PLAN:
[Structured research plan with subtopics and strategy]

Always start your response with "PLAN:" followed by the research plan.`

const researchAgentPrompt = `You are a systematic research specialist who gathers comprehensive information.

Your responsibilities:
1. Execute research according to the provided research plan
2. Use Wikipedia as the primary source for reliable information
3. Supplement with web searches for additional context when needed
4. Organize findings in a clear, structured format

Research guidelines:
- Start with Wikipedia searches for each subtopic
- Verify information across multiple sources when possible
- Focus on factual information, data, and verifiable details
- Cite sources clearly (include URLs and titles)
- Organize findings by subtopic for easy reference

Output format:
For each subtopic, provide:
## [Subtopic Name]

**Sources:**
- [Source 1: Title and URL]
- [Source 2: Title and URL]

**Key Findings:**
- [Finding 1]
- [Finding 2]
- [etc.]

**Supporting Details:**
[Detailed information with inline citations]

---
Continue this format for all subtopics.`

const writingAgentPrompt = `You are an academic writing specialist who synthesizes research into comprehensive reports.

Your responsibilities:
1. Transform research findings into well-structured academic reports
2. Ensure proper citations and attribution
3. Create coherent narratives that connect different aspects of the research

Report structure:
# [Research Topic]

## Executive Summary
[Brief overview of key findings]

## Introduction
[Context and background]

## Main Sections
[Organized by subtopics with proper headings]
- Use the research findings to create comprehensive sections
- Include citations in [Source Name](URL) format
- Connect ideas across sections for coherent flow

## Conclusion
[Synthesis of findings and key takeaways]

## References
[List of all sources cited]

Do NOT include a quality assessment — end your report with the References section.`

// Package-level agents, assigned once in NewAgents() before the worker
// starts registering components.
var (
	ScopingAgent  *agnt5.Agent
	ResearchAgent *agnt5.Agent
	WritingAgent  *agnt5.Agent
)

// NewAgents builds the three research-pipeline agents.
//
// Note: the Go SDK has no max_tokens option on NewAgent (Python's
// Agent(max_tokens=8192) has no equivalent here yet) — omitted rather than
// faked.
func NewAgents(model agnt5.LanguageModel) error {
	var err error

	ScopingAgent, err = agnt5.NewAgent("ScopingAgent",
		agnt5.WithAgentModel(model),
		agnt5.WithAgentInstructions(scopingAgentPrompt),
		agnt5.WithAgentMaxTurns(3),
	)
	if err != nil {
		return err
	}

	fetchWebpage, err := NewFetchWebpageTool()
	if err != nil {
		return err
	}
	wikipediaSearch, err := NewWikipediaSearchTool()
	if err != nil {
		return err
	}

	ResearchAgent, err = agnt5.NewAgent("ResearchAgent",
		agnt5.WithAgentModel(model),
		agnt5.WithAgentInstructions(researchAgentPrompt),
		agnt5.WithAgentTools(fetchWebpage, wikipediaSearch),
		agnt5.WithAgentMaxTurns(10),
	)
	if err != nil {
		return err
	}

	WritingAgent, err = agnt5.NewAgent("WritingAgent",
		agnt5.WithAgentModel(model),
		agnt5.WithAgentInstructions(writingAgentPrompt),
		agnt5.WithAgentMaxTurns(3),
	)
	return err
}
