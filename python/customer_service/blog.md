# Building a Conversational Travel Booking Agent with AGNT5

Ever wished you had a travel agent that remembers your entire conversation, understands context, and can search for real-time flight and hotel data on demand? That's exactly what this Travel Booking Agent accomplishes: a conversational AI system that maintains context across multiple interactions while providing access to live travel data.

## What Makes This Different?

Unlike simple chatbots that forget context between messages or static travel search tools, this system is designed to **remember everything and understand naturally**. When you start planning a trip from New York to London, you can have a flowing conversation:

1. **"I want to travel to London next month"**
   - Agent understands intent and asks for clarification on dates

2. **"December 15th to 22nd"**
   - Agent remembers the destination (London) and departure (implied from context)
   - Searches for flights and hotels using real-time data

3. **"Can you find cheaper options?"**
   - Agent knows what "options" refers to (previous flight results)
   - Maintains context without requiring you to repeat everything

4. **"Also, I need hotels near the city center"**
   - Agent refines hotel search based on new requirements
   - Creates a comprehensive itinerary combining all information

The entire conversation flows naturally with full context retention across all interactions.

## The Conversational Architecture

The system uses a layered architecture designed for natural, context-aware interactions:

### The Travel Booking Agent - Your Intelligent Assistant

The heart of the system is a single, powerful agent that orchestrates all travel booking tasks:

```python
from agnt5 import Agent
from travel_booking.tools import search_flights, search_hotels, create_itinerary

travel_booking_agent = Agent(
    name="TravelBookingAgent",
    model="openai/gpt-4o-mini",
    instructions="""You are a professional travel booking assistant with access
    to real-time flight and hotel search capabilities.

    Your responsibilities:
    1. Understand user travel needs through natural conversation
    2. Extract key details: departure city, destination, dates, travelers, budget
    3. Search for flights and hotels using your tools
    4. Create comprehensive travel itineraries
    5. Maintain conversation context and remember user preferences

    Always:
    - Be friendly and professional
    - Ask clarifying questions when needed
    - Provide detailed information about search results
    - Offer alternatives when available
    - Remember the conversation context across all messages""",
    tools=[search_flights, search_hotels, create_itinerary],
)
```

**Key features:**
- Single agent with multi-tool orchestration
- Natural language understanding
- Context-aware responses
- Real-time data access through SerpAPI

### The Tool Layer - Real-Time Travel Data

Three specialized tools provide access to live travel information:

#### 1. Flight Search Tool

```python
from agnt5 import tool
from serpapi import GoogleSearch

@tool(auto_schema=True)
def search_flights(
    departure: str,
    destination: str,
    outbound_date: str,
    return_date: str = None,
    adults: int = 1,
    travel_class: str = "economy"
) -> str:
    """Search for flights between two cities using Google Flights data.

    Args:
        departure: Departure city or airport code
        destination: Destination city or airport code
        outbound_date: Departure date (YYYY-MM-DD)
        return_date: Return date for round trips
        adults: Number of adult passengers
        travel_class: economy, business, or first

    Returns:
        Formatted flight results with prices, times, and airlines
    """
    # SerpAPI Google Flights search
    params = {
        "engine": "google_flights",
        "departure_id": departure,
        "arrival_id": destination,
        "outbound_date": outbound_date,
        # ... more parameters
    }

    search = GoogleSearch(params)
    results = search.get_dict()

    # Format and return flight options
    return format_flight_results(results)
```

**Key feature:** Real-time flight data from Google Flights via SerpAPI, not static datasets.

#### 2. Hotel Search Tool

