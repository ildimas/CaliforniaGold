from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status, Form
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import io
import json
import mimetypes
from sqlalchemy.orm import Session
from datetime import timedelta
from .minio_client import minio_client
from . import crud, models, schemas, auth, job_crud, minio_utils, zip_utils
from .database import SessionLocal, engine, get_db
from .db_wait import wait_for_postgres

app = FastAPI(
    title="California Gold API",
    description="""
    # California Gold API
    
    Современное REST API для управления файлами и пользователями.
    
    ## Возможности системы
    
    ### 📁 Управление файлами
    - Загрузка файлов в MinIO
    - Скачивание файлов
    - Получение списка файлов
    - Удаление файлов
    - Генерация presigned URL
    
    ### 👥 Управление пользователями
    - Создание пользователей
    - Получение информации о пользователях
    - Обновление профилей
    - Удаление пользователей
    - Поиск по username
    
    ### 🔒 Безопасность
    - Хеширование паролей с PBKDF2-SHA256
    - Валидация данных
    - Проверка уникальности email и username
    
    Добро пожаловать в California Gold API!
    """,
    version="1.0.0",
    contact={
        "name": "California Gold Team",
        "email": "support@californiagold.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
)

# Настройка CORS для разрешения запросов с веб-страниц
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене укажите конкретные домены
    allow_credentials=True,
    allow_methods=["*"],  # Разрешить все HTTP методы
    allow_headers=["*"],  # Разрешить все заголовки
)

# Ожидаем готовности PostgreSQL перед созданием таблиц
print("🔄 Ожидание готовности PostgreSQL...")
if wait_for_postgres():
    print("📊 Создание таблиц в базе данных...")
    models.Base.metadata.create_all(bind=engine)
    print("✅ Таблицы созданы успешно!")
else:
    print("❌ Не удалось подключиться к PostgreSQL")

@app.get("/", tags=["🏠 Главная"])
def read_root():
    """
    **Главная страница API**
    
    Приветственное сообщение и проверка работоспособности всех сервисов.
    """
    return {
        "message": "Добро пожаловать в California Gold API!",
        "status": "active",
        "version": "1.0.0",
        "team": "California Gold Team",
        "services": {
            "minio": "✅ Подключен",
            "postgresql": "✅ Подключен"
        },
        "description": "Современное API для управления файлами и пользователями"
    }

# Эндпоинты аутентификации
@app.post("/auth/register", response_model=schemas.UserResponse, tags=["🔐 Аутентификация"])
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    **Регистрация пользователя**
    
    Создает нового пользователя в системе.
    
    **Обязательные поля:**
    - **username**: Уникальное имя пользователя
    
    **Опциональные поля:**
    - **email**: Email адрес (должен быть уникальным если указан)
    - **password**: Пароль (минимум 6 символов)
    - **full_name**: Полное имя
    - **bio**: Биография
    - **avatar_url**: Ссылка на аватар
    
    Возвращает информацию о созданном пользователе.
    """
    # Проверяем, существует ли пользователь с таким email (только если email указан)
    if user.email:
        db_user = crud.get_user_by_email(db, email=user.email)
        if db_user:
            raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    
    # Проверяем, существует ли пользователь с таким username
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username уже занят")
    
    return crud.create_user(db=db, user=user)

@app.post("/auth/login", response_model=schemas.Token, tags=["🔐 Аутентификация"])
def login_user(user_credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    """
    **Вход в систему**
    
    Аутентифицирует пользователя и возвращает JWT токен.
    
    - **username**: Имя пользователя
    - **password**: Пароль
    
    Возвращает JWT токен для доступа к защищенным эндпоинтам.
    """
    user = auth.authenticate_user(db, user_credentials.username, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me", response_model=schemas.UserResponse, tags=["🔐 Аутентификация"])
def read_users_me(current_user: models.User = Depends(auth.get_current_active_user)):
    """
    **Текущий пользователь**
    
    Возвращает информацию о текущем авторизованном пользователе.
    """
    return current_user

@app.post("/upload", tags=["📁 Файлы"])
async def upload_file(
    file: UploadFile = File(...), 
    bucket_name: str = "uploads",
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    **Загрузка файла**
    
    Загружает файл в MinIO хранилище.
    
    - **file**: Файл для загрузки
    - **bucket_name**: Имя bucket (по умолчанию: "uploads")
    
    Возвращает информацию о загруженном файле.
    """
    try:
        # Определяем content type
        content_type = file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
        
        # Читаем файл в память
        file_data = io.BytesIO(await file.read())
        
        # Загружаем в MinIO
        success = minio_client.upload_file(
            bucket_name=bucket_name,
            object_name=file.filename,
            file_data=file_data,
            content_type=content_type
        )
        
        if success:
            return {
                "message": "Файл успешно загружен",
                "filename": file.filename,
                "bucket": bucket_name,
                "size": file.size
            }
        else:
            raise HTTPException(status_code=500, detail="Ошибка при загрузке файла")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")

