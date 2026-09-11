# Production Deployment

The local SQLite database and the deployed PostgreSQL database are separate. A GST profile created on localhost is not automatically available after deployment.

## Render API

Deploy the API from the repository root using `render.yaml`. In the Render service environment, set:

```text
DATABASE_URL=<Render PostgreSQL connection string>
SECRET_KEY=<long random production secret>
UPLOAD_DIR=/var/data/uploads
EXPORT_DIR=/var/data/exports
CORS_ORIGINS=https://gst-red-ten.vercel.app,https://<your-custom-domain>
```

`CORS_ORIGINS` must contain the exact deployed frontend origins, separated by commas. Do not leave only localhost origins in production.

## Vercel frontend

In the Vercel project settings, add these environment variables for the Production environment before redeploying:

```text
NEXT_PUBLIC_API_BASE=https://gst-txbs.onrender.com
NEXT_PUBLIC_SITE_URL=https://gst-red-ten.vercel.app
```

These values are embedded during the Next.js build, so changing them requires a new deployment.

## GST profiles

After the first production deployment:

1. Open the deployed frontend and register or log in to the production account.
2. Create the GST profile from the GST Profile page.
3. Refresh the page and confirm that the profile is listed under Saved GSTINs.

The API intentionally returns only profiles belonging to the authenticated production user. Local users and local GST profiles are not copied to production.

## Verification

Check the API directly:

```bash
curl https://<your-render-api>.onrender.com/health
```

It should return `{"status":"healthy"}`. If the frontend shows zero profiles, inspect the browser Network tab for `/auth/me` and `/gst-profile`; a `401` means the production session is invalid, while an empty `200` response means that user has not created a profile in the production database.
