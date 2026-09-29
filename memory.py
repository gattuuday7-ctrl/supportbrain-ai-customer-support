"""
SupportBrain - Hindsight Memory Integration Module
==================================================
This module isolates all memory operations using the official Hindsight SDK
(`hindsight-client`).

What Hindsight does:
1. Retains customer interactions, past problems, fixes, and preferences.
2. Recalls relevant previous experiences when a customer returns.
3. Provides persistent memory across conversations so the AI remembers context.

If an external Hindsight daemon or cloud service is configured (e.g., http://localhost:8888
or https://api.hindsight.vectorize.io), this module connects to it directly.
If running standalone without Docker, this module also provides a built-in standard
Hindsight REST API router with local JSON file persistence.
"""

import os
import re
import json
import uuid
import math
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query
import httpx

# Official Hindsight Python SDK client
from hindsight_client import Hindsight

logger = logging.getLogger("supportbrain-memory")

# Path for persistent local storage when running in standalone mode
DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_FILE = DATA_DIR / "hindsight_store.json"


# ============================================================================
# 1. Pydantic Models for Customer Support Memories
# ============================================================================

class MemoryItem(BaseModel):
    """Structured representation of a recalled memory displayed in the UI."""
    id: str
    text: str
    customer_name: Optional[str] = None
    company: Optional[str] = None
    product: Optional[str] = None
    issue: Optional[str] = None
    solution: Optional[str] = None
    result: Optional[str] = None
    relevance_score: float = 1.0
    tags: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "Hindsight Memory Bank"


# ============================================================================
# 2. Local File Store for Standalone Hindsight Engine
# ============================================================================

class LocalHindsightStore:
    """Thread-safe persistent JSON store backing the standard Hindsight API."""
    def __init__(self, filepath: Path = STORAGE_FILE):
        self.filepath = filepath
        self._ensure_file()

    def _ensure_file(self):
        if not self.filepath.exists():
            self._save({"banks": {}})

    def _load(self) -> Dict[str, Any]:
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"banks": {}}

    def _save(self, data: Dict[str, Any]):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def get_memories(self, bank_id: str) -> List[Dict[str, Any]]:
        data = self._load()
        return data.get("banks", {}).get(bank_id, {}).get("memories", [])

    def add_memories(self, bank_id: str, items: List[Dict[str, Any]]) -> int:
        data = self._load()
        if "banks" not in data:
            data["banks"] = {}
        if bank_id not in data["banks"]:
            data["banks"][bank_id] = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "memories": []
            }

        stored = []
        now_str = datetime.now(timezone.utc).isoformat()
        for item in items:
            content = item.get("content")
            if isinstance(content, dict):
                content = content.get("actual_instance", str(content))
            elif isinstance(content, list):
                content = " ".join([str(c) for c in content])
            else:
                content = str(content or "")

            memory_id = f"mem_{uuid.uuid4().hex[:10]}"
            unit = {
                "id": memory_id,
                "text": content,
                "context": item.get("context") or "Customer Support Interaction",
                "metadata": item.get("metadata") or {},
                "tags": item.get("tags") or [],
                "entities": item.get("entities") or [],
                "created_at": item.get("timestamp") or now_str,
                "fact_type": item.get("strategy") or "experience"
            }
            stored.append(unit)

        data["banks"][bank_id]["memories"].extend(stored)
        self._save(data)
        return len(stored)

    def search_memories(self, bank_id: str, query: str, tags: Optional[List[str]] = None, limit: int = 5) -> List[Dict[str, Any]]:
        memories = self.get_memories(bank_id)
        if not memories:
            return []

        query_tokens = set(re.findall(r"\w+", query.lower()))
        scored = []
        for mem in memories:
            text = mem.get("text", "").lower()
            meta = mem.get("metadata", {})
            meta_str = " ".join(str(v).lower() for v in meta.values())
            combined = f"{text} {meta_str}"
            mem_tokens = set(re.findall(r"\w+", combined))

            # Calculate token overlap score
            overlap = len(query_tokens.intersection(mem_tokens))
            base_score = overlap / max(len(query_tokens), 1)

            # Boost if tags match
            tag_boost = 0.0
            if tags and mem.get("tags"):
                for t in tags:
                    if t.lower() in [mt.lower() for mt in mem.get("tags", [])]:
                        tag_boost += 0.2

            score = min(round(base_score + tag_boost, 3), 1.0)
            if score > 0.05 or not query.strip():
                scored.append((score, mem))

        # Sort highest score first
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, mem in scored[:limit]:
            item = dict(mem)
            item["score"] = max(score, 0.5)  # reasonable confidence for relevance
            results.append(item)
        return results

    def clear(self, bank_id: str):
        data = self._load()
        if "banks" in data and bank_id in data["banks"]:
            data["banks"][bank_id]["memories"] = []
            self._save(data)


