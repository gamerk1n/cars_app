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

### Демо-доступы (после `seed_demo`)

- `employee` / `demo12345`
- `service_admin` / `demo12345`
- `sys_admin` / `demo12345`

