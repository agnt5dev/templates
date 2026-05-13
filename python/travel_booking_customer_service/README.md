# AI Travel Booking Assistant

> Conversational travel agent that searches real flights and hotels, creates itineraries, and remembers every detail of your trip - all through natural chat.

## Quick Start

```bash
cd customer_service_agnt5
export OPENAI_API_KEY=sk-... SERPAPI_KEY=your_key
agnt5 dev up
```

## What You Can Build

- **Travel Booking Platforms**: Multi-turn conversational booking with real-time flight/hotel search
- **Customer Service Chatbots**: Context-aware assistants that maintain conversation history and user preferences across sessions
- **Trip Planning Services**: AI agents that orchestrate complex multi-step workflows (search → compare → book → itinerary)

## Installation

### Prerequisites
- Python 3.10+
- AGNT5 CLI installed ([installation guide](https://docs.agnt5.com))
- OpenAI API key
- SerpAPI key (for flight and hotel search)

### Setup

1. Install uv (Python package manager):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Clone or create from template:
   ```bash
   agnt5 create --template travel-booking my-travel-agent
   cd my-travel-agent
   ```

3. Install dependencies:
   ```bash
   uv sync
   ```

4. Set up environment variables:
   ```bash
   # Create .env file
   cat > .env << EOF
   OPENAI_API_KEY=your_openai_api_key_here
   SERPAPI_KEY=your_serpapi_key_here
   EOF
   ```

   Get a SerpAPI key at: https://serpapi.com (free tier available)

5. Start the AGNT5 dev server:
   ```bash
   agnt5 dev up
   ```

## Usage

### Start the Travel Agent Worker

```bash
cd customer_service_agnt5
uv run python -m travel_booking.main
```

The worker connects to AGNT5 and registers the travel booking workflow.

### Book Travel Through Chat

**Option 1: Using the AGNT5 CLI**

```bash
# Start planning a trip
agnt5 workflow run travel_booking_workflow \
  --input '{"message": "I want to plan a trip from New York to Paris in December"}'

# Continue the conversation (use returned session_id)
agnt5 workflow run travel_booking_workflow \
  --input '{"message": "Show me flights for December 15-22", "session_id": "abc-123"}'

# Ask for hotels
agnt5 workflow run travel_booking_workflow \
  --input '{"message": "What hotels are available?", "session_id": "abc-123"}'

# Create full itinerary
agnt5 workflow run travel_booking_workflow \
  --input '{"message": "Create a complete itinerary for my trip", "session_id": "abc-123"}'
```

**Option 2: Using HTTP API**

```bash
# First message
curl -X POST http://localhost:34183/v1/workflows/travel_booking_workflow/run \
  -H "Content-Type: application/json" \
  -d '{"message": "I need to book a flight from San Francisco to Tokyo"}'

# Follow-up in same session
curl -X POST http://localhost:34183/v1/workflows/travel_booking_workflow/run \
  -H "Content-Type: application/json" \
  -d '{"message": "Make it for 2 people departing January 10", "session_id": "xyz-789"}'
```

**Option 3: From Python Code**

```python
from agnt5 import WorkflowClient

client = WorkflowClient()

# Start conversation
result = client.run_workflow(
    "travel_booking_workflow",
    inputs={"message": "Plan a family trip to London"}
)

session_id = result["session_id"]

# Continue conversation
result = client.run_workflow(
    "travel_booking_workflow",
    inputs={
        "message": "We're a family of 4, traveling March 15-25",
        "session_id": session_id
    }
)

# Request complete itinerary
result = client.run_workflow(
    "travel_booking_workflow",
    inputs={
        "message": "Create a complete itinerary with flights, hotels, and activities",
        "session_id": session_id
    }
)
```

### View Results

The workflow returns comprehensive booking information:

```json
{
  "status": "completed",
  "session_id": "abc-123-def-456",
  "output": "I found 3 great flight options for you from JFK to CDG:\n\n1. Air France AF123 - $850\n   Departs: 6:00 PM, Arrives: 8:00 AM+1\n   Duration: 8h 0m\n\n2. Delta DL456 - $920\n   Departs: 8:30 PM, Arrives: 10:30 AM+1\n   Duration: 8h 0m\n\nAnd 3 hotel options in Paris:\n\n1. Hotel Plaza Athénée - $450/night (4.8★)\n...",
  "tool_calls_made": 2,
  "tools_used": ["search_flights", "search_hotels"],
  "conversation_length": 6,
  "total_searches": 2
}
```

### What You Get

Each conversation provides:

1. **Real-Time Search Results**
   - Flights: Airlines, prices, times, durations, flight numbers
   - Hotels: Names, prices, ratings, reviews, amenities
   - Powered by SerpAPI (live Google Flights/Hotels data)

2. **Complete Itineraries**
   - Day-by-day activity suggestions
   - Flight and hotel recommendations
   - Total cost estimates
   - Personalized based on preferences

3. **Persistent Conversation State**
   - Full message history
   - User preferences (budget, dates, destinations)
   - Shopping cart (items being considered)
   - Confirmed bookings
   - Search history

4. **Context-Aware Responses**
   - Agent remembers previous messages
   - Never asks for information already provided
   - Builds understanding incrementally across turns

### Example Conversation

```bash
User: "I want to plan a trip from NYC to Paris"
Agent: "Great! I'd be happy to help you plan your Paris trip. When are you thinking of traveling?"

User: "December 15 to 22, for 2 people"
Agent: [Searches flights] "I found some excellent options:
       1. Air France - $850/person, 6:00 PM departure...
       2. Delta - $920/person, 8:30 PM departure...
       Would you like me to search for hotels as well?"

User: "Yes, show me hotels near the Eiffel Tower"
Agent: [Searches hotels] "Here are top-rated hotels near the Eiffel Tower:
       1. Hotel Plaza Athénée - $450/night (4.8★)...
       Would you like me to create a complete itinerary?"

User: "Yes please"
Agent: [Creates itinerary] "Here's your complete Paris itinerary for Dec 15-22:

       FLIGHTS:
       - Outbound: Air France AF123, Dec 15, 6:00 PM...

       HOTELS:
       - Hotel Plaza Athénée, 7 nights, $3,150 total...

       DAY-BY-DAY ACTIVITIES:
       Day 1 (Dec 15): Arrival, check-in, evening Eiffel Tower visit...
       Day 2 (Dec 16): Louvre Museum, Seine River cruise...

       TOTAL ESTIMATED COST: $5,850 for 2 people"
```

## Configuration

### Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...           # Your OpenAI API key
SERPAPI_KEY=your_key            # Your SerpAPI key for flight/hotel search

# Optional
AGNT5_API_URL=http://localhost:34183    # AGNT5 Gateway URL
```

### Customization Options

Modify `src/travel_booking/agents.py` to customize:

- **LLM Model**: Change from `gpt-4o-mini` to `gpt-4o` for better quality
- **Communication Style**: Adjust agent instructions for different tones (formal, casual, enthusiastic)
- **Search Preferences**: Modify default number of results returned
- **Tools**: Add new tools (car rentals, activities, restaurant bookings)

Example - Using GPT-4 for Premium Experience:

```python
travel_booking_agent = Agent(
    name="travel_booking_agent",
    model="openai/gpt-4o",  # Changed from gpt-4o-mini
    instructions="""...""",
    tools=[search_flights, search_hotels, create_itinerary],
    temperature=0.2,
)
```

Example - Adding Budget Constraints:

```python
# In agent instructions, add:
"""
## Budget Awareness
- Always ask about budget preferences early in the conversation
- Filter and prioritize results based on stated budget
- Provide options across different price ranges (economy, mid-range, luxury)
- Show total cost estimates proactively
"""
```

<details>
<summary>Architecture</summary>

## System Architecture

### Single-Agent Architecture with Tools

The system uses one intelligent agent with access to three tools:

```
User Message
     ↓
Travel Booking Agent (context-aware)
     ↓
   Tool Selection
     ↓
   ┌─────┴──────┬──────────────┐
   ↓            ↓              ↓
search_flights  search_hotels  create_itinerary
   ↓            ↓              ↓
 SerpAPI      SerpAPI        Framework
   ↓            ↓              ↓
Response with real-time data
```

### Agent

**Travel Booking Agent** (`travel_booking_agent`)
- Model: `openai/gpt-4o-mini` (configurable)
- Context-aware: Reviews full conversation history
- Tools: `search_flights`, `search_hotels`, `create_itinerary`
- Temperature: 0.2 (focused, consistent responses)
- Capabilities:
  - Multi-turn conversation handling
  - Automatic information gathering
  - Intelligent tool orchestration
  - Airport code inference (NYC→JFK, LA→LAX, etc.)
  - Context building across messages

### Tools

1. **`search_flights`** - Real-time flight search via SerpAPI
   - Parameters: departure_id, arrival_id, outbound_date, return_date, adults
   - Returns: Top 3 flights with prices, airlines, times, durations
   - Backend: SerpAPI Google Flights

2. **`search_hotels`** - Real-time hotel search via SerpAPI
   - Parameters: location, check_in_date, check_out_date, adults
   - Returns: Top 3 hotels with prices, ratings, amenities
   - Backend: SerpAPI Google Hotels

3. **`create_itinerary`** - Itinerary framework creation
   - Parameters: destination, travel_dates, preferences
   - Returns: Structured itinerary template
   - Agent enriches with flight/hotel details

### Workflow

**`travel_booking_workflow`** - Chat-enabled workflow:

```python
@workflow
async def travel_booking_workflow(ctx, message, session_id):
    # 1. Load/create session entity
    session = TravelBookingSession(key=f"travel_booking:{session_id}")

    # 2. Add user message to history
    await session.add_message("user", message)

    # 3. Get conversation context
    messages = await session.get_messages()

    # 4. Build context-aware input for agent
    if len(messages) > 1:
        # Include last 5 messages for context
        context_str = build_context(messages[-5:])
        agent_input = f"{context_str}\nCurrent message: {message}"
    else:
        agent_input = message

    # 5. Run agent with tools
    result = await travel_booking_agent.run(agent_input, context=ctx)

    # 6. Save response and track tool usage
    await session.add_message("assistant", result.output)
    if result.tool_calls:
        await session.record_search({
            "tools_used": [tc["name"] for tc in result.tool_calls]
        })

    # 7. Return response
    return {"status": "completed", "output": result.output, ...}
```

### State Management

**`TravelBookingSession` Entity** - Comprehensive session state:

```python
TravelBookingSession(key="travel_booking:{session_id}")
  ├── messages: [
  │     {role, content, timestamp},  # Full conversation history
  │     ...
  │   ]
  ├── preferences: {                 # User travel preferences
  │     budget: "$2000",
  │     dates: "Dec 15-22",
  │     ...
  │   }
  ├── cart_items: {                  # Items being considered
  │     "flight_1": {type, details, cost},
  │     "hotel_1": {type, details, cost},
  │     ...
  │   }
  ├── bookings: [                    # Confirmed bookings
  │     {booking_id, type, details, cost, confirmation_number},
  │     ...
  │   ]
  ├── search_history: [              # Search tracking
  │     {tools_used, timestamp},
  │     ...
  │   ]
  └── trip_details: {                # Overall trip info
        trip_name: "Paris Vacation",
        start_date: "2024-12-15",
        end_date: "2024-12-22",
        status: "planning",
        total_cost: 5850.00
      }
```

**Entity Features:**
- ✅ Persists across workflow runs
- ✅ Survives server restarts
- ✅ Tracks complete booking lifecycle
- ✅ Supports cart/booking management
- ✅ Session-based isolation

### Conversation Flow

```
Message 1: "I want to go to Paris"
  → Session created
  → Message stored
  → Agent extracts intent: travel to Paris
  → Response: "When would you like to travel?"

Message 2: "December 15-22"
  → Session loaded (has message 1)
  → Context: User wants Paris trip
  → Agent extracts dates
  → Calls search_flights(JFK→CDG, Dec 15-22)
  → Response: Flight options + hotel prompt

Message 3: "Show me hotels"
  → Session loaded (has messages 1-2)
  → Context: Paris trip Dec 15-22, flights shown
  → Calls search_hotels(Paris, Dec 15-22)
  → Response: Hotel options

Message 4: "Create full itinerary"
  → Session loaded (has messages 1-3)
  → Context: Full trip details known
  → Calls create_itinerary(Paris, Dec 15-22, prefs)
  → Agent combines all previous tool results
  → Response: Complete itinerary with flights, hotels, activities
```

### Project Structure

```
customer_service_agnt5/
├── src/
│   └── travel_booking/
│       ├── agents.py              # Travel booking agent
│       ├── workflows.py           # Chat workflow
│       ├── tools.py               # Flight, hotel, itinerary tools
│       ├── entities.py            # TravelBookingSession entity
│       ├── main.py                # Worker entry point
│       └── __init__.py
├── pyproject.toml                 # Dependencies
├── .env                           # Environment variables
└── README.md
```

</details>

## Troubleshooting

### Common Issues

**Worker not starting:**
```bash
# Check AGNT5 dev server
agnt5 dev status

# Restart dev server
agnt5 dev down
agnt5 dev up
```

**API Key Errors:**
```bash
# Verify OpenAI key
echo $OPENAI_API_KEY

# Verify SerpAPI key
echo $SERPAPI_KEY

# Check .env file
cat .env
```

**No search results:**
- Verify SerpAPI key is valid and has credits
- Check SerpAPI dashboard: https://serpapi.com/dashboard
- Review logs for API errors: `agnt5 dev logs`
- Test SerpAPI directly: `curl "https://serpapi.com/search?engine=google_flights&api_key=YOUR_KEY"`

**Agent not remembering context:**
- Ensure using same `session_id` across messages
- Check entity state in database
- Review conversation history: Look at `messages` field in response
- Context limited to last 5 messages (configurable in `workflows.py:91`)

**Slow responses:**
- SerpAPI searches can take 5-10 seconds each
- Consider caching popular routes
- Use faster model: Change to `gpt-3.5-turbo` in `agents.py`

**Invalid airport codes:**
- Agent auto-infers codes (NYC→JFK, LA→LAX)
- Add more mappings in agent instructions (`agents.py:95-109`)
- Or modify to ask user for specific airport

## Customization

### Add More Tools

Extend beyond flights and hotels:

**1. Add Car Rental Tool**

```python
# In tools.py
@tool(auto_schema=True)
async def search_car_rentals(
    ctx: Context,
    location: str,
    pickup_date: str,
    dropoff_date: str
) -> Dict:
    """Search for car rentals using SerpAPI."""
    # Implementation
    ...

# In agents.py - add to tools list
tools=[search_flights, search_hotels, search_car_rentals, create_itinerary]
```

**2. Add Activity Booking**

```python
@tool(auto_schema=True)
async def search_activities(
    ctx: Context,
    destination: str,
    activity_type: str,
    date: str
) -> Dict:
    """Search for tours and activities."""
    # Use TripAdvisor or Viator API
    ...
```

**3. Add Restaurant Reservations**

```python
@tool(auto_schema=True)
async def find_restaurants(
    ctx: Context,
    location: str,
    cuisine: str,
    date: str,
    party_size: int
) -> Dict:
    """Find restaurants and availability."""
    # Use OpenTable or Google Places API
    ...
```

### Multi-Agent Extensions

Transform into multi-agent system with specialists:

- **Flight Specialist Agent**: Expert in finding best flight deals
- **Hotel Specialist Agent**: Expert in accommodation recommendations
- **Itinerary Specialist Agent**: Expert in creating day-by-day plans
- **Triage Agent**: Routes to appropriate specialist (like tutor agent)

See `agnt5_tutor_agent` blueprint for handoff pattern examples.

### Related Templates

- **Tutor Agent**: See `agnt5_tutor_agent` for multi-agent handoff patterns
- **Deep Research**: See `agnt5_deep_research` for multi-stage workflows
- **Code Reviewer**: See `code_reviewer` for quality assessment

### Extension Ideas

1. **Price Alerts**: Monitor prices and notify when deals appear
2. **Multi-City Trips**: Support complex itineraries with multiple destinations
3. **Group Travel**: Handle multiple travelers with different preferences
4. **Loyalty Programs**: Integrate airline/hotel loyalty points
5. **Payment Integration**: Add Stripe/PayPal for actual bookings
6. **Travel Insurance**: Recommend and quote insurance options
7. **Visa Requirements**: Check and advise on visa needs
8. **Weather Integration**: Show forecast for travel dates
9. **Currency Conversion**: Display prices in user's preferred currency
10. **Review Summaries**: Aggregate hotel/restaurant reviews with AI

## License

MIT License - see [LICENSE](../../LICENSE) file for details
