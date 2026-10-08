# Financial Tracker

Веб-приложение для личного и совместного учета доходов и расходов. Стек: Django, Django REST Framework, PostgreSQL, Django templates, CSS и JavaScript.

## Возможности

- Регистрация, вход и выход через Django-сессии; JWT endpoint доступен для клиентов API.
- Личные категории и операции, группы и роли `OWNER`, `MEMBER`, `OBSERVER`.
- Серверная проверка доступа: владелец управляет группой, категориями и участниками; участник читает данные и меняет свои операции; наблюдатель читает групповые данные.
- Фильтрация операций по типу, категории, группе и датам; агрегат `summary`.
- Экспорт доступных операций в CSV и импорт с проверкой категории, группы и прав.
- Страницы `/login/`, `/register/`, `/`, `/groups/`, `/operations/`, `/statistics/`.

## Локальный запуск через Docker Compose

Нужны Docker Desktop и Docker Compose. Скопируйте `.env.example` в `.env` в корне проекта и при необходимости задайте локальный пароль:

```dotenv
POSTGRES_DB=financial_tracker
POSTGRES_USER=financial_tracker
POSTGRES_PASSWORD=change-me-for-local-use
POSTGRES_HOST=db
POSTGRES_PORT=5432
DJANGO_SECRET_KEY=replace-with-a-long-random-value
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,backend
```

Запуск и остановка:

```sh
docker compose up --build
docker compose down
```

Откройте <http://localhost:8000/>. `docker compose down -v` удаляет локальный том PostgreSQL вместе с данными.

## Размещение на Render

В корне репозитория есть `render.yaml` для Blueprint. Он создаёт Python Web Service из `backend`: устанавливает `requirements.txt`, собирает статику, применяет миграции и запускает `config.wsgi:application` через Gunicorn. WhiteNoise отдаёт собранные статические файлы.

Для Blueprint выберите New → Blueprint и подключите репозиторий. Render передаст внутренний `DATABASE_URL` и сгенерирует `DJANGO_SECRET_KEY`. `DJANGO_DEBUG=0` и `DJANGO_ALLOWED_HOSTS=.onrender.com` заданы в конфигурации; `RENDER_EXTERNAL_HOSTNAME` автоматически добавляется в `ALLOWED_HOSTS` и `CSRF_TRUSTED_ORIGINS`. При ручном создании Python Web Service задайте Root Directory `backend`, Build Command `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate --noinput`, Start Command `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2` и те же переменные окружения.

Blueprint использует бесплатные планы для демо. У бесплатной Render PostgreSQL есть ограничения, включая срок хранения 30 дней; для длительного хранения данных выберите платный план базы перед созданием или обновите его в Render. Подробнее: <https://render.com/docs/free>.

Переменные окружения Django: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`. Для локального Compose также используются `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` и `APP_PORT`.

## API

- `POST /api/auth/register/` — регистрация (`username`, `email`, `password`).
- `POST /api/auth/login/` — JWT (`username`, `password`); `POST /api/auth/refresh/` — обновление токена.
- `/api/groups/`, `/api/groups/{id}/members/`, `/api/categories/`, `/api/operations/` — CRUD. Добавлять, менять роли и удалять участников может только владелец. В веб-интерфейсе участника добавляют по точному имени пользователя и выбирают роль.
- `GET /api/operations/summary/` — доходы, расходы и баланс.
- `GET /api/operations/export-csv/`; `POST /api/operations/import-csv/` — импорт multipart-файлом `file`.
- Экспорт CSV использует русские заголовки, названия категорий и групп, локальные дату и сумму. Импорт принимает этот формат и старый формат `date,type,amount,category,group,description`; в старом формате category/group задаются UUID, в русском — названиями.
- Фильтры операций: `type`, `category`, `group`, `date_from`, `date_to`.

В интерфейсе DRF использует Django-сессию и CSRF. Для внешнего клиента используйте JWT Bearer token.

## Проверки

```sh
cd backend
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test finance
```

Для запуска тестов без PostgreSQL задайте `DJANGO_USE_SQLITE=1`. Приложение в обычном режиме использует PostgreSQL.