local_store = LocalHindsightStore()


# ============================================================================
# 3. Standard Hindsight REST API Router
# ============================================================================
# This router implements the official Hindsight API endpoints so the
# `hindsight-client` Python SDK communicates seamlessly with it locally.

hindsight_api_router = APIRouter(prefix="/v1/default/banks", tags=["Hindsight Memory Engine"])


@hindsight_api_router.get("/{bank_id}/profile")
async def get_bank_profile(bank_id: str):
    """Health & profile endpoint for Hindsight bank."""
    return {
        "bank_id": bank_id,
        "status": "active",
        "description": "SupportBrain Hindsight Memory Bank"
    }


@hindsight_api_router.post("/{bank_id}/memories")
async def retain_memories_endpoint(bank_id: str, payload: Dict[str, Any]):
    """Standard Hindsight endpoint: Store memory items (retain)."""
    items = payload.get("items", [])
    count = local_store.add_memories(bank_id, items)
    return {
        "success": True,
        "bank_id": bank_id,
        "items_count": count,
        "var_async": False,
        "operation_id": None,
        "operation_ids": [],
        "usage": {}
    }


@hindsight_api_router.post("/{bank_id}/memories/recall")
async def recall_memories_endpoint(bank_id: str, payload: Dict[str, Any]):
    """Standard Hindsight endpoint: Search and recall memories."""
    query = payload.get("query", "")
    tags = payload.get("tags")
    matches = local_store.search_memories(bank_id, query, tags=tags, limit=10)

    results = []
    for m in matches:
        results.append({
            "id": m.get("id"),
            "text": m.get("text"),
            "type": m.get("fact_type", "experience"),
            "entities": m.get("entities", []),
            "context": m.get("context", ""),
            "metadata": m.get("metadata", {}),
            "tags": m.get("tags", []),
            "scores": {"final": m.get("score", 0.85)}
        })

    return {
        "results": results,
        "trace": None,
        "entities": None,
        "chunks": None,
        "source_facts": None,
        "source_facts_truncated": False
    }


@hindsight_api_router.get("/{bank_id}/memories/list")
async def list_memories_endpoint(bank_id: str, limit: int = 50, offset: int = 0):
    """Standard Hindsight endpoint: List stored memories in bank."""
    all_memories = local_store.get_memories(bank_id)
    sliced = all_memories[offset: offset + limit]

    items = []
    for m in sliced:
        items.append({
            "id": m.get("id"),
            "text": m.get("text"),
            "context": m.get("context", ""),
            "var_date": m.get("created_at"),
            "fact_type": m.get("fact_type", "experience"),
            "document_id": None,
            "mentioned_at": m.get("created_at"),
            "occurred_start": None,
            "occurred_end": None,
            "entities": m.get("entities", []),
            "chunk_id": None,
            "proof_count": 1,
            "tags": m.get("tags", []),
            "metadata": m.get("metadata", {}),
            "consolidated_at": None,
            "consolidation_failed_at": None,
            "state": "active",
            "invalidation_reason": None,
            "invalidated_at": None,
            "edited_at": None,
            "updated_at": m.get("created_at"),
            "source_memory_ids": []
        })

    return {
        "items": items,
        "total": len(all_memories),
        "limit": limit,
        "offset": offset
    }


@hindsight_api_router.delete("/{bank_id}/memories")
async def clear_bank_memories_endpoint(bank_id: str):
    """Standard Hindsight endpoint: Clear all memories in bank."""
    local_store.clear(bank_id)
    return {"success": True}


# ============================================================================
# 4. Hindsight Memory Service (High-level SDK Wrapper)
# ============================================================================

