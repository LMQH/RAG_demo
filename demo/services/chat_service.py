"""
聊天服务：处理流式对话业务逻辑
"""
import json
import asyncio
from typing import Generator, AsyncGenerator, Optional
from sqlalchemy.orm import Session

from demo.tools import inference_service, RAGService
from demo.services.conversation_memory import ConversationService
from demo.config import SystemPrompts


# 同步生成器，暂且保留为备份，后续可删除
def generate_response_stream(
    query: str,
    context: str,
    conversation_history: list,
    conversation_id: int,
    scenario: Optional[str] = None
) -> Generator[str, None, None]:
    """生成流式响应（同步生成器）
    
    Args:
        query: 用户查询
        context: RAG检索到的上下文
        conversation_history: 对话历史
        conversation_id: 对话ID
        scenario: 场景类型，可选值：'technical'(技术支持), 'sales'(销售咨询), None(默认客服)
    """
    # 获取系统提示词（根据场景选择）
    system_prompt = SystemPrompts.get_prompt(scenario)
    
    # 构建消息列表
    messages = [
        {"role": "system", "content": system_prompt}
    ]
    
    # 添加上下文
    if context:
        messages.append({
            "role": "system",
            "content": f"""以下是知识库文档内容，请严格按照这些内容回答用户问题：

{context}

## 重要要求：
1. 必须严格按照上述文档内容回答，不能使用文档外的任何信息
2. 如果文档是Q&A格式，匹配用户问题与文档中的问题，返回对应的答案
3. 如果文档中包含图片信息，请在回答时：
   - 提及图片内容或描述
   - 提供图片链接（如果文档中有）
   - 说明图片与答案的关系
4. 如果文档中没有相关信息，必须明确告知"根据知识库文档，暂无相关信息"
5. 禁止编造、猜测或使用通用知识"""
        })
    else:
        # 如果没有检索到相关内容，也要明确告知
        messages.append({
            "role": "system",
            "content": "知识库中没有检索到相关信息，请明确告知用户并建议联系人工客服。"
        })
    
    # 添加历史对话（已经是按轮次获取的完整消息列表）
    for msg in conversation_history:
        messages.append({
            "role": msg.role,
            "content": msg.content
        })
    
    # 添加当前问题
    messages.append({
        "role": "user",
        "content": query
    })
    
    # 调用推理服务（流式）
    try:
        full_response = ""
        stream = inference_service.generate(messages, stream=True)
        
        for content in stream:
            if content:
                full_response += content
                # 发送数据块
                yield f"data: {json.dumps({'content': content, 'done': False}, ensure_ascii=False)}\n\n"
        
        # 发送完成信号
        yield f"data: {json.dumps({'content': '', 'done': True, 'full_response': full_response}, ensure_ascii=False)}\n\n"
        
    except Exception as e:
        error_msg = f"生成回复时出错: {str(e)}"
        yield f"data: {json.dumps({'error': error_msg, 'done': True}, ensure_ascii=False)}\n\n"


