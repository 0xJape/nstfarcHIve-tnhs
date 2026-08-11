from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys

import sqlite3
import secrets
import hashlib
import hmac
import csv
import threading
import time
from urllib.request import Request, urlopen
from contextlib import closing
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .operational_db import assign_patient, confirm_pre_registration, create_patient, create_pre_registration, delete_pre_registration, dispatch_webhook_outbox, initialize as initialize_operational_db, list_facilities, list_patients, list_pre_registrations, list_public_facilities, ready as operational_db_ready, review_pre_registration

ROOT = Path(__file__).resolve().parents[1]
API_VERSION = "2.2.1-verification-fix"
SESSIONS: dict[str, str] = {}
AUTH_DB = ROOT / "data" / "archive_auth.sqlite"

def load_local_env() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists(): return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))

load_local_env()
CHAT_SYSTEM_PROMPT = """You are ARCHIVE Care Guide embedded inside the ARCHIVE Region XII website in the Philippines. Discuss only HIV education, testing, prevention, treatment navigation, privacy, ARCHIVE public data, ARCHIVE care registration, and how the ARCHIVE model works. Never diagnose symptoms, estimate personal HIV status or risk, or replace a clinician. Encourage verified HIV testing and qualified care. Always guide users through features available on this website before suggesting outside resources. To find testing, tell users to click “Open private care registration” in this chat or “Find care” in the site header, then choose a verified testing center by selecting a ribbon marker on the ARCHIVE map. Do not tell users to search online, visit another health website, use a US hotline, or provide invented phone numbers. ARCHIVE workflow is exact: 1) choose a verified testing center using a ribbon marker; 2) choose municipality; 3) provide email and/or mobile number and preferred contact channel; 4) explicitly consent to discreet contact; 5) submit and receive a reference code; 6) an authorized care administrator reviews the request; 7) secure instructions follow after acceptance. Initial navigation needs no name, diagnosis, or HIV status. Public maps and forecasts contain aggregate planning data, not personal records or diagnoses. Never ask for names, HIV status, symptoms, passwords, or unnecessary personal details.

If asked what mathematical or forecasting model ARCHIVE uses, answer from these verified project facts: it uses a hybrid Multiple Linear Regression (MLR) and Long Short-Term Memory (LSTM) neural-network model to forecast monthly municipality reported HIV diagnoses, conditional on a regional monthly case total. Final prediction is weighted as 85% MLR plus 15% LSTM: forecast = 0.85 × MLR prediction + 0.15 × LSTM prediction. The saved model bundle reports test R² about 0.929 for the hybrid, but this is development-model performance, not proof of future accuracy. Phase 2 then combines forecasts with population-coupled care-cascade simulation, spatial neighbor effects, Getis-Ord Gi* hotspot analysis, transmission-pressure proxies, uncertainty, and testing-center planning through 2050. State clearly that outputs are aggregate planning scenarios, not official surveillance, individual risk estimates, or diagnoses.

Response format: start with one direct sentence. Then use 2-4 short bullet points beginning with “•” when steps or choices help. End with one brief next action or question. Stay under 90 words unless emergency guidance requires more. Avoid greetings, repetition, medical jargon, long disclaimers, and markdown headings. For unrelated requests, briefly redirect to HIV or ARCHIVE guidance. If immediate danger or emergency symptoms are mentioned, advise local emergency services or urgent clinical care."""

def groq_chat(message: str, history: list[dict[str, str]]) -> str:
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key: raise RuntimeError("GROQ_API_KEY is not configured")
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    messages.extend({"role": item.get("role", "user"), "content": str(item.get("content", ""))[:2000]} for item in history[-8:] if item.get("role") in {"user", "assistant"})
    messages.append({"role": "user", "content": message[:2000]})
    body = json.dumps({"model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"), "messages": messages, "temperature": 0.2, "max_tokens": 350}).encode()
    request = Request("https://api.groq.com/openai/v1/chat/completions", data=body, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "ARCHIVE-care-guide/1.0"}, method="POST")
    with urlopen(request, timeout=25) as response:
        result = json.loads(response.read())
    return str(result["choices"][0]["message"]["content"])

