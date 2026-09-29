"""
SupportBrain - FastAPI Main Server
==================================
Connects FastAPI backend, Groq LLM agent, Hindsight memory engine,
and static frontend.

Core Endpoints:
- POST /api/chat: Customer message -> Recall from Hindsight -> Groq LLM -> Retain in Hindsight
- GET  /api/memories: Retrieve all stored memories in Hindsight bank
- POST /api/memories/seed: Populate initial demo memories (Rahul Sharma, etc.)
- DELETE /api/memories: Reset/clear memory bank
- GET  /api/status: Check connectivity to Groq and Hindsight
"""

import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Internal modules
from .memory import memory_service, hindsight_api_router, MemoryItem
from .agent import support_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("supportbrain-main")

# Directory paths
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(
    title="SupportBrain API",
    description="AI Customer Support Agent with Persistent Hindsight Memory",
    version="1.0.0"
)

# Enable CORS for development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the standard Hindsight REST API router
# This enables the official hindsight-client SDK to talk to local storage
# or external Hindsight instances seamlessly.
app.include_router(hindsight_api_router)


# ============================================================================
# Request / Response Schemas
# ============================================================================

class ChatRequest(BaseModel):
    customer_name: Optional[str] = "Rahul Sharma"
    company: Optional[str] = "Acme Technologies"
    product: Optional[str] = "Enterprise Dashboard"
    message: str = Field(..., min_length=1, description="Customer message")
    chat_history: Optional[List[Dict[str, str]]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    response: str
    customer_name: str
    company: str
    product: str
    recalled_memories: List[MemoryItem]
    extracted_facts: Optional[Dict[str, Any]] = None
    llm_provider: str


# ============================================================================
# API Endpoints
# ============================================================================

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """
    Main Customer Support Workflow:
    1. Identifies the customer.
    2. Recalls relevant previous experiences from Hindsight.
    3. Supplies memories to Groq LLM as context.
    4. Generates memory-aware support response.
    5. Retains the new interaction in Hindsight for future conversations.
    """
    c_name = req.customer_name or "Rahul Sharma"
    c_comp = req.company or "Acme Technologies"
    c_prod = req.product or "Enterprise Dashboard"
    msg = req.message.strip()

    # Step 1: Recall relevant memories from Hindsight
    recalled = await memory_service.recall_memories(
        customer_name=c_name,
        query=msg,
        company=c_comp,
        product=c_prod,
        limit=4
    )

    # Step 2: Convert to dicts for the LLM
    memories_dict = [m.model_dump() for m in recalled]

    # Step 3: Generate response with Groq LLM (or smart fallback)
    reply, extracted = await support_agent.generate_response(
        customer_name=c_name,
        company=c_comp,
        product=c_prod,
        user_message=msg,
        chat_history=req.chat_history,
        recalled_memories=memories_dict
    )

    # Step 4: If new customer info was extracted, update profile values
    if extracted:
        if extracted.get("customer_name"):
            c_name = extracted["customer_name"]
        if extracted.get("company"):
            c_comp = extracted["company"]
        if extracted.get("product"):
            c_prod = extracted["product"]

    # Step 5: Retain the interaction in Hindsight
    # Save conversation context and any extracted resolution
    issue_text = extracted.get("issue") if extracted else None
    sol_text = extracted.get("solution") if extracted else None
    res_text = extracted.get("result") if extracted else None

    # Asynchronously retain in Hindsight
    await memory_service.retain_interaction(
        customer_name=c_name,
        company=c_comp,
        product=c_prod,
        interaction_text=f"Customer said: '{msg}' | Agent answered: '{reply}'",
        issue=issue_text,
        solution=sol_text,
        result=res_text
    )

    provider_name = f"Groq ({support_agent.model})" if support_agent.is_configured() else "SupportBrain Local LLM"

    return ChatResponse(
        response=reply,
        customer_name=c_name,
        company=c_comp,
        product=c_prod,
        recalled_memories=recalled,
        extracted_facts=extracted,
        llm_provider=provider_name
    )


@app.get("/api/memories", response_model=List[MemoryItem])
async def get_all_memories():
    """Retrieve all memories stored in the Hindsight bank."""
    return await memory_service.list_all_memories()


@app.post("/api/memories/seed")
async def seed_memories():
    """
    Seed initial demo memories (e.g., Rahul Sharma's previous invalid session issue)
    for easy one-click hackathon demonstration.
    """
    count = await memory_service.seed_example_memories()
    return {"success": True, "seeded_count": count, "message": "Demo memories seeded into Hindsight successfully."}


@app.delete("/api/memories")
async def clear_memories():
    """Clear all memories in the Hindsight bank for a clean state."""
    await memory_service.clear_bank()
    return {"success": True, "message": "Hindsight memory bank cleared."}


@app.get("/api/status")
async def get_status():
    """System status check for Groq and Hindsight."""
    memories = await memory_service.list_all_memories()
    return {
        "status": "healthy",
        "hindsight": {
            "bank_id": memory_service.bank_id,
            "base_url": memory_service.base_url,
            "total_memories": len(memories),
            "status": "connected"
        },
        "groq": {
            "is_configured": support_agent.is_configured(),
            "model": support_agent.model
        }
    }


# ============================================================================
# Static Files & Frontend Serving
# ============================================================================

# Mount frontend directory for assets
if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")


@app.get("/")
async def serve_index():
    """Serve the SupportBrain dashboard UI."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "SupportBrain API is running. Place index.html in frontend/ to view UI."}


@app.get("/style.css")
async def serve_style():
    """Serve style.css directly from root."""
    return FileResponse(FRONTEND_DIR / "style.css")


@app.get("/app.js")
async def serve_app_js():
    """Serve app.js directly from root."""
    return FileResponse(FRONTEND_DIR / "app.js")
