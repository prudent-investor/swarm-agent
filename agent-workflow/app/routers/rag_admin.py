from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.rag import RAGRunner, create_config

logger = logging.getLogger(__name__)

router = APIRouter()


class RAGReindexRequest(BaseModel):
    confirm: bool = Field(..., description="Must be true to run the pipeline.")
    dry_run: bool = False


@router.post("/rag/reindex")
def trigger_reindex(payload: RAGReindexRequest) -> Any:
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Confirmation required to run reindex.")

    config = create_config(dry_run=payload.dry_run)
    runner = RAGRunner(config)
    result = runner.run()

    logger.info(
        "rag.admin.reindex",
        extra={"dry_run": payload.dry_run, "chunks": result.chunks_count},
    )

    return {
        "dry_run": result.dry_run,
        "processed_urls": result.processed_urls,
        "raw_documents": result.raw_count,
        "chunks_created": result.chunks_count,
        "embedded_chunks": result.embedded_count,
        "index_items": result.index_count,
    }
