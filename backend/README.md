# Nagari Backend (FastAPI)

Handles the "Request a Demo" form: validates, stores in a database, and emails
nagarischoolsystem@gmail.com.

## Run locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
# edit .env (see "Email setup" below)
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

Frontend (separate terminal, from the project root):

```bash
cp .env.local.example .env.local   # Windows: copy .env.local.example .env.local
npm run dev
```

## Email setup (Gmail)

1. Turn on 2-Step Verification for the Gmail account.
2. Create an App Password at https://myaccount.google.com/apppasswords
3. Put it in `.env` as `SMTP_PASSWORD` (your normal Gmail password will NOT work).

If SMTP is not configured or fails, the request is still saved and the user still
sees success. The row's `email_sent` column stays `false`, so you can spot misses.

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/demo-requests` | none | Form submission (rate limited) |
| GET | `/api/demo-requests?status=New&limit=50&offset=0` | `X-Admin-Key` | List requests, newest first |
| PATCH | `/api/demo-requests/{id}/status` | `X-Admin-Key` | Body: `{"status": "Contacted"}` |
| GET | `/health` | none | Uptime check |

Statuses: `New` (default), `Contacted`, `Completed`.

Change a status from the terminal:

```bash
curl -X PATCH http://localhost:8000/api/demo-requests/1/status \
  -H "X-Admin-Key: YOUR_ADMIN_API_KEY" -H "Content-Type: application/json" \
  -d '{"status": "Contacted"}'
```

## Tests

```bash
pytest
```

## Deploying (Render + Neon + Resend)

Backend on Render (web service), database on Neon (Postgres), email through Resend.

Render settings:

- Root Directory: `backend`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips="*"`
- Health Check Path: `/health`

Render environment variables:

| Variable | Value |
|---|---|
| `PYTHON_VERSION` | `3.12.3` |
| `DATABASE_URL` | Neon connection string |
| `RESEND_API_KEY` | key from resend.com |
| `NOTIFY_EMAIL` | `nagarischoolsystem@gmail.com` |
| `CORS_ORIGINS` | your live frontend URL, e.g. `https://yoursite.com` (no trailing slash) |
| `ADMIN_API_KEY` | long random string |

Then set `NEXT_PUBLIC_API_URL` on the frontend host to the Render URL and redeploy the frontend.

Notes:

- Render free web services block SMTP ports, which is why production uses Resend (HTTPS).
- `--forwarded-allow-ips="*"` is required on Render. Without it every visitor looks like one IP
  and the rate limit blocks everyone after a few submissions.
- Free web services sleep after 15 minutes idle; the first request afterwards takes about a minute.
