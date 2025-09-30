import time
import psycopg2
from psycopg2 import OperationalError
import os

def wait_for_postgres(max_retries=30, delay=2):
    """Ожидает готовности PostgreSQL"""
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/californiagold")
    
    for attempt in range(max_retries):
        try:
            # Парсим URL для получения параметров подключения
            if database_url.startswith("postgresql://"):
                # Убираем postgresql:// и разделяем
                url_parts = database_url[13:].split("@")
                if len(url_parts) == 2:
                    user_pass = url_parts[0].split(":")
                    host_port_db = url_parts[1].split("/")
                    if len(user_pass) == 2 and len(host_port_db) == 2:
                        user, password = user_pass
                        host_port = host_port_db[0].split(":")
                        host = host_port[0]
                        port = int(host_port[1]) if len(host_port) > 1 else 5432
                        database = host_port_db[1]
                        
                        # Пытаемся подключиться
                        conn = psycopg2.connect(
                            host=host,
                            port=port,
                            database=database,
                            user=user,
                            password=password
                        )
                        conn.close()
                        print(f"✅ PostgreSQL готов! (попытка {attempt + 1})")
                        return True
        except OperationalError as e:
            print(f"⏳ Ожидание PostgreSQL... (попытка {attempt + 1}/{max_retries})")
            time.sleep(delay)
        except Exception as e:
            print(f"❌ Ошибка при подключении к PostgreSQL: {e}")
            time.sleep(delay)
    
    print("❌ Не удалось подключиться к PostgreSQL после всех попыток")
    return False

if __name__ == "__main__":
    wait_for_postgres()
