"""
版本历史 API
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from demo.models.schema import get_db
from demo.services.version_service import get_version_history

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/version-history")
async def list_version_history(db: Session = Depends(get_db)):
    """获取知识库历史版本列表"""
    return get_version_history(db)

