import asyncio
import json

import httpx
from agnt5 import Client
from agnt5.eval import LLMJudge, LLMJudgeConfig, llm_judge


# ---------------------------------------------------------------------------
# Journey 1: Standalone Python — SDK only, no platform needed
# ---------------------------------------------------------------------------
async def test_journey1_standalone():
    """LLM Judge runs entirely in the SDK, calling OpenAI/Anthropic directly."""
    print("\n=== Journey 1: Standalone Python LLM Judge ===\n")

    config = LLMJudgeConfig(
        criteria="Is the response helpful and factually correct?",
        model="openai/gpt-4o-mini",
    )

    result = await llm_judge(
        output="The capital of France is Paris.",
        config=config,
        expected="Paris",
    )

    print(f"  Score:       {result.score}")
    print(f"  Passed:      {result.passed}")
    print(f"  Explanation: {result.explanation}")


# ---------------------------------------------------------------------------
# Journey 2: SDK client.eval() — execute component + score via platform
# ---------------------------------------------------------------------------
async def test_journey2_client_eval():
    """Calls client.eval() which executes a component on the platform and scores the output."""
    print("\n=== Journey 2: SDK client.eval() ===\n")

    client = Client()

    result = client.eval(
        component="hello_world",
        input_data={"name": "World"},
        expected="Hello World",
        scorers=[
            "exact_match",
            LLMJudge(criteria="Is the greeting friendly and welcoming?"),
        ],
    )

    print(f"  Passed:  {result.passed}")
    print(f"  Output:  {result.output}")
    print(f"  Scores:  {result.scores}")
    print(f"  Raw:     {vars(result) if hasattr(result, '__dict__') else result}")
    for score in result.scores:
        status = "pass" if score.passed else "fail"
        print(f"  {score.scorer}: {score.score} ({status})")
        if hasattr(score, "explanation") and score.explanation:
            print(f"    explanation: {score.explanation}")


# ---------------------------------------------------------------------------
# Journey 3: REST API /v1/eval/score — score an output directly via curl/HTTP
# ---------------------------------------------------------------------------
async def test_journey3_rest_api():
    """Calls the gateway /v1/eval/score endpoint directly over HTTP."""
    print("\n=== Journey 3: REST API /v1/eval/score ===\n")

    url = "http://localhost:34183/v1/eval/score"
    payload = {
        "scorer_name": "llm_judge",
        "scorer_type": "llm_judge",
        "output": "Hello Claude, welcome!",
        "expected": "Hello Claude",
        "config": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "criteria": "Is this a friendly greeting?",
        },
    }

    async with httpx.AsyncClient() as http:
        resp = await http.post(url, json=payload)
        data = resp.json()

    if "error" in data:
        print(f"  Error: {data['error']}")
    else:
        print(f"  Score:       {data.get('score')}")
        print(f"  Passed:      {data.get('passed')}")
        print(f"  Explanation: {data.get('explanation')}")
    print(f"  Raw response: {json.dumps(data, indent=2)}")


# ---------------------------------------------------------------------------
# Main — run all or pick one
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    tests = {
        "1": ("Journey 1: Standalone", test_journey1_standalone),
        "2": ("Journey 2: client.eval()", test_journey2_client_eval),
        "3": ("Journey 3: REST API", test_journey3_rest_api),
    }

    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg in tests:
                print(f"\nRunning {tests[arg][0]}...")
                asyncio.run(tests[arg][1]())
            else:
                print(f"Unknown journey: {arg}. Use 1, 2, or 3.")
    else:
        print("Running all journeys...\n")
        for key, (label, fn) in tests.items():
            try:
                asyncio.run(fn())
            except Exception as e:
                print(f"  FAILED: {e}")
