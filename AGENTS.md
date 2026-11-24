# NetForDebutant — agent instructions

Repo is a Django/Django REST Framework API. Only `backend/` contains real code; `frontend/` and `mobile/` are empty placeholders.

## Layout
- `backend/` — Django project, settings module `config.settings`, entrypoint `manage.py`
- `backend/config/` — Django settings/urls/wsgi/asgi
- `backend/network/` — the only app: models, api (viewsets/serializers), services (google_oauth), routers, migrations
- `backend/.venv` — existing virtual environment (activated before any django/pip command)

## Setup
1. `cd backend && source .venv/bin/activate`
2. `pip install -r requirements.txt` (venv already has packages installed; only re-run if requirements change)
3. Copy `backend/.env.example` to `backend/.env` if missing — `.env` is gitignored and contains SECRET_KEY, DEBUG, DATABASE_URL, GOOGLE_ID_CLIENT_FOR_WEB
4. PostgreSQL must be running locally: `DATABASE_URL=postgres://...@localhost:5432/netfordebutant` — create the `netfordebutant` database before migrating
5. `DJANGO_SETTINGS_MODULE` defaults to `config.settings` via `manage.py`

## Commands (run from `backend/`, venv activated)
- `python manage.py runserver` — dev server
- `python manage.py migrate` — apply migrations (0001–0005 already exist)
- `python manage.py makemigrations network` — after model changes
- `python manage.py shell` — Django shell
- `python manage.py createsuperuser` — admin user
- `python manage.py test` — test runner (tests live in `backend/network/tests/test_api.py`; no pytest/ruff/mypy config exists)
- `python manage.py spectacular --file schema.yml --validate` — regenerate the committed OpenAPI schema after any endpoint/serializer change

## API documentation (drf-spectacular)
- OpenAPI 3.1 schema + Swagger UI + ReDoc served locally (assets via `drf-spectacular-sidecar`, no CDN):
  - `/api/v1/schema/` (YAML), `/api/v1/schema/?format=json`, `/api/v1/schema/swagger-ui/`, `/api/v1/schema/redoc/`
- `GET /health/` — public health check at repo root (view in `network/views.py`, route in `config/urls.py`): 200 `{"status":"ok","database":"ok"}` or 503 if the DB is unreachable; no auth/throttle by design
- `backend/schema.yml` is committed and checked by `DocumentationTests.test_schema_yml_commité_est_a_jour` — regenerate it whenever you change endpoints/serializers
- Config in `config/settings.py`: `SPECTACULAR_SETTINGS`, `REST_FRAMEWORK['DEFAULT_SCHEMA_CLASS']`; routes in `config/urls.py`
- Custom actions/params are annotated with `@extend_schema` in `network/api/viewset.py` (e.g. `?seuil=` on `ma-progression`, `X-Client-Type` header on auth, response shapes for register/login/stats)
- `SerializerMethodField` types are declared with `@extend_schema_field` in `network/api/serializer.py` — add one if a new method field triggers a schema warning
- Gotcha: `ma-progression` returns a plain list; `UserViewSet.pagination_class` is a property returning `None` for that action, otherwise the schema would wrongly wrap it in a paginated object

## Architecture notes
- Custom user model: `AUTH_USER_MODEL = "network.Utilisateur"` — UUID primary key, `USERNAME_FIELD = "email"`, `username` still required
- Routes are registered in `backend/network/routers.py` (DRF DefaultRouter): `v1/users`, `v1/auth`, `v1/categories`; mounted at `api/` in `config/urls.py`
- JWT via `djangorestframework_simplejwt`: access 10 min, refresh 7 days, rotation + blacklist enabled; endpoints under `v1/auth`: register, login, google_oauth, logout, refresh, csrf_token
- `REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES` is JWT only
- Throttle scopes: `auth_login` 5/min, `auth_register` 3/hour, `auth_google` 10/min

## Auth/CSRF quirks (easy to get wrong)
- Web auth endpoints (register/login/google_oauth/logout/refresh) enforce CSRF unless header `X-Client-Type: mobile` is present
- Mobile clients: skip CSRF, receive access + refresh tokens in the response body
- Web clients: receive `access` in body; `refresh_token` set as httpOnly cookie at path `/api/v1/auth/`; logout/refresh read it from cookies
- `GET v1/auth/csrf_token` returns `csrfToken` for the frontend (ensure_csrf_cookie)
- CORS allowed origins: `https://netfordebutant.com`, `http://localhost:5173`; `CSRF_TRUSTED_ORIGINS` matches
- `CSRF_COOKIE_SECURE = not DEBUG` — secure only when `DEBUG=False`

## Verified gotcha
- `network/services/google_oauth.py` reads `settings.GOOGLE_CLIENT_ID`, but `config/settings.py` defines `GOOGLE_ID_CLIENT_FOR_WEB` (from env `GOOGLE_ID_CLIENT_FOR_WEB`). `GOOGLE_CLIENT_ID` does not exist in settings → calling the `google_oauth` endpoint raises `AttributeError`. Fix one side to match the other before relying on Google OAuth.

## Media / static
- `ImageField` uploads go to `notions/photos/` and `users/avatars/`; served via `static()` only when `DEBUG=True`; `media/` is gitignored

## Git
- Default work branch is `refactor/viewset`; long-lived branches include `main` and many `feature/*` / `fix/*` / `refactor/*` pairs tracked from `origin`