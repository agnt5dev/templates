# Travel Booking Assistant — AGNT5 Template (Go)

A conversational travel agent that searches real flights and hotels, builds itineraries, and remembers every detail across a multi-turn chat session.

## What it does

- **Search flights and hotels** in real time using SerpAPI (Google Flights / Hotels data).
- **Build complete itineraries** with day-by-day plans, cost estimates, and recommendations.
- **Maintain conversation state** across turns — the agent never asks for information you've already given.

## Key concepts

- **Single agent with tools** — One context-aware agent orchestrates three tools: `search_flights`, `search_hotels`, and `create_itinerary`.
- **Durable conversation history** — The workflow reads/writes session-scoped memory (`ctx.Memory().Conversation()`) around each agent call, so history survives worker restarts without a separate entity.
- **Generous turn budget** — Trip-planning requests call all three tools in one turn before answering, so the agent is configured with `WithAgentMaxTurns(8)` rather than the SDK's default of `1`.

## Setup

1. Install Go 1.23+:
   ```bash
   go version
   ```

2. Clone or create from template:
   ```bash
   agnt5 create --template go/travel_booking_customer_service my-travel-agent
   cd my-travel-agent
   ```

3. Download dependencies:
   ```bash
   go mod download
   ```

4. Set up environment variables:
   ```bash
   cat > .env << EOF
   OPENAI_API_KEY=your_openai_api_key_here
   SERPAPI_KEY=your_serpapi_key_here
   EOF
   ```

   Get a SerpAPI key at: https://serpapi.com (free tier available)

5. Start the AGNT5 dev server:
   ```bash
   agnt5 dev
   ```
