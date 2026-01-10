import asyncio
from code_reviewer.workflow import code_reviewer_workflow
from agnt5 import with_entity_context
from code_reviewer.config import config

@with_entity_context
async def main():
    pr_url = "https://github.com/arunreddy/agnt5/pull/118"   # optional
    ticket_url = "https://agentifytest.atlassian.net/browse/SCRUM-5"

    print("🚀 Running Context Builder Workflow...")
    
    result = await code_reviewer_workflow(pr_url=pr_url, ticket_url=ticket_url)
    print("✅ Workflow completed successfully!")
    print("---- Workflow Result ----")
    print(result["context"]["output"])


if __name__ == "__main__":
    asyncio.run(main())
