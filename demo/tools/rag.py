"""
RAG检索工具
"""
import json
from typing import List, Dict
from demo.config import settings

# 延迟导入避免循环依赖
def _get_services():
    from demo.tools.embedding import EmbeddingService
    from demo.tools.vector_db import MilvusService
    return EmbeddingService(), MilvusService()

_embedding_service, _milvus_service = _get_services()


def retrieve_documents(query: str, top_k: int = None) -> List[Dict]:
    """从知识库中检索相关文档"""
    if not query or not query.strip():
        return []
    
    query_embedding = _embedding_service.encode_single(query)
    
    if top_k is None:
        top_k = settings.TOP_K
    
    results = _milvus_service.search(query_embedding, top_k=top_k)
    return results


def build_rag_context(retrieved_docs: List[Dict]) -> str:
    """构建RAG上下文，包含图片信息"""
    if not retrieved_docs:
        return ""
    
    context_parts = []
    context_parts.append("=== 知识库文档内容（请严格按照以下内容回答）===\n")
    
    for i, doc in enumerate(retrieved_docs, 1):
        metadata = doc.get('metadata', {})
        content = doc.get('content', '')
        
        # 解析元数据（可能是字符串或字典）
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}
        
        # 提取图片信息
        images = metadata.get('images', [])
        
        # 构建文档片段标题
        if isinstance(metadata, dict) and metadata.get('split_method') == 'hierarchical_markdown_parser':
            # 使用层级解析器切分的文档，显示完整层级路径
            hierarchy_titles = metadata.get('hierarchy_titles', '')
            title = metadata.get('title', '')
            if hierarchy_titles:
                context_parts.append(f"\n【文档片段{i}】{hierarchy_titles}\n{content}\n")
            elif title:
                context_parts.append(f"\n【文档片段{i}】{title}\n{content}\n")
            else:
                context_parts.append(f"\n【文档片段{i}】\n{content}\n")
        elif isinstance(metadata, dict) and metadata.get('main_heading'):
            main_heading = metadata.get('main_heading', '')
            sub_heading = metadata.get('sub_heading', '')
            if sub_heading:
                context_parts.append(f"\n【文档片段{i}】{main_heading} > {sub_heading}\n{content}\n")
            else:
                context_parts.append(f"\n【文档片段{i}】{main_heading}\n{content}\n")
        else:
            context_parts.append(f"\n【文档片段{i}】\n{content}\n")
        
        # 添加图片信息
        if images and len(images) > 0:
            context_parts.append(f"\n【图片信息{i}】")
            for j, img in enumerate(images, 1):
                img_alt = img.get('alt', '图片')
                img_url = img.get('url', '')
                img_title = img.get('title', '')
                if img_title:
                    context_parts.append(f"  图片{j}: {img_alt} - {img_url} (标题: {img_title})")
                else:
                    context_parts.append(f"  图片{j}: {img_alt} - {img_url}")
            context_parts.append("")
    
    context_parts.append("\n=== 重要提示：必须严格按照上述文档内容回答，不能使用文档外的信息 ===\n")
    context_parts.append("=== 如果文档中包含图片，请在回答时提及图片内容或提供图片链接 ===\n")
    
    return "\n".join(context_parts)


# 向后兼容的类接口
class RAGService:
    """RAG检索服务（向后兼容）"""
    
    @staticmethod
    def retrieve(query: str, top_k: int = None) -> List[Dict]:
        """RAG检索：将查询向量化，然后检索相关文档"""
        return retrieve_documents(query, top_k)
    
    @staticmethod
    def build_context(retrieved_docs: List[Dict]) -> str:
        """构建上下文"""
        return build_rag_context(retrieved_docs)

