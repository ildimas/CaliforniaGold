import os
import uuid
from minio import Minio
from minio.error import S3Error
from typing import Optional, Tuple
import mimetypes

# Настройки MinIO
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "californiagold")

def get_minio_client() -> Minio:
    """Создает клиент MinIO"""
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False  # Используем HTTP для локальной разработки
    )

def ensure_bucket_exists(client: Minio, bucket_name: str = MINIO_BUCKET) -> bool:
    """Проверяет существование bucket и создает его если нужно"""
    try:
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            print(f"✅ Bucket '{bucket_name}' создан")
        return True
    except S3Error as e:
        print(f"❌ Ошибка при создании bucket: {e}")
        return False

def upload_file_to_minio(file_content: bytes, file_name: str, content_type: Optional[str] = None) -> Tuple[bool, str]:
    """
    Загружает файл в MinIO
    
    Returns:
        Tuple[bool, str]: (success, file_path)
    """
    try:
        client = get_minio_client()
        
        # Убеждаемся что bucket существует
        if not ensure_bucket_exists(client):
            return False, ""
        
        # Генерируем уникальный путь для файла
        file_uuid = str(uuid.uuid4())
        file_extension = os.path.splitext(file_name)[1]
        object_name = f"jobs/{file_uuid}{file_extension}"
        
        # Определяем content type если не указан
        if not content_type:
            content_type, _ = mimetypes.guess_type(file_name)
            if not content_type:
                content_type = "application/octet-stream"
        
        # Загружаем файл
        from io import BytesIO
        file_data = BytesIO(file_content)
        
        client.put_object(
            MINIO_BUCKET,
            object_name,
            file_data,
            len(file_content),
            content_type=content_type
        )
        
        print(f"✅ Файл '{file_name}' загружен в MinIO как '{object_name}'")
        return True, object_name
        
    except S3Error as e:
        print(f"❌ Ошибка загрузки файла в MinIO: {e}")
        return False, ""
    except Exception as e:
        print(f"❌ Неожиданная ошибка при загрузке файла: {e}")
        return False, ""

def get_file_from_minio(object_name: str) -> Tuple[bool, bytes]:
    """
    Получает файл из MinIO
    
    Returns:
        Tuple[bool, bytes]: (success, file_content)
    """
    try:
        client = get_minio_client()
        
        response = client.get_object(MINIO_BUCKET, object_name)
        file_content = response.read()
        response.close()
        response.release_conn()
        
        return True, file_content
        
    except S3Error as e:
        print(f"❌ Ошибка получения файла из MinIO: {e}")
        return False, b""
    except Exception as e:
        print(f"❌ Неожиданная ошибка при получении файла: {e}")
        return False, b""

def delete_file_from_minio(object_name: str) -> bool:
    """
    Удаляет файл из MinIO
    
    Returns:
        bool: success
    """
    try:
        client = get_minio_client()
        client.remove_object(MINIO_BUCKET, object_name)
        print(f"✅ Файл '{object_name}' удален из MinIO")
        return True
        
    except S3Error as e:
        print(f"❌ Ошибка удаления файла из MinIO: {e}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка при удалении файла: {e}")
        return False

def get_file_url(object_name: str, expires_in_seconds: int = 3600) -> str:
    """
    Получает временную URL для доступа к файлу
    
    Returns:
        str: URL для доступа к файлу
    """
    try:
        client = get_minio_client()
        return client.presigned_get_object(MINIO_BUCKET, object_name, expires_in_seconds)
    except S3Error as e:
        print(f"❌ Ошибка получения URL файла: {e}")
        return ""
