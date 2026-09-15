"""FastAPI server with REST API and WebSocket endpoints."""

from __future__ import annotations

import asyncio
import time
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from mercatus.db.database import Database, db
from mercatus.db.migrations import init_schema, seed_knowledge
from mercatus.models.llm import llm_client
from mercatus.models.config import get_settings
from mercatus.server.websocket import ws_manager, WebSocketHandler
from mercatus.utils.logger import get_logger
from mercatus.utils.security import sanitize_input, validate_module, generate_session_id

# Import new modules
from mercatus.monitor.system import system_monitor
from mercatus.monitor.metrics import metrics_tracker
from mercatus.integrations.webhooks import webhook_manager
from mercatus.integrations.api_keys import api_key_manager
from mercatus.integrations.connectors import connector_manager
from mercatus.integrations.oauth import oauth_manager
from mercatus.training.feedback import feedback_manager
from mercatus.training.replay import replay_manager
from mercatus.training.adaptation import adaptation_manager

logger = get_logger("server")

# Global state (initialized in lifespan)
start_time: float = 0


# === Request/Response Models ===

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000, description="User message")
    module: str = Field("general", description="Module context")
    session_id: Optional[str] = Field(None, description="Session ID for context")


class ChatResponseModel(BaseModel):
    response: str
    confidence: float
    module: str
    session_id: str
    memories_used: int
    fallback: bool
    timestamp: str


class DecisionRequest(BaseModel):
    context: str = Field(..., min_length=1, max_length=10000)
    options: list[str] = Field(..., min_length=2, max_length=10)
    module: str = Field("general")
    session_id: Optional[str] = None


class KnowledgeRequest(BaseModel):
    module: str
    category: str
    key: str
    value: str
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    tags: list[str] = []


class FeedbackRequest(BaseModel):
    outcome: str
    score: float = Field(..., ge=0.0, le=1.0)


class HealthResponse(BaseModel):
    status: str
    llm_connected: bool
    db_connected: bool
    uptime_seconds: float
    memory_count: int
    version: str = "2.0.0"


class SettingsResponse(BaseModel):
    llm_base_url: str
    llm_model: str
    host: str
    port: int
    log_level: str


# === New Request Models ===

class WebhookRequest(BaseModel):
    url: str = Field(..., description="Webhook endpoint URL")
    events: list[str] = Field(..., description="Events to subscribe to")


class APIKeyRequest(BaseModel):
    name: str = Field(..., description="Key name")
    scopes: list[str] = Field(..., description="Permission scopes")
    rate_limit: int = Field(100, description="Requests per minute")


class TrainingFeedbackRequest(BaseModel):
    memory_id: int
    rating: int = Field(..., ge=1, le=5, description="Rating 1-5")
    correction: Optional[str] = None
    comment: Optional[str] = None
    category: str = "general"


class ConnectorRequest(BaseModel):
    webhook_url: Optional[str] = None
    bot_token: Optional[str] = None
    channel_id: Optional[str] = None
    api_key: Optional[str] = None


# === Router for API v1 ===

router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=HealthResponse)
async def health(request: Request):
    """Health check endpoint."""
    agent = request.app.state.agent
    db_conn = request.app.state.db

    if not agent:
        raise HTTPException(status_code=503, detail="Agent not ready")

    return HealthResponse(
        status="healthy",
        llm_connected=llm_client.is_available,
        db_connected=db_conn.is_connected,
        uptime_seconds=agent.uptime_seconds,
        memory_count=await agent._memory.count_episodic(),
    )


@router.post("/chat", response_model=ChatResponseModel)
async def chat(request: Request, body: ChatRequest):
    """Send a message to the agent."""
    agent = request.app.state.agent
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not ready")

    try:
        response = await agent.chat(
            message=body.message,
            module=body.module,
            session_id=body.session_id,
        )
        return ChatResponseModel(**response.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail="Internal processing error")


@router.post("/decisions")
async def make_decision(request: Request, body: DecisionRequest):
    """Get a decision between options."""
    agent = request.app.state.agent
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not ready")

    try:
        decision = await agent.decide(
            context=body.context,
            options=body.options,
            module=body.module,
            session_id=body.session_id,
        )
        return decision.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Decision error: {e}")
        raise HTTPException(status_code=500, detail="Internal processing error")


