"""Main entry point for Coding Agent (Development Mode).

This file demonstrates direct workflow execution without Worker.
Use this for local testing and development.
For production deployment, use app.py instead.
"""

import asyncio

from agnt5._telemetry import setup_module_logger
from agnt5.entity import with_entity_context

from coding_agent_agnt5.workflows import coding_agent_workflow
from coding_agent_agnt5.config import config


logger = setup_module_logger(__name__)


@with_entity_context
async def main(task_description: str, max_retries: int = 15):
    """Run the coding agent workflow in development mode.

    Args:
        task_description: Description of the coding task
        max_retries: Maximum number of retry attempts (default: 15)

    Returns:
        WorkflowResult model or None if configuration error
    """
    try:
        config.validate()
    except ValueError as e:
        logger.error("❌ Configuration Error: %s", e)
        return None

    result = await coding_agent_workflow(task_description, max_retries)

    if result.success:
        logger.info("✅ WORKFLOW SUCCESSFUL")
        logger.info("📄 Generated Code:\n%s", result.code or 'No code')
        if result.documentation:
            logger.info("📝 Documentation saved to: final_response.md")
    else:
        logger.error("❌ WORKFLOW FAILED: %s", result.error)
        if result.code:
            code_preview = result.code[:500]
            logger.info("📄 Last Generated Code Preview:\n%s...", code_preview)

    return result


if __name__ == "__main__":
    task_description = """
    Given a string s, return whether s is a valid number.

For example, all the following are valid numbers: "2", "0089", "-0.1", "+3.14", "4.", "-.9", "2e10", "-90E3", "3e+7", "+6e-1", "53.5e93", "-123.456e789", while the following are not valid numbers: "abc", "1a", "1e", "e3", "99e2.5", "--6", "-+3", "95a54e53".

Formally, a valid number is defined using one of the following definitions:

An integer number followed by an optional exponent.
A decimal number followed by an optional exponent.
An integer number is defined with an optional sign '-' or '+' followed by digits.

A decimal number is defined with an optional sign '-' or '+' followed by one of the following definitions:

Digits followed by a dot '.'.
Digits followed by a dot '.' followed by digits.
A dot '.' followed by digits.
An exponent is defined with an exponent notation 'e' or 'E' followed by an integer number.

The digits are defined as one or more digits.
 
    """

    asyncio.run(main(task_description, max_retries=15))
