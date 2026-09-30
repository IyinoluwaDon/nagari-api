import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import email_service, models, schemas
from .config import get_settings
from .database import Base, SessionLocal, engine, get_db
from .rate_limit import check_rate_limit

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nagari")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Nagari API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "X-Admin-Key"],
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    """Return {"errors": {"field": "message"}} so the frontend can show inline errors."""
    errors: dict[str, str] = {}
    for err in exc.errors():
        field = str(err["loc"][-1]) if err["loc"] else "form"
        msg = err["msg"].removeprefix("Value error, ")
        if err["type"] == "missing":
            msg = "This field is required."
        elif err["type"] == "string_too_short":
            msg = f"Must be at least {err['ctx']['min_length']} characters."
        elif err["type"] == "string_too_long":
            msg = f"Must be at most {err['ctx']['max_length']} characters."
        elif err["type"] == "literal_error":
            msg = "Please choose a valid option."
        elif err["type"] == "value_error" and field == "email":
            msg = "Enter a valid email address."
        errors.setdefault(field, msg)
    return JSONResponse(
        status_code=422,
        content={"detail": "Please check the highlighted fields.", "errors": errors},
    )


def require_admin(x_admin_key: str | None = Header(default=None)) -> None:
    key = get_settings().admin_api_key
    if not key:
        raise HTTPException(status_code=503, detail="Admin access is not configured.")
    if not x_admin_key or not secrets.compare_digest(x_admin_key, key):
        raise HTTPException(status_code=401, detail="Invalid admin key.")


def _notify_and_record(request_id: int) -> None:
    """Runs after the response is sent. Email failure never affects the user."""
    with SessionLocal() as db:
        req = db.get(models.DemoRequest, request_id)
        if req and email_service.send_notification(req):
            req.email_sent = True
            db.commit()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post(
    "/api/demo-requests",
    response_model=schemas.DemoRequestCreated,
    status_code=201,
    dependencies=[Depends(check_rate_limit)],
)
def create_demo_request(
    payload: schemas.DemoRequestCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    thanks = "Thank you. Your request has been received. Our team will contact you soon."

    if payload.website:  # honeypot tripped: pretend success, store nothing
        return schemas.DemoRequestCreated(id=0, message=thanks)

    req = models.DemoRequest(
        full_name=payload.full_name,
        school_name=payload.school_name,
        email=payload.email,
        phone=payload.phone,
        role=payload.role,
        message=payload.message,
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    background.add_task(_notify_and_record, req.id)
    return schemas.DemoRequestCreated(id=req.id, message=thanks)


@app.get(
    "/api/demo-requests",
    response_model=list[schemas.DemoRequestOut],
    dependencies=[Depends(require_admin)],
)
def list_demo_requests(
    status: models.RequestStatus | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(models.DemoRequest).order_by(models.DemoRequest.created_at.desc())
    if status:
        stmt = stmt.where(models.DemoRequest.status == status)
    return db.scalars(stmt.limit(limit).offset(offset)).all()


@app.patch(
    "/api/demo-requests/{request_id}/status",
    response_model=schemas.DemoRequestOut,
    dependencies=[Depends(require_admin)],
)
def update_status(
    request_id: int, body: schemas.StatusUpdate, db: Session = Depends(get_db)
):
    req = db.get(models.DemoRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found.")
    req.status = body.status
    db.commit()
    db.refresh(req)
    return req
