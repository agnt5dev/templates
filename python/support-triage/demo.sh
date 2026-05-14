#!/bin/bash
# Support Triage Demo - AGNT5 Killer Quickstart
#
# This script demonstrates AGNT5's unique capabilities:
# 1. Crash-resume: Kill server mid-run, restart, continues from exact step
# 2. Human-in-the-loop: Durable pauses for approval that survive restarts
# 3. Exactly-once: No duplicate side effects after recovery
#
# Usage:
#   ./demo.sh           Run the full demo
#   ./demo.sh chaos     Demo with simulated crash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          AGNT5 Support Triage Demo                            ║${NC}"
echo -e "${BLUE}║          Crash-Resume • HITL • Exactly-Once                   ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if AGNT5 CLI is available
if ! command -v agnt5 &> /dev/null; then
    echo -e "${RED}Error: agnt5 CLI not found.${NC}"
    echo "Please install AGNT5 first: pip install agnt5-cli"
    exit 1
fi

# Step 1: Start dev server
echo -e "${GREEN}1️⃣  Starting AGNT5 dev server...${NC}"
echo ""

# Check if dev server is already running
if curl -s http://localhost:34183/health > /dev/null 2>&1; then
    echo -e "${YELLOW}   Dev server already running.${NC}"
else
    echo "   Run: agnt5 dev up"
    echo ""
    echo -e "${YELLOW}   (In a separate terminal, or use 'agnt5 dev up --background')${NC}"
    echo ""
    read -p "   Press Enter when dev server is ready..."
fi

echo ""

# Step 2: Install dependencies (if needed)
if [ ! -d ".venv" ]; then
    echo -e "${GREEN}2️⃣  Setting up environment...${NC}"
    python -m venv .venv
    source .venv/bin/activate
    pip install -e . -q
    echo "   Dependencies installed."
else
    source .venv/bin/activate
fi

echo ""

# Step 3: Start the worker
echo -e "${GREEN}3️⃣  Starting support-triage worker...${NC}"
echo "   Run: python app.py"
echo ""

# Start worker in background for demo
python app.py &
WORKER_PID=$!
echo "   Worker PID: $WORKER_PID"
sleep 2

echo ""

# Step 4: Submit a ticket
echo -e "${GREEN}4️⃣  Submitting a support ticket...${NC}"
echo ""

TICKET='{"ticket_id":"TCK-1001","subject":"Need a refund","body":"I upgraded by mistake and would like my money back please."}'

echo "   Ticket: $TICKET"
echo ""

RESPONSE=$(curl -s -X POST http://localhost:34183/api/v1/workflows/support_triage/runs \
    -H "Content-Type: application/json" \
    -d "$TICKET")

RUN_ID=$(echo $RESPONSE | jq -r '.run_id // .id // empty' 2>/dev/null || echo "")

if [ -z "$RUN_ID" ]; then
    echo -e "${RED}   Error submitting ticket. Response: $RESPONSE${NC}"
    kill $WORKER_PID 2>/dev/null || true
    exit 1
fi

echo -e "${GREEN}   Run ID: $RUN_ID${NC}"
echo ""

# Step 5: Show Dev Studio link
echo -e "${GREEN}5️⃣  Watch progress in Dev Studio:${NC}"
echo ""
echo -e "   ${BLUE}http://localhost:3000/runs/$RUN_ID${NC}"
echo ""

# Step 6: Demo instructions
echo -e "${GREEN}6️⃣  The Magic Moments:${NC}"
echo ""
echo "   📌 CRASH-RESUME:"
echo "      Kill the worker now (Ctrl+C), then restart with 'python app.py'"
echo "      The workflow continues from the EXACT step it was on!"
echo ""
echo "   ⏸️  HUMAN-IN-THE-LOOP:"
echo "      When the workflow pauses for approval, close your laptop."
echo "      Come back hours later - the approval is still waiting!"
echo ""
echo "   ✅ EXACTLY-ONCE:"
echo "      Check .agnt5_demo/replies.log after approval."
echo "      No matter how many crashes, there's exactly ONE reply posted."
echo ""

# Wait for user
echo -e "${YELLOW}Press Ctrl+C to stop the demo.${NC}"
echo ""

# Keep running
wait $WORKER_PID