@app.get("/files", tags=["📁 Файлы"])
async def list_files(
    bucket_name: str = "uploads", 
    prefix: str = "",
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    **Список файлов**
    
    Получает список всех файлов в указанном bucket.
    
    - **bucket_name**: Имя bucket (по умолчанию: "uploads")
    - **prefix**: Фильтр по префиксу имени файла
    
    Возвращает список файлов с метаданными.
    """
    try:
        files = minio_client.list_files(bucket_name, prefix)
        return {
            "bucket": bucket_name,
            "files": files,
            "count": len(files)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")

@app.get("/download/{filename}", tags=["📁 Файлы"])
async def download_file(
    filename: str, 
    bucket_name: str = "uploads",
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    **Скачивание файла**
    
    Скачивает файл из MinIO хранилища.
    
    - **filename**: Имя файла для скачивания
    - **bucket_name**: Имя bucket (по умолчанию: "uploads")
    
    Возвращает файл как поток данных.
    """
    try:
        file_data = minio_client.download_file(bucket_name, filename)
        
        if file_data is None:
            raise HTTPException(status_code=404, detail="Файл не найден")
        
        # Определяем content type
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        
        return StreamingResponse(
            io.BytesIO(file_data),
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")

@app.delete("/files/{filename}", tags=["📁 Файлы"])
async def delete_file(
    filename: str, 
    bucket_name: str = "uploads",
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    **Удаление файла**
    
    Удаляет файл из MinIO хранилища.
    
    - **filename**: Имя файла для удаления
    - **bucket_name**: Имя bucket (по умолчанию: "uploads")
    
    Возвращает подтверждение об удалении.
    """
    try:
        success = minio_client.delete_file(bucket_name, filename)
        
        if success:
            return {"message": f"Файл '{filename}' успешно удален"}
        else:
            raise HTTPException(status_code=500, detail="Ошибка при удалении файла")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")

@app.get("/files/{filename}/url", tags=["📁 Файлы"])
async def get_file_url(
    filename: str, 
    bucket_name: str = "uploads", 
    expires: int = 3600,
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    **Presigned URL**
    
    Генерирует временную ссылку для доступа к файлу.
    
    - **filename**: Имя файла
    - **bucket_name**: Имя bucket (по умолчанию: "uploads")
    - **expires**: Время жизни ссылки в секундах (по умолчанию: 3600)
    
    Возвращает presigned URL для безопасного доступа к файлу.
    """
    try:
        url = minio_client.get_presigned_url(bucket_name, filename, expires)
        
        if url:
            return {
                "filename": filename,
                "url": url,
                "expires_in_seconds": expires
            }
        else:
            raise HTTPException(status_code=404, detail="Файл не найден или ошибка при создании URL")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")

@app.get("/health", tags=["🔧 Система"])
async def health_check():
    """
    **Проверка здоровья**
    
    Проверяет состояние всех сервисов API.
    
    Возвращает статус MinIO и общее состояние системы.
    """
    return {
        "status": "healthy",
        "minio_endpoint": minio_client.endpoint,
        "message": "FastAPI и MinIO работают корректно"
    }

# Эндпоинты для пользователей


@app.get("/users/", response_model=List[schemas.UserResponse], tags=["👥 Пользователи"])
def read_users(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    **Список пользователей**
    
    Получает список всех пользователей с пагинацией.
    
    - **skip**: Количество записей для пропуска (по умолчанию: 0)
    - **limit**: Максимальное количество записей (по умолчанию: 100)
    
    Возвращает список пользователей с метаданными.
    """
    users = crud.get_users(db, skip=skip, limit=limit)
    return users

@app.get("/users/{user_id}", response_model=schemas.UserResponse, tags=["👥 Пользователи"])
def read_user(
    user_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    **Получение пользователя по ID**
    
    Получает информацию о пользователе по его уникальному идентификатору.
    
    - **user_id**: Уникальный идентификатор пользователя
    
    Возвращает полную информацию о пользователе.
    """
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return db_user

@app.put("/users/{user_id}", response_model=schemas.UserResponse, tags=["👥 Пользователи"])
def update_user(
    user_id: int, 
    user_update: schemas.UserUpdate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    **Обновление пользователя**
    
    Обновляет информацию о пользователе.
    
    - **user_id**: Уникальный идентификатор пользователя
    - **user_update**: Данные для обновления (все поля опциональны)
    
    Возвращает обновленную информацию о пользователе.
    """
    db_user = crud.update_user(db, user_id=user_id, user_update=user_update)
    if db_user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return db_user

@app.delete("/users/{user_id}", tags=["👥 Пользователи"])
def delete_user(
    user_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    **Удаление пользователя**
    
    Удаляет пользователя из системы.
    
    - **user_id**: Уникальный идентификатор пользователя
    
    Возвращает подтверждение об удалении.
    """
    success = crud.delete_user(db, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return {"message": "Пользователь успешно удален"}

@app.get("/users/username/{username}", response_model=schemas.UserResponse, tags=["👥 Пользователи"])
def read_user_by_username(
    username: str, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    **Поиск пользователя по username**
    
    Получает информацию о пользователе по его имени пользователя.
    
    - **username**: Имя пользователя для поиска
    
    Возвращает полную информацию о пользователе.
    """
    db_user = crud.get_user_by_username(db, username=username)
    if db_user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return db_user

# ==================== ЭНДПОИНТЫ ДЛЯ ЗАДАНИЙ ====================

@app.post("/jobs/", response_model=schemas.JobResponse, tags=["📋 Задания"])
def create_job(
    title: str = Form(None),
    description: str = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    **Создание нового задания**
    
    Создает новое задание с возможностью загрузки файла или ZIP архива.
    
    **Опциональные поля:**
    - **title**: Название задания (если не указано, будет использовано имя файла)
    - **description**: Описание задания
    - **file**: Файл для загрузки в MinIO (поддерживаются обычные файлы и ZIP архивы)
    
    **Поддерживаемые типы файлов:**
    - Обычные файлы (любого типа)
    - ZIP архивы (с автоматическим анализом содержимого)
    
    **Примечание:** Если title не указан, будет использовано имя загруженного файла.
    
    Возвращает информацию о созданном задании.
    """
    # Определяем title - используем имя файла если title не указан
    job_title = title
    if not job_title and file and file.filename:
        job_title = file.filename
    
    # Создаем задание
    job_data = schemas.JobCreate(title=job_title, description=description)
    db_job = job_crud.create_job(db=db, job=job_data, owner_id=current_user.id)
    
    # Если есть файл, загружаем его в MinIO
    if file and file.filename:
        file_content = file.file.read()
        
        # Определяем тип файла
        is_zip = zip_utils.is_zip_file(file_content, file.filename)
        file_type = "zip" if is_zip else "single"
        
        # Если это ZIP файл, валидируем его
        if is_zip:
            is_valid, error_message = zip_utils.validate_zip_file(file_content)
            if not is_valid:
                job_crud.delete_job(db=db, job_id=db_job.id)
                raise HTTPException(status_code=400, detail=f"Некорректный ZIP файл: {error_message}")
        
        # Загружаем файл в MinIO
        success, file_path = minio_utils.upload_file_to_minio(
            file_content=file_content,
            file_name=file.filename,
            content_type=file.content_type
        )
        
        if success:
            zip_contents = None
            
            # Если это ZIP файл, анализируем его содержимое
            if is_zip:
                zip_contents = zip_utils.get_zip_contents(file_content)
                print(f"📦 ZIP архив содержит {len(zip_contents)} файлов")
            
            # Обновляем информацию о файле в задании
            job_crud.update_job_file_info(
                db=db,
                job_id=db_job.id,
                file_name=file.filename,
                file_size=len(file_content),
                file_content_type=file.content_type,
                file_path=file_path,
                file_type=file_type,
                zip_contents=zip_contents
            )
        else:
            # Если загрузка файла не удалась, удаляем задание
            job_crud.delete_job(db=db, job_id=db_job.id)
            raise HTTPException(status_code=500, detail="Ошибка загрузки файла")
    
    return db_job

@app.get("/jobs/", response_model=List[schemas.JobResponse], tags=["📋 Задания"])
def get_user_jobs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    **Получение заданий пользователя**
    
    Получает список заданий текущего пользователя с пагинацией.
    
    - **skip**: Количество заданий для пропуска (по умолчанию 0)
    - **limit**: Максимальное количество заданий (по умолчанию 100)
    
    Возвращает список заданий пользователя.
    """
    jobs = job_crud.get_jobs_by_owner(db=db, owner_id=current_user.id, skip=skip, limit=limit)
    return jobs

@app.get("/jobs/{job_id}", response_model=schemas.JobResponse, tags=["📋 Задания"])
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    **Получение задания по ID**
    
    Получает информацию о конкретном задании.
    
    - **job_id**: ID задания
    
    Возвращает информацию о задании.
    """
    job = job_crud.get_job(db=db, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    
    # Проверяем, что пользователь является владельцем задания
    if job.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этому заданию")
    
    return job

@app.get("/jobs/uuid/{job_uuid}", response_model=schemas.JobResponse, tags=["📋 Задания"])
def get_job_by_uuid(
    job_uuid: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    **Получение задания по UUID**
    
    Получает информацию о задании по его UUID.
    
    - **job_uuid**: UUID задания
    
    Возвращает информацию о задании.
    """
    job = job_crud.get_job_by_uuid(db=db, job_uuid=job_uuid)
    if job is None:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    
    # Проверяем, что пользователь является владельцем задания
    if job.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этому заданию")
    
    return job

@app.put("/jobs/{job_id}", response_model=schemas.JobResponse, tags=["📋 Задания"])
def update_job(
    job_id: int,
    job_update: schemas.JobUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    **Обновление задания**
    
    Обновляет информацию о задании.
    
    - **job_id**: ID задания
    - **job_update**: Данные для обновления
    
    Возвращает обновленную информацию о задании.
    """
    job = job_crud.get_job(db=db, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    
    # Проверяем, что пользователь является владельцем задания
    if job.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этому заданию")
    
    updated_job = job_crud.update_job(db=db, job_id=job_id, job_update=job_update)
    return updated_job

@app.delete("/jobs/{job_id}", tags=["📋 Задания"])
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    **Удаление задания**
    
    Удаляет задание и связанный с ним файл из MinIO.
    
    - **job_id**: ID задания
    
    Возвращает сообщение об успешном удалении.
    """
    job = job_crud.get_job(db=db, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    
    # Проверяем, что пользователь является владельцем задания
    if job.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этому заданию")
    
    # Удаляем файл из MinIO если он есть
    if job.file_path:
        minio_utils.delete_file_from_minio(job.file_path)
    
    # Удаляем задание из базы данных
    success = job_crud.delete_job(db=db, job_id=job_id)
    if not success:
        raise HTTPException(status_code=500, detail="Ошибка удаления задания")
    
    return {"message": "Задание успешно удалено"}

@app.get("/jobs/{job_id}/file", tags=["📋 Задания"])
def download_job_file(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    **Скачивание файла задания**
    
    Скачивает файл, связанный с заданием.
    
    - **job_id**: ID задания
    
    Возвращает файл для скачивания.
    """
    job = job_crud.get_job(db=db, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    
    # Проверяем, что пользователь является владельцем задания
    if job.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этому заданию")
    
    if not job.file_path:
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    # Получаем файл из MinIO
    success, file_content = minio_utils.get_file_from_minio(job.file_path)
    if not success:
        raise HTTPException(status_code=500, detail="Ошибка получения файла")
    
    # Возвращаем файл для скачивания
    return StreamingResponse(
        io.BytesIO(file_content),
        media_type=job.file_content_type or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={job.file_name}"}
    )

@app.get("/jobs/{job_id}/zip-contents", tags=["📋 Задания"])
def get_zip_contents(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    **Получение содержимого ZIP архива**
    
    Получает список файлов в ZIP архиве задания.
    
    - **job_id**: ID задания
    
    Возвращает информацию о файлах в ZIP архиве.
    """
    job = job_crud.get_job(db=db, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    
    # Проверяем, что пользователь является владельцем задания
    if job.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этому заданию")
    
    if job.file_type != "zip":
        raise HTTPException(status_code=400, detail="Задание не содержит ZIP архив")
    
    if not job.zip_contents:
        return {"message": "ZIP архив пуст или содержимое не найдено"}
    
    try:
        zip_contents = json.loads(job.zip_contents)
        return {
            "job_id": job.id,
            "zip_filename": job.file_name,
            "total_files": len(zip_contents),
            "files": zip_contents
        }
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Ошибка при чтении содержимого ZIP архива")

@app.get("/jobs/{job_id}/zip-info", tags=["📋 Задания"])
def get_zip_info(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    **Получение информации о ZIP архиве**
    
    Получает общую информацию о ZIP архиве задания.
    
    - **job_id**: ID задания
    
    Возвращает статистику ZIP архива.
    """
    job = job_crud.get_job(db=db, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    
    # Проверяем, что пользователь является владельцем задания
    if job.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этому заданию")
    
    if job.file_type != "zip":
        raise HTTPException(status_code=400, detail="Задание не содержит ZIP архив")
    
    # Получаем файл из MinIO для анализа
    success, file_content = minio_utils.get_file_from_minio(job.file_path)
    if not success:
        raise HTTPException(status_code=500, detail="Ошибка получения файла")
    
    zip_info = zip_utils.get_zip_file_info(file_content)
    
    return {
        "job_id": job.id,
        "zip_filename": job.file_name,
        "file_size": job.file_size,
        "zip_info": zip_info
    }
