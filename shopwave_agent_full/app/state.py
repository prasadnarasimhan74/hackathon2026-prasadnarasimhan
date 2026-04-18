from typing import Annotated, Any, Dict, List, Literal, Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    ticket_id: str
    ticket: Dict[str, Any]
    customer_email: str
    extracted_order_id: Optional[str]
    intent: Optional[str]
    kb_query: Optional[str]
    customer: Optional[Dict[str, Any]]
    order: Optional[Dict[str, Any]]
    product: Optional[Dict[str, Any]]
    kb_results: List[Dict[str, Any]]
    eligibility: Optional[Dict[str, Any]]
    missing_fields: List[str]
    risk_flags: List[str]
    decision: Optional[Dict[str, Any]]
    draft_reply: Optional[str]
    escalation_summary: Optional[str]
    escalation_priority: Optional[Literal["low", "medium", "high", "urgent"]]
    tool_trace: List[Dict[str, Any]]
    final_status: Optional[str]
    messages: Annotated[List[BaseMessage], add_messages]
