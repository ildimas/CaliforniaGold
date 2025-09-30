#!/usr/bin/env python3
"""
Миграция для добавления поддержки ZIP файлов в таблицу jobs
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Получаем URL базы данных из переменных окружения
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/californiagold")

def migrate_jobs_zip():
    """Добавляет поля для поддержки ZIP файлов в таблицу jobs"""
    try:
        # Создаем подключение к базе данных
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as connection:
            # Начинаем транзакцию
            trans = connection.begin()
            
            try:
                # Проверяем, существует ли таблица jobs
                result = connection.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'jobs'
                    );
                """))
                
                table_exists = result.scalar()
                
                if not table_exists:
                    print("❌ Таблица 'jobs' не существует!")
                    return False
                
                # Проверяем, существуют ли уже нужные колонки
                result = connection.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'jobs' 
                    AND column_name IN ('file_type', 'zip_contents');
                """))
                
                existing_columns = [row[0] for row in result.fetchall()]
                
                # Добавляем колонку file_type если её нет
                if 'file_type' not in existing_columns:
                    print("🔄 Добавляем колонку 'file_type'...")
                    connection.execute(text("""
                        ALTER TABLE jobs 
                        ADD COLUMN file_type VARCHAR(20) DEFAULT 'single';
                    """))
                    print("✅ Колонка 'file_type' добавлена")
                else:
                    print("✅ Колонка 'file_type' уже существует")
                
                # Добавляем колонку zip_contents если её нет
                if 'zip_contents' not in existing_columns:
                    print("🔄 Добавляем колонку 'zip_contents'...")
                    connection.execute(text("""
                        ALTER TABLE jobs 
                        ADD COLUMN zip_contents TEXT;
                    """))
                    print("✅ Колонка 'zip_contents' добавлена")
                else:
                    print("✅ Колонка 'zip_contents' уже существует")
                
                # Создаем индекс для file_type для быстрого поиска
                try:
                    print("🔄 Создаем индекс для 'file_type'...")
                    connection.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_jobs_file_type 
                        ON jobs(file_type);
                    """))
                    print("✅ Индекс для 'file_type' создан")
                except Exception as e:
                    print(f"⚠️  Индекс для 'file_type' уже существует или ошибка: {e}")
                
                # Подтверждаем транзакцию
                trans.commit()
                
                print("✅ Миграция для поддержки ZIP файлов завершена успешно!")
                return True
                
            except SQLAlchemyError as e:
                # Откатываем транзакцию в случае ошибки
                trans.rollback()
                print(f"❌ Ошибка при миграции: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Ошибка подключения к базе данных: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Запуск миграции для поддержки ZIP файлов...")
    success = migrate_jobs_zip()
    
    if success:
        print("🎉 Миграция завершена успешно!")
        sys.exit(0)
    else:
        print("💥 Миграция завершилась с ошибкой!")
        sys.exit(1)