def groq_tts(text: str) -> bytes:
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key: raise RuntimeError("GROQ_API_KEY is not configured")
    body = json.dumps({"model": os.getenv("TTS_MODEL", "canopylabs/orpheus-v1-english"), "input": text[:4000], "voice": os.getenv("TTS_VOICE", "autumn"), "response_format": "wav"}).encode()
    request = Request("https://api.groq.com/openai/v1/audio/speech", data=body, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "ARCHIVE-care-guide/1.0"}, method="POST")
    with urlopen(request, timeout=30) as response: return response.read()

def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"{salt.hex()}${digest.hex()}"

def password_matches(password: str, stored: str) -> bool:
    salt, expected = stored.split("$", 1)
    actual = password_hash(password, bytes.fromhex(salt)).split("$", 1)[1]
    return hmac.compare_digest(actual, expected)

def init_auth_db() -> None:
    username = os.getenv("ARCHIVE_ADMIN_USERNAME", "").strip()
    password = os.getenv("ARCHIVE_ADMIN_PASSWORD", "")
    if not username or not password:
        raise RuntimeError("ARCHIVE_ADMIN_USERNAME and ARCHIVE_ADMIN_PASSWORD are required")
    if os.getenv("RENDER") and len(password) < 12:
        raise RuntimeError("ARCHIVE_ADMIN_PASSWORD must contain at least 12 characters on Render")
    AUTH_DB.parent.mkdir(exist_ok=True)
    with sqlite3.connect(AUTH_DB) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS admin_users (username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, active INTEGER NOT NULL DEFAULT 1)")
        connection.execute(
            "INSERT INTO admin_users (username, password_hash, active) VALUES (?, ?, 1) "
            "ON CONFLICT(username) DO UPDATE SET password_hash=excluded.password_hash, active=1",
            (username, password_hash(password)),
        )

