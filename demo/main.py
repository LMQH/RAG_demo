"""
FastAPI主应用定义
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from demo.config import settings
from demo.models.schema import init_db
from demo.api import chat_api
from demo.api.admin import router as admin_router

# 创建FastAPI应用
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该设置具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat_api.router)
app.include_router(admin_router)


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化数据库"""
    init_db()


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "RAG Demo API",
        "version": settings.API_VERSION,
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok"}

