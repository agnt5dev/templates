/**
 * Deep Research Agents
 *
 * Three specialized agents for the research pipeline:
 * 1. ScopingAgent  — Analyzes topic and creates a structured research plan
 * 2. ResearchAgent — Conducts systematic research using Wikipedia and web sources
 * 3. WritingAgent  — Synthesizes findings into a comprehensive academic report
 */

import { Agent, LM } from '@agnt5/sdk';
import { fetchWebpage, wikipediaSearch } from './tools.js';

const SCOPING_AGENT_INSTRUCTIONS = `You are a research scoping specialist who structures research requests into actionable plans.

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

Always start your response with "PLAN:" followed by the research plan.`;

const RESEARCH_AGENT_INSTRUCTIONS = `You are a systematic research specialist who gathers comprehensive information.

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

**Supporting Details:**
[Detailed information with inline citations]

---
Continue this format for all subtopics.`;

const WRITING_AGENT_INSTRUCTIONS = `You are an academic writing specialist who synthesizes research into comprehensive reports.

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

Do NOT include a quality assessment — end your report with the References section.`;

// Lazy singletons — each agent is created once on first use and reused for all
// subsequent calls. This prevents the AgentRegistry "Overwriting existing agent"
// warning that occurs when factory functions are called inside parallel tasks.
let _scopingAgent: Agent | undefined;
let _researchAgent: Agent | undefined;
let _writingAgent: Agent | undefined;

export function getScopingAgent(): Agent {
  if (!_scopingAgent) {
    _scopingAgent = new Agent({
      name: 'ScopingAgent',
      model: LM.openai(),
      modelName: 'openai/gpt-4o-mini',
      instructions: SCOPING_AGENT_INSTRUCTIONS,
      temperature: 0.3,
    });
  }
  return _scopingAgent;
}

export function getResearchAgent(): Agent {
  if (!_researchAgent) {
    _researchAgent = new Agent({
      name: 'ResearchAgent',
      model: LM.openai(),
      modelName: 'openai/gpt-4o-mini',
      instructions: RESEARCH_AGENT_INSTRUCTIONS,
      tools: [wikipediaSearch, fetchWebpage],
      temperature: 0.2,
    });
  }
  return _researchAgent;
}

export function getWritingAgent(): Agent {
  if (!_writingAgent) {
    _writingAgent = new Agent({
      name: 'WritingAgent',
      model: LM.openai(),
      modelName: 'openai/gpt-4o-mini',
      instructions: WRITING_AGENT_INSTRUCTIONS,
      temperature: 0.3,
    });
  }
  return _writingAgent;
}
