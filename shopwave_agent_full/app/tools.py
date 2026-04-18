import json
from pathlib import Path
from typing import Any, Dict, List

from langchain_core.tools import tool

BASE = Path(__file__).parent / "sample_data"


def _load_json(name: str) -> List[Dict[str, Any]]:
    with open(BASE / name, "r", encoding="utf-8") as f:
        return json.load(f)


CUSTOMERS = _load_json("customers.json")
ORDERS = _load_json("orders.json")
PRODUCTS = _load_json("products.json")
TICKETS = _load_json("tickets.json")
KB = (BASE / "knowledge-base.md").read_text(encoding="utf-8")


class RefundEligibilityError(Exception):
    pass


@tool
def get_ticket(ticket_id: str) -> Dict[str, Any]:
    """Retrieve a support ticket by its ticket ID."""
    for ticket in TICKETS:
        if ticket["ticket_id"] == ticket_id:
            return ticket
    raise ValueError(f"Ticket not found: {ticket_id}")


@tool
def get_customer(email: str) -> Dict[str, Any]:
    """Retrieve a customer record by their email address."""
    for customer in CUSTOMERS:
        if customer["email"].lower() == email.lower():
            return customer
    raise ValueError(f"Customer not found for email: {email}")


@tool
def get_order(order_id: str) -> Dict[str, Any]:
    """Retrieve an order record by its order ID."""
    for order in ORDERS:
        if order["order_id"] == order_id:
            return order
    raise ValueError(f"Order not found: {order_id}")


@tool
def get_customer_orders(email: str) -> List[Dict[str, Any]]:
    """Get all orders placed by a customer identified by their email address."""
    customer = get_customer.invoke({"email": email})
    return [o for o in ORDERS if o["customer_id"] == customer["customer_id"]]


@tool
def get_product(product_id: str) -> Dict[str, Any]:
    """Retrieve a product record by its product ID."""
    for product in PRODUCTS:
        if product["product_id"] == product_id:
            return product
    raise ValueError(f"Product not found: {product_id}")


@tool
def search_knowledge_base(query: str) -> List[Dict[str, Any]]:
    """Search the support knowledge base for policy excerpts relevant to the query."""
    sections = KB.split("## ")
    q = query.lower()
    matches: List[Dict[str, Any]] = []
    for sec in sections:
        if q in sec.lower():
            matches.append({"excerpt": sec[:1200].strip()})

    if not matches:
        keywords = q.split()
        for sec in sections:
            score = sum(1 for kw in keywords if kw in sec.lower())
            if score:
                matches.append({"excerpt": sec[:1200].strip(), "score": score})
        matches.sort(key=lambda x: x.get("score", 0), reverse=True)

    return matches[:3] if matches else [{"excerpt": KB[:1200]}]


@tool
def check_refund_eligibility(order_id: str) -> Dict[str, Any]:
    """Check whether an order is eligible for a refund based on its status and product return policy."""
    order = get_order.invoke({"order_id": order_id})
    product = get_product.invoke({"product_id": order["product_id"]})

    if order.get("refund_status") == "processed":
        return {
            "eligible": False,
            "reason": "Refund already processed",
            "amount": 0.0,
        }

    if order["status"] == "processing":
        return {
            "eligible": True,
            "reason": "Order is still processing and can be cancelled before shipment",
            "amount": float(order["amount"]),
        }

    if order["status"] == "delivered":
        if product["returnable"]:
            return {
                "eligible": True,
                "reason": "Delivered order is potentially refundable subject to policy review",
                "amount": float(order["amount"]),
            }
        return {
            "eligible": False,
            "reason": "Product is marked non-returnable",
            "amount": 0.0,
        }

    if order["status"] == "shipped":
        return {
            "eligible": False,
            "reason": "Shipped orders cannot be cancelled; customer must wait for delivery",
            "amount": 0.0,
        }

    raise RefundEligibilityError(f"Unhandled order status: {order['status']}")


@tool
def issue_refund(order_id: str, amount: float) -> Dict[str, Any]:
    """Issue a refund for the given order ID and amount to the original payment method."""
    return {
        "success": True,
        "refund_id": f"RF-{order_id}",
        "order_id": order_id,
        "amount": amount,
        "message": "Refund issued to the original payment method.",
    }


@tool
def send_reply(ticket_id: str, message: str) -> Dict[str, Any]:
    """Send a reply message to the customer for the specified support ticket."""
    return {
        "success": True,
        "ticket_id": ticket_id,
        "message": message,
    }


@tool
def escalate(ticket_id: str, summary: str, priority: str) -> Dict[str, Any]:
    """Escalate a support ticket to the human support queue with a case summary and priority level."""
    return {
        "success": True,
        "ticket_id": ticket_id,
        "summary": summary,
        "priority": priority,
        "queue": "human_support",
    }