```python
@tool(auto_schema=True)
def search_hotels(
    location: str,
    check_in: str,
    check_out: str,
    adults: int = 1,
    sort_by: str = "highest_rated"
) -> str:
    """Search for hotels in a specific location using Google Hotels data.

    Args:
        location: City or location to search for hotels
        check_in: Check-in date (YYYY-MM-DD)
        check_out: Check-out date (YYYY-MM-DD)
        adults: Number of guests
        sort_by: highest_rated, lowest_price, or most_reviewed

    Returns:
        Formatted hotel results with prices, ratings, and amenities
    """
    # SerpAPI Google Hotels search
    params = {
        "engine": "google_hotels",
        "q": location,
        "check_in_date": check_in,
        "check_out_date": check_out,
        # ... more parameters
    }

    search = GoogleSearch(params)
    results = search.get_dict()

    # Format and return hotel options
    return format_hotel_results(results)
```

**Key feature:** Live hotel availability and pricing, refreshed with each search.

#### 3. Itinerary Creation Tool

```python
@tool(auto_schema=True)
def create_itinerary(
    destination: str,
    start_date: str,
    end_date: str,
    flight_info: str = "",
    hotel_info: str = "",
    preferences: str = ""
) -> str:
    """Create a comprehensive travel itinerary.

    Args:
        destination: Travel destination
        start_date: Trip start date
        end_date: Trip end date
        flight_info: Flight details if available
        hotel_info: Hotel details if available
        preferences: User preferences (sightseeing, food, culture, etc.)

    Returns:
        Structured itinerary with day-by-day activities
    """
    # Generate structured itinerary
    itinerary = build_itinerary_structure(
        destination, start_date, end_date,
        flight_info, hotel_info, preferences
    )

    return format_itinerary(itinerary)
```

**Key feature:** Intelligent itinerary generation based on destination knowledge and user preferences.

## The Conversational Workflow

The magic happens in the chat-enabled workflow orchestration:

```python
from agnt5 import workflow, WorkflowContext
from travel_booking.entities import TravelBookingSession

@workflow(chat=True)  # Enable multi-turn conversation support
async def travel_booking_workflow(
    ctx: WorkflowContext,
    message: str,
    session_id: str = None
) -> dict:
    """Conversational travel booking workflow with persistent state.

    The chat=True flag enables:
    - Multi-turn conversations
    - Automatic message routing to the agent
    - Conversation history management
    - Context retention across messages
    """

    # Load or create session entity
    if not session_id:
        session_id = generate_session_id()

    session = TravelBookingSession(key=f"travel:{session_id}")

    # Get conversation history
    conversation_history = await session.get_conversation_index()

    # Add current message to history
    conversation_history.append({
        "role": "user",
        "content": message,
        "timestamp": datetime.now().isoformat()
    })

    # Run agent with full conversation context
    result = await travel_booking_agent.run(
        message=message,
        conversation_history=conversation_history,
        context=ctx
    )

    # Store agent response in history
    conversation_history.append({
        "role": "assistant",
        "content": result.output,
        "timestamp": datetime.now().isoformat(),
        "tools_used": [tool.name for tool in result.tools_called]
    })

    # Persist updated conversation
    await session.set_conversation_index(conversation_history)

    # Extract and store booking details if mentioned
    if result.extracted_info:
        await session.update_booking_details(result.extracted_info)

    return {
        "response": result.output,
        "session_id": session_id,
        "conversation_length": len(conversation_history),
        "tools_used": [tool.name for tool in result.tools_called]
    }
```

**What `chat=True` enables:**
- Automatic conversation history management
- Multi-turn context retention
- Session-based state persistence
- Natural conversational flow

## State Management: Never Lose Context

One of the most powerful features is conversation-aware state management through entities:

```python
from agnt5 import entity

@entity
class TravelBookingSession:
    """Persistent state for travel booking conversations.

    Stores everything needed to resume conversations and maintain context:
    - Full conversation history
    - Extracted booking details (dates, locations, preferences)
    - Search results cache
    - User preferences and requirements
    """

    def __init__(self, key: str):
        self.key = key

    async def get_conversation_index(self) -> list:
        """Retrieve full conversation history."""
        return await self.get("conversation_index", [])

    async def set_conversation_index(self, history: list):
        """Store updated conversation history."""
        await self.set("conversation_index", history)

    async def get_booking_details(self) -> dict:
        """Get extracted booking information."""
        return await self.get("booking_details", {})

    async def update_booking_details(self, details: dict):
        """Update booking details (merge with existing)."""
        current = await self.get_booking_details()
        current.update(details)
        await self.set("booking_details", current)

    async def cache_search_results(self, search_type: str, results: dict):
        """Cache flight/hotel search results for quick reference."""
        cache_key = f"{search_type}_results"
        await self.set(cache_key, {
            "results": results,
            "timestamp": datetime.now().isoformat()
        })

    async def get_user_preferences(self) -> dict:
        """Retrieve user preferences learned over time."""
        return await self.get("preferences", {})
```

