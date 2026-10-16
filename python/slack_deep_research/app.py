#!/usr/bin/env python3
"""Slack Deep Research Agent - AGNT5 Worker."""

import asyncio
import logging
import os
import sys

from agnt5 import Worker

from slack_deep_research.approval import _claim_event, _post_report, _request_plan_approval
from slack_deep_research.agents import scoping_agent, research_agent, writing_agent
from slack_deep_research.functions import _conduct_research, _plan_research, _write_report
from slack_deep_research.tools import fetch_webpage_tool, wikipedia_search_tool
from slack_deep_research.workflows import slack_deep_research

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

SERVICE_NAME = "slack-deep-research"


async def main():
    logger.info("Starting %s worker...", SERVICE_NAME)

    coordinator_endpoint = os.getenv("AGNT5_COORDINATOR_ENDPOINT", "http://localhost:34186")
    tenant_id = os.getenv("AGNT5_TENANT_ID")
    deployment_id = os.getenv("AGNT5_DEPLOYMENT_ID")

    logger.info("Environment — TENANT_ID: %s  DEPLOYMENT_ID: %s", tenant_id, deployment_id)

    try:
        worker = Worker(
            service_name=SERVICE_NAME,
            service_version="1.0.0",
            coordinator_endpoint=coordinator_endpoint,
            runtime="standalone",
            workflows=[slack_deep_research],
            functions=[
                _claim_event,
                _plan_research,
                _request_plan_approval,
                _conduct_research,
                _write_report,
                _post_report,
            ],
            agents=[scoping_agent, research_agent, writing_agent],
            tools=[fetch_webpage_tool, wikipedia_search_tool],
        )

        logger.info("Worker registered:")
        logger.info("  Workflow : slack_deep_research (triggers: slack.app_mention, slack.message)")
        logger.info("  Agents   : ScopingAgent, ResearchAgent, WritingAgent")
        logger.info("  Tools    : wikipedia_search_tool, fetch_webpage_tool")

        await worker.run()
        return 0

    except ImportError as e:
        logger.error("Make sure to install agnt5: pip install agnt5")
        logger.error("Import error: %s", e)
        return 1
    except Exception as e:
        logger.error("Worker failed: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
