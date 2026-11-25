# KEREM Spa — PWA

FastAPI + SQLModel + frontend estático (PWA mobile-first, estilo dark, marca KEREM). DB PostgreSQL en Supabase.

## Ejecutar local

1. **Python 3.11+** y entorno virtual:
```bash
cd /mnt/c/Users/winch/Documents/Desarrollo_python/kerem
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configura `.env`**:
```bash
cp .env.example .env
```
- Para local rápido puedes usar SQLite cambiando `DATABASE_URL=sqlite:///./kerem_local.db` (solo dev; para producción usa Supabase).
- Para Supabase: pega la URI `postgresql+psycopg://...:6543/postgres?sslmode=require`.

3. **Crear tablas + admin + servicios**:
```bash
python -m app.seed
```

4. **Levantar servidor**:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

5. Abre `http://localhost:8000` (cliente) y `http://localhost:8000/dashboard` (admin).
   - Admin inicial: `ADMIN_EMAIL` / `ADMIN_PASSWORD` del `.env`.
   - En celular misma red: `http://IP-DE-TU-PC:8000`.

## Supabase

1. Crea proyecto en https://supabase.com.
2. **Project Settings > Database > Connection string**. Elige **URI** y modo **Transaction pooler** (puerto `6543`).
3. Ajusta el formato para SQLAlchemy/psycopg3:
   ```env
   DATABASE_URL=postgresql+psycopg://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres?sslmode=require
   ```
   > Nota: Supabase puede mostrar `postgresql://`; cámbialo a `postgresql+psycopg://`.
4. En tu máquina, con `.env` apuntando a Supabase:
   ```bash
   python -m app.seed
   ```
   Esto crea tablas y el admin inicial en Supabase.
5. Verifica en Supabase > Table Editor: `user`, `service`, `appointment`, `patientrecord`, `clinicalhistory`, `notification`.

## Vercel

El repo ya incluye `vercel.json`, `main.py` y `.python-version` para FastAPI en Vercel.

1. Sube el proyecto a GitHub (no subas `.env`, `.venv`, `*.db`).
2. En https://vercel.com > **Add New Project** > importa el repo.
3. Framework Preset: **FastAPI** (o auto). Root Directory: `.`.
4. En **Environment Variables** pega las de `vercel-env.example.txt`:
   - `DATABASE_URL`: URI de Supabase transaction pooler con `sslmode=require`.
   - `SECRET_KEY`: valor largo aleatorio (`openssl rand -hex 32`).
   - `ADMIN_*`, `AGENDA_*`, `MAIL_*`, `GOOGLE_*` según necesites.
5. Deploy. Vercel dará `https://tu-proyecto.vercel.app`.
6. Si la DB es nueva, corre seed apuntando a Supabase desde local:
   ```bash
   # con .env usando la DATABASE_URL de Supabase
   python -m app.seed
   ```
   (En Vercel no se corre seed automáticamente).
7. Verifica:
   - `https://tu-proyecto.vercel.app/health` -> `{"status":"ok"}`
   - `https://tu-proyecto.vercel.app/` -> PWA cliente
   - `https://tu-proyecto.vercel.app/dashboard` -> admin

### Google OAuth en producción
En Google Cloud Console, agrega:
- Authorized JavaScript origin: `https://tu-proyecto.vercel.app`
- Authorized redirect URI: `https://tu-proyecto.vercel.app/auth/google/callback`
Y actualiza `GOOGLE_REDIRECT_URI` en Vercel.

## PWA

- Manifest: `/static/manifest.json`
- Service Worker: `/sw.js` (`kerem-shell-v1`)
- Instalable desde Chrome/Edge/Android: menú “Agregar a pantalla de inicio”.
- Offline práctico: app shell disponible; acciones de cita/admin requieren internet.

## Endpoints clave

- Cliente: `/auth/register`, `/auth/login`, `/auth/me`, `/services`, `/appointments/slots`, `/appointments`, `/notifications`
- Admin: `/admin/patients`, `/admin/appointments`, `/admin/services`, `/admin/patients/{id}/ficha`, `/admin/patients/{id}/records`