**This means:**
- If a user disconnects mid-conversation, they can resume exactly where they left off
- The agent remembers all previous searches and conversations
- Search results are cached to avoid redundant API calls
- User preferences persist across sessions
- Perfect for real-world customer service scenarios

## How It Works in Practice

### Example 1: Simple Flight Search

**Conversation:**

```
User: I want to fly from New York to London

Agent: I'd be happy to help you find flights from New York to London!
       To search for the best options, I need a few more details:

       - What are your travel dates?
       - How many passengers?
       - Do you prefer economy, business, or first class?

User: December 15th to 22nd, just me, economy is fine

Agent: [Calls search_flights tool]

       Great! I found several flight options for you:

       Option 1: British Airways
       - Outbound: Dec 15, 7:00 PM - 7:15 AM+1 (Direct)
       - Return: Dec 22, 9:30 AM - 12:45 PM
       - Price: $650 per person

       Option 2: Delta Airlines
       - Outbound: Dec 15, 9:15 PM - 9:45 AM+1 (Direct)
       - Return: Dec 22, 6:00 PM - 9:15 PM
       - Price: $725 per person

       Would you like me to search for hotels in London as well?

User: Yes, somewhere in central London

Agent: [Calls search_hotels tool]

       Perfect! Here are some highly-rated hotels in central London:

       Hotel 1: The Hoxton, Holborn
       - Rating: 4.5/5 (2,341 reviews)
       - Price: $180/night ($1,260 total for 7 nights)
       - Location: Central London, near British Museum

       Hotel 2: Premier Inn London County Hall
       - Rating: 4.3/5 (1,892 reviews)
       - Price: $145/night ($1,015 total for 7 nights)
       - Location: South Bank, near London Eye

       Would you like me to create a complete itinerary for your trip?
```

**What happened:**
- Agent remembered departure/destination across messages
- Extracted details naturally from conversation
- Used real-time tools for current prices
- Offered proactive next steps

**Time:** Real-time responses with live data.

### Example 2: Complex Multi-Turn Planning

**Conversation:**

```
User: I'm planning a family vacation

Agent: Wonderful! I'd love to help plan your family vacation.
       To get started, could you tell me:
       - Where would you like to go?
       - How many people are traveling?
       - Do you have any date preferences?

User: Four of us - two adults, two kids. Thinking about Orlando.

Agent: Orlando is a fantastic family destination! When are you planning to visit?

User: Spring break, probably mid-March

Agent: Perfect timing! March weather in Orlando is great.
       Do you have specific dates in mind, like March 15-22?

User: Yes, that works. We'll need a hotel near the theme parks.

Agent: [Calls search_flights tool]
       [Calls search_hotels tool]

       I've found some great options for your family trip to Orlando:

       FLIGHTS:
       - JetBlue: $320/person ($1,280 total for 4)
       - Southwest: $285/person ($1,140 total for 4)

       HOTELS (near theme parks):
       - Holiday Inn Resort Orlando Suites
         * $165/night, sleeps 6, shuttle to parks
         * Total: $1,155 for 7 nights

       - Wyndham Grand Orlando Resort Bonnet Creek
         * $210/night, family suite, water park access
         * Total: $1,470 for 7 nights

       Would you like me to create a day-by-day itinerary including
       theme park recommendations?

User: Yes please! We want to hit Disney and Universal.

Agent: [Calls create_itinerary tool]

       Here's your Orlando family vacation itinerary:

       DAY 1 (March 15): Arrival
       - Flight arrival ~2 PM
       - Check into hotel
       - Explore Disney Springs (free, great for dinner)

       DAY 2-3: Magic Kingdom
       - Full days at Magic Kingdom
       - FastPass recommendations: Space Mountain, Seven Dwarfs

       DAY 4: Epcot
       - World Showcase exploration
       - Character dining at Akershus

       DAY 5-6: Universal Orlando
       - Universal Studios & Islands of Adventure
       - Wizarding World of Harry Potter (both parks)

       DAY 7: Relaxation Day
       - Hotel pool and water park
       - Pack and prepare for departure

       DAY 8 (March 22): Departure
       - Late checkout, afternoon flight home

       Total estimated cost: ~$3,800-4,200
       (flights + hotel + park tickets + meals)

User: Can we do Universal in one day instead and add another Disney park?

Agent: Absolutely! Let me adjust the itinerary:

       [Updates itinerary based on conversation context]

       UPDATED ITINERARY:
       DAY 5: Universal (both parks in one day - doable with early start!)
       DAY 6: Hollywood Studios (Star Wars Galaxy's Edge!)

       This gives you 4 Disney park days and 1 Universal day.
       Much better for experiencing all of Disney!
```

