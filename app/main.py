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
    title="🧟‍♀️ California Gold ЗЗЗЗЗЗЗЗЗОМБИ API 🧟‍♂️",
    description="""
    🏆 California Gold ЗЗЗЗЗЗЗЗЗОМБИ API 🏆
    🧟‍♀️ Современное МОООООООООЗГИ API для управления файлами и пользователями 🧟‍♂️

    🧟‍♀️ Возможности ЗЗЗЗЗЗЗЗЗОМБИ системы МОООООООООЗГИ 🧟‍♂️

    📁 Управление ЗЗЗЗЗЗЗЗЗОМБИ файлами МОООООООООЗГИ
    🧟‍♀️ Загрузка файлов в MinIO
    🧟‍♂️ Скачивание файлов
    🧟‍♀️ Получение списка файлов
    🧟‍♂️ Удаление файлов
    🧟‍♀️ Генерация presigned URL

    👥 Управление ЗЗЗЗЗЗЗЗЗОМБИ пользователями МОООООООООЗГИ
    🧟‍♀️ Создание пользователей
    🧟‍♂️ Получение информации о пользователях
    🧟‍♀️ Обновление профилей
    🧟‍♂️ Удаление пользователей
    🧟‍♀️ Поиск по username

    🔒 ЗЗЗЗЗЗЗЗЗОМБИ Безопасность МОООООООООЗГИ
    🧟‍♀️ Хеширование паролей с PBKDF2-SHA256
    🧟‍♂️ Валидация данных
    🧟‍♀️ Проверка уникальности email и username

    🧟‍♀️ Добро пожаловать в мир ЗЗЗЗЗЗЗЗЗОМБИ-технологий МОООООООООЗГИ! 🧟‍♂️
    Наше ЗЗЗЗЗЗЗЗЗОМБИ API готово к бою с любыми задачами МОООООООООЗГИ! ⚔️
    """,
    version="1.0.0",
    contact={
        "name": "🧟‍♀️ California Gold ЗЗЗЗЗЗЗЗЗОМБИ Team МОООООООООЗГИ 🧟‍♂️",
        "email": "zombies@californiagold.com",
    },
    license_info={
        "name": "🧟‍♀️ ЗЗЗЗЗЗЗЗЗОМБИ MIT License МОООООООООЗГИ 🧟‍♂️",
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
    🧟‍♀️ **Главная страница зомби-API** 🧟‍♂️
    
    Приветственное сообщение от зомби-команды и проверка работоспособности всех сервисов!
    """
    return {
        "message": "🧟‍♀️ Добро пожаловать в California Gold Zombie API! 🧟‍♂️",
        "status": "🧟‍♀️ ЗОМБИ-АКТИВЕН! 🧟‍♂️",
        "version": "1.0.0",
        "zombie_team": "🧟‍♀️ California Gold Zombie Squad 🧟‍♂️",
        "services": {
            "minio": "🧟‍♀️ ЗОМБИ-ПОДКЛЮЧЕН! 🧟‍♂️",
            "postgresql": "🧟‍♀️ ЗОМБИ-ПОДКЛЮЧЕН! 🧟‍♂️"
        },
        "zombie_power": "⚡ Наша зомби-сила готова к бою! ⚡",
        "warning": "⚠️ Осторожно! Зомби-код может быть заразным! ⚠️"
    }

@app.post("/upload", tags=["📁 Файлы"])
async def upload_file(file: UploadFile = File(...), bucket_name: str = "uploads"):
    """
    🧟‍♀️ **ЗОМБИ-ЗАГРУЗКА ФАЙЛА** 🧟‍♂️
    
    Наши зомби-роботы загружают файлы в <span style="background: linear-gradient(45deg, #ff6b6b, #4ecdc4); color: white; padding: 2px 6px; border-radius: 4px;">MinIO</span> хранилище!
    
    - **file**: 🧟‍♀️ <span style="color: #e74c3c;">Файл для зомби-загрузки</span> 🧟‍♂️
    - **bucket_name**: 🧟‍♀️ <span style="color: #3498db;">Имя зомби-bucket</span> (по умолчанию: "uploads") 🧟‍♂️
    
    Возвращает <span style="background: #f39c12; color: white; padding: 2px 6px; border-radius: 4px;">зомби-информацию</span> о загруженном файле! 🧟‍♀️
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
    🧟‍♀️ **ЗОМБИ-СПИСОК ФАЙЛОВ** 🧟‍♂️
    
    Наши зомби-скауты исследуют <span style="background: linear-gradient(45deg, #667eea, #764ba2); color: white; padding: 2px 6px; border-radius: 4px;">bucket</span> и находят все файлы!
    
    - **bucket_name**: 🧟‍♀️ <span style="color: #e74c3c;">Имя зомби-bucket</span> (по умолчанию: "uploads") 🧟‍♂️
    - **prefix**: 🧟‍♀️ <span style="color: #9b59b6;">Фильтр по префиксу</span> имени файла 🧟‍♂️
    
    Возвращает <span style="background: #27ae60; color: white; padding: 2px 6px; border-radius: 4px;">зомби-список</span> файлов с метаданными! 🧟‍♀️
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
    🧟‍♀️ **ЗОМБИ-СКАЧИВАНИЕ ФАЙЛА** 🧟‍♂️
    
    Наши зомби-курьеры доставляют файлы из <span style="background: linear-gradient(45deg, #ff6b6b, #4ecdc4); color: white; padding: 2px 6px; border-radius: 4px;">MinIO</span> хранилища!
    
    - **filename**: 🧟‍♀️ <span style="color: #e74c3c;">Имя файла для зомби-скачивания</span> 🧟‍♂️
    - **bucket_name**: 🧟‍♀️ <span style="color: #3498db;">Имя зомби-bucket</span> (по умолчанию: "uploads") 🧟‍♂️
    
    Возвращает файл как <span style="background: #8e44ad; color: white; padding: 2px 6px; border-radius: 4px;">зомби-поток данных</span>! 🧟‍♀️
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
    🧟‍♀️ **ЗОМБИ-УНИЧТОЖЕНИЕ ФАЙЛА** 🧟‍♂️
    
    Наши зомби-уничтожители стирают файлы из <span style="background: linear-gradient(45deg, #ff6b6b, #4ecdc4); color: white; padding: 2px 6px; border-radius: 4px;">MinIO</span> хранилища!
    
    - **filename**: 🧟‍♀️ <span style="color: #e74c3c;">Имя файла для зомби-уничтожения</span> 🧟‍♂️
    - **bucket_name**: 🧟‍♀️ <span style="color: #3498db;">Имя зомби-bucket</span> (по умолчанию: "uploads") 🧟‍♂️
    
    Возвращает <span style="background: #e74c3c; color: white; padding: 2px 6px; border-radius: 4px;">зомби-подтверждение</span> об удалении! 🧟‍♀️
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
    🧟‍♀️ **ЗОМБИ-PRESIGNED URL** 🧟‍♂️
    
    Наши зомби-маги создают <span style="background: linear-gradient(45deg, #f39c12, #e67e22); color: white; padding: 2px 6px; border-radius: 4px;">временные зомби-ссылки</span> для доступа к файлам!
    
    - **filename**: 🧟‍♀️ <span style="color: #e74c3c;">Имя зомби-файла</span> 🧟‍♂️
    - **bucket_name**: 🧟‍♀️ <span style="color: #3498db;">Имя зомби-bucket</span> (по умолчанию: "uploads") 🧟‍♂️
    - **expires**: 🧟‍♀️ <span style="color: #9b59b6;">Время жизни зомби-ссылки</span> в секундах (по умолчанию: 3600) 🧟‍♂️
    
    Возвращает <span style="background: #16a085; color: white; padding: 2px 6px; border-radius: 4px;">зомби-presigned URL</span> для безопасного доступа! 🧟‍♀️
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
    🧟‍♀️ **ЗОМБИ-ПРОВЕРКА ЗДОРОВЬЯ** 🧟‍♂️
    
    Наши зомби-доктора проверяют состояние всех <span style="background: linear-gradient(45deg, #ff6b6b, #4ecdc4); color: white; padding: 2px 6px; border-radius: 4px;">зомби-сервисов</span> API!
    
    Возвращает <span style="background: #27ae60; color: white; padding: 2px 6px; border-radius: 4px;">зомби-статус</span> MinIO и общее состояние зомби-системы! 🧟‍♀️
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
    🧟‍♀️ **ЗОМБИ-СОЗДАНИЕ ПОЛЬЗОВАТЕЛЯ** 🧟‍♂️
    
    Наши зомби-акушеры создают нового <span style="background: linear-gradient(45deg, #f093fb, #f5576c); color: white; padding: 2px 6px; border-radius: 4px;">зомби-пользователя</span> в системе!
    
    - **username**: 🧟‍♀️ <span style="color: #e74c3c;">Уникальное зомби-имя</span> пользователя 🧟‍♂️
    - **email**: 🧟‍♀️ <span style="color: #3498db;">Зомби-email адрес</span> (должен быть уникальным) 🧟‍♂️
    - **password**: 🧟‍♀️ <span style="color: #9b59b6;">Зомби-пароль</span> (минимум 6 символов) 🧟‍♂️
    - **full_name**: 🧟‍♀️ <span style="color: #f39c12;">Полное зомби-имя</span> (опционально) 🧟‍♂️
    - **bio**: 🧟‍♀️ <span style="color: #16a085;">Зомби-биография</span> (опционально) 🧟‍♂️
    - **avatar_url**: 🧟‍♀️ <span style="color: #8e44ad;">Ссылка на зомби-аватар</span> (опционально) 🧟‍♂️
    
    Возвращает <span style="background: #27ae60; color: white; padding: 2px 6px; border-radius: 4px;">зомби-информацию</span> о созданном пользователе! 🧟‍♀️
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
    🧟‍♀️ **ЗОМБИ-СПИСОК ПОЛЬЗОВАТЕЛЕЙ** 🧟‍♂️
    
    Наши зомби-переписчики составляют <span style="background: linear-gradient(45deg, #667eea, #764ba2); color: white; padding: 2px 6px; border-radius: 4px;">зомби-список</span> всех пользователей!
    
    - **skip**: 🧟‍♀️ <span style="color: #e74c3c;">Количество записей для зомби-пропуска</span> (по умолчанию: 0) 🧟‍♂️
    - **limit**: 🧟‍♀️ <span style="color: #3498db;">Максимальное количество зомби-записей</span> (по умолчанию: 100) 🧟‍♂️
    
    Возвращает <span style="background: #27ae60; color: white; padding: 2px 6px; border-radius: 4px;">зомби-список</span> пользователей с метаданными! 🧟‍♀️
    """
    users = crud.get_users(db, skip=skip, limit=limit)
    return users

@app.get("/users/{user_id}", response_model=schemas.UserResponse, tags=["👥 Пользователи"])
def read_user(user_id: int, db: Session = Depends(get_db)):
    """
    🧟‍♀️ **ЗОМБИ-ПОИСК ПОЛЬЗОВАТЕЛЯ ПО ID** 🧟‍♂️
    
    Наши зомби-детективы находят пользователя по <span style="background: linear-gradient(45deg, #e74c3c, #c0392b); color: white; padding: 2px 6px; border-radius: 4px;">зомби-идентификатору</span>!
    
    - **user_id**: 🧟‍♀️ <span style="color: #e74c3c;">Уникальный зомби-идентификатор</span> пользователя 🧟‍♂️
    
    Возвращает <span style="background: #27ae60; color: white; padding: 2px 6px; border-radius: 4px;">полную зомби-информацию</span> о пользователе! 🧟‍♀️
    """
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return db_user

@app.put("/users/{user_id}", response_model=schemas.UserResponse, tags=["👥 Пользователи"])
def update_user(user_id: int, user_update: schemas.UserUpdate, db: Session = Depends(get_db)):
    """
    🧟‍♀️ **ЗОМБИ-ОБНОВЛЕНИЕ ПОЛЬЗОВАТЕЛЯ** 🧟‍♂️
    
    Наши зомби-хирурги обновляют информацию о <span style="background: linear-gradient(45deg, #f39c12, #e67e22); color: white; padding: 2px 6px; border-radius: 4px;">зомби-пользователе</span>!
    
    - **user_id**: 🧟‍♀️ <span style="color: #e74c3c;">Уникальный зомби-идентификатор</span> пользователя 🧟‍♂️
    - **user_update**: 🧟‍♀️ <span style="color: #3498db;">Зомби-данные для обновления</span> (все поля опциональны) 🧟‍♂️
    
    Возвращает <span style="background: #27ae60; color: white; padding: 2px 6px; border-radius: 4px;">обновленную зомби-информацию</span> о пользователе! 🧟‍♀️
    """
    db_user = crud.update_user(db, user_id=user_id, user_update=user_update)
    if db_user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return db_user

@app.delete("/users/{user_id}", tags=["👥 Пользователи"])
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """
    🧟‍♀️ **ЗОМБИ-УНИЧТОЖЕНИЕ ПОЛЬЗОВАТЕЛЯ** 🧟‍♂️
    
    Наши зомби-палачи удаляют пользователя из <span style="background: linear-gradient(45deg, #e74c3c, #c0392b); color: white; padding: 2px 6px; border-radius: 4px;">зомби-системы</span>!
    
    - **user_id**: 🧟‍♀️ <span style="color: #e74c3c;">Уникальный зомби-идентификатор</span> пользователя 🧟‍♂️
    
    Возвращает <span style="background: #e74c3c; color: white; padding: 2px 6px; border-radius: 4px;">зомби-подтверждение</span> об удалении! 🧟‍♀️
    """
    success = crud.delete_user(db, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return {"message": "Пользователь успешно удален"}

@app.get("/users/username/{username}", response_model=schemas.UserResponse, tags=["👥 Пользователи"])
def read_user_by_username(username: str, db: Session = Depends(get_db)):
    """
    🧟‍♀️ **ЗОМБИ-ПОИСК ПО USERNAME** 🧟‍♂️
    
    Наши зомби-сыщики находят пользователя по <span style="background: linear-gradient(45deg, #9b59b6, #8e44ad); color: white; padding: 2px 6px; border-radius: 4px;">зомби-имени</span> пользователя!
    
    - **username**: 🧟‍♀️ <span style="color: #e74c3c;">Зомби-имя пользователя</span> для поиска 🧟‍♂️
    
    Возвращает <span style="background: #27ae60; color: white; padding: 2px 6px; border-radius: 4px;">полную зомби-информацию</span> о пользователе! 🧟‍♀️
    """
    db_user = crud.get_user_by_username(db, username=username)
    if db_user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return db_user
