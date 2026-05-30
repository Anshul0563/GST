# GST Bharat

GST Bharat is a SaaS-style eCommerce GST automation platform for Indian sellers. It normalizes marketplace reports, validates GST data, and produces consolidated GSTR-1 JSON, Excel, Tally XML, and 2A/2B reconciliation reports.

## Stack

- Frontend: Next.js, React, Tailwind CSS, TanStack Table, React Hook Form
- Backend: FastAPI, SQLAlchemy, pandas, openpyxl
- Storage: SQLite for local development, PostgreSQL-ready through `DATABASE_URL`
- Jobs: local background task processing with a path to Celery/RQ later

## Quick Start

Copy the sample environment and start the API:

```bash
cp .env.example apps/api/.env
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the web app in another terminal:

```bash
cd apps/web
npm install
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open `http://127.0.0.1:3000`.

## Environment

Local development defaults to SQLite at `apps/api/gst_bharat.db`. For production, set a strong `SECRET_KEY` and use PostgreSQL:

```bash
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/gst_bharat
SECRET_KEY=replace-with-a-long-random-secret
UPLOAD_DIR=../../storage/uploads
EXPORT_DIR=../../storage/exports
```

Generated SQLite databases, uploads, exports, and build caches are ignored by git. Keep only source code, tests, and stable public assets committed.

## Modules

- Auth, subscription access, and GST profiles
- Platform imports for Amazon, Flipkart, Meesho, Myntra, JioMart, Snapdeal, and custom CSV/Excel
- Normalized transaction database with GST validation
- GSTR-1 portal-style JSON and Excel export
- eCom to Tally XML and voucher export
- 2A/2B reconciliation reports

## Verification

Backend:

```bash
cd apps/api
.venv/bin/python -m pytest -q
```

Frontend:

```bash
cd apps/web
npm run lint
npm run build
```
