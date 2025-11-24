"""
文档查询和删除 API
"""
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from demo.models.schema import get_db, Document, DocumentMapping
from demo.services.document_service import DocumentService

router = APIRouter(prefix="/api/admin", tags=["admin"])

document_service = DocumentService()


@router.get("/documents")
async def list_documents(
    version: Optional[int] = Query(None, description="版本号（可选，不指定则返回最新版本）"),
    db: Session = Depends(get_db)
):
    """获取指定版本的文档列表（不指定版本则返回最新版本）
    
    查询MySQL中活跃的文档映射记录，返回知识库中的文档列表。
    如果指定了版本号，返回该版本的所有文档（包括活跃和非活跃）。
    如果未指定版本号，返回最新版本的活跃文档。
    
    返回格式：
    {
        "version": 当前版本号,
        "documents": [
            {
                "file_id": 版本内编号（从1开始）,
                "document_id": 文档ID,
                "filename": 文件名,
                ...
            }
        ]
    }
    """
    if version is None:
        max_version = db.query(func.max(DocumentMapping.version)).scalar()
        
        if max_version is None:
            return {
                "version": None,
                "documents": []
            }
        
        mappings = db.query(DocumentMapping, Document).join(
            Document, DocumentMapping.document_id == Document.id
        ).filter(
            DocumentMapping.version == max_version,
            DocumentMapping.is_active == True
        ).order_by(DocumentMapping.created_at.asc()).all()
        
        documents = []
        for file_id, (mapping, document) in enumerate(mappings, start=1):
            documents.append({
                "file_id": file_id,
                "document_id": mapping.document_id,
                "filename": mapping.filename,
                "file_path": mapping.file_path,
                "chunk_count": document.chunk_count,
                "version": mapping.version,
                "created_at": mapping.created_at.isoformat() if mapping.created_at else None,
                "updated_at": mapping.updated_at.isoformat() if mapping.updated_at else None
            })
        
        return {
            "version": max_version,
            "documents": documents
        }
    else:
        version_exists = db.query(DocumentMapping).filter(
            DocumentMapping.version == version
        ).first()
        
        if not version_exists:
            raise HTTPException(status_code=404, detail=f"版本 {version} 不存在")
        
        mappings = db.query(DocumentMapping, Document).join(
            Document, DocumentMapping.document_id == Document.id
        ).filter(
            DocumentMapping.version == version
        ).order_by(DocumentMapping.created_at.asc()).all()
        
        documents = []
        for file_id, (mapping, document) in enumerate(mappings, start=1):
            documents.append({
                "file_id": file_id,
                "document_id": mapping.document_id,
                "filename": mapping.filename,
                "file_path": mapping.file_path,
                "chunk_count": document.chunk_count,
                "version": mapping.version,
                "is_active": mapping.is_active,
                "created_at": mapping.created_at.isoformat() if mapping.created_at else None,
                "updated_at": mapping.updated_at.isoformat() if mapping.updated_at else None
            })
        
        return {
            "version": version,
            "documents": documents
        }


@router.delete("/documents/{document_id}")
async def delete_document(document_id: int, db: Session = Depends(get_db)):
    """删除文档"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    try:
        document_service.delete_document(document_id, db)
        
        if os.path.exists(document.file_path):
            os.remove(document.file_path)
        
        return {"message": "文档删除成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文档时出错: {str(e)}")

