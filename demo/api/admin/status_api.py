"""
状态监听 API (SSE)
"""
from typing import Optional
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from demo.services.sse_service import SSEService

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/upload/status/{version}")
async def stream_upload_status(version: int):
    """实时监听指定版本的文件处理状态
    
    使用 Server-Sent Events (SSE) 自动轮询，当文件处理完成时自动推送结果。
    返回格式：
    {
      "message": "文件已完成处理",
      "filename": "example.md",
      "document_id": 1,
      "version": 1,
      "status": "finish"
    }
    """
    return StreamingResponse(
        SSEService.stream_upload_status(version),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/knowledge-base/rebuild/status")
async def stream_rebuild_status(
    version: Optional[int] = Query(None, description="预期版本号（从重建接口返回的expected_version）")
):
    """实时监听知识库重建任务状态
    
    使用 Server-Sent Events (SSE) 自动轮询，当重建完成时自动推送结果。
    如果提供了 version 参数，将监听该特定版本的重建状态。
    如果未提供，将监听最近一次重建任务。
    """
    return StreamingResponse(
        SSEService.stream_rebuild_status(version),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

