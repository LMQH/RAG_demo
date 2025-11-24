"""
版本管理服务
"""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from demo.models.schema import DocumentMapping

logger = logging.getLogger(__name__)


def copy_previous_version_mappings(db: Session, new_version: int) -> int:
    """将上一个版本的所有活跃文档映射复制到新版本"""
    current_max_version = db.query(func.max(DocumentMapping.version)).scalar()
    
    if current_max_version is None:
        return 0
    
    previous_mappings = db.query(DocumentMapping).filter(
        DocumentMapping.version == current_max_version,
        DocumentMapping.is_active == True
    ).all()
    
    if not previous_mappings:
        return 0
    
    # 将旧版本的映射标记为非活跃
    db.query(DocumentMapping).filter(
        DocumentMapping.version == current_max_version,
        DocumentMapping.is_active == True
    ).update({"is_active": False})
    
    # 复制映射到新版本
    copied_count = 0
    for old_mapping in previous_mappings:
        new_mapping = DocumentMapping(
            document_id=old_mapping.document_id,
            filename=old_mapping.filename,
            file_path=old_mapping.file_path,
            is_active=True,
            version=new_version
        )
        db.add(new_mapping)
        copied_count += 1
    
    db.commit()
    logger.info(f"已将 {copied_count} 个文档映射从版本 {current_max_version} 复制到版本 {new_version}")
    return copied_count


def get_version_history(db: Session):
    """获取知识库历史版本列表"""
    versions = db.query(
        DocumentMapping.version,
        func.count(DocumentMapping.id).label('document_count'),
        func.min(DocumentMapping.created_at).label('created_at')
    ).group_by(DocumentMapping.version).order_by(DocumentMapping.version.desc()).all()
    
    if not versions:
        return []
    
    max_version = max(v.version for v in versions)
    
    result = []
    for v in versions:
        active_count = db.query(func.count(DocumentMapping.id)).filter(
            DocumentMapping.version == v.version,
            DocumentMapping.is_active == True
        ).scalar() or 0
        
        result.append({
            "version": v.version,
            "document_count": v.document_count,
            "active_count": active_count,
            "is_current": v.version == max_version,
            "created_at": v.created_at.isoformat() if v.created_at else None
        })
    
    return result

