# API для управления пользователями

## Описание

Добавлена функциональность управления пользователями с подключением к PostgreSQL.

## Новые эндпоинты

### Пользователи
- `POST /users/` - Создание нового пользователя
- `GET /users/` - Получение списка пользователей (с пагинацией)
- `GET /users/{user_id}` - Получение пользователя по ID
- `GET /users/username/{username}` - Получение пользователя по username
- `PUT /users/{user_id}` - Обновление пользователя
- `DELETE /users/{user_id}` - Удаление пользователя

## Модель пользователя

```json
{
  "username": "string",
  "email": "string",
  "full_name": "string (optional)",
  "bio": "string (optional)",
  "avatar_url": "string (optional)",
  "password": "string (только при создании)"
}
```

## Запуск

1. Запустите контейнеры:
```bash
docker-compose up --build
```

2. API будет доступно по адресу: http://localhost:8000
3. Документация API: http://localhost:8000/docs

## База данных

- PostgreSQL доступна на порту 5432
- База данных: `californiagold`
- Пользователь: `postgres`
- Пароль: `password`

## Примеры использования

### Создание пользователя
```bash
curl -X POST "http://localhost:8000/users/" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "full_name": "Test User",
    "password": "securepassword"
  }'
```

### Получение списка пользователей
```bash
curl -X GET "http://localhost:8000/users/"
```

### Получение пользователя по ID
```bash
curl -X GET "http://localhost:8000/users/1"
```
