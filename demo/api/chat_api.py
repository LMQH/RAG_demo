"""
聊天 API 接口
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from demo.models.schema import get_db, Conversation
from demo.models.message import ChatRequest
from demo.services.conversation_memory import ConversationService
from demo.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/stream")
async def chat_stream(request: ChatRequest, db: Session = Depends(get_db)):
    """流式对话接口
    
    支持场景参数：
    - 不传或传 None：默认企业级客服助手
    - 'technical'：技术支持场景
    - 'sales'：销售咨询场景
    """
    try:
        stream_generator = ChatService.create_chat_stream(
            message=request.message,
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            db=db,
            scenario=request.scenario
        )
        
        return StreamingResponse(
            stream_generator,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理请求时出错: {str(e)}")


@router.get("/conversations/{user_id}")
async def get_conversations(user_id: str, db: Session = Depends(get_db)):
    """获取用户的对话列表"""
    conversations = db.query(Conversation).filter(
        Conversation.user_id == user_id
    ).order_by(Conversation.updated_at.desc()).all()
    
    return [{
        "id": conv.id,
        "title": conv.title,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at
    } for conv in conversations]


@router.get("/messages/{conversation_id}")
async def get_messages(conversation_id: int, db: Session = Depends(get_db)):
    """获取对话消息列表"""
    messages = ConversationService.get_messages(db, conversation_id, limit=100)
    return [{
        "id": msg.id,
        "role": msg.role,
        "content": msg.content,
        "created_at": msg.created_at
    } for msg in messages]

