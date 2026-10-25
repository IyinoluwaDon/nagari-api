# Nagari Demo Request API

A FastAPI backend for the Nagari website's Request a Demo form. It validates submissions, stores demo requests in a relational database, sends notification email, and provides admin-key-protected listing and status-update endpoints.

The service supports local development with SQLite and the documented Render/Neon/Postgres and Resend deployment configuration. `backend/app/` contains API routes, schemas, persistence, email delivery, and rate limiting; `backend/tests/` covers the request flow. The backend README contains the endpoint reference and deployment settings.

## Run locally

```sh
cd backend
python -m venv .venv
# Activate the environment, then:
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

The interactive API documentation is available at `http://localhost:8000/docs` while the server is running.
