"""
向量化工具
"""
from openai import OpenAI, AsyncOpenAI
from typing import List, Dict
import logging
import hashlib
from demo.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """向量化服务：使用API进行向量化，支持缓存"""
    
    def __init__(self, cache_size: int = 1000):
        if not settings.EMBEDDING_API_KEY:
            raise ValueError("EMBEDDING_API_KEY未配置，必须提供API密钥才能使用向量化服务")
        
        try:
            # 同步客户端（向后兼容）
            self.api_client = OpenAI(
                api_key=settings.EMBEDDING_API_KEY,
                base_url=settings.EMBEDDING_API_BASE_URL if settings.EMBEDDING_API_BASE_URL else None
            )
            # 异步客户端
            self.async_api_client = AsyncOpenAI(
                api_key=settings.EMBEDDING_API_KEY,
                base_url=settings.EMBEDDING_API_BASE_URL if settings.EMBEDDING_API_BASE_URL else None
            )
            
            # 向量化缓存：key为文本的MD5哈希，value为向量
            self._cache: Dict[str, List[float]] = {}
            self._cache_size = cache_size
            logger.info(f"Embedding API服务已初始化（同步和异步），缓存大小: {cache_size}")
        except Exception as e:
            logger.error(f"初始化Embedding API客户端失败: {str(e)}")
            raise ValueError(f"无法初始化Embedding API客户端: {str(e)}")
    
    def _get_cache_key(self, text: str) -> str:
        """生成缓存键"""
        # 使用文本内容和模型名称生成唯一键
        cache_input = f"{settings.EMBEDDING_API_MODEL}:{text}"
        return hashlib.md5(cache_input.encode('utf-8')).hexdigest()
    
    def _clean_cache_if_needed(self):
        """如果缓存过大，清理最旧的条目（FIFO策略）"""
        if len(self._cache) >= self._cache_size:
            # 删除最旧的条目（简单实现：删除前一半）
            keys_to_remove = list(self._cache.keys())[:self._cache_size // 2]
            for key in keys_to_remove:
                del self._cache[key]
            logger.debug(f"清理了 {len(keys_to_remove)} 个缓存条目")
    
    def encode(self, texts: List[str]) -> List[List[float]]:
        """将文本列表转换为向量列表"""
        if not texts:
            return []
        
        try:
            response = self.api_client.embeddings.create(
                model=settings.EMBEDDING_API_MODEL,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            error_msg = str(e)
            logger.error(f"API向量化失败: {error_msg}")
            raise ValueError(f"向量化失败: {error_msg}")
    
    # ========== 异步方法 ==========
    
    async def encode_async(self, texts: List[str]) -> List[List[float]]:
        """异步批量向量化文本列表"""
        if not texts:
            return []
        
        try:
            # 分批处理，避免单次请求过大
            batch_size = 100
            results = []
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i+batch_size]
                response = await self.async_api_client.embeddings.create(
                    model=settings.EMBEDDING_API_MODEL,
                    input=batch
                )
                results.extend([item.embedding for item in response.data])
            
            return results
        except Exception as e:
            error_msg = str(e)
            logger.error(f"API异步向量化失败: {error_msg}")
            raise ValueError(f"异步向量化失败: {error_msg}")
    
    async def encode_single_async(self, text: str, use_cache: bool = True) -> List[float]:
        """异步将单个文本转换为向量（支持缓存）"""
        if not text or not text.strip():
            raise ValueError("输入文本不能为空")
        
        # 检查缓存
        if use_cache:
            cache_key = self._get_cache_key(text)
            if cache_key in self._cache:
                logger.debug(f"向量化缓存命中: {text[:50]}...")
                return self._cache[cache_key]
        
        # 调用API向量化
        result = await self.encode_async([text])
        embedding = result[0] if result else []
        
        # 存入缓存
        if use_cache and embedding:
            self._clean_cache_if_needed()
            cache_key = self._get_cache_key(text)
            self._cache[cache_key] = embedding
            logger.debug(f"向量化结果已缓存: {text[:50]}...")
        
        return embedding
    
    def encode_single(self, text: str, use_cache: bool = True) -> List[float]:
        """将单个文本转换为向量（支持缓存）"""
        if not text or not text.strip():
            raise ValueError("输入文本不能为空")
        
        # 检查缓存
        if use_cache:
            cache_key = self._get_cache_key(text)
            if cache_key in self._cache:
                logger.debug(f"向量化缓存命中: {text[:50]}...")
                return self._cache[cache_key]
        
        # 调用API向量化
        result = self.encode([text])
        embedding = result[0] if result else []
        
        # 存入缓存
        if use_cache and embedding:
            self._clean_cache_if_needed()
            cache_key = self._get_cache_key(text)
            self._cache[cache_key] = embedding
            logger.debug(f"向量化结果已缓存: {text[:50]}...")
        
        return embedding

