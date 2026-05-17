# GST Bharat

GST Bharat is an original SaaS-style eCommerce GST automation platform for Indian sellers. It normalizes marketplace reports, validates GST data, and produces consolidated GSTR-1 JSON, Excel, Tally XML, and 2A/2B reconciliation reports.

## Stack

- Frontend: Next.js, React, Tailwind CSS, shadcn-style local components, TanStack Table, React Hook Form
- Backend: FastAPI, SQLAlchemy, PostgreSQL-ready settings, pandas/openpyxl parsers
- Jobs: lightweight background task abstraction for local processing, ready to move to Celery/RQ

## Quick Start

Backend:

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd apps/web
npm install
npm run dev
```

Open `http://localhost:3000`.

## Environment

Backend defaults to SQLite for local development. Set `DATABASE_URL` to PostgreSQL in production:

```bash
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/gst_bharat
SECRET_KEY=change-me
UPLOAD_DIR=../../storage/uploads
EXPORT_DIR=../../storage/exports
```

## Modules

- Auth and GST profiles
- Platform imports for Amazon, Flipkart, Meesho, Myntra, JioMart, Snapdeal, and custom Excel
- Normalized transaction database
- GST classification and validations
- GSTR-1 portal-style JSON and Excel export
- eCom to Tally XML
- 2A/2B reconciliation report

# GST
