"""文风分析路由:本计划 v2 暂未实现 agent-writer-service,返回 501。"""
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

router = APIRouter()


@router.post("/{book_id}/style/analyze")
async def analyze_style(book_id: UUID):
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "agent-writer-service not yet implemented")


@router.get("/{book_id}/style/fingerprint")
async def get_fingerprint(book_id: UUID):
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "agent-writer-service not yet implemented")
