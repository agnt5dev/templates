import os

from agnt5 import Agent, MCPClient, WorkflowContext, workflow
from agnt5.lm import BuiltInTool
from agnt5.tools import web_search

from deep_wiki_agent.functions import canned_brief, save_report

DEEPWIKI_URL = "https://mcp.deepwiki.com/mcp"

INVESTIGATOR_PROMPT = """You are a research investigator. Use the DeepWiki tools
to read source repos and the search tool for outside context. Produce a brief
with sections: Answer, Evidence, Trade-offs, Risks, Open questions. Cite specific
files or URLs in Evidence."""


@workflow
async def investigate_with_review(ctx: WorkflowContext, question: str) -> dict:
    """Investigate a question with MCP-backed tools and human review."""
    mcp: MCPClient | None = None
    tools_used = 0

    try:
        if os.getenv("AGNT5_MOCK_MODE") == "1":
            draft = canned_brief(question)
        else:
            # 1. Connect to a remote MCP server. Tools are discovered AFTER connect,
            #    so the tool list is part of each run's recorded state — not module
            #    state captured at import time.
            mcp = MCPClient(id="deep-wiki-agent")
            mcp.add_streamable_http_server("deepwiki", DEEPWIKI_URL)
            await mcp.connect()
            mcp_tools = mcp.get_tools()

            # 2. Build the tool list explicitly. No hidden bundles — what's in here
            #    is exactly what the agent sees.
            tools = list(mcp_tools)
            built_in_tools: list[BuiltInTool] = []
            if (
                os.getenv("AGNT5_BRAVE_SEARCH_API_KEY")
                or os.getenv("AGNT5_TAVILY_API_KEY")
                or os.getenv("AGNT5_SEARXNG_URL")
            ):
                tools.insert(0, web_search(max_results=5))      # AGNT5 tool
            else:
                built_in_tools.append(BuiltInTool.WEB_SEARCH)   # provider-hosted

            # 3. Run the agent. context=ctx is REQUIRED for durability — without it,
            #    every model call replays from scratch on retry.
            investigator = Agent(
                name="deep_wiki_investigator",
                model="openai/gpt-4o-mini",
                instructions=INVESTIGATOR_PROMPT,
                tools=tools,
                built_in_tools=built_in_tools,
                max_iterations=6,
            )
            result = await investigator.run(user_message=question, context=ctx)
            draft = result.output
            tools_used = len(tools) + len(built_in_tools)

        # 4. Pause for human review. Durable — the workflow is not in process
        #    memory while it waits. wait_for_user accepts input_type values
        #    "text", "approval", "select", or "multiselect".
        decision = await ctx.wait_for_user(
            question=f"Review the brief:\n\n{draft}",
            input_type="select",
            options=[
                {"id": "approve", "label": "Approve"},
                {"id": "edit",    "label": "Edit before saving"},
                {"id": "reject",  "label": "Reject"},
            ],
        )

        if decision == "reject":
            return {"status": "rejected", "draft": draft}

        if decision == "edit":
            edited = await ctx.wait_for_user(
                question="Paste the edited brief:",
                input_type="text",
            )
            if edited:
                draft = edited

        # 5. Side effect through ctx.step so it's checkpointed once and
        #    skipped on replay.
        saved = await ctx.step(save_report, question=question, brief=draft)
        return {
            "status": "approved",
            "report_path": saved["path"],
            "tool_count": tools_used,
        }
    finally:
        if mcp is not None:
            await mcp.disconnect()
