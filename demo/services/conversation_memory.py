"""
对话记录存储服务
"""
from sqlalchemy.orm import Session
from demo.models.schema import Conversation, Message
from typing import Optional, List
from datetime import datetime


class ConversationService:
    """对话服务"""
    
    @staticmethod
    def create_conversation(db: Session, user_id: str, title: Optional[str] = None) -> Conversation:
        """创建对话"""
        conversation = Conversation(
            user_id=user_id,
            title=title or f"对话_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation
    
    @staticmethod
    def get_conversation(db: Session, conversation_id: int) -> Optional[Conversation]:
        """获取对话"""
        return db.query(Conversation).filter(Conversation.id == conversation_id).first()
    
    @staticmethod
    def add_message(db: Session, conversation_id: int, role: str, content: str) -> Message:
        """添加消息"""
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        return message
    
    @staticmethod
    def get_messages(db: Session, conversation_id: int, limit: int = 10) -> List[Message]:
        """获取对话消息"""
        return db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at.asc()).limit(limit).all()
    
    @staticmethod
    def get_last_n_rounds(db: Session, conversation_id: int, n_rounds: int = 5, exclude_message_id: Optional[int] = None) -> List[Message]:
        """
        获取最后N轮对话，包括不完整的轮次
        
        优先获取完整的轮次（user + assistant），但如果某轮只有user消息（assistant缺失），也会被包含。
        这样可以确保即使因为网络或API问题导致assistant回复失败，用户之前的消息仍能被包含在历史上下文中。
        
        Args:
            db: 数据库会话
            conversation_id: 对话ID
            n_rounds: 要获取的轮数
            exclude_message_id: 要排除的消息ID（通常是刚保存的当前用户消息）
        
        Returns:
            按时间顺序排列的消息列表，包含完整的轮次（user + assistant）和不完整的轮次（只有user）
        """
        # 获取所有消息（从旧到新）
        all_messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at.asc()).all()
        
        # 排除指定的消息（通常是刚保存的当前用户消息）
        if exclude_message_id:
            all_messages = [msg for msg in all_messages if msg.id != exclude_message_id]
        
        if not all_messages:
            return []
        
        # 找出所有user消息的索引位置
        user_indices = [i for i, msg in enumerate(all_messages) if msg.role == 'user']
        
        if not user_indices:
            return []
        
        # 获取最后N条user消息的索引
        last_n_user_indices = user_indices[-n_rounds:] if len(user_indices) > n_rounds else user_indices
        
        # 构建结果：对于每个user消息，如果有对应的assistant，则都包含
        result = []
        used_indices = set()  # 记录已使用的消息索引，避免重复添加
        
        for user_idx in last_n_user_indices:
            user_msg = all_messages[user_idx]
            
            # 检查是否有对应的assistant消息（在user之后）
            assistant_msg = None
            if user_idx + 1 < len(all_messages):
                next_msg = all_messages[user_idx + 1]
                # 如果下一条消息是assistant且还没被使用过，则是对应的assistant
                if next_msg.role == 'assistant' and (user_idx + 1) not in used_indices:
                    assistant_msg = next_msg
                    used_indices.add(user_idx + 1)
            
            # 添加到结果：总是包含user消息，如果assistant存在也包含
            result.append(user_msg)
            used_indices.add(user_idx)
            if assistant_msg:
                result.append(assistant_msg)
        
        return result

