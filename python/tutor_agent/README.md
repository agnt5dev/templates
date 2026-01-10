# AI Tutor Agent

> Multi-subject educational assistant that intelligently routes questions to specialized tutors for history, math, and more - with full conversation memory.

## Quick Start

```bash
cd agnt5_tutor_agent
export OPENAI_API_KEY=sk-...
agnt5 dev up
```

## What You Can Build

- **Personalized Tutoring Systems**: Multi-subject tutors that maintain learning context across sessions
- **Educational Chatbots**: Subject-aware assistants that delegate to specialized domain experts
- **Adaptive Learning Platforms**: Conversation-based tutoring with persistent student history and progress tracking

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
   agnt5 create --template tutor-agent my-tutor
   cd my-tutor
   ```

3. Install dependencies:
   ```bash
   uv sync
   ```

4. Set up environment variables:
   ```bash
   # Create .env file
   echo "OPENAI_API_KEY=your_openai_api_key_here" > .env
   ```

5. Start the AGNT5 dev server:
   ```bash
   agnt5 dev up
   ```

## Usage

### Start the Tutor Worker

```bash
cd agnt5_tutor_agent
uv run python app.py
```

The worker connects to AGNT5 and registers the tutor workflow.

### Ask Questions

**Option 1: Using the AGNT5 CLI**

```bash
# Start a new tutoring session
agnt5 workflow run tutor_chat_workflow \
  --input '{"message": "What caused the French Revolution?"}'

# Continue the conversation (use the returned session_id)
agnt5 workflow run tutor_chat_workflow \
  --input '{"message": "What role did Marie Antoinette play?", "session_id": "abc-123"}'
```

**Option 2: Using HTTP API**

```bash
# First question
curl -X POST http://localhost:34183/v1/workflows/tutor_chat_workflow/run \
  -H "Content-Type: application/json" \
  -d '{"message": "Solve the equation: 2x + 5 = 15"}'

# Follow-up question (same session)
curl -X POST http://localhost:34183/v1/workflows/tutor_chat_workflow/run \
  -H "Content-Type: application/json" \
  -d '{"message": "Can you explain each step?", "session_id": "xyz-789"}'
```

**Option 3: From Python Code**

```python
from agnt5 import WorkflowClient

client = WorkflowClient()

# First question
result = client.run_workflow(
    "tutor_chat_workflow",
    inputs={"message": "What is the Pythagorean theorem?"}
)

session_id = result["session_id"]

# Follow-up question
result = client.run_workflow(
    "tutor_chat_workflow",
    inputs={
        "message": "Can you show me an example?",
        "session_id": session_id
    }
)
```

### View Results

The workflow returns a complete tutoring response with conversation state:

```json
{
  "output": "The Pythagorean theorem states that in a right triangle, a² + b² = c²...",
  "session_id": "abc-123-def-456",
  "message_count": 2,
  "subject": "math",
  "conversation_preview": [
    {
      "role": "user",
      "content": "What is the Pythagorean theorem?",
      "subject": "general",
      "timestamp": 1703001234.567
    },
    {
      "role": "assistant",
      "content": "The Pythagorean theorem states...",
      "subject": "math",
      "timestamp": 1703001235.890
    }
  ]
}
```

### What You Get

Each tutoring interaction provides:

1. **Intelligent Response** - Context-aware answer from the appropriate specialist tutor
2. **Session Continuity** - Conversation history maintained across multiple questions
3. **Subject Tracking** - Automatic detection and routing based on subject area (history, math, general)
4. **Conversation Preview** - Recent message history for context

### Multi-Turn Conversations

The tutor remembers your conversation:

```bash
# Session starts
User: "What is algebra?"
Tutor: [Math tutor explains algebra basics]

# Follow-up (same session)
User: "Can you give me an example?"
Tutor: [Math tutor provides example, remembering context]

# Another follow-up
User: "What about quadratic equations?"
Tutor: [Math tutor explains, building on previous discussion]
```

## Configuration

### Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...           # Your OpenAI API key
```

### Customization Options

Modify `agents.py` to customize tutor behavior:

- **Add New Subjects**: Create new specialized agents (e.g., science, literature)
- **Change LLM Models**: Use different models for different tutors
- **Adjust Teaching Style**: Modify agent instructions for different grade levels
- **Add Tools**: Equip tutors with search, calculators, or other tools

Example - Adding a Science Tutor:

```python
# Create specialized science tutor
science_tutor_agent = Agent(
    name="science_tutor",
    model="openai/gpt-4o-mini",
    instructions="""You are a specialized science tutor...
    - Explain scientific concepts with experiments and examples
    - Cover physics, chemistry, biology
    - Use diagrams and visual descriptions...""",
)

# Add handoff to triage agent
triage_agent = Agent(
    name="triage_tutor",
    model="openai/gpt-4o-mini",
    instructions="...",
    handoffs=[
        handoff(history_tutor_agent, description="..."),
        handoff(math_tutor_agent, description="..."),
        handoff(science_tutor_agent, description="Transfer to science tutor for physics, chemistry, biology questions"),
    ],
)
```

<details>
<summary>Architecture</summary>

## System Architecture

### Agent Handoff Pattern

The tutor uses AGNT5's **handoff pattern** for intelligent routing:

```
User Question
      ↓
Triage Agent (analyzes subject)
      ↓
   Handoff Decision
      ↓
   ┌──────┴──────┐
   ↓             ↓
History Tutor  Math Tutor
   ↓             ↓
Specialized Response
```

