"""
Agno Markdown切分器
使用Agno官方的MarkdownChunking进行文档切分
"""
import re
import json
import logging
from typing import List, Dict
from demo.config import settings
from .utils import extract_images_from_text, extract_structure_info

# 尝试导入Agno的MarkdownChunking和Document
try:
    from agno.knowledge.chunking.markdown import MarkdownChunking  # type: ignore
    from agno.knowledge.document.base import Document  # type: ignore
    AGNO_AVAILABLE = True
except (ImportError, ModuleNotFoundError) as e:
    AGNO_AVAILABLE = False
    logging.warning(f"Agno框架未安装，将无法使用MarkdownChunking。错误: {e}。请运行: pip install agno unstructured")
except Exception as e:
    # 捕获其他可能的异常（如依赖问题）
    AGNO_AVAILABLE = False
    logging.warning(f"Agno框架导入失败: {type(e).__name__}: {e}。请检查依赖是否完整安装。")

logger = logging.getLogger(__name__)


def split_with_markdown_chunking(content: str) -> List[Dict[str, str]]:
    """
    使用Agno的MarkdownChunking进行Markdown文档切分
    基于文档结构（标题、段落、章节）进行智能分块
    
    返回格式: List[Dict[str, str]]，每个dict包含 'content' 和 'metadata' 字段
    """
    if not AGNO_AVAILABLE:
        raise ImportError("Agno框架未安装，无法使用MarkdownChunking")
    
    try:
        # 初始化MarkdownChunking策略
        chunking_strategy = MarkdownChunking(
            chunk_size=settings.CHUNK_SIZE,
            overlap=settings.CHUNK_OVERLAP
        )
        
        # 创建Document对象（chunk方法需要Document对象，而不是字符串）
        document = Document(content=content)
        
        # 使用chunk方法切分文档
        # MarkdownChunking的chunk方法返回Document对象列表
        chunk_objects = chunking_strategy.chunk(document)
        
        # 转换为标准格式
        chunks = []
        for i, chunk_obj in enumerate(chunk_objects):
            # 提取chunk内容
            chunk_content = ""
            if hasattr(chunk_obj, 'content'):
                chunk_content = chunk_obj.content or ""
            elif hasattr(chunk_obj, 'text'):
                chunk_content = chunk_obj.text or ""
            elif isinstance(chunk_obj, str):
                chunk_content = chunk_obj
            else:
                # 尝试获取其他可能的属性
                chunk_content = str(chunk_obj)
            
            # 只跳过完全为空的内容，不进行长度限制
            if not chunk_content or not chunk_content.strip():
                continue
            
            # 提取图片信息
            images = extract_images_from_text(chunk_content)
            
            # 提取结构信息
            structure = extract_structure_info(chunk_content)
            
            # 提取标题信息
            heading_match = re.search(r'^(#{1,6})\s+(.+)', chunk_content, re.MULTILINE)
            if heading_match:
                heading_level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()
            else:
                heading_level = 0
                heading_text = ""
            
            # 构建metadata
            metadata = {
                "chunk_id": i + 1,
                "heading": heading_text,
                "heading_level": heading_level,
                "images": images,
                "structure": structure,
                "type": "markdown_chunk",
                "split_method": "markdown_chunking"
            }
            
            # 如果chunk有metadata属性，合并进去
            if hasattr(chunk_obj, 'metadata') and chunk_obj.metadata:
                if isinstance(chunk_obj.metadata, dict):
                    metadata.update(chunk_obj.metadata)
            
            chunks.append({
                "content": chunk_content,
                "metadata": json.dumps(metadata, ensure_ascii=False)
            })
        
        if chunks:
            logger.info(f"使用MarkdownChunking切分文档，生成 {len(chunks)} 个chunks")
            return chunks
        else:
            logger.warning("MarkdownChunking未生成有效chunks，将使用fallback方法")
            return []
            
    except Exception as e:
        logger.error(f"使用MarkdownChunking切分文档时出错: {str(e)}", exc_info=True)
        raise


def is_agno_available() -> bool:
    """检查Agno是否可用"""
    return AGNO_AVAILABLE

