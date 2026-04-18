import json
import logging
from typing import Any, Dict, List

import anthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.prebuilt import ToolNode

from .models import get_llm
from .tools import (
    check_refund_eligibility,
    escalate,
    get_customer,
    get_customer_orders,
    get_order,
    get_product,
    get_ticket,
    issue_refund,
    search_knowledge_base,
    send_reply,
)

logger = logging.getLogger("shopwave")

# --------------------------------------------------------------------------- #
# Tool registry                                                                #
# --------------------------------------------------------------------------- #

ALL_TOOLS = [
    get_ticket,
    get_customer,
    get_customer_orders,
    get_order,
    get_product,
    search_knowledge_base,
    check_refund_eligibility,
    issue_refund,
    escalate,
    send_reply,
]

tool_node = ToolNode(ALL_TOOLS, handle_tool_errors=True)

# --------------------------------------------------------------------------- #
# System prompt                                                                #
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = """\
You are ShopWave's AI customer support agent. Resolve support tickets using the
tools available. Follow this exact process:

1. Call get_ticket to load the ticket.
2. Call get_customer with the customer_email from the ticket.
3. If the ticket mentions an order ID (format ORD-XXXX), call get_order.
   Otherwise call get_customer_orders to find the relevant order.
4. Call get_product with the product_id from the order.
5. Call search_knowledge_base with a query relevant to the issue (e.g.
   "refund policy", "warranty policy", "return policy").
6. If the issue involves a refund or return, call check_refund_eligibility with:
   - order_id: the order ID
   - as_of_date: the ticket's created_at date in YYYY-MM-DD format (e.g. "2024-03-15").
     This ensures the return window is evaluated as of when the customer reported the
     issue, not today.
7. Decide on the final action:
   - check_refund_eligibility returns eligible: true → call issue_refund, then
     call send_reply confirming the refund.
   - check_refund_eligibility returns escalate_reason: "warranty_claim" → the
     return window is expired but warranty is active. Check the ticket body:
       * If the customer describes a defect, malfunction, or damage → escalate
         as a warranty claim.
       * If the customer just dislikes the product (no defect mentioned) → reply
         that the return window is closed and no refund is available; do NOT issue
         a refund or escalate.
   - Needs human review (replacement, high-value order > $200, fraud risk, or
     eligibility tool error) → call escalate, then call send_reply informing the
     customer that a specialist will follow up.
   - Otherwise â†’ call send_reply with a helpful resolution.

Rules:
- Always call send_reply as the LAST action â€” this marks the ticket as handled.
- Use the customer's first name in the reply.
- Be concise and empathetic.
- DO NOT invent data that is not returned by a tool.
- When calling escalate, write a clear case summary as the `summary` argument.
"""

# --------------------------------------------------------------------------- #
# Agent node                                                                   #
# --------------------------------------------------------------------------- #


