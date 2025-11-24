"""
文档处理工具
提供文档切分、向量化和存储的统一接口
"""
import logging
from typing import List, Dict
from demo.tools.chunking import split_with_markdown_chunking, is_agno_available, split_markdown_by_structure

logger = logging.getLogger(__name__)

# 延迟导入避免循环依赖
def _get_services():
    from demo.tools.embedding import EmbeddingService
    from demo.tools.vector_db import MilvusService
    return EmbeddingService(), MilvusService()

_embedding_service, _milvus_service = _get_services()


def split_text(content: str) -> List[Dict[str, str]]:
    """
    文档切分策略：优先使用Agno的MarkdownChunking，失败则使用通用Markdown结构切分作为备用
    
    Args:
        content: Markdown文档内容
    
    返回格式: List[Dict[str, str]]，每个dict包含 'content' 和 'metadata' 字段
    """
    # 1. 优先使用MarkdownChunking（如果可用）
    if is_agno_available():
        try:
            markdown_chunks = split_with_markdown_chunking(content)
            if markdown_chunks and len(markdown_chunks) > 0:
                return markdown_chunks
        except Exception as e:
            logger.warning(f"MarkdownChunking切分失败，使用备用方法: {str(e)}")
            # 继续使用备用方法
    else:
        logger.warning("Agno框架未安装，使用备用Markdown结构切分方法")
    
    # 2. 备用方法：使用通用Markdown结构切分
    try:
        # 检查内容是否为空
        if not content or not content.strip():
            logger.error("文档内容为空，无法切分")
            return []
        
        md_chunks = split_markdown_by_structure(content)
        logger.debug(f"结构切分返回了 {len(md_chunks) if md_chunks else 0} 个chunks")
        
        if md_chunks and len(md_chunks) > 0:
            # 只过滤掉完全为空的内容，不进行长度限制
            filtered_chunks = [
                chunk for chunk in md_chunks 
                if chunk.get("content") and chunk["content"].strip()
            ]
            logger.debug(f"过滤后剩余 {len(filtered_chunks)} 个chunks（过滤前 {len(md_chunks)} 个，仅过滤空内容）")
            
            if filtered_chunks:
                logger.info(f"使用通用Markdown结构切分，生成 {len(filtered_chunks)} 个chunks")
                return filtered_chunks
            else:
                logger.warning(f"所有chunks都为空（过滤前 {len(md_chunks)} 个chunks）")
        else:
            logger.warning(f"结构切分返回空列表或None")
    except Exception as e:
        logger.error(f"通用Markdown结构切分失败: {str(e)}", exc_info=True)
    
    # 如果所有方法都失败，返回空列表
    logger.error("所有文档切分方法均失败，返回空列表")
    return []


def embed_texts(chunks: List[Dict[str, str]]) -> List[List[float]]:
    """向量化文本列表（支持Dict格式，提取content字段）"""
    # 提取content字段
    texts = []
    for chunk in chunks:
        if isinstance(chunk, dict):
            texts.append(chunk.get("content", ""))
        else:
            # 向后兼容：如果传入的是字符串
            texts.append(chunk)
    return _embedding_service.encode(texts)


def embed_single_text(text: str) -> List[float]:
    """向量化单个文本"""
    return _embedding_service.encode_single(text)


def insert_vectors(document_id: int, chunks: List[Dict[str, str]], embeddings: List[List[float]]):
    """插入向量到向量数据库（支持Dict格式的chunks）"""
    _milvus_service.insert(document_id, chunks, embeddings)


def delete_vectors_by_document_id(document_id: int):
    """根据文档ID删除向量"""
    _milvus_service.delete_by_document_id(document_id)