**What happened:**
- Agent built understanding progressively through conversation
- Remembered family composition (4 people: 2 adults, 2 kids)
- Tracked destination (Orlando), dates (March 15-22)
- Adjusted plans based on feedback
- Maintained full context across 8+ message turns
- Provided personalized recommendations

**Time:** Fluid, real-time conversation with immediate adjustments.

## What Makes It Reliable?

### 1. Conversation Memory, Not Just Message Memory

The system doesn't just remember the last message - it maintains a structured conversation index:

```python
conversation_history = [
    {
        "role": "user",
        "content": "I want to fly to London",
        "timestamp": "2025-11-11T10:00:00",
        "extracted_info": {"destination": "London"}
    },
    {
        "role": "assistant",
        "content": "Great! When would you like to travel?",
        "timestamp": "2025-11-11T10:00:05",
        "tools_used": []
    },
    {
        "role": "user",
        "content": "December 15th to 22nd",
        "timestamp": "2025-11-11T10:01:00",
        "extracted_info": {
            "outbound_date": "2025-12-15",
            "return_date": "2025-12-22"
        }
    },
    # ... conversation continues
]
```

This enables:
- Reference resolution ("Can you find cheaper options?" - cheaper than what?)
- Context carryover (remembers destination from 5 messages ago)
- User preference learning (always prefers window seats)
- Conversation resumption after days or weeks

### 2. Real-Time Data, Not Static Results

SerpAPI integration provides:
- Current flight prices and availability
- Live hotel rates and occupancy
- Real airline schedules and routes
- Up-to-date reviews and ratings

The agent always works with fresh data, not cached or outdated information.

### 3. Intelligent Tool Orchestration

The agent decides when and how to use tools based on conversation context:

```python
# Agent reasoning process:
User: "I need a hotel"
→ Missing location, dates
→ Ask clarifying questions
→ Don't call search_hotels yet

User: "In London, December 15-22"
→ Has all required parameters
→ Call search_hotels(location="London", check_in="2025-12-15", ...)
→ Return formatted results

User: "Can you find cheaper options?"
→ Understands "cheaper" refers to previous hotel results
→ Call search_hotels with sort_by="lowest_price"
→ Compare with previous results
```

### 4. Graceful Failure Recovery

If a tool call fails or the workflow is interrupted:

```python
# Session state preserves everything
session = TravelBookingSession(key="travel:session_123")

# Can resume from any point
conversation = await session.get_conversation_index()
# → Full history available

booking_details = await session.get_booking_details()
# → Extracted info preserved: {
#     "departure": "New York",
#     "destination": "London",
#     "outbound_date": "2025-12-15",
#     "return_date": "2025-12-22",
#     "travelers": 1
#   }

# Continue conversation seamlessly
```

