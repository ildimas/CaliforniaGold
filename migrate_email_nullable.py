#!/usr/bin/env python3
"""
Миграция для изменения поля email на nullable в таблице users
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Получаем URL базы данных из переменных окружения
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/californiagold")

def migrate_email_nullable():
    """Изменяет поле email на nullable"""
    try:
        # Создаем подключение к базе данных
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as connection:
            # Начинаем транзакцию
            trans = connection.begin()
            
            try:
                # Проверяем, существует ли таблица users
                result = connection.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'users'
                    );
                """))
                
                table_exists = result.scalar()
                
                if not table_exists:
                    print("❌ Таблица 'users' не существует!")
                    return False
                
                # Проверяем текущее состояние поля email
                result = connection.execute(text("""
                    SELECT is_nullable 
                    FROM information_schema.columns 
                    WHERE table_name = 'users' 
                    AND column_name = 'email';
                """))
                
                current_nullable = result.scalar()
                
                if current_nullable == 'YES':
                    print("✅ Поле 'email' уже nullable")
                    return True
                
                print("🔄 Изменяем поле 'email' на nullable...")
                
                # Изменяем поле email на nullable
                connection.execute(text("""
                    ALTER TABLE users 
                    ALTER COLUMN email DROP NOT NULL;
                """))
                
                # Подтверждаем транзакцию
                trans.commit()
                
                print("✅ Поле 'email' успешно изменено на nullable!")
                return True
                
            except SQLAlchemyError as e:
                # Откатываем транзакцию в случае ошибки
                trans.rollback()
                print(f"❌ Ошибка при изменении поля email: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Ошибка подключения к базе данных: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Запуск миграции для поля email...")
    success = migrate_email_nullable()
    
    if success:
        print("🎉 Миграция завершена успешно!")
        sys.exit(0)
    else:
        print("💥 Миграция завершилась с ошибкой!")
        sys.exit(1)
