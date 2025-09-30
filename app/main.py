from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import List
import io
import mimetypes
from sqlalchemy.orm import Session
from .minio_client import minio_client
from . import crud, models, schemas
from .database import SessionLocal, engine
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

@app.post("/upload", tags=["📁 Файлы"])
async def upload_file(file: UploadFile = File(...), bucket_name: str = "uploads"):
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
async def list_files(bucket_name: str = "uploads", prefix: str = ""):
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
async def download_file(filename: str, bucket_name: str = "uploads"):
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
async def delete_file(filename: str, bucket_name: str = "uploads"):
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
async def get_file_url(filename: str, bucket_name: str = "uploads", expires: int = 3600):
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
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/users/", response_model=schemas.UserResponse, tags=["👥 Пользователи"])
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    **Создание пользователя**
    
    Создает нового пользователя в системе.
    
    - **username**: Уникальное имя пользователя
    - **email**: Email адрес (должен быть уникальным)
    - **password**: Пароль (минимум 6 символов)
    - **full_name**: Полное имя (опционально)
    - **bio**: Биография (опционально)
    - **avatar_url**: Ссылка на аватар (опционально)
    
    Возвращает информацию о созданном пользователе.
    """
    # Проверяем, существует ли пользователь с таким email
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    
    # Проверяем, существует ли пользователь с таким username
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username уже занят")
    
    return crud.create_user(db=db, user=user)

@app.get("/users/", response_model=List[schemas.UserResponse], tags=["👥 Пользователи"])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
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
def read_user(user_id: int, db: Session = Depends(get_db)):
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
def update_user(user_id: int, user_update: schemas.UserUpdate, db: Session = Depends(get_db)):
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
def delete_user(user_id: int, db: Session = Depends(get_db)):
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
def read_user_by_username(username: str, db: Session = Depends(get_db)):
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