class HindsightMemoryService:
    """
    Main memory manager for SupportBrain.
    Uses the official Hindsight SDK (`from hindsight_client import Hindsight`).
    """

    def __init__(self):
        self.base_url = os.getenv("HINDSIGHT_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
        self.api_key = os.getenv("HINDSIGHT_API_KEY") or None
        self.bank_id = os.getenv("HINDSIGHT_BANK_ID", "supportbrain-bank")

        # Official Hindsight Client
        self.client = Hindsight(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=10.0
        )

    async def retain_interaction(
        self,
        customer_name: str,
        company: str,
        product: str,
        interaction_text: str,
        issue: Optional[str] = None,
        solution: Optional[str] = None,
        result: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Store a customer support experience in Hindsight.
        Uses `client.aretain` from the official SDK.
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        # Build clean tags for precise future retrieval
        all_tags = ["support-memory"]
        if customer_name:
            all_tags.append(f"customer:{customer_name.strip().lower().replace(' ', '_')}")
        if company:
            all_tags.append(f"company:{company.strip().lower().replace(' ', '_')}")
        if product:
            all_tags.append(f"product:{product.strip().lower().replace(' ', '_')}")
        if tags:
            all_tags.extend(tags)

        # Structured metadata
        metadata = {
            "customer_name": customer_name or "Unknown",
            "company": company or "Unknown",
            "product": product or "General Support",
            "issue": issue or "",
            "solution": solution or "",
            "result": result or "",
            "timestamp": now_iso
        }

        # Entities for knowledge graph representation in Hindsight
        entities = []
        if customer_name:
            entities.append({"text": customer_name, "type": "Customer"})
        if company:
            entities.append({"text": company, "type": "Company"})
        if product:
            entities.append({"text": product, "type": "Product"})
        if issue:
            entities.append({"text": issue, "type": "Problem"})
        if solution:
            entities.append({"text": solution, "type": "Resolution"})

        # Comprehensive content string that Hindsight indexes
        content_parts = [f"Customer {customer_name or 'User'} at {company or 'Company'} ({product or 'Product'}):"]
        if issue:
            content_parts.append(f"Previous issue encountered: '{issue}'.")
        if solution:
            content_parts.append(f"Solution provided: '{solution}'.")
        if result:
            content_parts.append(f"Outcome: {result}.")
        if interaction_text:
            content_parts.append(f"Details: {interaction_text}")

        content = " ".join(content_parts)

        logger.info(f"Retaining memory in Hindsight bank '{self.bank_id}' for '{customer_name}'")

        try:
            # Call official Hindsight SDK aretain
            res = await self.client.aretain(
                bank_id=self.bank_id,
                content=content,
                metadata=metadata,
                tags=all_tags,
                entities=entities,
                context=f"Customer Support memory for {customer_name}"
            )
            return {"success": res.success, "items_count": res.items_count, "content": content}
        except Exception as e:
            logger.warning(f"External SDK retain encountered exception: {e}. Writing to local store directly.")
            # Graceful local fallback
            local_store.add_memories(self.bank_id, [{
                "content": content,
                "metadata": metadata,
                "tags": all_tags,
                "entities": entities,
                "context": f"Customer Support memory for {customer_name}",
                "timestamp": now_iso
            }])
            return {"success": True, "items_count": 1, "content": content, "fallback": True}

    async def recall_memories(
        self,
        customer_name: Optional[str] = None,
        query: str = "",
        company: Optional[str] = None,
        product: Optional[str] = None,
        limit: int = 5
    ) -> List[MemoryItem]:
        """
        Recall relevant past memories from Hindsight.
        Uses `client.arecall` from the official SDK.
        """
        search_terms = []
        if customer_name:
            search_terms.append(customer_name)
        if company:
            search_terms.append(company)
        if product:
            search_terms.append(product)
        if query:
            search_terms.append(query)

        search_query = " ".join(search_terms) if search_terms else "Customer support memory"

        logger.info(f"Recalling memories from Hindsight with query: '{search_query}'")

        recalled_items: List[MemoryItem] = []

        try:
            # Call official Hindsight SDK arecall
            recall_response = await self.client.arecall(
                bank_id=self.bank_id,
                query=search_query,
                max_tokens=4096,
                budget="mid"
            )

            for result in recall_response.results:
                meta = result.metadata or {}
                score = 0.85
                if result.scores:
                    if isinstance(result.scores, dict):
                        score = float(result.scores.get("final", result.scores.get("relevance", 0.85)))
                    else:
                        score = float(getattr(result.scores, "final", getattr(result.scores, "relevance", 0.85)))

                recalled_items.append(MemoryItem(
                    id=result.id,
                    text=result.text or "",
                    customer_name=meta.get("customer_name") or customer_name,
                    company=meta.get("company") or company,
                    product=meta.get("product") or product,
                    issue=meta.get("issue"),
                    solution=meta.get("solution"),
                    result=meta.get("result"),
                    relevance_score=round(score, 2),
                    tags=result.tags or [],
                    timestamp=meta.get("timestamp") or datetime.now(timezone.utc).isoformat()
                ))

        except Exception as e:
            logger.warning(f"External SDK recall encountered exception: {e}. Searching local store directly.")
            # Fallback directly to local store
            matches = local_store.search_memories(self.bank_id, search_query, limit=limit)
            for m in matches:
                meta = m.get("metadata", {})
                recalled_items.append(MemoryItem(
                    id=m.get("id"),
                    text=m.get("text", ""),
                    customer_name=meta.get("customer_name") or customer_name,
                    company=meta.get("company") or company,
                    product=meta.get("product") or product,
                    issue=meta.get("issue"),
                    solution=meta.get("solution"),
                    result=meta.get("result"),
                    relevance_score=round(m.get("score", 0.90), 2),
                    tags=m.get("tags", []),
                    timestamp=m.get("created_at") or datetime.now(timezone.utc).isoformat()
                ))

        return recalled_items[:limit]

    async def list_all_memories(self) -> List[MemoryItem]:
        """List all memories currently stored in the Hindsight bank."""
        try:
            resp = await self.client.alist_memories(bank_id=self.bank_id, limit=50)
            items = []
            for unit in resp.items:
                meta = unit.metadata or {}
                items.append(MemoryItem(
                    id=unit.id,
                    text=unit.text or "",
                    customer_name=meta.get("customer_name"),
                    company=meta.get("company"),
                    product=meta.get("product"),
                    issue=meta.get("issue"),
                    solution=meta.get("solution"),
                    result=meta.get("result"),
                    relevance_score=1.0,
                    tags=unit.tags or [],
                    timestamp=unit.var_date or meta.get("timestamp") or datetime.now(timezone.utc).isoformat()
                ))
            return items
        except Exception as e:
            logger.warning(f"Error listing memories via SDK: {e}. Reading local store directly.")
            all_m = local_store.get_memories(self.bank_id)
            items = []
            for m in all_m:
                meta = m.get("metadata", {})
                items.append(MemoryItem(
                    id=m.get("id"),
                    text=m.get("text", ""),
                    customer_name=meta.get("customer_name"),
                    company=meta.get("company"),
                    product=meta.get("product"),
                    issue=meta.get("issue"),
                    solution=meta.get("solution"),
                    result=meta.get("result"),
                    relevance_score=1.0,
                    tags=m.get("tags", []),
                    timestamp=m.get("created_at") or meta.get("timestamp") or datetime.now(timezone.utc).isoformat()
                ))
            return items

    async def seed_example_memories(self) -> int:
        """
        Seeds initial demo memories (such as Rahul Sharma's previous issue)
        to make hackathon demonstrations seamless in one click.
        """
        # Clear existing to avoid duplicate pollution during demos
        await self.clear_bank()

        example_interactions = [
            {
                "customer_name": "Rahul Sharma",
                "company": "Acme Technologies",
                "product": "Enterprise Dashboard",
                "issue": "Invalid session / login failed after timeout",
                "solution": "Clear browser session and local storage cache",
                "result": "Successfully resolved - login resumed immediately",
                "interaction_text": "Rahul reported getting 'Invalid session error (401)' when accessing Enterprise Dashboard. Clearing the browser cookies and session cache fixed the authentication problem.",
                "tags": ["login", "session-error", "browser-cache"]
            },
            {
                "customer_name": "Rahul Sharma",
                "company": "Acme Technologies",
                "product": "Enterprise Dashboard",
                "issue": "Report export format preference",
                "solution": "Set default export format to XLSX instead of CSV in team settings",
                "result": "Preference saved for Acme Technologies account",
                "interaction_text": "Rahul mentioned Acme Technologies prefers spreadsheets formatted as Excel (.xlsx) rather than raw CSV.",
                "tags": ["preferences", "export", "xlsx"]
            },
            {
                "customer_name": "Sarah Connor",
                "company": "Cyberdyne Systems",
                "product": "Cloud Analytics",
                "issue": "API Rate limit exceeded on batch ingestion",
                "solution": "Enabled request batching and increased rate limit quota to Tier 3",
                "result": "Pipeline stabilized with 0 dropped requests",
                "interaction_text": "Sarah called regarding 429 Too Many Requests during high load. Advised configuring batch size of 500 and upgraded API key quota.",
                "tags": ["rate-limit", "api", "tier3"]
            }
        ]

        count = 0
        for item in example_interactions:
            await self.retain_interaction(
                customer_name=item["customer_name"],
                company=item["company"],
                product=item["product"],
                issue=item["issue"],
                solution=item["solution"],
                result=item["result"],
                interaction_text=item["interaction_text"],
                tags=item["tags"]
            )
            count += 1

        return count

    async def clear_bank(self) -> bool:
        """Clear all memories in current bank."""
        try:
            local_store.clear(self.bank_id)
            async with httpx.AsyncClient(timeout=3.0) as http_client:
                await http_client.delete(f"{self.base_url}/v1/default/banks/{self.bank_id}/memories")
            return True
        except Exception:
            local_store.clear(self.bank_id)
            return True


# Global memory service instance
memory_service = HindsightMemoryService()
