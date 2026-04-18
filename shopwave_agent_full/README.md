# ShopWave Support Agent

A full-stack AI customer support agent for the ShopWave e-commerce scenario. The LLM (Claude) autonomously decides which tools to call, in what order, to resolve each support ticket end-to-end.

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| AI orchestration | LangGraph 1.1.7 (ReAct loop) |
| LLM | Anthropic Claude via `langchain-anthropic` 1.4.1 |
| Tools | 10 LangChain `@tool` decorated functions |
| Frontend | React + Vite + TypeScript |
| Checkpointing | LangGraph `MemorySaver` |

## Architecture

The agent uses a **LLM-driven ReAct loop** — Claude receives all tool schemas via `bind_tools()` and autonomously decides which tools to call and in what order.

```
START
  │
  ▼
agent  ──(has tool_calls)──▶  tools  ──▶  agent  ──▶ ...
  │                                                     │
  └──────(no tool_calls)─────────────────▶  finalize
                                                │
                                               END
```

- **`agent` node** — invokes Claude with all 10 tools bound; LLM decides next action
- **`tools` node** — LangGraph `ToolNode` executes the tool calls the LLM requested
- **`finalize` node** — parses message history into structured state fields for the frontend

## Available tools

| Tool | Description |
|---|---|
| `get_ticket` | Load a support ticket by ID |
| `get_customer` | Look up customer record by email |
| `get_customer_orders` | All orders for a customer |
| `get_order` | Load a specific order by ID |
| `get_product` | Load product details |
| `search_knowledge_base` | Keyword search across policy docs |
| `check_refund_eligibility` | Determine if an order qualifies for refund |
| `issue_refund` | Process a refund |
| `escalate` | Route ticket to human support queue |
| `send_reply` | Send reply to the customer |

## Policy constraints enforced

- `issue_refund` is only called after `check_refund_eligibility` confirms eligibility
- Warranty and replacement requests are escalated to a human specialist
- High-value orders (> $200) are escalated
- Claimed tier/VIP status is verified against the customer record
- Missing order details trigger a clarification reply

## Project structure

```
app/
  main.py          FastAPI app — /health, /tickets, /run endpoints
  graph.py         LangGraph StateGraph definition
  nodes.py         agent_node, tool_node, should_continue, finalize_node
  tools.py         10 @tool decorated functions
  models.py        get_llm() — returns ChatAnthropic instance
  state.py         AgentState TypedDict
  logic.py         Business logic helpers
  sample_data/     customers.json, orders.json, products.json, tickets.json, knowledge-base.md
frontend/
  src/App.tsx      React UI — ticket selector, status banner, result cards, tool trace timeline
  src/styles.css   Dark theme styles
```

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Anthropic API key — get one at [console.anthropic.com](https://console.anthropic.com)

### Backend

```bash
# Windows
py -3.11 -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3.11 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

Create `.env` in the project root:

```env
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL_ID=claude-sonnet-4-5
```

Start the server:

```bash
# Windows
py -3.11 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# macOS / Linux
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The frontend calls `http://127.0.0.1:8000`.

## API

### `GET /health`
```json
{ "status": "ok" }
```

### `GET /tickets`
Returns the list of all sample tickets.

### `POST /run`
```json
{ "ticket_id": "TKT-001" }
```

Returns the full `AgentState` on success, or a structured error response on failure.

**Error responses:**

| Status | Cause |
|---|---|
| 401 | Invalid `ANTHROPIC_API_KEY` |
| 404 | Ticket ID not found |
| 429 | Anthropic rate limit exceeded |
| 503 | Cannot reach Anthropic API |
| 502 | Anthropic returned an API error |
| 500 | Unexpected internal error |

## Suggested next upgrades

- Replace keyword KB search with vector/semantic search
- Add streaming SSE updates from LangGraph to the UI
- Persist checkpoints in Redis or Postgres instead of in-memory
- Add a supervisor review queue and audit log
- Add a test suite covering all ticket scenarios
