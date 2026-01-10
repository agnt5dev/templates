# Deep Research Agent

> Autonomous AI research system that turns any topic into a comprehensive, Wikipedia-sourced report with quality assessment - no intervention needed.

## Quick Start

```bash
cd agnt5_deep_research
export OPENAI_API_KEY=sk-...
agnt5 dev up
```

## What You Can Build

- **Academic Research Assistant**: Generate comprehensive research reports on any topic with proper citations and quality scoring
- **Knowledge Base Generator**: Automatically create structured documentation from Wikipedia sources on complex subjects
- **Research Pipeline**: Build autonomous multi-agent systems that plan, research, write, and evaluate content without human intervention

## Installation

### Prerequisites
- Python 3.10+
- AGNT5 CLI installed ([installation guide](https://docs.agnt5.com))
- OpenAI API key

### Setup

1. Install uv (Python package manager):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Clone or create from template:
   ```bash
   agnt5 create --template deep-research my-research-agent
   cd my-research-agent
   ```

3. Set up environment variables:
   ```bash
   # Create .env file
   echo "OPENAI_API_KEY=your_openai_api_key_here" > .env
   ```

4. Start the AGNT5 dev server:
   ```bash
   agnt5 dev up
   ```

## Usage

### Start the Worker

First, start the research worker:

```bash
cd agnt5_deep_research
uv run python app.py
```

The worker will connect to the AGNT5 dev server and be ready to process research requests.

### Trigger Research

**Option 1: Using the AGNT5 CLI**

```bash
# Trigger a research workflow
agnt5 workflow run deep_research_workflow --input '{"message": "Artificial Intelligence Ethics"}'
```

**Option 2: Using HTTP API**

```bash
curl -X POST http://localhost:34183/v1/workflows/deep_research_workflow/run \
  -H "Content-Type: application/json" \
  -d '{"message": "Quantum Computing Applications in Healthcare"}'
```

**Option 3: From Python Code**

```python
from agnt5 import WorkflowClient

client = WorkflowClient()
result = client.run_workflow(
    "deep_research_workflow",
    inputs={"message": "Climate Change Adaptation Strategies"}
)
```

### View Results

The workflow returns a complete research report:

```json
{
  "status": "completed",
  "session_id": "abc-123-def-456",
  "topic": "Artificial Intelligence Ethics",
  "research_plan": "PLAN:\n1. AI Ethics Fundamentals\n2. Bias and Fairness...",
  "report": "# Artificial Intelligence Ethics\n\n## Executive Summary...",
  "quality_assessment": "QUALITY ASSESSMENT:\n- Completeness: 9/10...",
  "stage": "completed"
}
```

### What You Get

Each research session produces:

1. **Research Plan** - Structured breakdown of 3-6 subtopics
2. **Final Report** - Academic-style document with:
   - Executive Summary
   - Introduction
   - Main Sections (organized by subtopic)
   - Conclusion
   - References (all Wikipedia sources cited)
3. **Quality Assessment** - Evaluation scores:
   - Completeness (how well it answers the question)
   - Accuracy (source quality and citations)
   - Clarity (organization and readability)
   - Depth (level of detail and analysis)
   - Overall score out of 10

### Resume Interrupted Research

If the workflow fails or is interrupted, you can resume using the session ID:

```bash
# The workflow automatically resumes from the last completed stage
agnt5 workflow run deep_research_workflow --input '{"message": "same topic", "session_id": "abc-123-def-456"}'
```

## Configuration

### Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...           # Your OpenAI API key
```

### Customization Options

Modify `src/deep_research/agents.py` to customize:

- **LLM Models**: Change from `gpt-4o-mini` to other OpenAI models
- **Research Sources**: Extend beyond Wikipedia (add custom tools)
- **Quality Metrics**: Adjust evaluation criteria in the Writing Agent
- **Subtopic Count**: Modify the planning agent to generate more/fewer subtopics

Example - using GPT-4 for better quality:

```python
research_agent = Agent(
    name="ResearchAgent",
    model="openai/gpt-4",  # Changed from openai/gpt-4o-mini
    instructions=research_agent_prompt,
    tools=[wikipedia_search_tool, fetch_webpage_tool],
    max_tokens=4096
)
```

<details>
<summary>Architecture</summary>

## System Architecture

### Three-Stage Pipeline

The system uses a coordinated multi-agent architecture:

```
Topic Input → Scoping Agent → Research Agent → Writing Agent → Final Report + Quality Score
                    ↓               ↓                ↓
              Research Plan    Gathered Facts    Synthesized Content
                    ↓               ↓                ↓
              ResearchSession Entity (State Management)
```

### Agents

1. **Scoping Agent** (`gpt-4o-mini`)
   - Analyzes research topics
   - Creates structured research plans (3-6 subtopics)
   - Makes reasonable assumptions for vague requests
   - No user interaction required

2. **Research Agent** (`gpt-4o-mini`)
   - Executes research plan systematically
   - Uses Wikipedia as primary source
   - Gathers comprehensive information per subtopic
   - Organizes findings with citations
   - **Tools**: `wikipedia_search_tool`, `fetch_webpage_tool`

3. **Writing Agent** (`gpt-4o-mini`)
   - Synthesizes research into academic reports
   - Evaluates quality (completeness, accuracy, clarity, depth)
   - Generates structured output with executive summary
   - Provides actionable quality scores

### State Management

**ResearchSession Entity** maintains workflow state:
- Stores: topic, research plan, findings, final report, quality assessment
- Enables resumable research sessions
- Persists in AGNT5 entity store
- Survives failures and restarts

### Workflows

**Main Workflow** (`deep_research_workflow`):
```python
@workflow
def deep_research_workflow(topic: str) -> dict:
    # Stage 1: Planning
    plan = scoping_agent.run(topic)

    # Stage 2: Research
    findings = research_agent.run(plan)

    # Stage 3: Writing & Evaluation
    report = writing_agent.run(findings)

    return {
        "report": report.content,
        "quality_score": report.quality_assessment
    }
```

### Tools

- **wikipedia_search_tool**: Searches Wikipedia for relevant articles
- **fetch_webpage_tool**: Fetches and extracts content from Wikipedia pages

### Project Structure

```
agnt5_deep_research/
├── src/
│   └── deep_research/
│       ├── agents.py           # 3 specialized agents
│       ├── workflows.py        # Main workflow orchestration
│       ├── entities.py         # ResearchSession entity
│       ├── tools.py           # Wikipedia and web fetch tools
│       ├── prompts.py         # Agent system prompts
│       └── __init__.py
├── agnt5.yaml                 # AGNT5 project configuration
├── pyproject.toml             # Python dependencies
├── uv.lock                    # Locked dependencies
└── README.md
```

</details>

## Troubleshooting

### Common Issues

**Worker not starting:**
```bash
# Check if AGNT5 dev server is running
agnt5 dev status

# Restart dev server
agnt5 dev down
agnt5 dev up
```

**OpenAI API errors:**
```bash
# Verify API key is set
echo $OPENAI_API_KEY

# Check .env file exists
cat .env
```

**Module import errors:**
```bash
# Reinstall dependencies
uv sync --reinstall

# Ensure you're in the project directory
cd agnt5_deep_research
```

**Research getting stuck:**
- Check worker logs: `agnt5 worker logs`
- Verify Wikipedia connectivity
- Check OpenAI API rate limits

**State not persisting:**
- Ensure AGNT5 dev server is running
- Check database connectivity in AGNT5 logs
- Verify ResearchSession entity is properly defined

## Customization

### Extend Research Sources

Beyond Wikipedia, you can add custom tools for:
- **Academic Databases**: PubMed, arXiv, Google Scholar
- **News Sources**: NewsAPI, Reuters, Associated Press
- **Corporate Knowledge**: Internal wikis, documentation systems

### Related Templates

- **Multi-Agent Customer Service**: See `customer_service_agnt5` blueprint for agent handoff patterns
- **Code Review Agent**: See `code_reviewer` blueprint for quality assessment patterns
- **Tutor Agent**: See `tutor_agent` blueprint for educational conversation flows

### Extension Ideas

1. **Multi-Source Research**: Combine Wikipedia with academic papers and news articles
2. **Interactive Mode**: Add user feedback loops between pipeline stages
3. **Citation Export**: Generate BibTeX, MLA, or APA formatted references
4. **Visual Reports**: Add charts, graphs, and diagrams to reports
5. **Comparative Analysis**: Research and compare multiple topics side-by-side
6. **Translation**: Generate reports in multiple languages

## License

MIT License - see [LICENSE](../../LICENSE) file for details
