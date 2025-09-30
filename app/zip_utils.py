import zipfile
import json
import os
from typing import List, Dict, Tuple, Optional
from io import BytesIO
import mimetypes

def is_zip_file(file_content: bytes, filename: str) -> bool:
    """
    Проверяет, является ли файл ZIP архивом
    
    Args:
        file_content: Содержимое файла
        filename: Имя файла
        
    Returns:
        bool: True если файл является ZIP архивом
    """
    # Проверяем расширение файла
    if not filename.lower().endswith('.zip'):
        return False
    
    # Проверяем сигнатуру ZIP файла
    try:
        with zipfile.ZipFile(BytesIO(file_content), 'r') as zip_file:
            # Пытаемся прочитать список файлов
            zip_file.namelist()
            return True
    except (zipfile.BadZipFile, zipfile.LargeZipFile):
        return False
    except Exception:
        return False

def get_zip_contents(file_content: bytes) -> List[Dict[str, str]]:
    """
    Получает список файлов в ZIP архиве
    
    Args:
        file_content: Содержимое ZIP файла
        
    Returns:
        List[Dict]: Список файлов с информацией о каждом
    """
    contents = []
    
    try:
        with zipfile.ZipFile(BytesIO(file_content), 'r') as zip_file:
            for file_info in zip_file.filelist:
                # Пропускаем директории
                if file_info.is_dir():
                    continue
                
                # Получаем информацию о файле
                file_data = {
                    'filename': file_info.filename,
                    'size': file_info.file_size,
                    'compressed_size': file_info.compress_size,
                    'compression_ratio': round((1 - file_info.compress_size / file_info.file_size) * 100, 2) if file_info.file_size > 0 else 0,
                    'modified_time': file_info.date_time,
                    'is_encrypted': file_info.flag_bits & 0x1 != 0,
                    'content_type': mimetypes.guess_type(file_info.filename)[0] or 'application/octet-stream'
                }
                contents.append(file_data)
                
    except Exception as e:
        print(f"❌ Ошибка при чтении ZIP архива: {e}")
        return []
    
    return contents

def validate_zip_file(file_content: bytes, max_files: int = 1000, max_size: int = 100 * 1024 * 1024) -> Tuple[bool, str]:
    """
    Валидирует ZIP файл на предмет безопасности и размера
    
    Args:
        file_content: Содержимое ZIP файла
        max_files: Максимальное количество файлов в архиве
        max_size: Максимальный размер архива в байтах
        
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    try:
        # Проверяем размер файла
        if len(file_content) > max_size:
            return False, f"ZIP файл слишком большой. Максимальный размер: {max_size // (1024*1024)}MB"
        
        with zipfile.ZipFile(BytesIO(file_content), 'r') as zip_file:
            # Проверяем количество файлов
            file_count = len([f for f in zip_file.filelist if not f.is_dir()])
            if file_count > max_files:
                return False, f"ZIP файл содержит слишком много файлов. Максимум: {max_files}"
            
            # Проверяем на zip bombs (файлы с очень высоким коэффициентом сжатия)
            for file_info in zip_file.filelist:
                if file_info.is_dir():
                    continue
                
                # Проверяем на подозрительно высокий коэффициент сжатия
                if file_info.file_size > 0:
                    compression_ratio = file_info.compress_size / file_info.file_size
                    if compression_ratio < 0.01:  # Менее 1% от оригинального размера
                        return False, f"Подозрительный файл в архиве: {file_info.filename} (коэффициент сжатия: {compression_ratio:.2%})"
                
                # Проверяем на слишком длинные имена файлов
                if len(file_info.filename) > 255:
                    return False, f"Слишком длинное имя файла: {file_info.filename}"
                
                # Проверяем на подозрительные пути (zip slip атаки)
                if '..' in file_info.filename or file_info.filename.startswith('/'):
                    return False, f"Подозрительный путь в архиве: {file_info.filename}"
            
            # Проверяем на зашифрованные файлы
            encrypted_files = [f for f in zip_file.filelist if f.flag_bits & 0x1 != 0]
            if encrypted_files:
                return False, f"ZIP файл содержит зашифрованные файлы: {[f.filename for f in encrypted_files]}"
                
    except zipfile.BadZipFile:
        return False, "Поврежденный ZIP файл"
    except zipfile.LargeZipFile:
        return False, "ZIP файл слишком большой для обработки"
    except Exception as e:
        return False, f"Ошибка валидации ZIP файла: {str(e)}"
    
    return True, ""

def extract_zip_file(file_content: bytes, extract_to: str) -> Tuple[bool, List[str]]:
    """
    Извлекает ZIP файл в указанную директорию
    
    Args:
        file_content: Содержимое ZIP файла
        extract_to: Путь для извлечения
        
    Returns:
        Tuple[bool, List[str]]: (success, extracted_files)
    """
    extracted_files = []
    
    try:
        os.makedirs(extract_to, exist_ok=True)
        
        with zipfile.ZipFile(BytesIO(file_content), 'r') as zip_file:
            for file_info in zip_file.filelist:
                if file_info.is_dir():
                    continue
                
                # Безопасное извлечение файла
                safe_path = os.path.normpath(os.path.join(extract_to, file_info.filename))
                
                # Проверяем, что путь находится внутри целевой директории
                if not safe_path.startswith(os.path.normpath(extract_to)):
                    continue
                
                # Создаем директории если нужно
                os.makedirs(os.path.dirname(safe_path), exist_ok=True)
                
                # Извлекаем файл
                with open(safe_path, 'wb') as f:
                    f.write(zip_file.read(file_info.filename))
                
                extracted_files.append(safe_path)
                
    except Exception as e:
        print(f"❌ Ошибка при извлечении ZIP файла: {e}")
        return False, []
    
    return True, extracted_files

def create_zip_from_files(file_paths: List[str], zip_name: str) -> Tuple[bool, bytes]:
    """
    Создает ZIP файл из списка файлов
    
    Args:
        file_paths: Список путей к файлам
        zip_name: Имя ZIP файла
        
    Returns:
        Tuple[bool, bytes]: (success, zip_content)
    """
    try:
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in file_paths:
                if os.path.isfile(file_path):
                    # Добавляем файл в архив
                    arcname = os.path.basename(file_path)
                    zip_file.write(file_path, arcname)
        
        zip_buffer.seek(0)
        return True, zip_buffer.getvalue()
        
    except Exception as e:
        print(f"❌ Ошибка при создании ZIP файла: {e}")
        return False, b""

def get_zip_file_info(file_content: bytes) -> Dict[str, any]:
    """
    Получает общую информацию о ZIP файле
    
    Args:
        file_content: Содержимое ZIP файла
        
    Returns:
        Dict: Информация о ZIP файле
    """
    try:
        with zipfile.ZipFile(BytesIO(file_content), 'r') as zip_file:
            file_list = zip_file.filelist
            
            total_files = len([f for f in file_list if not f.is_dir()])
            total_size = sum(f.file_size for f in file_list if not f.is_dir())
            total_compressed_size = sum(f.compress_size for f in file_list if not f.is_dir())
            
            return {
                'total_files': total_files,
                'total_size': total_size,
                'total_compressed_size': total_compressed_size,
                'compression_ratio': round((1 - total_compressed_size / total_size) * 100, 2) if total_size > 0 else 0,
                'is_encrypted': any(f.flag_bits & 0x1 != 0 for f in file_list),
                'comment': zip_file.comment.decode('utf-8') if zip_file.comment else None
            }
            
    except Exception as e:
        print(f"❌ Ошибка при получении информации о ZIP файле: {e}")
        return {}
