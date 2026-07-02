# Travel Booking Assistant — AGNT5 TypeScript Template

A conversational travel agent that searches real flights and hotels, builds itineraries, and remembers every detail across a multi-turn chat session.

## What it does

- **Search flights and hotels** in real time using SerpAPI (Google Flights / Hotels data).
- **Build complete itineraries** with day-by-day plans, cost estimates, and recommendations.
- **Maintain conversation context** across turns — the agent never asks for information you've already given.

## Key concepts

- **Single agent with tools** — One context-aware agent orchestrates three tools: `search_flights`, `search_hotels`, and `create_itinerary`.
- **Multi-turn chat** — The agent builds context incrementally across messages within a session.

## Setup

1. Install Node.js 22+:
   ```bash
   node --version
   ```

2. Clone or create from template:
   ```bash
   agnt5 create --template travel-booking my-travel-agent
   cd my-travel-agent
   ```

3. Install dependencies:
   ```bash
   npm install
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
