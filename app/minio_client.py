import os
from minio import Minio
from minio.error import S3Error
from typing import Optional, BinaryIO
import logging

logger = logging.getLogger(__name__)

class MinIOClient:
    def __init__(self):
        self.endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.secure = False  # Для локальной разработки
        
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )
        
        # Создаем bucket по умолчанию при инициализации
        self._ensure_bucket_exists("uploads")
    
    def _ensure_bucket_exists(self, bucket_name: str):
        """Создает bucket если он не существует"""
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                logger.info(f"Bucket '{bucket_name}' создан")
        except S3Error as e:
            logger.error(f"Ошибка при создании bucket '{bucket_name}': {e}")
    
    def upload_file(self, bucket_name: str, object_name: str, file_data: BinaryIO, 
                   content_type: str = "application/octet-stream") -> bool:
        """Загружает файл в MinIO"""
        try:
            file_data.seek(0)  # Перемещаем указатель в начало файла
            
            # Получаем размер файла
            file_data.seek(0, 2)  # Перемещаемся в конец файла
            file_size = file_data.tell()  # Получаем размер
            file_data.seek(0)  # Возвращаемся в начало
            
            self.client.put_object(
                bucket_name, 
                object_name, 
                file_data, 
                length=file_size,  # Указываем точный размер файла
                content_type=content_type
            )
            logger.info(f"Файл '{object_name}' успешно загружен в bucket '{bucket_name}'")
            return True
        except S3Error as e:
            logger.error(f"Ошибка при загрузке файла: {e}")
            return False
    
    def download_file(self, bucket_name: str, object_name: str) -> Optional[bytes]:
        """Скачивает файл из MinIO"""
        try:
            response = self.client.get_object(bucket_name, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            logger.info(f"Файл '{object_name}' успешно скачан из bucket '{bucket_name}'")
            return data
        except S3Error as e:
            logger.error(f"Ошибка при скачивании файла: {e}")
            return None
    
    def delete_file(self, bucket_name: str, object_name: str) -> bool:
        """Удаляет файл из MinIO"""
        try:
            self.client.remove_object(bucket_name, object_name)
            logger.info(f"Файл '{object_name}' успешно удален из bucket '{bucket_name}'")
            return True
        except S3Error as e:
            logger.error(f"Ошибка при удалении файла: {e}")
            return False
    
    def list_files(self, bucket_name: str, prefix: str = "") -> list:
        """Получает список файлов в bucket"""
        try:
            objects = self.client.list_objects(bucket_name, prefix=prefix, recursive=True)
            files = []
            for obj in objects:
                files.append({
                    "name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified
                })
            return files
        except S3Error as e:
            logger.error(f"Ошибка при получении списка файлов: {e}")
            return []
    
    def get_presigned_url(self, bucket_name: str, object_name: str, 
                         expires_in_seconds: int = 3600) -> Optional[str]:
        """Получает presigned URL для доступа к файлу"""
        try:
            url = self.client.presigned_get_object(bucket_name, object_name, 
                                                 expires_in_seconds)
            return url
        except S3Error as e:
            logger.error(f"Ошибка при создании presigned URL: {e}")
            return None

# Глобальный экземпляр клиента
minio_client = MinIOClient()