## Technical Excellence Under the Hood

### AGNT5 Platform Features

The system leverages AGNT5's conversational features:

**Chat-Enabled Workflows:**
- `@workflow(chat=True)` - Automatic conversation management
- Message routing to agents
- History preservation
- Session handling

**Entity State Management:**
- Persistent conversation storage
- Structured data extraction
- Search result caching
- User preference tracking

**Agent Framework:**
- Natural language understanding
- Multi-tool orchestration
- Context-aware responses
- Automatic schema generation for tools

**Tool Integration:**
- `@tool(auto_schema=True)` - Automatic OpenAPI schema generation
- Type-safe parameters
- Error handling
- Result formatting

### Deployment Modes

The system works across all AGNT5 deployment modes:

**Embedded Mode (Development):**
```bash
# Start platform
just platform dev-server python

# Start travel booking worker
cd blueprints/customer_service_agnt5
uv run agnt5 worker start --worker travel_booking.main:worker
```

**Community Edition (Self-Hosted):**
```bash
# Start all services with PostgreSQL
just dev-up-with-workers community

# Worker automatically starts in container
```

**Managed Edition (Production Scale):**
```bash
# Full event-sourcing with CockroachDB + Redpanda
just dev-up-with-workers managed

# Horizontally scalable for high-volume customer service
```

## Real-World Applications

This conversational travel agent excels at:

### Customer Service
- 24/7 travel booking assistance
- Natural language query handling
- Context-aware customer support
- Personalized recommendations

### Travel Agencies
- Automated trip planning
- Multi-turn itinerary creation
- Real-time price comparisons
- Customer preference learning

### Corporate Travel
- Business trip booking
- Policy compliance checking
- Travel approval workflows
- Expense estimation

### Personal Travel Planning
- Family vacation planning
- Budget-conscious travel search
- Complex multi-destination trips
- Special occasion travel

## Key Design Decisions

### Why Conversational vs. Form-Based?

**Traditional approach:** Fill out form (departure, destination, dates, travelers), then search.
**Conversational approach:** Natural dialogue that progressively builds understanding.

**Benefits:**
- ✅ More natural user experience
- ✅ Can handle incomplete information gracefully
- ✅ Adapts to user's communication style
- ✅ Learns preferences through conversation
- ✅ Can ask clarifying questions intelligently
- ⚠️ Requires more sophisticated state management

### Why Single Agent vs. Multiple Specialists?

**Alternative approach:** Separate agents for flights, hotels, itineraries.
**Current approach:** One agent with access to all tools.

**Benefits:**
- Simpler conversation flow (one voice, one context)
- Agent can coordinate across tools seamlessly
- Easier to maintain conversation coherence
- Better at understanding cross-domain requests ("find me flights and a hotel")
- Lower latency (no agent-to-agent handoffs)

### Why SerpAPI vs. Direct Airline/Hotel APIs?

**Alternatives considered:** Amadeus API, direct airline APIs, hotel aggregators.
**Why SerpAPI wins:**
- Aggregates data from Google Flights/Hotels (comprehensive coverage)
- Single API for multiple data sources
- No individual airline/hotel API integrations needed
- Consistent data format
- Lower maintenance burden

### Why Entity-Based State vs. Database Tables?

**Alternative approach:** Store conversations in PostgreSQL/MongoDB.
**Entity-based approach:** Use AGNT5's entity system.

**Benefits:**
- Automatic versioning and history
- Type-safe state access
- Built-in serialization
- Integrates with AGNT5 workflow lifecycle
- Survives platform restarts
- No separate database management

## Getting Started

### Prerequisites

- Python 3.10+
- OpenAI API key
- SerpAPI key
- AGNT5 platform running

### Quick Setup

