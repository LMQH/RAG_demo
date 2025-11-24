"""
文档上传 API
"""
import os
import uuid
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from demo.models.schema import get_db
from demo.services.document_service import DocumentService
from demo.services.background_tasks import process_document_background
from demo.services.version_service import copy_previous_version_mappings

router = APIRouter(prefix="/api/admin", tags=["admin"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

document_service = DocumentService()


@router.post("/upload")
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """上传Markdown文档（支持单个或多个文件，多个文件使用同一版本号）
    
    上传新文件时，会将当前知识库所有文件都更新到新版本。
    文件上传后会立即返回，文档处理（切割、向量化、存储）在后台异步进行。
    """
    if not files:
        raise HTTPException(status_code=400, detail="至少需要上传一个文件")
    
    version = document_service._get_next_version(db)
    copied_count = copy_previous_version_mappings(db, version)
    
    saved_files = []
    
    try:
        for file in files:
            if not file.filename or not file.filename.endswith('.md'):
                raise HTTPException(
                    status_code=400,
                    detail=f"文件 '{file.filename or '未知'}' 不支持，只支持Markdown文件(.md)"
                )
            
            file_id = str(uuid.uuid4())
            file_path = UPLOAD_DIR / f"{file_id}_{file.filename}"
            
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            saved_files.append((str(file_path), file.filename))
            
            background_tasks.add_task(
                process_document_background,
                str(file_path),
                file.filename,
                version
            )
        
        if len(files) == 1:
            return {
                "message": "文件已上传，正在后台处理中",
                "filename": saved_files[0][1],
                "version": version,
                "previous_files_copied": copied_count,
                "status": "processing"
            }
        else:
            return {
                "message": f"{len(files)} 个文件已上传，正在后台处理中",
                "total_files": len(files),
                "version": version,
                "previous_files_copied": copied_count,
                "status": "processing",
                "files": [filename for _, filename in saved_files]
            }
        
    except HTTPException:
        raise
    except Exception as e:
        for file_path, _ in saved_files:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
        raise HTTPException(status_code=500, detail=f"上传文件时出错: {str(e)}")

