"""
应用配置
"""
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""
    
    # API配置
    API_TITLE: str = "RAG Demo API"
    API_VERSION: str = "1.0.0"
    
    # MySQL配置
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "rag_demo"
    
    # Milvus配置
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION_NAME: str = "knowledge_base"
    
    # OpenAI配置（作为备用推理服务）
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: Optional[str] = None
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    
    # 华为云推理服务配置（优先使用）
    HUAWEI_API_KEY: str = "RHit7qnYZpdwXePYiPr6F0vVfT8zAWwNN4IMrkM2M9sZE00vo76krCCI-6FwhlusY6i1lju_gFm7ObqUxb-ENw"
    HUAWEI_API_URL: str = "https://api.modelarts-maas.com/v1/chat/completions"
    HUAWEI_MODEL: str = "deepseek-v3.2-exp"
    
    # 向量化API配置（必需）
    EMBEDDING_API_KEY: Optional[str] = None
    EMBEDDING_API_BASE_URL: Optional[str] = None
    EMBEDDING_API_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1024
    
    # 文档处理配置
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    
    # RAG配置
    TOP_K: int = 3
    
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()

