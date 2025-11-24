"""
Server-Sent Events (SSE) 服务
"""
import json
import asyncio
import logging
from typing import AsyncGenerator, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from demo.models.schema import DocumentMapping, Document, SessionLocal

logger = logging.getLogger(__name__)


class SSEService:
    """SSE 流生成服务"""
    
    @staticmethod
    async def stream_upload_status(version: int) -> AsyncGenerator[str, None]:
        """实时监听指定版本的文件处理状态"""
        db = SessionLocal()
        processed_files = set()
        
        try:
            yield f"data: {json.dumps({'message': '开始监听文件处理状态', 'version': version}, ensure_ascii=False)}\n\n"
            
            max_wait_time = 3600
            check_interval = 1
            elapsed_time = 0
            no_new_file_count = 0
            max_no_new_file = 300
            
            while elapsed_time < max_wait_time:
                try:
                    mappings = db.query(DocumentMapping, Document).join(
                        Document, DocumentMapping.document_id == Document.id
                    ).filter(
                        DocumentMapping.version == version,
                        DocumentMapping.is_active == True,
                        Document.chunk_count > 0
                    ).all()
                    
                    new_file_found = False
                    for mapping, document in mappings:
                        file_key = (mapping.document_id, mapping.filename)
                        if file_key not in processed_files:
                            result = {
                                "message": "文件已完成处理",
                                "filename": mapping.filename,
                                "document_id": mapping.document_id,
                                "version": version,
                                "status": "finish",
                                "chunk_count": document.chunk_count
                            }
                            yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
                            processed_files.add(file_key)
                            new_file_found = True
                            logger.info(f"推送文件处理完成通知: {mapping.filename}")
                    
                    if new_file_found:
                        no_new_file_count = 0
                    else:
                        no_new_file_count += 1
                        if no_new_file_count >= max_no_new_file:
                            logger.info(f"版本 {version} 的文件处理完成，停止监听")
                            break
                    
                    await asyncio.sleep(check_interval)
                    elapsed_time += check_interval
                    
                except Exception as e:
                    logger.error(f"检查文件状态时出错: {str(e)}")
                    await asyncio.sleep(check_interval)
                    elapsed_time += check_interval
            
            if elapsed_time >= max_wait_time:
                yield f"data: {json.dumps({'message': '监听超时，已停止', 'version': version}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'message': '所有文件处理完成，监听结束', 'version': version}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error(f"SSE 流生成错误: {str(e)}")
            error_msg = json.dumps({"error": f"监听过程中出错: {str(e)}"}, ensure_ascii=False)
            yield f"data: {error_msg}\n\n"
        finally:
            db.close()
    
    @staticmethod
    async def stream_rebuild_status(version: Optional[int] = None) -> AsyncGenerator[str, None]:
        """实时监听知识库重建任务状态"""
        db = SessionLocal()
        rebuild_started = False
        last_progress = None
        
        try:
            if version:
                yield f"data: {json.dumps({'message': f'开始监听知识库重建状态（版本 {version}）'}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'message': '开始监听知识库重建状态（最近一次）'}, ensure_ascii=False)}\n\n"
            
            initial_max_version = db.query(func.max(DocumentMapping.version)).scalar() or 0
            target_version = version if version else (initial_max_version + 1)
            
            max_wait_time = 7200
            check_interval = 2
            elapsed_time = 0
            no_progress_count = 0
            max_no_progress = 60
            
            while elapsed_time < max_wait_time:
                try:
                    current_max_version = db.query(func.max(DocumentMapping.version)).scalar() or 0
                    
                    if current_max_version >= target_version:
                        mappings = db.query(DocumentMapping, Document).join(
                            Document, DocumentMapping.document_id == Document.id
                        ).filter(
                            DocumentMapping.version == target_version
                        ).all()
                        
                        total_files = len(mappings)
                        completed_files = sum(1 for m, d in mappings if d.chunk_count > 0)
                        failed_files = [m for m, d in mappings if d.chunk_count == 0]
                        
                        current_progress = f"{completed_files}/{total_files}"
                        
                        if total_files > 0:
                            if completed_files == total_files:
                                total_chunks = sum(d.chunk_count for m, d in mappings)
                                result = {
                                    "message": "知识库重建完成",
                                    "version": target_version,
                                    "total_files": total_files,
                                    "success_count": completed_files,
                                    "fail_count": len(failed_files),
                                    "total_chunks": total_chunks,
                                    "status": "completed"
                                }
                                yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
                                logger.info(f"知识库重建完成: 版本 {target_version}, 文件数 {total_files}")
                                break
                            else:
                                if not rebuild_started:
                                    rebuild_started = True
                                    yield f"data: {json.dumps({
                                        'message': '知识库重建已开始',
                                        'status': 'processing',
                                        'version': target_version,
                                        'progress': current_progress,
                                        'total_files': total_files
                                    }, ensure_ascii=False)}\n\n"
                                elif current_progress != last_progress:
                                    yield f"data: {json.dumps({
                                        'message': '知识库重建进行中',
                                        'status': 'processing',
                                        'version': target_version,
                                        'progress': current_progress,
                                        'total_files': total_files,
                                        'completed_files': completed_files
                                    }, ensure_ascii=False)}\n\n"
                                    last_progress = current_progress
                                    no_progress_count = 0
                                else:
                                    no_progress_count += 1
                                    if no_progress_count >= max_no_progress:
                                        yield f"data: {json.dumps({
                                            'message': '重建进度长时间未更新，可能已完成或遇到问题',
                                            'status': 'warning',
                                            'version': target_version,
                                            'progress': current_progress,
                                            'total_files': total_files,
                                            'completed_files': completed_files
                                        }, ensure_ascii=False)}\n\n"
                                        break
                    else:
                        if not rebuild_started:
                            inactive_count = db.query(func.count(DocumentMapping.id)).filter(
                                DocumentMapping.is_active == False
                            ).scalar() or 0
                            
                            if inactive_count > 0:
                                rebuild_started = True
                                yield f"data: {json.dumps({
                                    'message': '知识库重建已开始（正在清空旧数据）',
                                    'status': 'processing',
                                    'version': target_version
                                }, ensure_ascii=False)}\n\n"
                    
                    await asyncio.sleep(check_interval)
                    elapsed_time += check_interval
                    
                except Exception as e:
                    logger.error(f"检查重建状态时出错: {str(e)}")
                    yield f"data: {json.dumps({
                        'message': f'检查状态时出错: {str(e)}',
                        'status': 'error'
                    }, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(check_interval)
                    elapsed_time += check_interval
            
            if elapsed_time >= max_wait_time:
                yield f"data: {json.dumps({
                    'message': '监听超时，已停止',
                    'status': 'timeout',
                    'version': target_version
                }, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error(f"SSE 流生成错误: {str(e)}")
            error_msg = json.dumps({
                "error": f"监听过程中出错: {str(e)}",
                "status": "error"
            }, ensure_ascii=False)
            yield f"data: {error_msg}\n\n"
        finally:
            db.close()