```bash
# 1. Clone and navigate to the blueprint
cd agnt5/blueprints/customer_service_agnt5

# 2. Install dependencies
uv sync

# 3. Configure environment
cat > .env << EOF
OPENAI_API_KEY=your_openai_key_here
SERPAPI_KEY=your_serpapi_key_here
EOF

# 4. Start AGNT5 platform (in separate terminal)
cd ../../
just platform dev-server python

# 5. Start the travel booking worker
cd blueprints/customer_service_agnt5
uv run agnt5 worker start --worker travel_booking.main:worker
```

### Run Your First Conversation

**Using Python SDK:**

```python
from agnt5 import Client

client = Client()

# Start a travel booking conversation
result = client.run_workflow(
    "travel_booking_workflow",
    input={"message": "I want to plan a trip to Paris"}
)

print(result["response"])
session_id = result["session_id"]

# Continue the conversation
result = client.run_workflow(
    "travel_booking_workflow",
    input={
        "message": "For two people, next month",
        "session_id": session_id  # Same session = maintains context
    }
)

print(result["response"])
```

**Using AGNT5 CLI:**

```bash
# First message
agnt5 run workflow travel_booking_workflow \
  --input '{"message": "I need a flight from NYC to SF"}'

# Continue conversation (use session_id from first response)
agnt5 run workflow travel_booking_workflow \
  --input '{"message": "Next Tuesday, returning Thursday", "session_id": "abc-123"}'
```

### Resume a Conversation

```python
# Continue conversation from hours/days later
result = client.run_workflow(
    "travel_booking_workflow",
    input={
        "message": "Actually, can we change the hotel to something cheaper?",
        "session_id": "abc-123-from-previous-conversation"
    }
)

# Agent has full context of previous conversation
# Knows which hotel search to re-run with different parameters
```

## Example Output

**Initial Query:** "I want to travel to Tokyo for cherry blossom season"

**Conversation Flow:**