# 异步生成器
async def generate_response_stream_async(
    query: str,
    context: str,
    conversation_history: list,
    conversation_id: int,
    scenario: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """生成异步流式响应
    
    Args:
        query: 用户查询
        context: RAG检索到的上下文
        conversation_history: 对话历史
        conversation_id: 对话ID（保留用于接口一致性，当前未使用但可能用于日志/调试）
        scenario: 场景类型，可选值：'technical'(技术支持), 'sales'(销售咨询), None(默认客服)
    """
    # conversation_id 保留用于接口一致性，将来可能用于日志记录或错误追踪
    _ = conversation_id
    # 获取系统提示词（根据场景选择）
    system_prompt = SystemPrompts.get_prompt(scenario)
    
    # 构建消息列表
    messages = [
        {"role": "system", "content": system_prompt}
    ]
    
    # 添加上下文
    if context:
        messages.append({
            "role": "system",
            "content": f"""以下是知识库文档内容，请严格按照这些内容回答用户问题：

{context}

## 重要要求：
1. 必须严格按照上述文档内容回答，不能使用文档外的任何信息
2. 如果文档是Q&A格式，匹配用户问题与文档中的问题，返回对应的答案
3. 如果文档中包含图片信息，请在回答时：
   - 提及图片内容或描述
   - 提供图片链接（如果文档中有）
   - 说明图片与答案的关系
4. 如果文档中没有相关信息，必须明确告知"根据知识库文档，暂无相关信息"
5. 禁止编造、猜测或使用通用知识"""
        })
    else:
        # 如果没有检索到相关内容，也要明确告知
        messages.append({
            "role": "system",
            "content": "知识库中没有检索到相关信息，请明确告知用户并建议联系人工客服。"
        })
    
    # 添加历史对话（已经是按轮次获取的完整消息列表）
    for msg in conversation_history:
        messages.append({
            "role": msg.role,
            "content": msg.content
        })
    
    # 添加当前问题
    messages.append({
        "role": "user",
        "content": query
    })
    
    # 调用异步推理服务（流式）
    try:
        full_response = ""
        async for content in inference_service.generate_async(messages, stream=True):
            if content:
                full_response += content
                # 发送数据块
                yield f"data: {json.dumps({'content': content, 'done': False}, ensure_ascii=False)}\n\n"
        
        # 发送完成信号
        yield f"data: {json.dumps({'content': '', 'done': True, 'full_response': full_response}, ensure_ascii=False)}\n\n"
        
    except Exception as e:
        error_msg = f"生成回复时出错: {str(e)}"
        yield f"data: {json.dumps({'error': error_msg, 'done': True}, ensure_ascii=False)}\n\n"


class ChatService:
    """聊天服务类"""
    
    @staticmethod
    async def create_chat_stream(
        message: str,
        user_id: str,
        conversation_id: int | None,
        db: Session,
        scenario: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """创建流式对话响应
        
        Args:
            message: 用户消息
            user_id: 用户ID
            conversation_id: 对话ID（可选，如果为None则创建新对话）
            db: 数据库会话
            scenario: 场景类型，可选值：'technical'(技术支持), 'sales'(销售咨询), None(默认客服)
            
        Yields:
            SSE格式的数据块
        """
        # 获取或创建对话
        if conversation_id:
            conversation = ConversationService.get_conversation(db, conversation_id)
            if not conversation:
                raise ValueError("对话不存在")
        else:
            conversation = ConversationService.create_conversation(db, user_id)
        
        # 保存用户消息
        current_user_message = ConversationService.add_message(
            db, conversation.id, "user", message
        )
        
        # 并行执行RAG检索和历史消息获取
        retrieved_docs_task = asyncio.create_task(
            RAGService.retrieve_async(message)
        )
        history_task = asyncio.create_task(
            asyncio.to_thread(
                ConversationService.get_last_n_rounds,
                db, conversation.id, 5, current_user_message.id
            )
        )
        
        # 等待两个任务完成
        retrieved_docs, history = await asyncio.gather(
            retrieved_docs_task, history_task
        )
        
        # 构建上下文（同步操作，很快）
        context = RAGService.build_context(retrieved_docs)
        
        # 使用异步流式生成
        full_response = ""
        async for chunk in generate_response_stream_async(
            message,
            context,
            history,
            conversation.id,
            scenario=scenario
        ):
            # 解析chunk以获取完整响应
            if chunk.startswith("data: "):
                data_str = chunk[6:].strip()
                if data_str:
                    try:
                        data = json.loads(data_str)
                        if not data.get('done') and data.get('content'):
                            full_response += data['content']
                        elif data.get('done'):
                            # 保存助手回复
                            if 'full_response' in data:
                                full_response = data['full_response']
                            if full_response:
                                # 在线程池中执行数据库操作
                                await asyncio.to_thread(
                                    ConversationService.add_message,
                                    db, conversation.id, "assistant", full_response
                                )
                    except (json.JSONDecodeError, KeyError, TypeError):
                        # 忽略JSON解析错误和其他数据格式错误
                        pass
            yield chunk

