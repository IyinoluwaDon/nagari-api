from unittest.mock import patch

from app import email_service, models
from app.database import SessionLocal

VALID = {
    "full_name": "Ada  Okafor",
    "school_name": "Bright Future Academy",
    "email": "  ADA@School.com ",
    "phone": "0810 919 8446",
    "role": "principal",
    "message": "We would like a demo.",
}
ADMIN = {"X-Admin-Key": "test-admin-key"}


def test_submit_success_stores_clean_data_with_new_status(client):
    with patch("app.main.email_service.send_notification", return_value=True) as send:
        r = client.post("/api/demo-requests", json=VALID)
    assert r.status_code == 201
    assert r.json()["id"] > 0
    send.assert_called_once()

    rows = client.get("/api/demo-requests", headers=ADMIN).json()
    assert len(rows) == 1
    row = rows[0]
    assert row["full_name"] == "Ada Okafor"
    assert row["email"] == "ada@school.com"
    assert row["phone"] == "08109198446"
    assert row["status"] == "New"
    assert row["created_at"]
    assert row["email_sent"] is True


def test_message_is_optional(client):
    body = {k: v for k, v in VALID.items() if k != "message"}
    with patch("app.main.email_service.send_notification", return_value=True):
        assert client.post("/api/demo-requests", json=body).status_code == 201


def test_validation_errors_are_per_field(client):
    r = client.post(
        "/api/demo-requests",
        json={"full_name": "A", "school_name": "", "email": "nope", "phone": "abc", "role": "hacker"},
    )
    assert r.status_code == 422
    errors = r.json()["errors"]
    for field in ("full_name", "school_name", "email", "phone", "role"):
        assert field in errors
    assert client.get("/api/demo-requests", headers=ADMIN).json() == []


def test_missing_fields(client):
    r = client.post("/api/demo-requests", json={})
    assert r.status_code == 422
    assert r.json()["errors"]["email"] == "This field is required."


def test_international_phone_accepted(client):
    with patch("app.main.email_service.send_notification", return_value=True):
        r = client.post("/api/demo-requests", json={**VALID, "phone": "+234 810 919 8446"})
    assert r.status_code == 201


def test_email_failure_does_not_fail_submission(client):
    with patch("app.email_service.smtplib.SMTP", side_effect=OSError("smtp down")), \
         patch("app.email_service.get_settings") as gs:
        gs.return_value.resend_api_key = ""
        gs.return_value.smtp_user = "x@gmail.com"
        gs.return_value.smtp_password = "pw"
        gs.return_value.smtp_host = "h"
        gs.return_value.smtp_port = 587
        r = client.post("/api/demo-requests", json=VALID)
    assert r.status_code == 201
    row = client.get("/api/demo-requests", headers=ADMIN).json()[0]
    assert row["email_sent"] is False


def test_honeypot_stores_nothing(client):
    r = client.post("/api/demo-requests", json={**VALID, "website": "http://spam.example"})
    assert r.status_code == 201
    assert client.get("/api/demo-requests", headers=ADMIN).json() == []


def test_admin_endpoints_need_key(client):
    assert client.get("/api/demo-requests").status_code == 401
    assert client.get("/api/demo-requests", headers={"X-Admin-Key": "wrong"}).status_code == 401


