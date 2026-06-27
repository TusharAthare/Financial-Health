# Financial Health

Personal finance analyzer — India-first (INR), privacy-first, PDF/CSV statement analysis.

## Stack

- **Backend**: Django 5.1 + DRF, PostgreSQL, Redis, Celery, JWT auth
- **Frontend**: React + TypeScript (Vite), TanStack Query, Tailwind CSS

## Quick start

### Backend

```bash
poetry config virtualenvs.in-project true
poetry install
cp .env.example .env

# Start Postgres + Redis
docker compose up -d db redis

# Migrate and run
poetry run python manage.py migrate
poetry run python manage.py runserver
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### Tests

```bash
ENVIRONMENT=TESTING poetry run python manage.py test core.tests
```

## API endpoints (Phase 1)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register/` | Register user |
| POST | `/api/auth/login/` | Login (JWT) |
| POST | `/api/refresh-token/` | Refresh access token |
| POST | `/api/logout/` | Blacklist refresh token |
| GET | `/api/core/me/` | Current user profile |
| GET/POST | `/api/statements/accounts/` | List/create accounts (tenant-scoped) |
