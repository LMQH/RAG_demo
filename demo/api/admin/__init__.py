"""
管理员 API 路由统一导出
"""
from fastapi import APIRouter
from demo.api.admin import upload_api, document_api, version_api, knowledge_base_api, status_api

# 创建主路由
router = APIRouter()

# 包含所有子路由
router.include_router(upload_api.router)
router.include_router(document_api.router)
router.include_router(version_api.router)
router.include_router(knowledge_base_api.router)
router.include_router(status_api.router)