@router.get("/memory/episodic")
async def get_episodic_memory(
    request: Request,
    session_id: Optional[str] = None,
    module: Optional[str] = None,
    limit: int = 50,
):
    """Retrieve episodic memories."""
    agent = request.app.state.agent
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not ready")

    memories = await agent._memory.get_episodic(session_id, module, limit)
    return [
        {
            "id": m.id,
            "session_id": m.session_id,
            "module": m.module,
            "query": m.query,
            "response": m.response[:500],
            "confidence": m.confidence,
            "outcome": m.outcome,
            "created_at": m.created_at,
        }
        for m in memories
    ]


@router.get("/memory/semantic")
async def get_semantic_memory(
    request: Request,
    module: Optional[str] = None,
    category: Optional[str] = None,
    key: Optional[str] = None,
    limit: int = 50,
):
    """Retrieve semantic memories."""
    agent = request.app.state.agent
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not ready")

    memories = await agent._memory.get_semantic(module, category, key, limit)
    return [
        {
            "id": m.id,
            "module": m.module,
            "category": m.category,
            "key": m.key,
            "value": m.value,
            "confidence": m.confidence,
            "tags": m.tags,
            "use_count": m.use_count,
        }
        for m in memories
    ]


@router.post("/memory/semantic")
async def add_knowledge(request: Request, body: KnowledgeRequest):
    """Add knowledge to semantic memory."""
    agent = request.app.state.agent
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not ready")

    try:
        memory_id = await agent.add_knowledge(
            module=body.module,
            category=body.category,
            key=body.key,
            value=body.value,
            confidence=body.confidence,
            tags=body.tags,
        )
        return {"id": memory_id, "status": "created"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/memory/{memory_id}")
async def delete_memory(request: Request, memory_id: int, memory_type: str = "episodic"):
    """Delete a memory by ID."""
    agent = request.app.state.agent
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not ready")

    if memory_type == "episodic":
        success = await agent._memory.delete_episodic(memory_id)
    elif memory_type == "semantic":
        success = await agent._memory.delete_semantic(memory_id)
    else:
        raise HTTPException(status_code=400, detail="Invalid memory type")

    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")

    return {"status": "deleted"}


@router.get("/sessions/{session_id}")
async def get_session(request: Request, session_id: str):
    """Get session history."""
    agent = request.app.state.agent
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not ready")

    history = await agent.get_session_history(session_id)
    return [
        {
            "query": h.query,
            "response": h.response[:300],
            "confidence": h.confidence,
            "created_at": h.created_at,
        }
        for h in history
    ]


@router.post("/feedback/{memory_id}")
async def provide_feedback(request: Request, memory_id: int, body: FeedbackRequest):
    """Provide feedback on a past interaction."""
    agent = request.app.state.agent
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not ready")

    await agent.provide_feedback(memory_id, body.outcome, body.score)
    return {"status": "received"}


# === Import Brain Map and Obsidian modules ===
from mercatus.core.brain import BrainMapGenerator
from mercatus.integrations.obsidian import ObsidianVaultGenerator

# === New Endpoints: System Metrics ===

@router.get("/system/metrics")
async def get_system_metrics():
    """Get real-time system metrics (CPU, RAM, disk, network)."""
    metrics = system_monitor.get_system_metrics()
    return metrics.to_dict()


@router.get("/system/info")
async def get_system_info():
    """Get system information."""
    metrics = system_monitor.get_system_metrics()
    return {
        "platform": metrics.platform_info,
        "uptime_seconds": metrics.uptime_seconds,
        "process_count": metrics.process_count,
    }


# === New Endpoints: Token Throughput ===

@router.get("/metrics/throughput")
async def get_throughput_metrics():
    """Get token throughput metrics."""
    return metrics_tracker.to_dict()


@router.get("/metrics/throughput/history")
async def get_throughput_history(hours: int = 24):
    """Get historical throughput metrics."""
    return await metrics_tracker.get_historical_stats(hours=hours)


# === New Endpoints: Integrations ===

@router.get("/integrations")
async def list_integrations():
    """List all configured integrations."""
    webhooks = await webhook_manager.list_webhooks()
    api_keys = await api_key_manager.list_keys()
    connectors = connector_manager.list_connectors()
    
    return {
        "webhooks": [
            {
                "id": w.id,
                "url": w.url,
                "events": w.events,
                "active": w.active,
                "created_at": w.created_at,
            }
            for w in webhooks
        ],
        "api_keys": [
            {
                "id": k.id,
                "name": k.name,
                "prefix": k.key_prefix,
                "scopes": k.scopes,
                "active": k.active,
                "created_at": k.created_at,
            }
            for k in api_keys
        ],
        "connectors": connectors,
    }


@router.get("/integrations/webhooks")
async def list_webhooks():
    """List registered webhooks."""
    webhooks = await webhook_manager.list_webhooks()
    return [
        {
            "id": w.id,
            "url": w.url,
            "events": w.events,
            "active": w.active,
            "created_at": w.created_at,
        }
        for w in webhooks
    ]


@router.post("/integrations/webhooks")
async def register_webhook(body: WebhookRequest):
    """Register a new webhook."""
    try:
        webhook = await webhook_manager.register(url=body.url, events=body.events)
        return {
            "id": webhook.id,
            "url": webhook.url,
            "events": webhook.events,
            "secret": webhook.secret,
            "status": "registered",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/integrations/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str):
    """Remove a webhook."""
    success = await webhook_manager.unregister(webhook_id)
    if not success:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"status": "deleted"}


