"""
向量数据库工具：Milvus
"""
import json
from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility
from typing import List, Dict
import logging
from demo.config import settings

logger = logging.getLogger(__name__)

# 全局连接状态管理
_connection_initialized = False
_collection_loaded = {}


class MilvusService:
    """Milvus向量数据库服务（优化连接复用）"""
    
    def __init__(self):
        self.collection_name = settings.MILVUS_COLLECTION_NAME
        self.dimension = settings.EMBEDDING_DIMENSION
        self._collection_loaded = False  # 实例级别的加载状态
        self._connect()
        self._ensure_collection()
    
    def _connect(self):
        """连接Milvus（复用连接）"""
        global _connection_initialized
        
        # 检查连接是否已存在
        try:
            existing_connections = connections.list_connections()
            if "default" in existing_connections:
                logger.debug("复用现有Milvus连接")
                _connection_initialized = True
                return
        except Exception:
            pass
        
        # 创建新连接
        try:
            connections.connect(
                alias="default",
                host=settings.MILVUS_HOST,
                port=settings.MILVUS_PORT
            )
            _connection_initialized = True
            logger.info("Milvus连接已建立")
        except Exception as e:
            logger.error(f"Milvus连接失败: {str(e)}")
            raise
    
    def _ensure_collection(self):
        """确保集合存在，不存在则创建"""
        # 定义必需的字段列表
        required_fields = {"id", "document_id", "chunk_index", "content", "metadata", "embedding"}
        
        if utility.has_collection(self.collection_name):
            self.collection = Collection(self.collection_name)
            # 检查字段是否存在
            existing_field_names = {field.name for field in self.collection.schema.fields}
            missing_fields = required_fields - existing_field_names
            
            # 查找embedding字段
            embedding_field = None
            for field in self.collection.schema.fields:
                if field.name == "embedding":
                    embedding_field = field
                    break
            existing_dim = embedding_field.params.get('dim') if embedding_field else None
            
            # 如果缺少必需字段或维度不匹配，删除旧集合并重新创建
            if missing_fields or (existing_dim and existing_dim != self.dimension):
                if missing_fields:
                    logger.warning(
                        f"集合缺少必需字段: {missing_fields}，"
                        f"正在删除旧集合并重新创建..."
                    )
                if existing_dim and existing_dim != self.dimension:
                    logger.warning(
                        f"集合维度({existing_dim})与API维度({self.dimension})不匹配，"
                        f"正在删除旧集合并重新创建..."
                    )
                utility.drop_collection(self.collection_name)
        
        if not utility.has_collection(self.collection_name):
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="document_id", dtype=DataType.INT64, description="文档ID"),
                FieldSchema(name="chunk_index", dtype=DataType.INT64, description="文档块索引"),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535, description="文档内容"),
                FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=2048, description="元数据（JSON格式）"),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension, description="向量")
            ]
            
            schema = CollectionSchema(fields=fields, description="知识库向量集合")
            self.collection = Collection(name=self.collection_name, schema=schema)
            
            index_params = {
                "metric_type": "L2",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024}
            }
            self.collection.create_index(field_name="embedding", index_params=index_params)
            logger.info(f"集合 '{self.collection_name}' 已创建，维度: {self.dimension}")
        else:
            self.collection = Collection(self.collection_name)
    
    def insert(self, document_id: int, chunks: List[Dict[str, str]], embeddings: List[List[float]]):
        """
        插入向量数据
        chunks: List[Dict[str, str]]，每个dict包含 'content' 和 'metadata' 字段
        """
        if not chunks or not embeddings:
            raise ValueError("chunks和embeddings不能为空")
        if len(chunks) != len(embeddings):
            raise ValueError(f"chunks数量({len(chunks)})与embeddings数量({len(embeddings)})不匹配")
        
        if embeddings and len(embeddings[0]) != self.dimension:
            actual_dim = len(embeddings[0])
            logger.warning(
                f"向量维度({actual_dim})与集合维度({self.dimension})不匹配，"
                f"正在删除旧集合并重建为{actual_dim}维度..."
            )
            
            if utility.has_collection(self.collection_name):
                utility.drop_collection(self.collection_name)
                logger.info(f"已删除旧集合 '{self.collection_name}'")
            
            self.dimension = actual_dim
            self._ensure_collection()
            logger.info(f"集合已重建，新维度: {self.dimension}")
        
        data = []
        for i, (chunk_dict, embedding) in enumerate(zip(chunks, embeddings)):
            # 支持新旧两种格式：Dict格式（新）或str格式（旧，向后兼容）
            if isinstance(chunk_dict, dict):
                content = chunk_dict.get("content", "")
                metadata = chunk_dict.get("metadata", "{}")
            else:
                # 向后兼容：如果传入的是字符串
                content = chunk_dict
                metadata = "{}"
            
            if not content or not content.strip():
                continue
            
            data.append({
                "document_id": document_id,
                "chunk_index": i,
                "content": content,
                "metadata": metadata,
                "embedding": embedding
            })
        
        if data:
            self.collection.insert(data)
            self.collection.flush()
    
    def search(self, query_embedding: List[float], top_k: int = None) -> List[Dict]:
        """向量检索（优化：避免重复load）"""
        if top_k is None:
            top_k = settings.TOP_K
        
        if len(query_embedding) != self.dimension:
            raise ValueError(
                f"查询向量维度({len(query_embedding)})与集合维度({self.dimension})不匹配"
            )
        
        # 优化：只在必要时加载collection（避免重复load）
        global _collection_loaded
        collection_key = self.collection_name
        
        # 检查collection是否已加载（使用全局和实例状态）
        if not self._collection_loaded or collection_key not in _collection_loaded:
            try:
                # 尝试获取collection状态，如果未加载会抛出异常
                # 使用has_index()方法检查，这是更可靠的方式
                if not self.collection.has_index():
                    # 如果没有索引，说明collection可能未正确初始化
                    logger.warning(f"Collection '{self.collection_name}' 没有索引，可能需要重新创建")
                else:
                    # 尝试访问num_entities来检查是否已加载
                    try:
                        _ = self.collection.num_entities
                        # 如果能访问，说明已加载
                        self._collection_loaded = True
                        _collection_loaded[collection_key] = True
                        logger.debug(f"Collection '{self.collection_name}' 已加载")
                    except Exception:
                        # 如果访问失败，需要加载
                        self.collection.load()
                        self._collection_loaded = True
                        _collection_loaded[collection_key] = True
                        logger.debug(f"Collection '{self.collection_name}' 已加载到内存")
            except Exception as e:
                # 如果检查过程出错，尝试加载
                logger.warning(f"检查collection状态时出错: {str(e)}，尝试加载collection")
                try:
                    self.collection.load()
                    self._collection_loaded = True
                    _collection_loaded[collection_key] = True
                    logger.debug(f"Collection '{self.collection_name}' 已加载到内存")
                except Exception as load_error:
                    logger.error(f"加载collection失败: {str(load_error)}")
                    raise
        
        # 根据top_k动态调整nprobe（优化搜索性能）
        nprobe = min(10, max(1, top_k * 2))  # nprobe范围：1-10
        
        search_params = {
            "metric_type": "L2",
            "params": {"nprobe": nprobe}
        }
        
        results = self.collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            output_fields=["document_id", "chunk_index", "content", "metadata"]
        )
        
        if not results or len(results) == 0:
            return []
        
        ret = []
        for hit in results[0]:
            entity = hit.entity
            metadata_str = entity.get("metadata", "{}")
            try:
                metadata = json.loads(metadata_str) if metadata_str else {}
            except:
                metadata = {}
            
            ret.append({
                "document_id": entity.get("document_id"),
                "chunk_index": entity.get("chunk_index"),
                "content": entity.get("content"),
                "metadata": metadata,
                "distance": hit.distance,
                "score": 1 / (1 + hit.distance) if hit.distance > 0 else 1.0
            })
        return ret
    
    def delete_by_document_id(self, document_id: int):
        """根据文档ID删除向量"""
        expr = f"document_id == {document_id}"
        self.collection.delete(expr)
        self.collection.flush()