```
Agent: That sounds wonderful! Cherry blossom season in Tokyo is typically
       late March to early April. Do you have specific dates in mind?

User: First week of April

Agent: Perfect timing! To search for flights, I need to know:
       - What city will you be departing from?
       - How many travelers?
       - Approximate return date?

User: From Los Angeles, just me, staying for a week

Agent: [Calls search_flights tool]

       Great! I found several flight options from Los Angeles to Tokyo:

       ✈️  FLIGHT OPTIONS (April 1-8, 2025)

       1. Japan Airlines (JAL)
          • Outbound: April 1, 11:30 AM → April 2, 3:00 PM (Direct)
          • Return: April 8, 5:00 PM → April 8, 11:30 AM
          • Price: $1,250 (Economy)
          • Flight time: 11h 30m outbound, 10h 30m return

       2. ANA (All Nippon Airways)
          • Outbound: April 1, 1:00 PM → April 2, 4:30 PM (Direct)
          • Return: April 8, 6:30 PM → April 8, 1:00 PM
          • Price: $1,180 (Economy)
          • Flight time: 11h 30m both ways

       Would you like me to search for hotels in Tokyo as well?

User: Yes, somewhere in Shinjuku or Shibuya

Agent: [Calls search_hotels tool]

       Excellent choice! Both areas are great for cherry blossom viewing.
       Here are highly-rated hotels:

       🏨 HOTEL OPTIONS (April 1-8, 2025)

       Shinjuku Area:

       1. Shinjuku Granbell Hotel
          • Rating: 4.4/5 (1,234 reviews)
          • Price: $145/night ($1,015 total)
          • Near Shinjuku Gyoen (famous for cherry blossoms!)
          • Free WiFi, English-speaking staff

       2. Hotel Gracery Shinjuku
          • Rating: 4.2/5 (2,891 reviews)
          • Price: $165/night ($1,155 total)
          • Next to Godzilla head, central location
          • Breakfast included

       Shibuya Area:

       3. Shibuya Excel Hotel Tokyu
          • Rating: 4.5/5 (1,567 reviews)
          • Price: $185/night ($1,295 total)
          • Connected to Shibuya Station
          • Spectacular city views

       Shall I create a complete 7-day itinerary including cherry
       blossom viewing spots?

User: Yes please! And the ANA flight with the Shinjuku Granbell Hotel.

Agent: [Calls create_itinerary tool]

       Perfect choices! Here's your Tokyo Cherry Blossom Itinerary:

       🌸 TOKYO CHERRY BLOSSOM ADVENTURE
       April 1-8, 2025 | Solo Traveler

       ═══════════════════════════════════════════
       BOOKING SUMMARY
       ═══════════════════════════════════════════

       Flight: ANA (All Nippon Airways)
       • LAX → NRT: April 1, 1:00 PM
       • NRT → LAX: April 8, 6:30 PM
       • Total: $1,180

       Hotel: Shinjuku Granbell Hotel
       • Check-in: April 1 (hotel will hold room until arrival)
       • Check-out: April 8
       • Total: $1,015 (7 nights)

       Trip Total: ~$2,195 (flights + hotel)

       ═══════════════════════════════════════════
       DAY-BY-DAY ITINERARY
       ═══════════════════════════════════════════

       DAY 1 (April 1) - Arrival
       • Arrive Narita 3:00 PM (local time)
       • Narita Express to Shinjuku (90 min, ¥3,250)
       • Check into hotel
       • Evening: Explore Shinjuku area, dinner at Omoide Yokocho

       DAY 2 (April 2) - Shinjuku & Yoyogi
       🌸 Peak cherry blossom viewing!
       • Morning: Shinjuku Gyoen National Garden (¥500 entry)
         → One of Tokyo's best cherry blossom spots
       • Afternoon: Meiji Shrine & Yoyogi Park
       • Evening: Shibuya Crossing & dinner

       DAY 3 (April 3) - Asakusa & Ueno
       🌸 Historical Tokyo with sakura
       • Morning: Senso-ji Temple in Asakusa
       • Afternoon: Ueno Park (1,000+ cherry trees!)
       • Evening: Ameyoko shopping street

       DAY 4 (April 4) - Day Trip to Hakone
       🌸 Mt. Fuji views with cherry blossoms
       • Hakone Round Course (hot springs, lake cruise)
       • Cherry blossoms along Lake Ashi
       • Return to Tokyo evening

       DAY 5 (April 5) - Harajuku & Omotesando
       • Morning: Takeshita Street & Harajuku fashion
       • Afternoon: Omotesando shopping & architecture
       • Evening: teamLab Borderless digital art museum

       DAY 6 (April 6) - Imperial Palace & Ginza
       🌸 Royal gardens with sakura
       • Morning: East Gardens of Imperial Palace (free)
       • Afternoon: Ginza luxury shopping
       • Evening: Tokyo Tower sunset views

       DAY 7 (April 7) - Meguro River & Odaiba
       🌸 Final cherry blossom viewing
       • Morning: Meguro River (2.5km of cherry trees!)
       • Afternoon: Odaiba futuristic district
       • Evening: Farewell dinner in Roppongi

       DAY 8 (April 8) - Departure
       • Check out by 11 AM
       • Store luggage at hotel
       • Last-minute shopping in Shinjuku
       • Narita Express to airport (4:00 PM recommended)

       ═══════════════════════════════════════════
       CHERRY BLOSSOM FORECAST
       ═══════════════════════════════════════════

       First week of April is typically peak bloom!
       Best spots included in itinerary:
       • Shinjuku Gyoen - 1,500 trees, Day 2
       • Ueno Park - Most famous spot, Day 3
       • Meguro River - Stunning tunnel, Day 7

       ═══════════════════════════════════════════
       ESTIMATED TOTAL BUDGET
       ═══════════════════════════════════════════

       • Flights: $1,180
       • Hotel: $1,015
       • Transportation: ~$150 (7-day metro pass + Narita Express)
       • Food: ~$350 ($50/day average)
       • Activities: ~$200 (temple entries, museums)
       • Shopping: ~$300 (souvenirs, misc)

       TOTAL: ~$3,195 for 7 days in Tokyo

       Ready to book? I can help you with next steps!
```

**Follow-up adjustments:**

