## Учёт подменных машин корпоративного автопарка



Монолитное веб-приложение на **Django + PostgreSQL** с ролями (Django Groups), UI на templates и DRF API.



### Требования



- **Python 3.12+**

- **PostgreSQL 14+**



### Быстрый старт (Windows / PowerShell)



1) Создайте виртуальное окружение и установите зависимости:



```powershell

.\.venv\Scripts\python.exe -m pip install -r requirements.txt

```



Если `.venv` ещё нет:



```powershell

& "C:\Users\<YOU>\AppData\Local\Programs\Python\Python312\python.exe" -m venv .venv

.\.venv\Scripts\python.exe -m pip install -r requirements.txt

```



2) Создайте `.env` на основе примера:



- Скопируйте `.env.example` → `.env`

- Укажите `DJANGO_SECRET_KEY` и параметры `DB_*`



3) Создайте БД в PostgreSQL (пример):



```sql

CREATE DATABASE cars_app;

```



4) Миграции:



```powershell

.\.venv\Scripts\python.exe manage.py migrate

```



5) Создайте группы ролей:



```powershell

.\.venv\Scripts\python.exe manage.py bootstrap_roles

```



6) (Опционально) Загрузите примерные фикстуры (группы + авто):



```powershell

.\.venv\Scripts\python.exe manage.py loaddata fixtures/demo.json

```



7) (Рекомендуется) Засидьте демо-данные (пользователи/заявки/выдачи/логи/отчёты):



```powershell

.\.venv\Scripts\python.exe manage.py seed_demo

```



8) Запуск:



```powershell

.\.venv\Scripts\python.exe manage.py runserver

```



### Разработка: тесты и линтер



Установка dev-зависимостей:



```powershell

.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

```



Запуск тестов:



```powershell

.\.venv\Scripts\python.exe -m pytest

```



(Допустим и `manage.py test` — те же кейсы в `requests.tests`.)



Проверка стиля:



```powershell

.\.venv\Scripts\ruff.exe check .

```



**Примечание:** приложение Django называется `requests`, из‑за этого не используйте `rest_framework.test.APIClient` в тестах внутри пакета `requests` — импорт пересекается с PyPI-пакетом `requests`. В проекте для API используются `django.test.Client` и сессионная аутентификация (или токен через HTTP).



### Роли (Groups)



- `employee`: создание заявки + просмотр своих заявок

- `service_admin`: управление заявками + автопарком + отчёты

- `sys_admin`: CRUD пользователей + просмотр логов



### UI страницы



- `/login/`, `/logout/`

- Сотрудник: `/requests/`, `/requests/new/`

- Администратор: `/requests/admin/dashboard/`, `/requests/admin/`, `/fleet/admin/`, `/reports/admin/`

- Системный админ: `/sysadmin/users/`, `/sysadmin/logs/`



### API (DRF)



Базовый префикс: `/api/`



- `/api/cars/`

- `/api/requests/`

  - actions: `/api/requests/{id}/approve/`, `/reject/`, `/pending/`, `/assign/`, `/complete/`

- `/api/reports/`

- `/api/logs/`



**Аутентификация:** сессия (браузер, CSRF) или **токен** DRF.



- Получить токен: `POST /api/auth/token/` с телом JSON `{"username": "...", "password": "..."}`.

- Запросы к API: заголовок `Authorization: Token <ваш_токен>`.



**Лимиты запросов (throttling):** для анонимных и авторизованных пользователей; в процессе `pytest` отключаются автоматически. Настройка через переменные `DRF_THROTTLE_ANON` и `DRF_THROTTLE_USER` (например `100/hour`).



**Проверка живости:**



- `GET /api/health/` — процесс отвечает.

- `GET /api/health/ready/` — проверка подключения к БД; при ошибке ответ **503** (для балансировщика / оркестратора).



### Продакшен: переменные окружения



При `DJANGO_DEBUG=0` рекомендуется задать:



- `DJANGO_ALLOWED_HOSTS` — список хостов через запятую.

- `DJANGO_CSRF_TRUSTED_ORIGINS` — полные origin с схемой, например `https://app.example.com` (через запятую при нескольких).

- `DJANGO_SECRET_KEY` — уникальный секрет.

- При работе за **Nginx** с TLS: `DJANGO_USE_PROXY_SSL_HEADER=1` (по умолчанию), заголовки `X-Forwarded-Proto` и `X-Forwarded-For` от прокси.

- `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_SESSION_COOKIE_SECURE`, `DJANGO_CSRF_COOKIE_SECURE` — по умолчанию включены при `DEBUG=0`; отключайте только если понимаете последствия.

- **HSTS:** `DJANGO_SECURE_HSTS_SECONDS` — выставляйте в ненулевое значение (например `31536000`) только когда сайт **всегда** отдаётся по HTTPS.



Уровень логов в консоль: `DJANGO_LOG_LEVEL` (по умолчанию `INFO`).



### Деплой: Gunicorn + Nginx (черновик)



1. На сервере: Python, venv, `pip install -r requirements.txt`, `.env` с прод-значениями, `migrate`, `bootstrap_roles`, при необходимости `collectstatic`:



```bash

python manage.py collectstatic --noinput

```



2. Запуск приложения (пример, unix-сокет или порт на loopback):



```bash

gunicorn config.wsgi:application --bind 127.0.0.1:8001 --workers 3

```



3. **Nginx:** `proxy_pass` на адрес Gunicorn; передать `X-Forwarded-For` и `X-Forwarded-Proto`; статику отдавать из `STATIC_ROOT` (после `collectstatic`), при необходимости — отдельный `location` для `MEDIA_URL`.



4. При обновлении: новый код, миграции, `collectstatic` при изменении статики, перезапуск Gunicorn.



### Демо-доступы (после `seed_demo`)



- `employee` / `demo12345`

- `service_admin` / `demo12345`

- `sys_admin` / `demo12345`