### Three-Agent System

1. **Triage Agent** (`triage_agent`)
   - Analyzes incoming questions
   - Detects subject area (history, math, general)
   - Routes via handoffs to specialist tutors
   - Model: `openai/gpt-4o-mini`

2. **History Tutor Agent** (`history_tutor_agent`)
   - Specializes in historical events, periods, figures
   - Provides context, timelines, and multiple perspectives
   - Connects past to present
   - Model: `openai/gpt-4o-mini`

3. **Math Tutor Agent** (`math_tutor_agent`)
   - Specializes in mathematical problems and concepts
   - Step-by-step problem solving
   - Teaches underlying principles
   - Model: `openai/gpt-4o-mini`

### Workflow

**`tutor_chat_workflow`** - Chat-based conversational workflow:

```python
@workflow(chat=True)
async def tutor_chat_workflow(ctx, message, session_id):
    # 1. Load/create conversation entity
    conversation = TutorConversation(key=f"tutor_session:{session_id}")

    # 2. Add user message to history
    await conversation.add_message("user", message)

    # 3. Detect subject (first message only)
    if first_message:
        subject = detect_subject(message)  # Simple keyword matching
        await conversation.set_primary_subject(subject)

    # 4. Get conversation context
    recent_messages = await conversation.get_recent_messages(5)

    # 5. Pass to triage agent (will handoff to specialist)
    result = await tutor_agent.run_sync(agent_input, context=ctx)

    # 6. Save response and return
    await conversation.add_message("assistant", response)
    return {"output": response, ...}
```

### State Management

**`TutorConversation` Entity** maintains session state:

```python
TutorConversation(key="tutor_session:{session_id}")
  ├── messages: [
  │     {role, content, subject, timestamp},
  │     ...
  │   ]
  ├── primary_subject: "history" | "math" | "general"
  └── message_count: int
```

**Features:**
- ✅ Persistent across multiple workflow runs
- ✅ Survives server restarts
- ✅ Tracks full conversation history
- ✅ Subject-aware message tagging

### Subject Detection

Simple keyword-based detection on first message:

```python
# History keywords
["history", "historical", "war", "revolution", "empire", "ancient", "medieval"]

# Math keywords
["math", "mathematics", "calculate", "equation", "solve", "algebra", "geometry"]
```

If no keywords match → remains "general" → triage agent handles routing

### Handoff Mechanism

The triage agent uses `handoffs` parameter:

```python
handoffs=[
    handoff(
        history_tutor_agent,
        description="Transfer to history tutor for historical questions"
    ),
    handoff(
        math_tutor_agent,
        description="Transfer to math tutor for math questions"
    ),
]
```

When the triage agent determines a specialist is needed, it automatically transfers the conversation using the handoff mechanism.

### Project Structure

```
agnt5_tutor_agent/
├── agents.py              # 3 agents (triage, history, math)
├── workflows.py           # tutor_chat_workflow
├── entities.py            # TutorConversation entity
├── app.py                 # Worker entry point
├── main.py                # Alternative entry point
├── pyproject.toml         # Dependencies
└── README.md
```

</details>

## Troubleshooting

### Common Issues

**Worker not starting:**
```bash
# Check AGNT5 dev server status
agnt5 dev status

# Restart dev server
agnt5 dev down
agnt5 dev up
```

**OpenAI API errors:**
```bash
# Verify API key
echo $OPENAI_API_KEY

# Check .env file
cat .env
```

**Conversation not persisting:**
- Ensure you're using the same `session_id` across requests
- Check AGNT5 logs for entity storage errors: `agnt5 dev logs`
- Verify entity state: Check the AGNT5 database

**Wrong tutor responding:**
- Check subject detection keywords in `workflows.py:42-49`
- Verify handoff descriptions in `agents.py:103-112`
- Review triage agent instructions in `agents.py:85-102`

**Agent not understanding context:**
- Conversation context is limited to recent 5 messages by default
- Increase context window: Change `get_recent_messages(5)` → `get_recent_messages(10)` in `workflows.py:57`

## Customization

### Add More Subjects

Extend beyond history and math:

1. **Create specialized agent** in `agents.py`:
   ```python
   science_tutor_agent = Agent(
       name="science_tutor",
       model="openai/gpt-4o-mini",
       instructions="..."
   )
   ```

2. **Add handoff to triage agent**:
   ```python
   handoffs=[
       ...,
       handoff(science_tutor_agent, description="...")
   ]
   ```

3. **Update subject detection** in `workflows.py`:
   ```python
   elif any(word in message_lower for word in ["science", "physics", "chemistry"]):
       detected_subject = "science"
   ```

### Related Templates

- **Multi-Agent Customer Service**: See `customer_service_agnt5` for production handoff patterns
- **Deep Research Agent**: See `agnt5_deep_research` for multi-stage agent orchestration
- **Code Reviewer**: See `code_reviewer` for quality assessment patterns

### Extension Ideas

1. **Add Tools**: Equip tutors with calculators, Wikipedia search, diagram generators
2. **Progress Tracking**: Add quiz generation and score tracking to entity
3. **Adaptive Difficulty**: Adjust explanations based on student performance
4. **Multi-Language**: Support tutoring in different languages
5. **Voice Interface**: Add speech-to-text for spoken questions
6. **Visual Learning**: Generate diagrams, charts, and illustrations

## License

MIT License - see [LICENSE](../../LICENSE) file for details
