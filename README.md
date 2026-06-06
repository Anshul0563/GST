# GST Bharat

GST Bharat is an eCommerce GST automation platform built for Indian sellers. It normalizes marketplace sales data, applies GST validation, and exports compliant reports in:

- GSTR-1 JSON
- Excel and export-ready spreadsheets
- Tally XML vouchers
- 2A/2B reconciliation reports

This repository contains a FastAPI backend and a Next.js frontend for a SaaS-style seller experience.

## Features

- Import marketplace sales from Amazon, Flipkart, Meesho, Myntra, JioMart, Snapdeal, and custom CSV/Excel files
- Normalize transactions with GST tax calculations and GSTIN validation
- Generate consolidated GSTR-1 JSON and Excel reports
- Export Tally-compatible XML vouchers
- Reconcile purchase claims against 2A/2B GST data
- User authentication, billing, and profile management

## Tech Stack

- Backend: Python, FastAPI, SQLAlchemy, Pydantic, pandas
- Frontend: Next.js, React, Tailwind CSS, React Hook Form, TanStack Table
- Data export: openpyxl, xlsxwriter
- Database: SQLite for local development, PostgreSQL-ready via `DATABASE_URL`

## Repository Layout

- `apps/api/` – backend service
- `apps/web/` – frontend application
- `storage/uploads/` – uploaded marketplace files
- `storage/exports/` – generated report files
- `render.yaml` – Render deployment blueprint
- `DEPLOYMENT.md` – deployment instructions

## Local Setup

### Backend

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create or update `apps/api/.env` with development values:

```bash
DATABASE_URL=sqlite:///./gst_bharat.db
SECRET_KEY=replace-with-a-long-random-secret
UPLOAD_DIR=../../storage/uploads
EXPORT_DIR=../../storage/exports
CORS_ORIGINS=http://localhost:3000
```

Run the API:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd apps/web
npm install
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open the app at `http://127.0.0.1:3000`.

## Environment Variables

Recommended local values:

- `DATABASE_URL` – database connection string
- `SECRET_KEY` – application secret
- `UPLOAD_DIR` – path for uploaded files
- `EXPORT_DIR` – path for generated exports
- `CORS_ORIGINS` – allowed frontend origins

For production, use PostgreSQL and strong secrets.

## Testing & Validation

### Backend tests

```bash
cd apps/api
.venv/bin/python -m pytest -q
```

### Frontend checks

```bash
cd apps/web
npm run lint
npm run build
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for Render and Vercel deployment instructions.

## Notes

- Keep `storage/uploads` and `storage/exports` on a persistent volume in production.
- Do not commit database files or generated exports.
- Set `CORS_ORIGINS` to exact frontend domains only.

## Contact

If you need help with setup, testing, or deployment, open an issue or ask the maintainer for the current environment details.