def validate_production_env() -> None:
    if not os.getenv("RENDER"):
        return
    required = ("DATABASE_URL", "ARCHIVE_CORS_ORIGIN", "ARCHIVE_PUBLIC_URL", "ARCHIVE_ADMIN_USERNAME", "ARCHIVE_ADMIN_PASSWORD")
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if missing:
        raise RuntimeError(f"Missing required Render environment variables: {', '.join(missing)}")
    for name in ("ARCHIVE_CORS_ORIGIN", "ARCHIVE_PUBLIC_URL"):
        value = os.environ[name].rstrip("/")
        if not value.startswith("https://") or "localhost" in value or "127.0.0.1" in value:
            raise RuntimeError(f"{name} must be a public HTTPS origin on Render")
        os.environ[name] = value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the latest arcHIVe Phase 2 GIS result")
    parser.add_argument("--host", default=os.getenv("ARCHIVE_API_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("ARCHIVE_API_PORT", "8765")))
    parser.add_argument("--run-dir", default=os.getenv("ARCHIVE_RUN_DIR") or None)
    parser.add_argument("--cors-origin", default=os.getenv("ARCHIVE_CORS_ORIGIN", "http://127.0.0.1:5173"))
    return parser.parse_args()


def resolve_run(explicit: str | None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    pointer = ROOT / "outputs" / "latest_phase2_run.txt"
    if pointer.exists():
        raw = pointer.read_text(encoding="utf-8", errors="ignore").strip().strip('"')
        if raw:
            candidates.append(Path(raw))
            candidates.append(ROOT / raw)
            candidates.append(ROOT / "outputs" / Path(raw.replace("\\", "/")).name)
    candidates.extend(sorted((ROOT / "outputs").glob("phase2_run_*"), reverse=True))
    candidates.extend(sorted((ROOT / "outputs").glob("test_fixture_run_*"), reverse=True))
    for candidate in candidates:
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        if (candidate / "PHASE2_SYSTEM_SUCCESS.txt").exists() and (candidate / "database" / "archive_phase2.sqlite").exists():
            return candidate.resolve()
    raise FileNotFoundError("No completed Phase 2 run was found. Run RUN_PHASE2_SYSTEM.bat first or pass --run-dir.")


def json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")


def first(query: dict[str, list[str]], key: str, default: str = "") -> str:
    return query.get(key, [default])[0]


def parse_limit(raw: str, default: int = 200, maximum: int = 5000) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, maximum))


class Handler(BaseHTTPRequestHandler):
    run_dir: Path
    database_path: Path
    cors_origin = "*"

    def common_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", self.cors_origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Cache-Control", "no-store")

    def send_json(self, payload: Any, status: int = 200) -> None:
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.common_headers()
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        body = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.common_headers()
        self.end_headers()
        self.wfile.write(body)

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        database_uri = self.database_path.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(database_uri, uri=True, timeout=5.0)) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(sql, params).fetchall()]

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.common_headers()
        self.end_headers()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/public/tts":
            try:
                length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length) or b"{}")
                text = str(payload.get("text", "")).strip()
                if not text: raise ValueError("Text is required")
                body = groq_tts(text)
                self.send_response(200); self.send_header("Content-Type", "audio/wav"); self.send_header("Content-Length", str(len(body))); self.common_headers(); self.end_headers(); self.wfile.write(body)
            except ValueError as exc: self.send_json({"error": str(exc)}, status=400)
            except Exception as exc: print(f"TTS upstream error: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True); self.send_json({"error": "Speech service unavailable"}, status=502)
            return
        if path == "/api/public/chat":
            try:
                length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length) or b"{}")
                message = str(payload.get("message", "")).strip()
                if not message: raise ValueError("Message is required")
                self.send_json({"reply": groq_chat(message, payload.get("history", []))})
            except ValueError as exc: self.send_json({"error": str(exc)}, status=400)
            except Exception as exc: print(f"Chat upstream error: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True); self.send_json({"error": "Chat service unavailable"}, status=502)
            return
        if path == "/api/pre-registrations":
            if not operational_db_ready(): self.send_json({"error": "Operational database unavailable"}, status=503); return
            try:
                length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length) or b"{}")
                municipality = str(payload.get("municipality", "")).strip()[:120]
                channel = str(payload.get("preferred_channel", "")); email = str(payload.get("email", "")).strip()[:254]; phone = str(payload.get("phone", "")).strip()[:40]
                contact = email or phone
                if not municipality or channel not in {"email", "sms"} or not contact or payload.get("consent") is not True: raise ValueError("Municipality, contact, channel, and consent are required")
                if email and ("@" not in email or len(email) < 5): raise ValueError("Invalid email")
                if phone and len(phone) < 7: raise ValueError("Invalid phone number")
                self.send_json(create_pre_registration({"municipality": municipality, "preferred_channel": channel, "contact_value": contact, "email": email, "phone": phone, "facility_code": str(payload["facility_code"])}), status=201)
            except (TypeError, ValueError, json.JSONDecodeError) as exc: self.send_json({"error": str(exc)}, status=400)
            return
        if path.startswith("/api/pre-registrations/") and path.endswith("/confirm"):
            try:
                length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length) or b"{}")
                reference_code = unquote(path.split("/api/pre-registrations/", 1)[1].removesuffix("/confirm"))
                result = confirm_pre_registration(reference_code, str(payload.get("token", "")))
                result["delivery"] = dispatch_webhook_outbox()
                self.send_json(result)
            except (TypeError, ValueError, json.JSONDecodeError) as exc: self.send_json({"error": str(exc)}, status=400)
            return
        if path.startswith("/api/admin/pre-registrations/") and path.endswith("/review"):
            actor = self.require_auth()
            if not actor: return
            try:
                length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length) or b"{}")
                decision = str(payload.get("decision", ""))
                if decision not in {"accept", "reject"}: raise ValueError("Decision must be accept or reject")
                reference_code = unquote(path.split("/api/admin/pre-registrations/", 1)[1].removesuffix("/review"))
                self.send_json(review_pre_registration(reference_code, decision, actor))
            except (TypeError, ValueError, json.JSONDecodeError) as exc: self.send_json({"error": str(exc)}, status=400)
            return
        if path.startswith("/api/admin/pre-registrations/") and path.endswith("/delete"):
            actor = self.require_auth()
            if not actor: return
            try:
                reference_code = unquote(path.split("/api/admin/pre-registrations/", 1)[1].removesuffix("/delete"))
                self.send_json(delete_pre_registration(reference_code, actor))
            except ValueError as exc: self.send_json({"error": str(exc)}, status=400)
            return
        if path == "/api/admin/webhooks/dispatch":
            actor = self.require_auth()
            if not actor: return
            self.send_json(dispatch_webhook_outbox())
            return
        if path == "/api/admin/patients":
            actor = self.require_auth()
            if not actor: return
            if not operational_db_ready():
                self.send_json({"error": "Operational database unavailable"}, status=503)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                allowed_age_groups = {"under_18", "18_24", "25_34", "35_44", "45_54", "55_plus", "not_disclosed"}
                allowed_treatment = {"not_linked", "referred", "on_treatment", "not_disclosed"}
                channel = str(payload.get("preferred_channel", ""))
                email = str(payload.get("email", "")).strip() or None
                phone = str(payload.get("phone", "")).strip() or None
                municipality = str(payload.get("municipality", "")).strip()
                age_group = str(payload.get("age_group", ""))
                treatment_status = str(payload.get("treatment_status", ""))
                email_consent = payload.get("email_consent") is True
                sms_consent = payload.get("sms_consent") is True
                if not municipality or age_group not in allowed_age_groups or treatment_status not in allowed_treatment:
                    raise ValueError("Invalid intake details")
                if channel == "email" and (not email or not email_consent):
                    raise ValueError("Email and email consent are required for email contact")
                if channel == "sms" and (not phone or not sms_consent):
                    raise ValueError("Phone and SMS consent are required for SMS contact")
                if channel not in {"email", "sms"}:
                    raise ValueError("Invalid preferred channel")
                diagnosis_date = str(payload.get("diagnosis_date", "")).strip() or None
                if diagnosis_date:
                    from datetime import date
                    date.fromisoformat(diagnosis_date)
                clean = {"email": email, "phone": phone, "preferred_channel": channel, "email_consent": email_consent, "sms_consent": sms_consent, "municipality": municipality[:120], "age_group": age_group, "diagnosis_date": diagnosis_date, "treatment_status": treatment_status, "referral_notes": str(payload.get("referral_notes", "")).strip()[:1000]}
                self.send_json(create_patient(clean, actor), status=201)
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                self.send_json({"error": str(exc)}, status=400)
            return
        if path.startswith("/api/admin/patients/") and path.endswith("/assignments"):
            actor = self.require_auth()
            if not actor: return
            if not operational_db_ready(): self.send_json({"error": "Operational database unavailable"}, status=503); return
            try:
                patient_code = unquote(path.split("/api/admin/patients/", 1)[1].removesuffix("/assignments"))
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                facility_code = str(payload.get("facility_code", "")).strip()
                if not facility_code: raise ValueError("Care center is required")
                self.send_json(assign_patient(patient_code, facility_code, actor), status=201)
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                self.send_json({"error": str(exc)}, status=400)
            return
        if path != "/api/auth/login":
            self.send_json({"error": "Unknown route"}, status=404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            username = str(payload.get("username", ""))
            password = str(payload.get("password", ""))
            with sqlite3.connect(AUTH_DB) as connection:
                row = connection.execute("SELECT password_hash FROM admin_users WHERE username=? AND active=1", (username,)).fetchone()
            if not row or not password_matches(password, row[0]):
                self.send_json({"error": "Invalid credentials"}, status=401)
                return
            token = secrets.token_urlsafe(32)
            SESSIONS[token] = username
            self.send_json({"token": token, "username": username})
        except (ValueError, json.JSONDecodeError):
            self.send_json({"error": "Invalid request"}, status=400)

    def require_auth(self) -> str | None:
        token = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if token in SESSIONS:
            return SESSIONS[token]
        self.send_json({"error": "Authentication required"}, status=401)
        return None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)
        try:
            if path in {"/", "/map"}:
                self.send_file(self.run_dir / "maps" / "arcHIVe_Region_XII_Interactive_Forecast_Map.html")
                return
            if path == "/api/health":
                analytics_ready = self.database_path.is_file()
                postgres_ready = operational_db_ready()
                ready = analytics_ready and postgres_ready
                self.send_json({
                    "status": "ok" if ready else "unavailable",
                    "api_version": API_VERSION,
                    "run_available": self.run_dir.exists(),
                    "database_available": analytics_ready,
                    "operational_database_available": postgres_ready,
                }, status=200 if ready else 503)
                return
            if path == "/api/version":
                self.send_json({"api_version": API_VERSION, "project": "arcHIVe Region XII Phase 2"})
                return
            if path == "/api/metadata":
                if not self.require_auth(): return
                rows = self.query("SELECT KEY, VALUE FROM metadata ORDER BY KEY")
                payload = {}
                for row in rows:
                    try:
                        payload[row["KEY"]] = json.loads(row["VALUE"])
                    except Exception:
                        payload[row["KEY"]] = row["VALUE"]
                self.send_json(payload)
                return
            if path == "/api/admin/patients":
                if not self.require_auth(): return
                if not operational_db_ready():
                    self.send_json({"error": "Operational database unavailable"}, status=503)
                    return
                self.send_json(list_patients())
                return
            if path == "/api/public/facilities":
                if not operational_db_ready(): self.send_json({"error": "Operational database unavailable"}, status=503); return
                self.send_json(list_public_facilities())
                return
            if path == "/api/admin/pre-registrations":
                if not self.require_auth(): return
                if not operational_db_ready(): self.send_json({"error": "Operational database unavailable"}, status=503); return
                self.send_json(list_pre_registrations())
                return
            if path == "/api/admin/facilities":
                if not self.require_auth(): return
                if not operational_db_ready(): self.send_json({"error": "Operational database unavailable"}, status=503); return
                self.send_json(list_facilities())
                return
            if path == "/api/dates":
                self.send_json(self.query("SELECT DISTINCT PERIOD FROM forecast_values ORDER BY PERIOD"))
                return
            if path in ("/api/historical-trend", "/api/public/historical-cases"):
                source = ROOT / "data" / "arcHIVe_Municipality_Monthly.csv"
                yearly: dict[str, float] = {}
                reported: dict[str, float] = {}
                with source.open(newline="", encoding="latin-1") as stream:
                    for row in csv.DictReader(stream):
                        if row.get("Current_Region_XII") != "Yes":
                            continue
                        year = row.get("Year", "").strip()
                        if year:
                            yearly[year] = max(yearly.get(year, 0), float(row.get("Rolling_12M_Cases") or 0))
                            reported[year] = reported.get(year, 0) + float(row.get("Reported_HIV_Cases") or 0)
                self.send_json([{"PERIOD": year, "REPORTED_HIV_CASES": reported.get(year, 0), "ROLLING_12M_CASES": yearly[year], "SOURCE": "historical aggregate records"} for year in sorted(yearly)])
                return
            if path == "/api/municipalities":
                self.send_json(self.query("SELECT * FROM municipalities ORDER BY PROVINCE, LOCATION"))
                return
            if path == "/api/snapshot":
                period = first(query, "period")
                if not period:
                    row = self.query("SELECT MAX(PERIOD) AS PERIOD FROM forecast_values")
                    period = row[0]["PERIOD"]
                self.send_json(self.query("SELECT * FROM forecast_values WHERE PERIOD=? ORDER BY TRANSMISSION_PRESSURE_INDEX DESC", (period,)))
                return
            if path == "/api/ranking":
                period = first(query, "period")
                metric = first(query, "metric", "TRANSMISSION_PRESSURE_INDEX")
                allowed = {
                    "PREDICTED_CASES", "NEW_INFECTIONS_ESTIMATE", "ROLLING_12M_CASES", "ROLLING_12M_RATE_PER_100K",
                    "GI_STAR_Z_SCORE", "TRANSMISSION_PRESSURE_INDEX",
                    "TESTING_CENTER_NEED_SCORE", "EFFECTIVE_INFECTIOUS_POOL",
                    "TESTING_ACCESS_SCORE", "VIRAL_SUPPRESSION_COVERAGE",
                }
                if metric not in allowed:
                    raise ValueError("Unsupported ranking metric")
                if not period:
                    period = self.query("SELECT MAX(PERIOD) AS PERIOD FROM forecast_values")[0]["PERIOD"]
                limit = parse_limit(first(query, "limit", "49"), 49, 49)
                self.send_json(self.query(f"SELECT PERIOD,PSGC,PROVINCE,LOCATION,{metric} AS VALUE FROM forecast_values WHERE PERIOD=? ORDER BY {metric} DESC LIMIT ?", (period, limit)))
                return
            if path == "/api/timeline":
                psgc = first(query, "psgc")
                location = first(query, "location")
                if psgc:
                    self.send_json(self.query("SELECT * FROM forecast_values WHERE PSGC=? ORDER BY PERIOD", (psgc,)))
                elif location:
                    self.send_json(self.query("SELECT * FROM forecast_values WHERE LOCATION=? ORDER BY PERIOD", (location,)))
                else:
                    raise ValueError("Provide psgc or location")
                return
            if path == "/api/hotspots":
                period = first(query, "period")
                sql = "SELECT * FROM hotspot_results"
                params: tuple[Any, ...] = ()
                if period:
                    sql += " WHERE PERIOD=?"; params = (period,)
                sql += " ORDER BY PERIOD, GI_STAR_Z_SCORE DESC"
                self.send_json(self.query(sql, params))
                return
            if path == "/api/transmission":
                period = first(query, "period")
                sql = "SELECT * FROM transmission_pressure"
                params = ()
                if period:
                    sql += " WHERE PERIOD=?"; params = (period,)
                sql += " ORDER BY PERIOD, TRANSMISSION_PRESSURE_INDEX DESC"
                self.send_json(self.query(sql, params))
                return
            if path == "/api/compartments":
                period = first(query, "period")
                location = first(query, "location")
                sql = "SELECT * FROM compartment_dynamics"
                clauses = []
                params_list: list[Any] = []
                if period:
                    clauses.append("PERIOD=?"); params_list.append(period)
                if location:
                    clauses.append("LOCATION=?"); params_list.append(location)
                if clauses:
                    sql += " WHERE " + " AND ".join(clauses)
                sql += " ORDER BY PERIOD, LOCATION"
                self.send_json(self.query(sql, tuple(params_list)))
                return
            if path == "/api/decomposition":
                location = first(query, "location")
                if not location:
                    raise ValueError("Provide location")
                self.send_json(self.query("SELECT * FROM decomposition_results WHERE LOCATION=? ORDER BY PERIOD", (location,)))
                return
            if path == "/api/testing-centers":
                self.send_json(self.query("SELECT * FROM testing_center_recommendations ORDER BY RECOMMENDED_ADDITIONAL_CENTERS DESC, TESTING_CENTER_NEED_SCORE DESC"))
                return
            if path == "/api/alerts":
                if not self.require_auth(): return
                limit = parse_limit(first(query, "limit", "500"), 500, 5000)
                self.send_json(self.query("SELECT * FROM alerts ORDER BY PERIOD DESC, TRANSMISSION_PRESSURE_INDEX DESC LIMIT ?", (limit,)))
                return
            if path == "/api/region-summary":
                if not self.require_auth(): return
                self.send_json(self.query("SELECT * FROM regional_summary ORDER BY PERIOD"))
                return
            if path == "/api/adjacency":
                self.send_json(self.query("SELECT * FROM adjacency_edges ORDER BY FROM_LOCATION, TO_LOCATION"))
                return
            if path == "/api/geometry/municipalities":
                self.send_file(self.run_dir / "maps" / "region12_municipalities_gap_filled.geojson")
                return
            if path == "/api/geometry/provinces":
                self.send_file(self.run_dir / "maps" / "region12_provinces.geojson")
                return
            if path == "/api/geometry/region":
                self.send_file(self.run_dir / "maps" / "region12_boundary.geojson")
                return
            if path.startswith("/charts/"):
                self.send_file(self.run_dir / "charts" / Path(path).name)
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown route")
        except ValueError as exc:
            self.send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            print(f"API error: {type(exc).__name__}: {exc}")
            self.send_json({"error": "Internal server error"}, status=500)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def main() -> int:
    args = parse_args()
    validate_production_env()
    run_dir = resolve_run(args.run_dir)
    init_auth_db()
    initialize_operational_db()
    Handler.run_dir = run_dir
    Handler.database_path = run_dir / "database" / "archive_phase2.sqlite"
    Handler.cors_origin = args.cors_origin
    def dispatch_loop() -> None:
        while True:
            try:
                dispatch_webhook_outbox()
            except Exception as error:
                print(f"Webhook dispatch error: {type(error).__name__}: {error}", file=sys.stderr, flush=True)
            time.sleep(60)

    threading.Thread(target=dispatch_loop, name="webhook-dispatch", daemon=True).start()
    ThreadingHTTPServer.daemon_threads = True
    ThreadingHTTPServer.block_on_close = False
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"arcHIVe Phase 2 API {API_VERSION}")
    print(f"Serving run: {run_dir}")
    print(f"Map: http://{args.host}:{args.port}/map")
    print(f"Health: http://{args.host}:{args.port}/api/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