def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke the Anthropic LLM with bound tools; it decides what to call next."""
    messages = state.get("messages") or []

    # First turn: seed the conversation with system prompt + initial request
    if not messages:
        ticket_id = state["ticket_id"]
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"Please resolve support ticket: {ticket_id}"),
        ]
        logger.debug("[AGENT] First turn â€” ticket_id=%s", ticket_id)

    llm = get_llm()
    if llm is None:
        logger.error("[AGENT] Anthropic LLM unavailable — check ANTHROPIC_API_KEY and ANTHROPIC_MODEL_ID")
        return {
            "messages": messages,
            "final_status": "error",
            "draft_reply": "LLM unavailable â€” cannot process ticket.",
        }

    llm_with_tools = llm.bind_tools(ALL_TOOLS)
    logger.debug("[AGENT] Invoking LLM â€” message count=%d", len(messages))
    try:
        response = llm_with_tools.invoke(messages)
    except anthropic.AuthenticationError as exc:
        logger.error("[AGENT] Authentication failed — check ANTHROPIC_API_KEY: %s", exc)
        return {
            "messages": messages,
            "final_status": "error",
            "draft_reply": "Authentication error — API key is invalid or missing.",
        }
    except anthropic.RateLimitError as exc:
        logger.warning("[AGENT] Rate limit hit: %s", exc)
        return {
            "messages": messages,
            "final_status": "error",
            "draft_reply": "Service temporarily busy — please retry in a moment.",
        }
    except anthropic.APIConnectionError as exc:
        logger.error("[AGENT] Network error reaching Anthropic API: %s", exc)
        return {
            "messages": messages,
            "final_status": "error",
            "draft_reply": "Could not reach the AI service — please check connectivity.",
        }
    except anthropic.APIStatusError as exc:
        logger.error("[AGENT] Anthropic API error status=%d body=%s", exc.status_code, exc.message)
        return {
            "messages": messages,
            "final_status": "error",
            "draft_reply": f"AI service returned an error ({exc.status_code}) — please retry.",
        }
    except Exception as exc:
        logger.exception("[AGENT] Unexpected LLM error: %s", exc)
        return {
            "messages": messages,
            "final_status": "error",
            "draft_reply": "An unexpected error occurred while processing the ticket.",
        }
    logger.debug(
        "[AGENT] LLM response â€” has_tool_calls=%s content_preview=%s",
        bool(getattr(response, "tool_calls", None)),
        str(getattr(response, "content", ""))[:120],
    )
    return {"messages": [response]}


# --------------------------------------------------------------------------- #
# Routing                                                                      #
# --------------------------------------------------------------------------- #


def should_continue(state: Dict[str, Any]) -> str:
    """Route to 'tools' if the LLM made tool calls, otherwise 'finalize'."""
    # Always finalize on error state
    if state.get("final_status") == "error":
        logger.debug("[ROUTE] → finalize (error state)")
        return "finalize"
    messages = state.get("messages") or []
    last = messages[-1] if messages else None
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        logger.debug("[ROUTE] â†’ tools (%d tool calls)", len(last.tool_calls))
        return "tools"
    logger.debug("[ROUTE] â†’ finalize")
    return "finalize"


# --------------------------------------------------------------------------- #
# Finalize node â€” parse message history into structured state for frontend     #
# --------------------------------------------------------------------------- #


def finalize_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Walk message history and populate structured state fields."""
    messages = state.get("messages") or []

    # Build tool_call_id â†’ tool_name mapping
    tc_id_to_name: Dict[str, str] = {}
    tool_trace: List[Dict[str, Any]] = []

    for msg in messages:
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                tc_id_to_name[tc["id"]] = tc["name"]
                tool_trace.append({"tool": tc["name"], "input": tc["args"]})

    # Collect tool results keyed by tool name (last call wins for duplicates)
    # ToolNode with handle_tool_errors=True returns errors as plain strings.
    tool_result_map: Dict[str, Any] = {}
    for msg in messages:
        if isinstance(msg, ToolMessage):
            name = tc_id_to_name.get(msg.tool_call_id, getattr(msg, "name", ""))
            if not name:
                continue
            content = msg.content
            is_error = isinstance(content, str) and content.startswith("Error")
            if is_error:
                logger.warning("[FINALIZE] Tool '%s' returned an error: %s", name, content[:200])
                # Mark the trace entry as failed
                for entry in tool_trace:
                    if entry["tool"] == name and "error" not in entry:
                        entry["error"] = content[:200]
                        break
                continue  # do not store error payloads as valid results
            try:
                parsed = json.loads(content) if isinstance(content, str) else content
            except (json.JSONDecodeError, TypeError):
                parsed = content
            tool_result_map[name] = parsed

    updates: Dict[str, Any] = {"tool_trace": tool_trace}

    # ---- Structured fields ------------------------------------------------ #

    ticket = tool_result_map.get("get_ticket") or state.get("ticket") or {}
    if isinstance(ticket, dict) and ticket:
        updates["ticket"] = ticket
        updates["customer_email"] = ticket.get("customer_email", "")

    customer = tool_result_map.get("get_customer")
    if isinstance(customer, dict):
        updates["customer"] = customer

    order = tool_result_map.get("get_order")
    if not isinstance(order, dict):
        orders = tool_result_map.get("get_customer_orders")
        if isinstance(orders, list) and orders:
            order = orders[0]
    if isinstance(order, dict):
        updates["order"] = order

    product = tool_result_map.get("get_product")
    if isinstance(product, dict):
        updates["product"] = product

    kb = tool_result_map.get("search_knowledge_base")
    if kb is not None:
        updates["kb_results"] = kb if isinstance(kb, list) else [{"excerpt": str(kb)}]

    eligibility = tool_result_map.get("check_refund_eligibility")
    if isinstance(eligibility, dict):
        updates["eligibility"] = eligibility

    # ---- Final status & decision ------------------------------------------ #

    if "issue_refund" in tool_result_map:
        updates["final_status"] = "refunded"
        updates["decision"] = {"action": "refund", "reason": "Refund issued by agent"}
    elif "escalate" in tool_result_map:
        updates["final_status"] = "escalated"
        esc = tool_result_map["escalate"]
        updates["escalation_summary"] = esc.get("summary", "") if isinstance(esc, dict) else ""
        updates["escalation_priority"] = esc.get("priority", "high") if isinstance(esc, dict) else "high"
        updates["decision"] = {"action": "escalate", "reason": "Escalated by agent"}
    else:
        updates["final_status"] = "replied"
        updates["decision"] = {"action": "reply", "reason": "Replied by agent"}

    # ---- Draft reply ------------------------------------------------------- #

    sr = tool_result_map.get("send_reply")
    if isinstance(sr, dict) and sr.get("message"):
        updates["draft_reply"] = sr["message"]
    else:
        # Fall back to last non-empty AI text content
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and isinstance(msg.content, str) and msg.content.strip():
                updates["draft_reply"] = msg.content.strip()
                break

    # ---- Intent (heuristic from ticket text) ------------------------------ #

    text = (
        f"{ticket.get('subject', '')} {ticket.get('body', '')}"
        if isinstance(ticket, dict)
        else ""
    ).lower()
    intent_map = [
        ("refund", "refund"),
        ("return", "return"),
        ("warranty", "warranty"),
        ("cancel", "cancellation"),
        ("replacement", "replacement"),
        ("tracking", "order_status"),
        ("status", "order_status"),
    ]
    updates["intent"] = next(
        (mapped for kw, mapped in intent_map if kw in text),
        "support",
    )

    logger.debug(
        "[FINALIZE] final_status=%s intent=%s draft_reply_len=%d tools_called=%s",
        updates.get("final_status"),
        updates.get("intent"),
        len(updates.get("draft_reply") or ""),
        [t["tool"] for t in tool_trace],
    )
    return updates
