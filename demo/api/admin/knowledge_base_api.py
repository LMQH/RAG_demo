"""
知识库重建 API
"""
import os
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session

from demo.models.schema import get_db
from demo.services.document_service import DocumentService
from demo.services.background_tasks import rebuild_knowledge_base_background

router = APIRouter(prefix="/api/admin", tags=["admin"])

document_service = DocumentService()


@router.post("/knowledge-base/rebuild")
async def rebuild_knowledge_base(
    background_tasks: BackgroundTasks,
    path: str = Query(default="uploads", description="要重建的目录路径（默认：uploads）"),
    db: Session = Depends(get_db)
):
    """重建知识库：清空旧映射和向量，重新处理uploads目录中的所有MD文件
    
    重建操作在后台异步进行，不会阻塞请求。
    返回预期的版本号，可用于监听重建状态。
    """
    if not path or not path.strip():
        path = "uploads"
    
    path = path.strip()
    
    if not os.path.exists(path):
        raise HTTPException(status_code=400, detail=f"路径不存在: {path}")
    
    expected_version = document_service._get_next_version(db)
    
    background_tasks.add_task(rebuild_knowledge_base_background, path)
    
    return {
        "message": "知识库重建任务已启动，正在后台处理中",
        "path": path,
        "expected_version": expected_version,
        "status": "processing",
        "status_url": f"/api/admin/knowledge-base/rebuild/status?version={expected_version}"
    }

