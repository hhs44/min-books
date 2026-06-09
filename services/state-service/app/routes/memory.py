"""记忆检索占位(详见 v2 plan §Phase C Task 22)。

State Service 只管真相文件 + 快照,agent 私有记忆由各 agent 服务自己管(v3 计划)。
这里留 501 Not Implemented 占位,等 v3 决定要不要做跨 agent 记忆代理。
"""
from fastapi import APIRouter, HTTPException, status

router = APIRouter()


@router.get("/{book_id}/memory")
async def recall_memory(book_id: str):
    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED,
        "memory recall delegated to agent services (v3)",
    )
