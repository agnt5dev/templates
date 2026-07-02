/**
 * Deep Research Functions
 *
 * Individual research functions used in the workflow pipeline:
 * 1. planResearch     — Creates a research plan using the Scoping Agent
 * 2. conductResearch  — Conducts research across all subtopics using the Research Agent
 * 3. writeReport      — Synthesizes all findings using the Writing Agent
 */

import { fn } from '@agnt5/sdk';
import type { Context } from '@agnt5/sdk';
import { getScopingAgent, getResearchAgent, getWritingAgent } from './agents.js';

export const planResearch = fn('plan_research').run(
  async (ctx: Context, input: { topic: string }): Promise<string> => {
    const { topic } = input;
    ctx.logger.info(`Stage 1: Creating research plan for: ${topic.slice(0, 50)}...`);

    const currentDate = new Date().toISOString().split('T')[0];

    const prompt = `Today's date is ${currentDate}.

Research topic: ${topic}

Create a structured research plan for this topic:
1. Break it into 3-6 manageable subtopics
2. Define the research strategy for each subtopic
3. Make reasonable assumptions if the topic is vague or ambiguous
4. Start your response with "PLAN:" followed by the structured plan`;

    const result = await getScopingAgent().run(prompt, ctx);

    let plan = result.output;
    if (plan.trim().startsWith('PLAN:')) {
      plan = plan.replace('PLAN:', '').trim();
    }

    ctx.logger.info('Research plan created successfully');
    return plan;
  },
);

export const conductResearch = fn('conduct_research').run(
  async (ctx: Context, input: { topic: string; research_plan: string }): Promise<string> => {
    const { topic, research_plan } = input;
    ctx.logger.info(`Stage 3: Conducting research for: ${topic.slice(0, 50)}...`);

    const prompt = `Execute systematic research for the following topic:

Topic: ${topic}

Research Plan:
${research_plan}

Instructions:
1. Research each subtopic thoroughly using Wikipedia as your primary source
2. Supplement with web searches for additional context when needed
3. Organize your findings by subtopic
4. Cite all sources clearly (include titles and URLs)
5. Focus on factual information and verifiable details

Use the wikipedia_search and fetch_webpage tools to gather comprehensive information.`;

    const result = await getResearchAgent().run(prompt, ctx);
    ctx.logger.info(`Research completed — ${result.output.length} characters of findings`);
    return result.output;
  },
);

export const writeReport = fn('write_report').run(
  async (
    ctx: Context,
    input: { topic: string; research_plan: string; research_findings: string },
  ): Promise<string> => {
    const { topic, research_plan, research_findings } = input;
    ctx.logger.info(`Stage 4: Writing report for: ${topic.slice(0, 50)}...`);

    const prompt = `Create a comprehensive academic report based on the research findings.

Topic: ${topic}

Research Plan:
${research_plan}

Research Findings:
${research_findings}

Instructions:
1. Synthesize the findings into a well-structured academic report
2. Follow the report structure: Executive Summary, Introduction, Main Sections, Conclusion, References
3. Use proper citations in [Source Name](URL) format
4. Create a coherent narrative that connects different aspects of the research
5. Ensure the report answers the original research question comprehensively
6. End your report with the References section`;

    const result = await getWritingAgent().run(prompt, ctx);

    ctx.logger.info('Report synthesized successfully');
    return result.output;
  },
);
