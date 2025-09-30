from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import List
import io
import mimetypes
from .minio_client import minio_client

app = FastAPI(title="FastAPI with MinIO", version="1.0.0")

@app.get("/")
def read_root():
    return {"message": "Hello zombie world! MinIO is connected!"}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), bucket_name: str = "uploads"):
    """Загружает файл в MinIO"""
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

@app.get("/files")
async def list_files(bucket_name: str = "uploads", prefix: str = ""):
    """Получает список файлов в bucket"""
    try:
        files = minio_client.list_files(bucket_name, prefix)
        return {
            "bucket": bucket_name,
            "files": files,
            "count": len(files)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")

@app.get("/download/{filename}")
async def download_file(filename: str, bucket_name: str = "uploads"):
    """Скачивает файл из MinIO"""
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

@app.delete("/files/{filename}")
async def delete_file(filename: str, bucket_name: str = "uploads"):
    """Удаляет файл из MinIO"""
    try:
        success = minio_client.delete_file(bucket_name, filename)
        
        if success:
            return {"message": f"Файл '{filename}' успешно удален"}
        else:
            raise HTTPException(status_code=500, detail="Ошибка при удалении файла")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")

@app.get("/files/{filename}/url")
async def get_file_url(filename: str, bucket_name: str = "uploads", expires: int = 3600):
    """Получает presigned URL для доступа к файлу"""
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

@app.get("/health")
async def health_check():
    """Проверка состояния сервиса"""
    return {
        "status": "healthy",
        "minio_endpoint": minio_client.endpoint,
        "message": "FastAPI и MinIO работают корректно"
    }
