"""
LLM推理工具
"""
import requests
import json
from typing import List, Generator, AsyncGenerator
import logging
import urllib3
import httpx
from demo.config import settings

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class InferenceService:
    """推理服务：优先使用华为云，失败时回退到OpenAI"""
    
    def __init__(self):
        self.use_huawei = False
        self.openai_client = None
        self.async_client = None
        self.async_openai_client = None
        
        if settings.HUAWEI_API_KEY and settings.HUAWEI_API_URL:
            self.use_huawei = True
            logger.info("使用华为云推理服务")
        else:
            logger.warning("华为云配置不完整，将使用OpenAI作为主要推理服务")
        
        # 初始化异步HTTP客户端（用于华为云API）
        try:
            self.async_client = httpx.AsyncClient(
                timeout=60.0,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
                verify=False
            )
            logger.info("异步HTTP客户端已初始化")
        except Exception as e:
            logger.warning(f"初始化异步HTTP客户端失败: {str(e)}")
        
        if settings.OPENAI_API_KEY:
            try:
                from openai import OpenAI, AsyncOpenAI
                # 同步客户端（向后兼容）
                self.openai_client = OpenAI(
                    api_key=settings.OPENAI_API_KEY,
                    base_url=settings.OPENAI_BASE_URL if settings.OPENAI_BASE_URL else None
                )
                # 异步客户端
                self.async_openai_client = AsyncOpenAI(
                    api_key=settings.OPENAI_API_KEY,
                    base_url=settings.OPENAI_BASE_URL if settings.OPENAI_BASE_URL else None
                )
                logger.info("OpenAI客户端已初始化（同步和异步）")
            except Exception as e:
                logger.warning(f"初始化OpenAI客户端失败: {str(e)}")
    
    def _call_huawei_api(self, messages: List[dict], stream: bool = False):
        """调用华为云API"""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {settings.HUAWEI_API_KEY}'
        }
        
        data = {
            "model": settings.HUAWEI_MODEL,
            "messages": messages,
            "chat_template_kwargs": {
                "thinking": True
            }
        }
        
        if stream:
            data["stream"] = True
        
        try:
            response = requests.post(
                settings.HUAWEI_API_URL,
                headers=headers,
                data=json.dumps(data),
                verify=False,
                stream=stream,
                timeout=60
            )
            response.raise_for_status()
            return response
        except Exception as e:
            logger.error(f"华为云API调用失败: {str(e)}")
            raise
    
    def _call_openai_api(self, messages: List[dict], stream: bool = False):
        """调用OpenAI API"""
        if not self.openai_client:
            raise ValueError("OpenAI客户端未初始化")
        
        return self.openai_client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            stream=stream,
            temperature=0.7
        )
    
    def generate(self, messages: List[dict], stream: bool = False):
        """生成回复（优先使用华为云，失败时回退到OpenAI）"""
        if self.use_huawei:
            try:
                if stream:
                    return self._generate_stream_huawei(messages)
                else:
                    response = self._call_huawei_api(messages, stream=False)
                    result = response.json()
                    return result.get('choices', [{}])[0].get('message', {}).get('content', '')
            except Exception as e:
                error_msg = f"华为云推理服务连接失败: {str(e)}，正在切换到OpenAI备用服务..."
                logger.warning(error_msg)
                print(f"\n⚠ {error_msg}")
                if self.openai_client:
                    if stream:
                        return self._generate_stream_openai(messages)
                    else:
                        response = self._call_openai_api(messages, stream=False)
                        return response.choices[0].message.content
                else:
                    raise ValueError("华为云推理服务连接失败，且OpenAI备用服务不可用，无法生成回复")
        
        if self.openai_client:
            if stream:
                return self._generate_stream_openai(messages)
            else:
                response = self._call_openai_api(messages, stream=False)
                return response.choices[0].message.content
        
        raise ValueError("没有可用的推理服务")
    
    def _generate_stream_huawei(self, messages: List[dict]) -> Generator[str, None, None]:
        """华为云流式生成"""
        response = self._call_huawei_api(messages, stream=True)
        
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data_str = line_str[6:].strip()
                    if data_str == '[DONE]':
                        break
                    try:
                        data = json.loads(data_str)
                        if 'choices' in data and len(data['choices']) > 0:
                            delta = data['choices'][0].get('delta', {})
                            if 'content' in delta:
                                yield delta['content']
                    except json.JSONDecodeError:
                        continue
    
    def _generate_stream_openai(self, messages: List[dict]) -> Generator[str, None, None]:
        """OpenAI流式生成"""
        stream = self._call_openai_api(messages, stream=True)
        for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content
    
    # ========== 异步方法 ==========
    
    async def _call_huawei_api_async(self, messages: List[dict], stream: bool = False):
        """异步调用华为云API（非流式）"""
        if not self.async_client:
            raise ValueError("异步HTTP客户端未初始化")
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {settings.HUAWEI_API_KEY}'
        }
        
        data = {
            "model": settings.HUAWEI_MODEL,
            "messages": messages,
            "chat_template_kwargs": {
                "thinking": True
            }
        }
        
        try:
            response = await self.async_client.post(
                settings.HUAWEI_API_URL,
                headers=headers,
                json=data
            )
            response.raise_for_status()
            return response
        except Exception as e:
            logger.error(f"华为云API异步调用失败: {str(e)}")
            raise
    
    async def _call_openai_api_async(self, messages: List[dict], stream: bool = False):
        """异步调用OpenAI API"""
        if not self.async_openai_client:
            raise ValueError("OpenAI异步客户端未初始化")
        
        return await self.async_openai_client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            stream=stream,
            temperature=0.7
        )
    
    async def generate_async(self, messages: List[dict], stream: bool = False):
        """异步生成回复（优先使用华为云，失败时回退到OpenAI）"""
        if self.use_huawei:
            try:
                if stream:
                    async for chunk in self._generate_stream_huawei_async(messages):
                        yield chunk
                else:
                    response = await self._call_huawei_api_async(messages, stream=False)
                    result = response.json()
                    return result.get('choices', [{}])[0].get('message', {}).get('content', '')
            except Exception as e:
                error_msg = f"华为云推理服务连接失败: {str(e)}，正在切换到OpenAI备用服务..."
                logger.warning(error_msg)
                if self.async_openai_client:
                    if stream:
                        async for chunk in self._generate_stream_openai_async(messages):
                            yield chunk
                    else:
                        response = await self._call_openai_api_async(messages, stream=False)
                        return response.choices[0].message.content
                else:
                    raise ValueError("华为云推理服务连接失败，且OpenAI备用服务不可用，无法生成回复")
        
        if self.async_openai_client:
            if stream:
                async for chunk in self._generate_stream_openai_async(messages):
                    yield chunk
            else:
                response = await self._call_openai_api_async(messages, stream=False)
                return response.choices[0].message.content
        
        raise ValueError("没有可用的推理服务")
    
    async def _generate_stream_huawei_async(self, messages: List[dict]) -> AsyncGenerator[str, None]:
        """华为云异步流式生成"""
        if not self.async_client:
            raise ValueError("异步HTTP客户端未初始化")
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {settings.HUAWEI_API_KEY}'
        }
        
        data = {
            "model": settings.HUAWEI_MODEL,
            "messages": messages,
            "chat_template_kwargs": {
                "thinking": True
            },
            "stream": True
        }
        
        try:
            async with self.async_client.stream(
                'POST',
                settings.HUAWEI_API_URL,
                headers=headers,
                json=data
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        line_str = line.decode('utf-8') if isinstance(line, bytes) else line
                        if line_str.startswith('data: '):
                            data_str = line_str[6:].strip()
                            if data_str == '[DONE]':
                                break
                            try:
                                data = json.loads(data_str)
                                if 'choices' in data and len(data['choices']) > 0:
                                    delta = data['choices'][0].get('delta', {})
                                    if 'content' in delta:
                                        yield delta['content']
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            logger.error(f"华为云异步流式生成失败: {str(e)}")
            raise
    
    async def _generate_stream_openai_async(self, messages: List[dict]) -> AsyncGenerator[str, None]:
        """OpenAI异步流式生成"""
        stream = await self._call_openai_api_async(messages, stream=True)
        async for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content
    
    async def close(self):
        """关闭异步客户端"""
        if self.async_client:
            await self.async_client.aclose()
        if self.async_openai_client:
            await self.async_openai_client.close()

