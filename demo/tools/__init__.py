"""
工具层：可被Agent调用的工具函数
"""
from .vector_db import MilvusService
from .embedding import EmbeddingService
from .llm import InferenceService
from .rag import retrieve_documents, build_rag_context, RAGService
from .document import (
    split_text,
    embed_texts,
    embed_single_text,
    insert_vectors,
    delete_vectors_by_document_id
)

# 全局服务实例（向后兼容）
milvus_service = MilvusService()
embedding_service = EmbeddingService()
inference_service = InferenceService()

__all__ = [
    # 服务类
    'MilvusService',
    'EmbeddingService',
    'InferenceService',
    # 全局服务实例
    'milvus_service',
    'embedding_service',
    'inference_service',
    # RAG工具
    'retrieve_documents',
    'build_rag_context',
    'RAGService',
    # 文档工具
    'split_text',
    'embed_texts',
    'embed_single_text',
    'insert_vectors',
    'delete_vectors_by_document_id',
]

