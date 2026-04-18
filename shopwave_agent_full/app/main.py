import logging
import uuid

import anthropic
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .graph import build_graph
from .tools import TICKETS

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("shopwave")

app = FastAPI(title="ShopWave LangGraph Agent", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

graph = build_graph()


# --------------------------------------------------------------------------- #
# Exception handlers                                                           #
# --------------------------------------------------------------------------- #

@app.exception_handler(anthropic.AuthenticationError)
async def handle_auth_error(request: Request, exc: anthropic.AuthenticationError):
    logger.error("[API] Anthropic auth error: %s", exc)
    return JSONResponse(status_code=401, content={"error": "Invalid API key", "detail": str(exc)})


@app.exception_handler(anthropic.RateLimitError)
async def handle_rate_limit(request: Request, exc: anthropic.RateLimitError):
    logger.warning("[API] Rate limit exceeded: %s", exc)
    return JSONResponse(status_code=429, content={"error": "Rate limit exceeded", "detail": "Please retry after a short delay."})


@app.exception_handler(anthropic.APIConnectionError)
async def handle_connection_error(request: Request, exc: anthropic.APIConnectionError):
    logger.error("[API] Anthropic connection error: %s", exc)
    return JSONResponse(status_code=503, content={"error": "AI service unavailable", "detail": "Cannot reach the Anthropic API."})


class RunRequest(BaseModel):
    ticket_id: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/tickets")
def list_tickets():
    return {"tickets": TICKETS}


@app.post("/run")
def run_agent(req: RunRequest):
    request_id = str(uuid.uuid4())[:8]
    logger.info("[RUN:%s] ticket_id=%s", request_id, req.ticket_id)
    ticket_ids = {t["ticket_id"] for t in TICKETS}
    if req.ticket_id not in ticket_ids:
        logger.warning("[RUN:%s] Ticket not found: %s", request_id, req.ticket_id)
        raise HTTPException(status_code=404, detail=f"Ticket '{req.ticket_id}' not found")

    # Use a unique thread_id per invocation so MemorySaver never replays a
    # previous run's message history into this fresh request.
    config = {"configurable": {"thread_id": str(uuid.uuid4())}, "recursion_limit": 30}
    try:
        result = graph.invoke({"ticket_id": req.ticket_id, "tool_trace": []}, config=config)
        status = result.get("final_status", "unknown")
        logger.info("[RUN:%s] Completed — intent=%s final_status=%s", request_id, result.get("intent"), status)
        if status == "error":
            # Agent returned a controlled error state — surface it as 500 with detail
            return JSONResponse(
                status_code=500,
                content={"error": result.get("draft_reply", "Agent encountered an error"), "request_id": request_id},
            )
        return result
    except anthropic.AuthenticationError as exc:
        logger.error("[RUN:%s] Auth error: %s", request_id, exc)
        raise HTTPException(status_code=401, detail="Invalid Anthropic API key")
    except anthropic.RateLimitError as exc:
        logger.warning("[RUN:%s] Rate limit: %s", request_id, exc)
        raise HTTPException(status_code=429, detail="Rate limit exceeded — please retry shortly")
    except anthropic.APIConnectionError as exc:
        logger.error("[RUN:%s] Connection error: %s", request_id, exc)
        raise HTTPException(status_code=503, detail="Could not reach the AI service")
    except anthropic.APIStatusError as exc:
        logger.error("[RUN:%s] Anthropic API status=%d: %s", request_id, exc.status_code, exc.message)
        raise HTTPException(status_code=502, detail=f"AI service error ({exc.status_code})")
    except Exception as exc:
        logger.exception("[RUN:%s] Unexpected error: %s", request_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error — see server logs")