```
User: Can we add a day trip to Kyoto?

Agent: Absolutely! Kyoto is amazing during cherry blossom season.
       Since it's a 2.5 hour bullet train ride, I recommend extending
       your trip by one day. Should I:

       1. Replace one Tokyo day with Kyoto (keep same dates)
       2. Extend trip to April 9 (add one day, but need to rebook flight)

       Which would you prefer?

User: Option 1, replace day 5

Agent: Perfect! Here's your updated itinerary:

       [Shows revised itinerary with Day 5 now being Kyoto day trip]

       DAY 5 (April 5) - Kyoto Day Trip 🌸
       • 6:00 AM: Shinkansen from Tokyo → Kyoto (¥13,320 round trip)
       • 8:30 AM: Arrive Kyoto
       • Morning: Philosopher's Path (cherry blossom canal)
       • Midday: Kiyomizu-dera Temple
       • Afternoon: Gion district & Maruyama Park
       • 6:00 PM: Shinkansen back to Tokyo
       • 8:30 PM: Arrive Shinjuku

       Updated trip cost: ~$3,325 (added bullet train fare)
```

## The Future of Conversational Travel Booking

What's exciting about this approach is how it **feels natural** while being highly functional. Unlike traditional booking tools that force structured inputs, this system:

1. **Understands naturally** - Handles vague requests like "somewhere warm in winter"
2. **Remembers everything** - Full conversation context across unlimited messages
3. **Learns preferences** - Remembers if you always prefer window seats or hotels near metro
4. **Adapts in real-time** - Can change plans mid-conversation without starting over

This makes it ideal for:
- **Customer service** - Deploy as 24/7 travel booking assistant
- **Integration** - Embed in websites, apps, Slack, WhatsApp
- **Personalization** - Build user profiles across multiple trips
- **Scaling** - Handle thousands of concurrent conversations

### Future Enhancements

The conversational architecture makes it easy to add:

**Additional Data Sources:**
- Direct airline APIs for better pricing
- Car rental integration
- Activity/tour booking
- Restaurant reservations
- Travel insurance

**Enhanced Intelligence:**
- Budget optimization ("find cheapest combination of flight + hotel")
- Seasonal insights ("best time to visit for weather/crowds")
- Point of interest recommendations based on interests
- Multi-destination trip planning
- Group travel coordination

**Personalization Features:**
```python
# Remember across sessions
user_profile = await session.get_user_profile()
# → {
#     "preferred_airlines": ["Delta", "United"],
#     "seat_preference": "window",
#     "dietary_restrictions": ["vegetarian"],
#     "travel_style": "budget-conscious",
#     "past_destinations": ["London", "Paris", "Tokyo"]
#   }

# Proactive recommendations
"Based on your previous trips to Paris and London, you might enjoy Barcelona!"
```

**Multi-Language Support:**
- Conversations in any language
- Automatic translation of search results
- Cultural context awareness

## Project Structure

```
customer_service_agnt5/
├── src/
│   └── travel_booking/
│       ├── agents.py        # Travel booking agent
│       ├── workflows.py     # Chat workflow + simple search workflows
│       ├── tools.py         # Flight, hotel, itinerary tools
│       ├── entities.py      # TravelBookingSession entity
│       └── main.py          # Worker configuration
├── pyproject.toml           # Dependencies and config
├── .env                     # API keys (not in git)
├── README.md                # Setup and usage guide
└── blog.md                  # This document
```

**Simple, conversational, and production-ready.**

## Conclusion

The Travel Booking Agent demonstrates how conversational AI can transform customer service experiences. By maintaining full conversation context, integrating real-time data, and providing natural interactions, the system becomes genuinely useful for real-world travel planning.

Whether you're building customer service platforms, travel applications, or personal assistants, this agent provides a robust foundation for conversational booking experiences - no scripted interactions required.

The future of customer service is conversational, context-aware, and surprisingly helpful.

---

**Ready to build your own conversational booking system?** Check out the [AGNT5 platform](https://github.com/arunreddy/agnt5) and start creating intelligent, stateful conversational agents.
