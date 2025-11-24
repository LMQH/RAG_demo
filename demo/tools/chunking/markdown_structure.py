"""
通用Markdown结构切分器
基于文档标题结构进行切分，作为备用切分方法
"""
import re
import json
import logging
from typing import List, Dict
from langchain_text_splitters import RecursiveCharacterTextSplitter
from demo.config import settings
from .utils import extract_images_from_text, extract_structure_info

logger = logging.getLogger(__name__)


def split_markdown_by_structure(content: str) -> List[Dict[str, str]]:
    """
    通用的Markdown结构切分方法
    支持各种格式：标题、段落、列表、代码块等
    
    返回格式: List[Dict[str, str]]，每个dict包含 'content' 和 'metadata' 字段
    """
    # 检查内容是否为空
    if not content or not content.strip():
        logger.warning("文档内容为空，无法切分")
        return []
    
    chunks = []
    content_length = len(content)
    logger.debug(f"开始切分文档，文档长度: {content_length} 字符")
    
    # 按一级标题分割（最顶层结构）
    top_level_pattern = r'(^#\s+.+?)(?=^#\s+|$)'
    top_level_matches = list(re.finditer(top_level_pattern, content, re.MULTILINE | re.DOTALL))
    logger.debug(f"找到一级标题数量: {len(top_level_matches)}")
    
    if not top_level_matches:
        # 如果没有一级标题，尝试按二级标题分割
        top_level_pattern = r'(^##\s+.+?)(?=^##\s+|$)'
        top_level_matches = list(re.finditer(top_level_pattern, content, re.MULTILINE | re.DOTALL))
        logger.debug(f"找到二级标题数量: {len(top_level_matches)}")
    
    # 用于处理超大块的递归切分器
    recursive_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=[
            "\n\n### ",  # 三级标题
            "\n\n#### ",  # 四级标题
            "\n\n##### ",  # 五级标题
            "\n\n###### ",  # 六级标题
            "\n\n",     # 段落
            "\n",       # 换行
            " ",        # 空格
            ""          # 字符
        ],
        length_function=len,
    )
    
    # 如果没有找到一级或二级标题，使用递归切分器直接切分整个文档
    if not top_level_matches:
        logger.warning("文档没有一级或二级标题，使用递归切分器进行切分")
        try:
            sub_chunks = recursive_splitter.split_text(content)
            logger.debug(f"递归切分器生成了 {len(sub_chunks)} 个chunks")
            # 只过滤掉完全为空的内容，不进行长度限制
            for i, sub_chunk in enumerate(sub_chunks):
                if sub_chunk and sub_chunk.strip():
                    chunk_images = extract_images_from_text(sub_chunk)
                    chunk_structure = extract_structure_info(sub_chunk)
                    chunks.append({
                        "content": sub_chunk,
                        "metadata": json.dumps({
                            "main_heading": "",
                            "heading_level": 0,
                            "images": chunk_images,
                            "structure": chunk_structure,
                            "type": "paragraph",
                            "part_index": i,
                            "split_method": "recursive_fallback"
                        }, ensure_ascii=False)
                    })
            logger.info(f"fallback切分完成，生成 {len(chunks)} 个有效chunks（过滤前共 {len(sub_chunks)} 个，仅过滤空内容）")
            if not chunks:
                logger.warning(f"fallback切分后没有有效chunks，所有chunks都为空（文档总长度: {content_length}字符）")
            return chunks
        except Exception as e:
            logger.error(f"递归切分器执行失败: {str(e)}", exc_info=True)
            return []
    
    for match in top_level_matches:
        block = match.group(1).strip()
        
        # 跳过空块
        if not block:
            continue
        
        # 提取主标题
        title_match = re.match(r'^(#{1,6})\s+(.+)', block, re.MULTILINE)
        if title_match:
            heading_level = len(title_match.group(1))
            heading_text = title_match.group(2).strip()
        else:
            heading_level = 0
            heading_text = ""
        
        # 提取图片信息
        images = extract_images_from_text(block)
        
        # 提取结构信息
        structure = extract_structure_info(block)
        
        # 如果块太大，进一步分割
        if len(block) > settings.CHUNK_SIZE:
            # 尝试按二级标题分割
            sub_pattern = r'(^##\s+.+?)(?=^##\s+|$)'
            sub_matches = list(re.finditer(sub_pattern, block, re.MULTILINE | re.DOTALL))
            
            if sub_matches:
                for sub_match in sub_matches:
                    sub_block = sub_match.group(1).strip()
                    sub_images = extract_images_from_text(sub_block)
                    sub_structure = extract_structure_info(sub_block)
                    
                    # 提取子标题
                    sub_title_match = re.match(r'^##\s+(.+)', sub_block, re.MULTILINE)
                    sub_title = sub_title_match.group(1).strip() if sub_title_match else ""
                    
                    if len(sub_block) > settings.CHUNK_SIZE:
                        # 继续递归切分
                        sub_chunks = recursive_splitter.split_text(sub_block)
                        for i, sub_chunk in enumerate(sub_chunks):
                            if sub_chunk and sub_chunk.strip():
                                chunk_images = extract_images_from_text(sub_chunk)
                                chunks.append({
                                    "content": sub_chunk,
                                    "metadata": json.dumps({
                                        "main_heading": heading_text,
                                        "sub_heading": sub_title,
                                        "heading_level": heading_level,
                                        "images": chunk_images,
                                        "structure": sub_structure,
                                        "type": "section_part",
                                        "part_index": i,
                                        "split_method": "markdown_structure+recursive"
                                    }, ensure_ascii=False)
                                })
                    else:
                        chunks.append({
                            "content": sub_block,
                            "metadata": json.dumps({
                                "main_heading": heading_text,
                                "sub_heading": sub_title,
                                "heading_level": heading_level,
                                "images": sub_images,
                                "structure": sub_structure,
                                "type": "section",
                                "split_method": "markdown_structure"
                            }, ensure_ascii=False)
                        })
            else:
                # 没有子标题，直接递归切分
                sub_chunks = recursive_splitter.split_text(block)
                for i, sub_chunk in enumerate(sub_chunks):
                    if sub_chunk and sub_chunk.strip():
                        chunk_images = extract_images_from_text(sub_chunk)
                        chunks.append({
                            "content": sub_chunk,
                            "metadata": json.dumps({
                                "main_heading": heading_text,
                                "heading_level": heading_level,
                                "images": chunk_images,
                                "structure": structure,
                                "type": "section_part",
                                "part_index": i,
                                "split_method": "markdown_structure+recursive"
                            }, ensure_ascii=False)
                        })
        else:
            # 块大小合适，直接作为一个chunk
            chunks.append({
                "content": block,
                "metadata": json.dumps({
                    "main_heading": heading_text,
                    "heading_level": heading_level,
                    "images": images,
                    "structure": structure,
                    "type": "section",
                    "split_method": "markdown_structure"
                }, ensure_ascii=False)
            })
    
    logger.info(f"结构切分完成，生成 {len(chunks)} 个chunks")
    if not chunks:
        logger.warning("结构切分后没有生成任何chunks，可能是文档格式问题或内容太短")
    return chunks

