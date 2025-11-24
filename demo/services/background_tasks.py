"""
后台任务处理
"""
import os
import logging
from sqlalchemy.orm import Session
from demo.models.schema import SessionLocal
from demo.services.document_service import DocumentService

logger = logging.getLogger(__name__)
document_service = DocumentService()


def process_document_background(file_path: str, filename: str, version: int):
    """后台任务：处理单个文档（切割、向量化、存储）"""
    db = SessionLocal()
    try:
        logger.info(f"开始处理文档: {filename} (版本: {version})")
        document = document_service.process_markdown_file(
            file_path, filename, db, version=version
        )
        logger.info(f"文档处理成功: {filename}, document_id={document.id}, chunks={document.chunk_count}")
    except Exception as e:
        logger.error(f"处理文档失败: {filename}, 错误: {str(e)}")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"已删除失败的文件: {file_path}")
            except Exception as cleanup_error:
                logger.error(f"删除文件失败: {file_path}, 错误: {str(cleanup_error)}")
        raise
    finally:
        db.close()


def rebuild_knowledge_base_background(path: str):
    """后台任务：重建知识库"""
    db = SessionLocal()
    try:
        logger.info(f"开始重建知识库: {path}")
        result = document_service.rebuild_knowledge_base(path, db)
        logger.info(f"知识库重建完成: {result.get('message', '')}")
    except Exception as e:
        logger.error(f"重建知识库失败: {str(e)}")
        raise
    finally:
        db.close()

