"""
向量化工具
"""
from openai import OpenAI
from typing import List
import logging
from demo.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """向量化服务：使用API进行向量化"""
    
    def __init__(self):
        if not settings.EMBEDDING_API_KEY:
            raise ValueError("EMBEDDING_API_KEY未配置，必须提供API密钥才能使用向量化服务")
        
        try:
            self.api_client = OpenAI(
                api_key=settings.EMBEDDING_API_KEY,
                base_url=settings.EMBEDDING_API_BASE_URL if settings.EMBEDDING_API_BASE_URL else None
            )
            logger.info("Embedding API服务已初始化")
        except Exception as e:
            logger.error(f"初始化Embedding API客户端失败: {str(e)}")
            raise ValueError(f"无法初始化Embedding API客户端: {str(e)}")
    
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
    
    def encode_single(self, text: str) -> List[float]:
        """将单个文本转换为向量"""
        if not text or not text.strip():
            raise ValueError("输入文本不能为空")
        return self.encode([text])[0]

