"""
文档处理服务
"""
import os
from typing import List, Dict, Optional
from pathlib import Path
from demo.config import settings
from demo.tools import (
    embedding_service,
    milvus_service,
    split_text,
    embed_texts,
    insert_vectors,
    delete_vectors_by_document_id
)
from demo.models.schema import Document, DocumentMapping
from sqlalchemy.orm import Session
from sqlalchemy import func


class DocumentService:
    """文档处理服务"""
    
    def __init__(self):
        # 默认uploads目录
        self.upload_dir = Path("uploads")
    
    def _get_next_version(self, db: Session) -> int:
        """获取下一个知识库版本号"""
        max_version = db.query(func.max(DocumentMapping.version)).scalar()
        return (max_version or 0) + 1
    
    def _get_relative_path(self, file_path: str) -> str:
        """获取相对于uploads目录的路径"""
        file_path_obj = Path(file_path)
        upload_dir_obj = Path(self.upload_dir).resolve()
        file_path_resolved = file_path_obj.resolve()
        
        try:
            # 尝试获取相对路径
            relative_path = file_path_resolved.relative_to(upload_dir_obj)
            return str(relative_path)
        except ValueError:
            # 如果不在uploads目录下，返回绝对路径
            return str(file_path_resolved)
    
    def _is_in_upload_dir(self, file_path: str) -> bool:
        """检查文件是否在uploads目录中"""
        file_path_obj = Path(file_path).resolve()
        upload_dir_obj = Path(self.upload_dir).resolve()
        try:
            file_path_obj.relative_to(upload_dir_obj)
            return True
        except ValueError:
            return False
    
    def process_markdown_file(self, file_path: str, filename: str, db: Session, version: Optional[int] = None) -> Document:
        """处理Markdown文件：读取、切割、向量化、存储，并创建映射记录"""
        # 验证文件路径
        if not os.path.exists(file_path):
            raise ValueError(f"文件不存在: {file_path}")
        if os.path.isdir(file_path):
            raise ValueError(f"输入的是目录，不是文件: {file_path}")
        if not os.path.isfile(file_path):
            raise ValueError(f"路径不是有效的文件: {file_path}")
        
        # 读取Markdown文件
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # 尝试其他编码
            with open(file_path, 'r', encoding='gbk') as f:
                content = f.read()
        
        # 切割文档（返回Dict格式，包含content和metadata）
        chunks = split_text(content)
        
        # 检查是否有有效块
        if not chunks or len(chunks) == 0:
            raise ValueError("文档切割后没有有效内容")
        
        # 向量化（从chunks中提取content）
        embeddings = embed_texts(chunks)
        
        # 获取知识库版本号
        if version is None:
            version = self._get_next_version(db)
        
        # 保存文档记录到MySQL
        document = Document(
            filename=filename,
            file_path=file_path,
            chunk_count=len(chunks)
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        
        # 存储向量到Milvus
        insert_vectors(document.id, chunks, embeddings)
        
        # 创建文档映射记录（如果文件在uploads目录中）
        if self._is_in_upload_dir(file_path):
            relative_path = self._get_relative_path(file_path)
            mapping = DocumentMapping(
                document_id=document.id,
                filename=filename,
                file_path=relative_path,
                is_active=True,
                version=version
            )
            db.add(mapping)
            db.commit()
        
        return document
    
    def _find_markdown_files(self, path: str) -> List[str]:
        """查找路径下的所有Markdown文件（递归）"""
        md_files = []
        path_obj = Path(path)
        
        if path_obj.is_file():
            if path_obj.suffix.lower() == '.md':
                md_files.append(str(path_obj))
        elif path_obj.is_dir():
            # 递归查找所有.md文件
            md_files = [str(f) for f in path_obj.rglob('*.md') if f.is_file()]
        else:
            raise ValueError(f"路径不存在: {path}")
        
        return sorted(md_files)
    
    def process_markdown_directory(self, path: str, db: Session, version: Optional[int] = None) -> List[Dict]:
        """批量处理Markdown文件（支持单个文件或目录，目录下递归查找所有.md文件）"""
        # 查找所有Markdown文件
        md_files = self._find_markdown_files(path)
        
        if not md_files:
            raise ValueError(f"未找到Markdown文件: {path}")
        
        # 获取知识库版本号（批量处理时使用同一个版本号）
        if version is None:
            version = self._get_next_version(db)
        
        results = []
        
        for file_path in md_files:
            try:
                filename = Path(file_path).name
                document = self.process_markdown_file(file_path, filename, db, version=version)
                results.append({
                    "success": True,
                    "document_id": document.id,
                    "filename": document.filename,
                    "chunk_count": document.chunk_count,
                    "file_path": file_path
                })
            except Exception as e:
                results.append({
                    "success": False,
                    "filename": Path(file_path).name,
                    "file_path": file_path,
                    "error": str(e),
                    "chunk_count": 0
                })
        
        return results
    
    def rebuild_knowledge_base(self, path: str, db: Session) -> Dict:
        """重建知识库：清空旧映射，重新处理uploads目录中的所有MD文件"""
        # 检查路径是否存在
        path_obj = Path(path).resolve()
        if not path_obj.exists():
            raise ValueError(f"路径不存在: {path}")
        
        if not path_obj.is_dir():
            raise ValueError(f"路径不是目录: {path}")
        
        # 获取新的版本号
        new_version = self._get_next_version(db)
        
        # 将所有旧映射标记为非活跃
        db.query(DocumentMapping).update({"is_active": False})
        db.commit()
        
        # 删除Milvus中的所有向量（清空知识库）
        from pymilvus import utility
        if utility.has_collection(milvus_service.collection_name):
            utility.drop_collection(milvus_service.collection_name)
            # 重新创建集合
            milvus_service._ensure_collection()
        
        # 重新处理目录中的所有MD文件
        results = self.process_markdown_directory(str(path), db, version=new_version)
        
        success_count = sum(1 for r in results if r.get('success', False))
        fail_count = len(results) - success_count
        total_chunks = sum(r.get('chunk_count', 0) for r in results if r.get('success', False))
        
        return {
            "message": "知识库重建完成",
            "version": new_version,
            "total_files": len(results),
            "success_count": success_count,
            "fail_count": fail_count,
            "total_chunks": total_chunks,
            "results": results
        }
    
    def delete_document(self, document_id: int, db: Session):
        """删除文档"""
        # 从Milvus删除向量
        delete_vectors_by_document_id(document_id)
        
        # 将映射标记为非活跃
        db.query(DocumentMapping).filter(
            DocumentMapping.document_id == document_id
        ).update({"is_active": False})
        
        # 从MySQL删除记录
        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            db.delete(document)
            db.commit()

