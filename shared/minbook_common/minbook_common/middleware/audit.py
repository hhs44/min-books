"""写 audit.audit_log(详见 §13 §8)。"""
import json
from datetime import datetime

from minbook_db.session import AsyncSessionLocal


async def audit_log(
    event_type: str,
    service_name: str | None = None,
    source_ip: str | None = None,
    user_agent: str | None = None,
    user_id: str | None = None,
    details: dict | None = None,
):
    """写一条 audit log(异步,fire-and-forget)。"""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                """INSERT INTO audit.audit_log
                   (event_type, service_name, source_ip, user_agent, user_id, details, occurred_at)
                   VALUES (:event_type, :service_name, :source_ip, :user_agent,
                           :user_id, :details, :occurred_at)""",
                {
                    "event_type": event_type,
                    "service_name": service_name,
                    "source_ip": source_ip,
                    "user_agent": user_agent,
                    "user_id": user_id,
                    "details": json.dumps(details or {}),
                    "occurred_at": datetime.utcnow(),
                },
            )
            await session.commit()
    except Exception:
        # 写 audit 失败不能阻塞主流程
        pass
