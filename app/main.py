import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from app.config import settings
from app.gateway import ResilientStreamRouter
from app.limiter import DragonflyTokenBucket

# Structural logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("gateway.main")

router_engine: ResilientStreamRouter = None # type: ignore
limiter_engine: DragonflyTokenBucket = None # type: ignore

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages system resource lifecycles during server initialization and shutdown."""
    global router_engine, limiter_engine
    logger.info("Initializing high-performance resource hooks...")
    router_engine = ResilientStreamRouter()
    limiter_engine = DragonflyTokenBucket()
    yield
    logger.info("Gracefully tearing down active resource connections...")
    await router_engine.close()

app = FastAPI(title="Enterprise AI Gateway MVP", lifespan=lifespan)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Uncaught proxy tracking anomaly hit: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal Gateway Transport Error", "message": str(exc)}
    )

@app.post("/v1/chat/completions")
async def handle_chat_completions(request: Request):
    """Unified API routing abstraction logic layer."""
    # Extract structural tenant context identifiers
    tenant_id = request.headers.get("X-Tenant-ID", "anonymous-default")
    
    # Evaluate Rate Limiting constraints (e.g., Max Capacity: 100 requests, Refill: 2 units/sec)
    is_limited = await limiter_engine.is_rate_limited(
        identifier=tenant_id, max_tokens=100, refill_rate=2.0
    )
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, 
            detail="Gateway rate limit exceeded. Verify usage metrics parameters."
        )

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed JSON request payload structure.")

    # Guardrails stage injection hook
    # TODO: Insert synchronous PII masking regex evaluation engine pipelines here

    return await router_engine.route_chat(payload)
