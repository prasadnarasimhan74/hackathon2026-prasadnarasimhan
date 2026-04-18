# ShopWave Agent — Failure Modes & Mitigations

This document describes how the ShopWave agent detects, handles, and communicates the six primary failure scenarios that can occur during a support-ticket processing run.

---

## Failure Mode 1 — Invalid or Expired API Key

| Attribute | Detail |
|-----------|--------|
| **Scenario** | The `ANTHROPIC_API_KEY` in `.env` is missing, incorrect, or has been revoked. |
| **Trigger** | Every call to `agent_node` invokes `llm.invoke(messages)`, which immediately raises `anthropic.AuthenticationError` if the key is bad. |
| **Detection** | `agent_node` wraps the LLM call in a `try/except` that explicitly catches `anthropic.AuthenticationError`. |
| **System Response** | The node logs `ERROR: Anthropic authentication failed — check ANTHROPIC_API_KEY` and sets `state["final_status"] = "error"`. `should_continue` sees `final_status == "error"` and routes straight to `finalize`. `finalize_node` propagates the error status. `main.py` catches `anthropic.AuthenticationError` and returns **HTTP 401** with a JSON body containing the `request_id` and a safe error message (the raw key is never exposed). |
| **User-visible behaviour** | The React frontend receives HTTP 401, displays a red "Authentication error" banner, and suggests checking the API key configuration. No partial data is shown. |
| **Log output** | `ERROR [agent_node] Anthropic authentication failed — check ANTHROPIC_API_KEY` |

---

## Failure Mode 2 — Rate Limit / Quota Exhaustion

| Attribute | Detail |
|-----------|--------|
| **Scenario** | The Anthropic API rejects requests because the account has hit its requests-per-minute or token-per-day quota. |
| **Trigger** | `anthropic.RateLimitError` is raised by the Anthropic client inside `agent_node`. |
| **Detection** | The `except anthropic.RateLimitError` branch in `agent_node`. |
| **System Response** | The node logs `WARNING: Anthropic rate limit hit`, appends a user-facing `AIMessage` ("I'm temporarily unavailable due to high demand. Please retry in a moment."), and sets `final_status = "error"`. `main.py` returns **HTTP 429** with `Retry-After: 60` in the response header so clients know when to retry. |
| **User-visible behaviour** | The frontend shows a yellow "Rate limited" banner with a "retry in 60 s" suggestion. The ticket is not modified; no tools were invoked. |
| **Log output** | `WARNING [agent_node] Anthropic rate limit hit — request_id=<id>` |

---

## Failure Mode 3 — Tool Execution Error (Missing Data / Invalid Input)

| Attribute | Detail |
|-----------|--------|
| **Scenario** | A tool (e.g. `get_ticket`, `get_order`) is called with an ID that does not exist in the sample data, or an internal `ValueError` / `KeyError` is raised inside the tool function. |
| **Trigger** | Any `Exception` raised inside a `@tool` function while `ToolNode` is executing. |
| **Detection** | `ToolNode(handle_tool_errors=True)` catches the exception automatically and returns a `ToolMessage` whose `content` begins with `"Error: ..."`. `finalize_node` checks every `ToolMessage`; if `content.startswith("Error:")` it sets that entry's `"error"` key in `tool_trace` and excludes it from `tool_result_map`. |
| **System Response** | The failed tool result is excluded from the final state fields (e.g. `ticket`, `order`). A `WARNING` is logged identifying which tool failed and with what message. The LLM can continue the loop — it sees the error `ToolMessage` in its history and may attempt recovery (calling the tool again with corrected parameters or choosing a different action). |
| **User-visible behaviour** | The frontend's tool trace timeline shows the failed call in red with the error text. Fields that depend on the failed tool appear as "N/A" — no crash, no silent wrong data. |
| **Log output** | `WARNING [finalize_node] Tool error in <tool_name>: Error: Ticket TKT-404 not found` |

---

## Failure Mode 4 — Network / Connectivity Failure

| Attribute | Detail |
|-----------|--------|
| **Scenario** | The host running the agent cannot reach `api.anthropic.com` — DNS failure, firewall block, or temporary outage. |
| **Trigger** | `anthropic.APIConnectionError` raised when the HTTP client cannot establish a connection. |
| **Detection** | `except anthropic.APIConnectionError` in `agent_node`. |
| **System Response** | Logs `ERROR: Cannot reach Anthropic API`, sets `final_status = "error"`. `main.py` catches the same exception class and returns **HTTP 503 Service Unavailable**. The ticket's JSON files were never modified (all write operations go through `issue_refund` / `escalate` tools which were not reached). |
| **User-visible behaviour** | Frontend shows "Service unavailable — please check your connection and retry." No data loss occurs because no write tools ran. |
| **Log output** | `ERROR [agent_node] Cannot reach Anthropic API — APIConnectionError` |

