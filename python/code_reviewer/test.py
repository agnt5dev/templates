import asyncio
from code_reviewer.workflow import code_reviewer_workflow
from code_reviewer.config import config


async def main():
    pr_url = "https://github.com/arunreddy/agnt5/pull/118"   # optional
    ticket_url = "https://agentifytest.atlassian.net/browse/SCRUM-5"

    print("🚀 Running Context Builder Workflow...")

    result = await code_reviewer_workflow(pr_url=pr_url, ticket_url=ticket_url)
    print("✅ Workflow completed successfully!")
    print("---- Workflow Result ----")
    print(f"PR #{result['pr_number']} — {result['repo']}")
    print(f"Files reviewed: {result['files_reviewed']}/{result['total_files']}")
    print(f"\n--- Context Summary ---\n{result['context_summary']}")
    print(f"\n--- Review Report ---\n{result['report']}")
    if result.get("report_file"):
        print(f"\n📄 Full report saved to: {result['report_file']}")


if __name__ == "__main__":
    asyncio.run(main())
