import asyncio
import os
from agnt5 import AgentContext
from dotenv import load_dotenv
from agents import tutor_agent

load_dotenv()

async def main():
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Please set OPENAI_API_KEY environment variable")
        return

    # Use the triage agent (with handoffs to specialized tutors)
    main_agent = tutor_agent

    # Create a context for logging
    ctx = AgentContext(run_id="tutor-test-session", agent_name="tutor_agent")

    ctx.logger.info("Starting tutor agent test session with handoffs")

    try:
        # Test the tutor agent with history question (should hand off to history_tutor)
        ctx.logger.info("Testing history question - expecting handoff to history tutor")
        result = await main_agent.run("What were the main causes of World War I?", context=ctx)
        print(f"\nHistory Question Response:\n{result.output}\n")
        ctx.logger.info("History question completed successfully")

        # Test with math question (should hand off to math_tutor)
        ctx.logger.info("Testing math question - expecting handoff to math tutor")
        result = await main_agent.run("Calculate the derivative of x^2 + 3x + 5", context=ctx)
        print(f"\nMath Question Response:\n{result.output}\n")
        ctx.logger.info("Math question completed successfully")

        ctx.logger.info("Tutor agent test session completed successfully")

    except Exception as e:
        ctx.logger.error(f"Test session failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
