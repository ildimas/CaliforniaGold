from sqlalchemy.orm import Session
from . import models, schemas
from typing import Optional, List
import uuid
import json

def get_job(db: Session, job_id: int) -> Optional[models.Job]:
    """Получает задание по ID"""
    return db.query(models.Job).filter(models.Job.id == job_id).first()

def get_job_by_uuid(db: Session, job_uuid: str) -> Optional[models.Job]:
    """Получает задание по UUID"""
    return db.query(models.Job).filter(models.Job.uuid == job_uuid).first()

def get_jobs_by_owner(db: Session, owner_id: int, skip: int = 0, limit: int = 100) -> List[models.Job]:
    """Получает задания пользователя с пагинацией"""
    return db.query(models.Job).filter(models.Job.owner_id == owner_id).offset(skip).limit(limit).all()

def get_all_jobs(db: Session, skip: int = 0, limit: int = 100) -> List[models.Job]:
    """Получает все задания с пагинацией"""
    return db.query(models.Job).offset(skip).limit(limit).all()

def create_job(db: Session, job: schemas.JobCreate, owner_id: int) -> models.Job:
    """Создает новое задание"""
    db_job = models.Job(
        title=job.title,
        description=job.description,
        file_type=job.file_type or "single",
        owner_id=owner_id,
        uuid=uuid.uuid4()
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job

def update_job(db: Session, job_id: int, job_update: schemas.JobUpdate) -> Optional[models.Job]:
    """Обновляет задание"""
    db_job = get_job(db, job_id)
    if not db_job:
        return None
    
    update_data = job_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_job, field, value)
    
    db.commit()
    db.refresh(db_job)
    return db_job

def update_job_file_info(db: Session, job_id: int, file_name: str, file_size: int, file_content_type: str, file_path: str, file_type: str = "single", zip_contents: Optional[List[dict]] = None) -> Optional[models.Job]:
    """Обновляет информацию о файле в задании"""
    db_job = get_job(db, job_id)
    if not db_job:
        return None
    
    db_job.file_name = file_name
    db_job.file_size = file_size
    db_job.file_content_type = file_content_type
    db_job.file_path = file_path
    db_job.file_type = file_type
    
    # Сохраняем содержимое ZIP архива как JSON
    if zip_contents:
        db_job.zip_contents = json.dumps(zip_contents, ensure_ascii=False)
    
    db.commit()
    db.refresh(db_job)
    return db_job

def update_job_status(db: Session, job_id: int, status: str) -> Optional[models.Job]:
    """Обновляет статус задания"""
    db_job = get_job(db, job_id)
    if not db_job:
        return None
    
    db_job.status = status
    if status == "completed":
        from sqlalchemy.sql import func
        db_job.completed_at = func.now()
    
    db.commit()
    db.refresh(db_job)
    return db_job

def delete_job(db: Session, job_id: int) -> bool:
    """Удаляет задание"""
    db_job = get_job(db, job_id)
    if not db_job:
        return False
    
    db.delete(db_job)
    db.commit()
    return True

def get_jobs_by_status(db: Session, status: str, skip: int = 0, limit: int = 100) -> List[models.Job]:
    """Получает задания по статусу"""
    return db.query(models.Job).filter(models.Job.status == status).offset(skip).limit(limit).all()

def get_job_with_zip_contents(db: Session, job_id: int) -> Optional[models.Job]:
    """Получает задание с распарсенным содержимым ZIP архива"""
    job = get_job(db, job_id)
    if not job:
        return None
    
    # Парсим ZIP содержимое если есть
    if job.zip_contents:
        try:
            job.zip_contents_parsed = json.loads(job.zip_contents)
        except json.JSONDecodeError:
            job.zip_contents_parsed = []
    else:
        job.zip_contents_parsed = []
    
    return job