def test_status_update_and_filter(client):
    with patch("app.main.email_service.send_notification", return_value=True):
        rid = client.post("/api/demo-requests", json=VALID).json()["id"]
    r = client.patch(f"/api/demo-requests/{rid}/status", json={"status": "Contacted"}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["status"] == "Contacted"
    assert len(client.get("/api/demo-requests?status=Contacted", headers=ADMIN).json()) == 1
    assert client.get("/api/demo-requests?status=New", headers=ADMIN).json() == []
    bad = client.patch(f"/api/demo-requests/{rid}/status", json={"status": "Bogus"}, headers=ADMIN)
    assert bad.status_code == 422
    assert client.patch("/api/demo-requests/999/status", json={"status": "New"}, headers=ADMIN).status_code == 404


def test_rate_limit(client, monkeypatch):
    from app import rate_limit
    monkeypatch.setattr(rate_limit, "get_settings", lambda: type("S", (), {"rate_limit_per_hour": 2})())
    with patch("app.main.email_service.send_notification", return_value=True):
        codes = [client.post("/api/demo-requests", json=VALID).status_code for _ in range(3)]
    assert codes == [201, 201, 429]


def test_email_content_escapes_html_and_sets_reply_to():
    req = models.DemoRequest(
        id=7, full_name="Ada", school_name="Bright\r\nBcc: evil@x.com",
        email="ada@school.com", phone="08109198446", role="principal",
        message="<script>alert(1)</script>",
    )
    from datetime import datetime, timezone
    req.created_at = datetime(2026, 9, 29, 10, 0, tzinfo=timezone.utc)
    with patch("app.email_service.get_settings") as gs:
        gs.return_value.smtp_user = "from@gmail.com"
        gs.return_value.notify_email = "nagarischoolsystem@gmail.com"
        msg = email_service.build_notification(req)
    assert msg["To"] == "nagarischoolsystem@gmail.com"
    assert msg["Reply-To"] == "ada@school.com"
    assert "\n" not in msg["Subject"] and "\r" not in msg["Subject"]
    html = msg.get_body(preferencelist=("html",)).get_content()
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_timestamps_are_utc_tagged(client):
    with patch("app.main.email_service.send_notification", return_value=True):
        client.post("/api/demo-requests", json=VALID)
    created = client.get("/api/demo-requests", headers=ADMIN).json()[0]["created_at"]
    assert created.endswith("Z") or created.endswith("+00:00")


def _fake_req():
    from datetime import datetime, timezone
    req = models.DemoRequest(
        id=3, full_name="Ada", school_name="Bright Future", email="ada@school.com",
        phone="08109198446", role="principal", message="Hi",
    )
    req.created_at = datetime(2026, 9, 29, 10, 0, tzinfo=timezone.utc)
    return req


def test_resend_is_used_when_key_is_set():
    class Resp:
        status_code = 200
        text = "{}"
    with patch("app.email_service.get_settings") as gs, \
         patch("app.email_service.httpx.post", return_value=Resp()) as post:
        gs.return_value.resend_api_key = "re_test"
        gs.return_value.resend_from = "Nagari Website <onboarding@resend.dev>"
        gs.return_value.notify_email = "nagarischoolsystem@gmail.com"
        gs.return_value.smtp_user = ""
        assert email_service.send_notification(_fake_req()) is True
    kwargs = post.call_args.kwargs
    assert post.call_args.args[0] == "https://api.resend.com/emails"
    assert kwargs["headers"]["Authorization"] == "Bearer re_test"
    body = kwargs["json"]
    assert body["to"] == ["nagarischoolsystem@gmail.com"]
    assert body["reply_to"] == "ada@school.com"
    assert "Bright Future" in body["subject"] and body["html"] and body["text"]


def test_resend_rejection_returns_false():
    class Resp:
        status_code = 403
        text = "only your own address"
    with patch("app.email_service.get_settings") as gs, \
         patch("app.email_service.httpx.post", return_value=Resp()):
        gs.return_value.resend_api_key = "re_test"
        gs.return_value.resend_from = "x"
        gs.return_value.notify_email = "n@x.com"
        gs.return_value.smtp_user = ""
        assert email_service.send_notification(_fake_req()) is False


def test_db_url_normalisation_and_driver_loads():
    from sqlalchemy import create_engine
    from app.database import normalize_db_url
    for raw in ("postgres://u:p@h/db?sslmode=require", "postgresql://u:p@h/db?sslmode=require"):
        url = normalize_db_url(raw)
        assert url == "postgresql+psycopg://u:p@h/db?sslmode=require"
        create_engine(url)  # loads the psycopg driver without connecting
    assert normalize_db_url("sqlite:///./x.db") == "sqlite:///./x.db"