---

## Failure Mode 5 — Infinite Tool-Call Loop / Runaway Recursion

| Attribute | Detail |
|-----------|--------|
| **Scenario** | The LLM enters a pathological state and keeps requesting tool calls indefinitely (e.g. re-calling `search_knowledge_base` in a tight loop). |
| **Trigger** | LangGraph's recursion counter reaches the configured ceiling. |
| **Detection** | `graph.invoke(state, config={"recursion_limit": 30})` in `logic.py`. LangGraph raises `langgraph.errors.GraphRecursionError` once 30 node activations are exceeded. |
| **System Response** | `main.py` catches `GraphRecursionError` in its generic `Exception` handler, logs `ERROR: Graph recursion limit reached`, and returns **HTTP 500** with a descriptive message. The hard cap of 30 steps means at most 14 full `agent → tools` cycles — sufficient for any legitimate ticket, far below infinite. |
| **User-visible behaviour** | Frontend shows "Processing error" banner with request ID for support tracing. The agent stops immediately; no further API spend is incurred. |
| **Log output** | `ERROR [main] Graph recursion limit reached — request_id=<id>` |

---

## Failure Mode 6 — Retired or Unknown Model ID

| Attribute | Detail |
|-----------|--------|
| **Scenario** | `ANTHROPIC_MODEL_ID` in `.env` is set to an invalid string or a model that has been retired by Anthropic (e.g. the old `claude-3-5-sonnet-20240620` cross-region inference profile that triggered the original `ResourceNotFoundException`). |
| **Trigger** | `anthropic.APIStatusError` (HTTP 4xx/5xx from the Anthropic platform) raised on the first `llm.invoke()` call in `agent_node`. |
| **Detection** | `except anthropic.APIStatusError as e` in `agent_node`; also handled globally by `@app.exception_handler(anthropic.APIError)` in `main.py`. |
| **System Response** | `agent_node` logs `ERROR: Anthropic API error status=<code> message=<msg>` and sets `final_status = "error"`. `main.py`'s exception handler returns **HTTP 502 Bad Gateway** — the upstream model service is the faulty party, not the client. The response body includes the full `status_code` and `message` fields from the Anthropic error so operators can diagnose quickly without reading logs. |
| **User-visible behaviour** | Frontend shows "Upstream API error (502)" with the model ID surfaced in the developer console. The fix — updating `ANTHROPIC_MODEL_ID` in `.env` and restarting the server — is unambiguous. |
| **Log output** | `ERROR [agent_node] Anthropic API error status=404 message=model not found` |

---

## Summary Table

| # | Failure | Exception Class | HTTP Status | Handled In |
|---|---------|-----------------|-------------|------------|
| 1 | Invalid/expired API key | `AuthenticationError` | 401 | `agent_node` + `main.py` |
| 2 | Rate limit / quota | `RateLimitError` | 429 | `agent_node` + `main.py` |
| 3 | Tool returns error | `Exception` (in tool) | — (LLM sees it) | `ToolNode` + `finalize_node` |
| 4 | Network failure | `APIConnectionError` | 503 | `agent_node` + `main.py` |
| 5 | Infinite tool loop | `GraphRecursionError` | 500 | LangGraph + `main.py` |
| 6 | Retired/invalid model | `APIStatusError` | 502 | `agent_node` + `main.py` |

---

## Design Principles

1. **No silent failures** — every exception is caught, logged with a severity level, and surfaces a distinct HTTP status code so monitoring tools can alert on specific error categories.
2. **State immutability on failure** — write-action tools (`issue_refund`, `send_reply`, `escalate`) are placed at the end of the LLM's plan. Network or auth failures before those tools execute leave ticket data unchanged.
3. **Request traceability** — a short `request_id` is generated per-request in `main.py` and included in every log line and error response body, enabling correlation without exposing internal secrets.
4. **Graceful degradation** — tool-level errors (Failure Mode 3) do not abort the entire run; the LLM can observe the error and attempt recovery or produce a partial response rather than a complete crash.
