# Financial Tracker

Веб-приложение для личного и совместного учета доходов и расходов. Стек: Django, Django REST Framework, PostgreSQL, Django templates, CSS и JavaScript.

## Залитый на хостинг
- https://financial-tracker-q1p9.onrender.com/

## Тестовые юзеры (формат логин:пароль):

- testuser:userpass
- user:userpass
- admin:adminpass

## Возможности

- Регистрация, вход и выход через Django-сессии; JWT endpoint доступен для клиентов API.
- Личные категории и операции, группы и роли `OWNER`, `MEMBER`, `OBSERVER`.
- Серверная проверка доступа: владелец управляет группой, категориями и участниками; участник читает данные и меняет свои операции; наблюдатель читает групповые данные.
- Фильтрация операций по типу, категории, группе и датам; агрегат `summary`.
- Экспорт доступных операций в CSV и импорт с проверкой категории, группы и прав.
- Страницы `/login/`, `/register/`, `/`, `/groups/`, `/operations/`, `/statistics/`.

## Структура проекта

- `backend/config/` — настройки Django, корневые URL-маршруты и WSGI/ASGI-конфигурация.
- `backend/finance/` — модели, API, сериализаторы, права доступа, веб-представления, тесты и миграции.
- `backend/templates/finance/` — Django-шаблоны страниц приложения.
- `backend/static/finance/` — общие CSS-стили и JavaScript.
- `backend/manage.py` и `backend/requirements.txt` — управление Django-проектом и Python-зависимости.
- `backend/Dockerfile` и `docker-compose.yml` — конфигурация контейнеров для локальной разработки.
- `render.yaml` — конфигурация развертывания проекта на Render.

## API

- `POST /api/auth/register/` — регистрация (`username`, `email`, `password`).
- `POST /api/auth/login/` — JWT (`username`, `password`); `POST /api/auth/refresh/` — обновление токена.
- `/api/groups/`, `/api/groups/{id}/members/`, `/api/categories/`, `/api/operations/` — CRUD. Добавлять, менять роли и удалять участников может только владелец. В веб-интерфейсе участника добавляют по точному имени пользователя и выбирают роль.
- `GET /api/operations/summary/` — доходы, расходы и баланс.
- `GET /api/operations/export-csv/`; `POST /api/operations/import-csv/` — импорт multipart-файлом `file`.
- Экспорт CSV использует русские заголовки, названия категорий и групп, локальные дату и сумму. Импорт принимает этот формат и старый формат `date,type,amount,category,group,description`; в старом формате category/group задаются UUID, в русском — названиями.
- Фильтры операций: `type`, `category`, `group`, `date_from`, `date_to`.

В интерфейсе DRF использует Django-сессию и CSRF. Для внешнего клиента используйте JWT Bearer token.
