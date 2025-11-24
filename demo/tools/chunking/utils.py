"""
文档切分工具函数
提供切分过程中使用的共享辅助函数
"""
import re
from typing import List, Dict


def extract_images_from_text(text: str) -> List[Dict[str, str]]:
    """
    从文本中提取Markdown图片信息
    支持格式：
    - ![alt](url)
    - ![alt](url "title")
    - ![alt text](url)
    """
    images = []
    # 匹配Markdown图片语法：![alt](url) 或 ![alt](url "title")
    pattern = r'!\[([^\]]*)\]\(([^\)]+)(?:\s+"([^"]+)")?\)'
    
    for match in re.finditer(pattern, text):
        alt_text = match.group(1) or "图片"
        url = match.group(2).strip()
        title = match.group(3) if match.group(3) else ""
        
        images.append({
            "alt": alt_text,
            "url": url,
            "title": title,
            "markdown": match.group(0)  # 保留原始Markdown格式
        })
    
    return images


def extract_structure_info(text: str) -> Dict[str, any]:
    """
    提取文本的结构信息（标题、列表等）
    """
    structure = {
        "headings": [],
        "has_lists": False,
        "has_code_blocks": False
    }
    
    # 提取标题
    heading_pattern = r'^(#{1,6})\s+(.+)$'
    for match in re.finditer(heading_pattern, text, re.MULTILINE):
        level = len(match.group(1))
        text_content = match.group(2).strip()
        structure["headings"].append({
            "level": level,
            "text": text_content
        })
    
    # 检查是否有列表
    if re.search(r'^[\s]*[-*+]\s+', text, re.MULTILINE) or re.search(r'^[\s]*\d+\.\s+', text, re.MULTILINE):
        structure["has_lists"] = True
    
    # 检查是否有代码块
    if re.search(r'```', text):
        structure["has_code_blocks"] = True
    
    return structure