@router.post("/integrations/api-keys")
async def generate_api_key(body: APIKeyRequest):
    """Generate a new API key."""
    try:
        full_key, api_key = await api_key_manager.create_key(
            name=body.name,
            scopes=body.scopes,
            rate_limit=body.rate_limit,
        )
        return {
            "key": full_key,
            "id": api_key.id,
            "name": api_key.name,
            "prefix": api_key.key_prefix,
            "scopes": api_key.scopes,
            "created_at": api_key.created_at,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/integrations/api-keys/{key_id}")
async def revoke_api_key(key_id: str):
    """Revoke an API key."""
    success = await api_key_manager.revoke_key(key_id)
    if not success:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"status": "revoked"}


@router.post("/integrations/{service}/connect")
async def connect_service(service: str, body: ConnectorRequest):
    """Connect an external service."""
    from mercatus.integrations.connectors import ConnectorConfig
    
    try:
        config = ConnectorConfig(
            service=service,
            webhook_url=body.webhook_url or "",
            bot_token=body.bot_token or "",
            channel_id=body.channel_id or "",
        )
        connector = connector_manager.create_connector(config)
        return {"service": service, "status": "connected"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/integrations/{service}")
async def disconnect_service(service: str):
    """Disconnect an external service."""
    success = connector_manager.remove_connector(service)
    if not success:
        raise HTTPException(status_code=404, detail="Service not connected")
    return {"status": "disconnected"}


# === New Endpoints: Training ===

@router.post("/training/feedback")
async def submit_training_feedback(body: TrainingFeedbackRequest):
    """Submit feedback on a response."""
    entry = await feedback_manager.submit_feedback(
        memory_id=body.memory_id,
        rating=body.rating,
        correction=body.correction,
        comment=body.comment,
        category=body.category,
    )
    return entry.to_dict()


@router.get("/training/history")
async def get_training_history(
    session_id: Optional[str] = None,
    module: Optional[str] = None,
    limit: int = 50,
):
    """Get feedback history."""
    return await feedback_manager.get_feedback_history(session_id, module, limit)


@router.get("/training/stats")
async def get_training_stats():
    """Get training statistics."""
    return await feedback_manager.get_feedback_stats()


@router.post("/training/adapt")
async def trigger_adaptation():
    """Trigger adaptation based on feedback."""
    # Get all feedback
    feedback = await feedback_manager.get_feedback_history(limit=1000)
    
    # Analyze and generate rules
    rules = await adaptation_manager.analyze_feedback(feedback)
    
    # Apply adaptations
    result = await adaptation_manager.apply_adaptations()
    
    return {
        "rules_generated": len(rules),
        "adaptations": result,
        "stats": adaptation_manager.get_stats(),
    }


@router.post("/training/replay/{session_id}")
async def replay_session(session_id: str):
    """Replay a session's interactions."""
    results = await replay_manager.replay_session(session_id)
    return {
        "session_id": session_id,
        "replayed": len(results),
        "improved": sum(1 for r in results if r.improved),
    }


# === Settings Endpoint ===

@router.get("/settings")
async def get_settings_endpoint():
    """Get current settings."""
    from mercatus.models.config import get_settings as get_config_settings
    settings = get_config_settings()
    return SettingsResponse(
        llm_base_url=settings.llm_base_url,
        llm_model=settings.llm_model,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )


# === New Endpoints: Analytics ===

@router.get("/analytics/conversations")
async def get_conversations_analytics(request: Request):
    """Get conversation analytics."""
    db_conn = request.app.state.db
    total = await db_conn.fetchval("SELECT COUNT(DISTINCT session_id) FROM episodic_memory") or 0
    total_messages = await db_conn.fetchval("SELECT COUNT(*) FROM episodic_memory") or 0
    avg_confidence = await db_conn.fetchval("SELECT AVG(confidence) FROM episodic_memory") or 0.0
    return {
        "total": total,
        "total_messages": total_messages,
        "avg_confidence": round(float(avg_confidence), 2),
    }


@router.get("/analytics/memory")
async def get_memory_analytics(request: Request):
    """Get memory analytics."""
    db_conn = request.app.state.db
    episodic_count = await db_conn.fetchval("SELECT COUNT(*) FROM episodic_memory") or 0
    semantic_count = await db_conn.fetchval("SELECT COUNT(*) FROM semantic_memory") or 0
    return {
        "total": episodic_count + semantic_count,
        "episodic_count": episodic_count,
        "semantic_count": semantic_count,
    }


@router.get("/analytics/tokens")
async def get_token_analytics():
    """Get token usage analytics."""
    stats = metrics_tracker.to_dict()
    return {
        "total_tokens": stats.get("total_tokens", 0),
        "avg_tps": stats.get("avg_tokens_per_second", 0),
        "avg_latency_ms": stats.get("avg_latency_ms", 0),
        "avg_confidence": 0.75,  # Placeholder
    }


# === New Endpoints: Logs ===

@router.get("/logs")
async def get_logs(limit: int = 100):
    """Get recent system logs."""
    logs = []
    log_file = Path("./logs/mercatus_2026-09-15.log")
    if log_file.exists():
        try:
            with open(log_file, "r") as f:
                lines = f.readlines()[-limit:]
                for line in lines:
                    line = line.strip()
                    if line:
                        parts = line.split(" | ", 3)
                        if len(parts) >= 4:
                            logs.append({
                                "timestamp": parts[0],
                                "level": parts[1],
                                "module": parts[2],
                                "message": parts[3],
                            })
                        else:
                            logs.append({
                                "timestamp": "",
                                "level": "INFO",
                                "module": "system",
                                "message": line,
                            })
        except Exception:
            pass
    return logs


# === New Endpoints: Security ===

@router.get("/security/audit")
async def get_security_audit(
    request: Request,
    type: Optional[str] = None,
    limit: int = 100,
):
    """Get security audit information."""
    from mercatus.utils.security import brute_force_protector, ip_blocker, audit_logger

    if type == "brute_force":
        stats = brute_force_protector.get_stats()
        return {
            "locked": stats["currently_locked"],
            "tracked": stats["tracked_identifiers"],
        }
    elif type == "ip_blocking":
        stats = ip_blocker.get_stats()
        return {
            "blocked": stats["blocked_ips"],
            "violations": stats["total_violations"],
        }
    else:
        # Return audit log entries
        db_conn = request.app.state.db
        entries = await audit_logger.get_audit_log(limit=limit)
        return entries


@router.get("/security/sessions")
async def get_security_sessions():
    """Get active sessions."""
    from mercatus.utils.security import session_manager
    sessions = session_manager.get_active_sessions()
    return sessions


# === New Endpoints: Brain Map ===

@router.get("/brain/graph")
async def get_brain_graph(
    request: Request,
    module: Optional[str] = None,
    limit: int = 200,
):
    """Get knowledge graph data (nodes and edges)."""
    db_conn = request.app.state.db
    generator = BrainMapGenerator(db_conn)
    graph = await generator.generate_graph(module=module, limit=limit)
    return graph.to_dict()


@router.get("/brain/node/{node_id}")
async def get_brain_node(request: Request, node_id: str):
    """Get details for a specific brain node."""
    db_conn = request.app.state.db
    generator = BrainMapGenerator(db_conn)
    details = await generator.get_node_details(node_id)
    if "error" in details:
        raise HTTPException(status_code=404, detail=details["error"])
    return details


# === New Endpoints: Obsidian ===

@router.get("/obsidian/export")
async def export_obsidian_vault(request: Request):
    """Export agent data as Obsidian vault (ZIP)."""
    db_conn = request.app.state.db
    generator = ObsidianVaultGenerator(db_conn)
    zip_path = await generator.export_as_zip()

    from fastapi.responses import FileResponse
    return FileResponse(
        path=str(zip_path),
        filename="mercatus-vault.zip",
        media_type="application/zip",
    )


@router.post("/obsidian/sync")
async def sync_obsidian_vault(request: Request):
    """Sync and regenerate Obsidian vault."""
    db_conn = request.app.state.db
    generator = ObsidianVaultGenerator(db_conn)
    stats = await generator.sync_vault()
    return stats


# === New Endpoints: Settings (POST) ===

class LLMSettingsRequest(BaseModel):
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None
    llm_timeout: Optional[int] = None


class MemorySettingsRequest(BaseModel):
    max_memory: Optional[int] = None
    working_memory_size: Optional[int] = None


@router.post("/settings/llm")
async def update_llm_settings(body: LLMSettingsRequest):
    """Update LLM settings (runtime)."""
    from mercatus.models.config import get_settings
    settings = get_settings()

    if body.llm_base_url:
        settings.llm_base_url = body.llm_base_url
    if body.llm_model:
        settings.llm_model = body.llm_model
    if body.llm_timeout:
        settings.llm_timeout = body.llm_timeout

    return {"status": "updated", "settings": {
        "llm_base_url": settings.llm_base_url,
        "llm_model": settings.llm_model,
        "llm_timeout": settings.llm_timeout,
    }}


@router.post("/settings/memory")
async def update_memory_settings(body: MemorySettingsRequest):
    """Update memory settings (runtime)."""
    from mercatus.models.config import get_settings
    settings = get_settings()

    if body.max_memory:
        settings.max_memory = body.max_memory
    if body.working_memory_size:
        settings.working_memory_size = body.working_memory_size

    return {"status": "updated", "settings": {
        "max_memory": settings.max_memory,
        "working_memory_size": settings.working_memory_size,
    }}


# === New Endpoints: Database ===

@router.post("/database/vacuum")
async def vacuum_database(request: Request):
    """Vacuum the database to reclaim space."""
    db_conn = request.app.state.db
    await db_conn.execute("VACUUM")
    await db_conn.commit()
    return {"status": "vacuumed"}


# === New Endpoints: Backup ===

@router.post("/backup/create")
async def create_backup(request: Request):
    """Create a backup of the database."""
    import shutil
    from datetime import datetime

    db_conn = request.app.state.db
    settings = get_settings()

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path("./backups")
    backup_dir.mkdir(exist_ok=True)
    backup_path = backup_dir / f"mercatus_backup_{timestamp}.db"

    if db_conn._db_path and Path(db_conn._db_path).exists():
        shutil.copy2(str(db_conn._db_path), str(backup_path))
        return {"status": "created", "path": str(backup_path), "timestamp": timestamp}
    else:
        raise HTTPException(status_code=404, detail="Database file not found")


@router.post("/backup/restore")
async def restore_backup(request: Request):
    """Restore database from a backup."""
    return {"status": "not_implemented", "message": "Use direct file restore"}


# === Application Factory ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global start_time

    settings = get_settings()
    logger.info("Starting Mercatus Agent v2.0...")

    # Initialize database
    await db.initialize()
    await init_schema(db)
    await seed_knowledge(db)

    # Initialize LLM
    await llm_client.initialize()
    if llm_client.is_available:
        logger.info(f"LLM connected: {settings.llm_model} at {settings.llm_base_url}")
    else:
        logger.warning("LLM not available — using rule-based fallback")

    # Initialize components
    from mercatus.core.memory import MemoryManager
    from mercatus.core.retrieval import RetrievalEngine
    from mercatus.core.decision import DecisionEngine
    from mercatus.core.agent import MercatusAgent

    memory = MemoryManager(db)
    retrieval = RetrievalEngine(memory, llm_client)
    decision = DecisionEngine(memory, retrieval, llm_client)
    app.state.agent = MercatusAgent(memory, retrieval, decision, llm_client)
    app.state.db = db
    start_time = time.time()

    # Set database for managers
    metrics_tracker._db = db
    webhook_manager._db = db
    api_key_manager._db = db
    oauth_manager._db = db
    feedback_manager._db = db
    replay_manager._db = db
    adaptation_manager._db = db

    logger.info(f"Mercatus Agent ready on port {settings.port}")

    yield

    # Shutdown
    logger.info("Shutting down Mercatus Agent...")
    await llm_client.close()
    await db.close()
    await webhook_manager.close()
    await connector_manager.close_all()


# Mount static files and templates
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Mercatus Agent",
        description="Specialized Language Memory Agent for Sales & Trading",
        version="2.0.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API router
    app.include_router(router)

    # Mount static files
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        """Serve the main dashboard."""
        return templates.TemplateResponse("index.html", {"request": request})

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time communication."""
        connection_id = generate_session_id()
        handler = WebSocketHandler(websocket.app.state.agent, ws_manager)
        await handler.handle(websocket, connection_id)

    return app


# Default app instance (for running with uvicorn)
app = create_app()
