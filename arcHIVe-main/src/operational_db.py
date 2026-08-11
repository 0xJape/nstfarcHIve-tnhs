from __future__ import annotations

import os
import json
import sys
import urllib.request
import secrets
import uuid
import csv
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Iterator

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

def database_url() -> str:
    return os.getenv("DATABASE_URL", "")

SCHEMA = """
CREATE TABLE IF NOT EXISTS care_facilities (
    id uuid PRIMARY KEY,
    facility_code text NOT NULL UNIQUE,
    name text NOT NULL,
    facility_type text NOT NULL,
    municipality text NOT NULL,
    province text NOT NULL,
    latitude double precision,
    longitude double precision,
    address text NOT NULL,
    services text NOT NULL DEFAULT '',
    opening_hours text NOT NULL DEFAULT '',
    phone text NOT NULL DEFAULT '',
    email text NOT NULL DEFAULT '',
    contact_people text NOT NULL DEFAULT '',
    active boolean NOT NULL DEFAULT true,
    source_url text,
    verified_on date NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE care_facilities ADD COLUMN IF NOT EXISTS latitude double precision;
ALTER TABLE care_facilities ADD COLUMN IF NOT EXISTS longitude double precision;
ALTER TABLE care_facilities ADD COLUMN IF NOT EXISTS phone text NOT NULL DEFAULT '';
ALTER TABLE care_facilities ADD COLUMN IF NOT EXISTS email text NOT NULL DEFAULT '';
ALTER TABLE care_facilities ADD COLUMN IF NOT EXISTS contact_people text NOT NULL DEFAULT '';
CREATE TABLE IF NOT EXISTS patients (
    id uuid PRIMARY KEY,
    patient_code text NOT NULL UNIQUE,
    care_status text NOT NULL DEFAULT 'new' CHECK (care_status IN ('new','contacted','assigned','booked','in_care','follow_up','closed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS pre_registrations (
    id uuid PRIMARY KEY,
    reference_code text NOT NULL UNIQUE,
    municipality text NOT NULL,
    preferred_channel text NOT NULL CHECK (preferred_channel IN ('email','sms')),
    contact_value text NOT NULL,
    email text,
    phone text,
    selected_facility_code text,
    consented_at timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','ticket_sent','accepted','rejected','converted')),
    created_at timestamptz NOT NULL DEFAULT now(),
    reviewed_at timestamptz,
    reviewed_by text
);
ALTER TABLE pre_registrations ADD COLUMN IF NOT EXISTS selected_facility_code text;
ALTER TABLE pre_registrations ADD COLUMN IF NOT EXISTS email text;
ALTER TABLE pre_registrations ADD COLUMN IF NOT EXISTS phone text;
ALTER TABLE pre_registrations DROP CONSTRAINT IF EXISTS pre_registrations_status_check;
ALTER TABLE pre_registrations ADD CONSTRAINT pre_registrations_status_check CHECK (status IN ('pending','ticket_sent','accepted','rejected','converted'));
ALTER TABLE pre_registrations ADD COLUMN IF NOT EXISTS ticket_token text;
CREATE TABLE IF NOT EXISTS patient_contacts (
    patient_id uuid PRIMARY KEY REFERENCES patients(id) ON DELETE CASCADE,
    email text,
    phone text,
    preferred_channel text NOT NULL CHECK (preferred_channel IN ('email','sms')),
    email_consent boolean NOT NULL DEFAULT false,
    sms_consent boolean NOT NULL DEFAULT false,
    consent_recorded_at timestamptz NOT NULL,
    CHECK (email IS NOT NULL OR phone IS NOT NULL),
    CHECK ((preferred_channel = 'email' AND email IS NOT NULL AND email_consent) OR (preferred_channel = 'sms' AND phone IS NOT NULL AND sms_consent))
);
CREATE TABLE IF NOT EXISTS patient_clinical (
    patient_id uuid PRIMARY KEY REFERENCES patients(id) ON DELETE CASCADE,
    municipality text NOT NULL,
    age_group text NOT NULL,
    diagnosis_date date,
    treatment_status text NOT NULL,
    referral_notes text NOT NULL DEFAULT '',
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS center_assignments (
    id uuid PRIMARY KEY,
    patient_id uuid NOT NULL REFERENCES patients(id),
    facility_id uuid NOT NULL REFERENCES care_facilities(id),
    status text NOT NULL CHECK (status IN ('proposed','accepted','declined','completed','cancelled')),
    assigned_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS appointments (
    id uuid PRIMARY KEY,
    assignment_id uuid NOT NULL REFERENCES center_assignments(id),
    scheduled_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('scheduled','confirmed','rescheduled','attended','missed','cancelled')),
    appointment_reference text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS communication_logs (
    id uuid PRIMARY KEY,
    patient_id uuid NOT NULL REFERENCES patients(id),
    appointment_id uuid REFERENCES appointments(id),
    channel text NOT NULL CHECK (channel IN ('email','sms')),
    message_type text NOT NULL,
    status text NOT NULL,
    provider_reference text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS webhook_outbox (
    id uuid PRIMARY KEY,
    event_type text NOT NULL,
    entity_id uuid NOT NULL,
    channel text NOT NULL CHECK (channel IN ('email','sms')),
    idempotency_key text NOT NULL UNIQUE,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','processing','sent','failed')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    available_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz
);
CREATE TABLE IF NOT EXISTS audit_events (
    id uuid PRIMARY KEY,
    actor text NOT NULL,
    action text NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid,
    outcome text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_patients_status ON patients(care_status);
CREATE INDEX IF NOT EXISTS idx_assignments_patient ON center_assignments(patient_id);
CREATE INDEX IF NOT EXISTS idx_appointments_schedule ON appointments(scheduled_at, status);
CREATE INDEX IF NOT EXISTS idx_outbox_delivery ON webhook_outbox(status, available_at);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_events(entity_type, entity_id, created_at);
"""


def available() -> bool:
    return bool(database_url())

def ready() -> bool:
    if not available():
        return False
    try:
        with psycopg.connect(database_url(), connect_timeout=3) as connection:
            connection.execute("SELECT 1")
        return True
    except psycopg.Error:
        return False


@contextmanager
def connect() -> Iterator[Connection]:
    if not database_url():
        raise RuntimeError("DATABASE_URL is required for operational data")
    with psycopg.connect(database_url()) as connection:
        yield connection


def initialize() -> None:
    if not available():
        return
    with connect() as connection:
        connection.execute(SCHEMA)
        facility_file = Path(__file__).parents[1] / "data" / "care_facilities.csv"
        if facility_file.exists():
            with facility_file.open(encoding="utf-8-sig", newline="") as source:
                for row in csv.DictReader(source):
                    connection.execute(
                        """INSERT INTO care_facilities
                        (id,facility_code,name,facility_type,municipality,province,latitude,longitude,address,services,opening_hours,phone,email,contact_people,source_url,verified_on)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (facility_code) DO UPDATE SET
                        name=EXCLUDED.name,facility_type=EXCLUDED.facility_type,municipality=EXCLUDED.municipality,
                        province=EXCLUDED.province,latitude=EXCLUDED.latitude,longitude=EXCLUDED.longitude,
                        address=EXCLUDED.address,services=EXCLUDED.services,opening_hours=EXCLUDED.opening_hours,
                        phone=EXCLUDED.phone,email=EXCLUDED.email,contact_people=EXCLUDED.contact_people,
                        source_url=EXCLUDED.source_url,verified_on=EXCLUDED.verified_on,active=true,updated_at=now()""",
                        (uuid.uuid4(), row["facility_id"], row["name"], row["facility_type"], row["municipality"], row["province"], float(row["latitude"]) if row["latitude"] else None, float(row["longitude"]) if row["longitude"] else None, row["address"], row["services"], row["opening_hours"], row["phone"], row["email"], row.get("contact_people") or "", row["source_url"] or None, row["verified_on"]),
                    )
        if os.getenv("ARCHIVE_SEED_DEMO", "").lower() == "true":
            connection.execute(
                """INSERT INTO care_facilities
                (id,facility_code,name,facility_type,municipality,province,address,services,opening_hours,source_url,verified_on)
                VALUES
                (%s,'DEMO-GSC','DEMO — General Santos Care Center','testing_center','GENERAL SANTOS CITY','South Cotabato','DEMO DATA — replace before production','HIV testing; counseling','Mon–Fri 08:00–17:00','',CURRENT_DATE),
                (%s,'DEMO-KID','DEMO — Kidapawan Care Center','testing_center','KIDAPAWAN CITY','Cotabato','DEMO DATA — replace before production','HIV testing; counseling','Mon–Fri 08:00–17:00','',CURRENT_DATE)
                ON CONFLICT (facility_code) DO NOTHING""",
                (uuid.uuid4(), uuid.uuid4()),
            )


def create_patient(payload: dict[str, object], actor: str) -> dict[str, object]:
    patient_id = uuid.uuid4()
    audit_id = uuid.uuid4()
    patient_code = f"AR-{secrets.token_hex(4).upper()}"
    with connect() as connection:
        connection.execute("INSERT INTO patients (id, patient_code) VALUES (%s, %s)", (patient_id, patient_code))
        connection.execute(
            "INSERT INTO patient_contacts (patient_id,email,phone,preferred_channel,email_consent,sms_consent,consent_recorded_at) VALUES (%s,%s,%s,%s,%s,%s,now())",
            (patient_id, payload.get("email"), payload.get("phone"), payload["preferred_channel"], payload["email_consent"], payload["sms_consent"]),
        )
        connection.execute(
            "INSERT INTO patient_clinical (patient_id,municipality,age_group,diagnosis_date,treatment_status,referral_notes) VALUES (%s,%s,%s,%s,%s,%s)",
            (patient_id, payload["municipality"], payload["age_group"], payload.get("diagnosis_date"), payload["treatment_status"], payload.get("referral_notes", "")),
        )
        connection.execute(
            "INSERT INTO audit_events (id,actor,action,entity_type,entity_id,outcome) VALUES (%s,%s,'patient.created','patient',%s,'success')",
            (audit_id, actor, patient_id),
        )
    return {"patient_code": patient_code, "care_status": "new"}

def create_pre_registration(payload: dict[str, str]) -> dict[str, str]:
    registration_id = uuid.uuid4()
    reference_code = f"REQ-{secrets.token_hex(4).upper()}"
    with connect() as connection:
        connection.execute("INSERT INTO pre_registrations (id,reference_code,municipality,preferred_channel,contact_value,email,phone,selected_facility_code,consented_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,now())", (registration_id, reference_code, payload['municipality'], payload['preferred_channel'], payload['contact_value'], payload.get('email'), payload.get('phone'), payload.get('facility_code')))
    return {"reference_code": reference_code, "status": "pending"}

def list_pre_registrations() -> list[dict[str, object]]:
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        return connection.execute("SELECT reference_code,municipality,preferred_channel,contact_value,selected_facility_code,status,created_at FROM pre_registrations WHERE status IN ('pending','ticket_sent') ORDER BY created_at DESC LIMIT 500").fetchall()

def review_pre_registration(reference_code: str, decision: str, actor: str) -> dict[str, object]:
    with connect() as connection:
        request = connection.execute("SELECT id,municipality,preferred_channel,contact_value,email,phone FROM pre_registrations WHERE reference_code=%s AND status='pending' FOR UPDATE", (reference_code,)).fetchone()
        if not request: raise ValueError("Pending request not found")
        if decision == 'reject':
            connection.execute("UPDATE pre_registrations SET status='rejected',reviewed_at=now(),reviewed_by=%s WHERE id=%s", (actor, request[0]))
            connection.execute("INSERT INTO audit_events (id,actor,action,entity_type,entity_id,outcome) VALUES (%s,%s,'registration.rejected','pre_registration',%s,'success')", (uuid.uuid4(), actor, request[0]))
            return {"reference_code": reference_code, "status": "rejected"}
        token = secrets.token_urlsafe(32)
        connection.execute("UPDATE pre_registrations SET status='ticket_sent',ticket_token=%s,reviewed_at=now(),reviewed_by=%s WHERE id=%s", (token, actor, request[0]))
        connection.execute("INSERT INTO webhook_outbox (id,event_type,entity_id,channel,idempotency_key) VALUES (%s,'registration.ticket_requested',%s,%s,%s)", (uuid.uuid4(), request[0], request[2], f"registration-ticket:{reference_code}"))
        connection.execute("INSERT INTO audit_events (id,actor,action,entity_type,entity_id,outcome) VALUES (%s,%s,'registration.accepted','pre_registration',%s,'success')", (uuid.uuid4(), actor, request[0]))
        return {"reference_code": reference_code, "status": "ticket_sent", "automation_status": "queued"}

def delete_pre_registration(reference_code: str, actor: str) -> dict[str, object]:
    with connect() as connection:
        deleted = connection.execute("DELETE FROM pre_registrations WHERE reference_code=%s AND status='pending' RETURNING id,reference_code", (reference_code,)).fetchone()
        if not deleted: raise ValueError("Only requests awaiting review can be deleted")
        connection.execute("INSERT INTO audit_events (id,actor,action,entity_type,entity_id,outcome) VALUES (%s,%s,'registration.deleted','pre_registration',%s,'success')", (uuid.uuid4(), actor, deleted[0]))
    return {"reference_code": deleted[1], "status": "deleted"}

def confirm_pre_registration(reference_code: str, token: str, actor: str = "patient") -> dict[str, object]:
    with connect() as connection:
        request = connection.execute("SELECT id,municipality,preferred_channel,contact_value,email,phone,ticket_token FROM pre_registrations WHERE reference_code=%s AND status='ticket_sent' FOR UPDATE", (reference_code,)).fetchone()
        if not request or not secrets.compare_digest(request[6] or "", token): raise ValueError("Invalid or expired ticket")
        patient = create_patient({"email": request[4], "phone": request[5], "preferred_channel": request[2], "email_consent": bool(request[4]), "sms_consent": bool(request[5]), "municipality": request[1], "age_group": "not_disclosed", "treatment_status": "not_disclosed", "referral_notes": "Confirmed from emailed care ticket"}, actor)
        connection.execute("UPDATE pre_registrations SET status='converted',ticket_token=NULL WHERE id=%s", (request[0],))
        connection.execute("INSERT INTO webhook_outbox (id,event_type,entity_id,channel,idempotency_key) VALUES (%s,'registration.referral_confirmed',%s,'email',%s)", (uuid.uuid4(), request[0], f"registration-referral:{reference_code}"))
        return {"reference_code": reference_code, "status": "converted", "handoff_status": "queued", **patient}


def list_patients() -> list[dict[str, object]]:
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        return connection.execute(
            "SELECT p.patient_code,p.care_status,c.preferred_channel,cl.municipality,cl.age_group,cl.treatment_status,p.created_at FROM patients p JOIN patient_contacts c ON c.patient_id=p.id JOIN patient_clinical cl ON cl.patient_id=p.id ORDER BY p.created_at DESC LIMIT 500"
        ).fetchall()


def list_facilities() -> list[dict[str, object]]:
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        return connection.execute("SELECT facility_code,name,facility_type,municipality,province,address,services,opening_hours,active,verified_on FROM care_facilities WHERE active=true ORDER BY province,municipality,name").fetchall()

def list_public_facilities() -> list[dict[str, object]]:
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        return connection.execute("SELECT facility_code,name,facility_type,municipality,province,address,latitude,longitude,services,opening_hours,phone,email,contact_people FROM care_facilities WHERE active=true AND latitude IS NOT NULL AND longitude IS NOT NULL ORDER BY province,municipality,name").fetchall()


def assign_patient(patient_code: str, facility_code: str, actor: str) -> dict[str, object]:
    assignment_id = uuid.uuid4()
    with connect() as connection:
        row = connection.execute("SELECT id FROM patients WHERE patient_code=%s", (patient_code,)).fetchone()
        facility = connection.execute("SELECT id FROM care_facilities WHERE facility_code=%s AND active=true", (facility_code,)).fetchone()
        if not row or not facility:
            raise ValueError("Patient or active care center not found")
        connection.execute("UPDATE patients SET care_status='assigned',updated_at=now() WHERE id=%s", (row[0],))
        connection.execute("INSERT INTO center_assignments (id,patient_id,facility_id,status,assigned_by) VALUES (%s,%s,%s,'proposed',%s)", (assignment_id, row[0], facility[0], actor))
        connection.execute("INSERT INTO webhook_outbox (id,event_type,entity_id,channel,idempotency_key) SELECT %s,'center.assignment_requested',%s,c.preferred_channel,%s FROM patient_contacts c WHERE c.patient_id=%s", (uuid.uuid4(), row[0], f"center-assignment:{assignment_id}", row[0]))
        connection.execute("INSERT INTO audit_events (id,actor,action,entity_type,entity_id,outcome) VALUES (%s,%s,'patient.assigned','patient',%s,'success')", (uuid.uuid4(), actor, row[0]))
    return {"assignment_id": str(assignment_id), "patient_code": patient_code, "facility_code": facility_code, "status": "proposed"}

def dispatch_webhook_outbox(limit: int = 20) -> dict[str, int]:
    webhook_url = os.getenv("MAKE_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return {"queued": 0, "sent": 0, "failed": 0}
    sent = failed = 0
    with connect() as connection:
        rows = connection.execute("SELECT id,event_type,entity_id,channel,idempotency_key FROM webhook_outbox WHERE status='pending' AND available_at<=now() ORDER BY created_at LIMIT %s FOR UPDATE SKIP LOCKED", (limit,)).fetchall()
        for row in rows:
            payload = {"event_type": row[1], "entity_id": str(row[2]), "channel": row[3], "idempotency_key": row[4]}
            try:
                if row[1] in {"registration.ticket_requested", "registration.referral_confirmed"}:
                    registration = connection.execute("""SELECT p.reference_code,p.municipality,p.preferred_channel,p.email,p.phone,p.ticket_token,
                        f.facility_code,f.name,f.address,f.municipality,f.province,f.email
                        FROM pre_registrations p LEFT JOIN care_facilities f ON f.facility_code=p.selected_facility_code WHERE p.id=%s""", (row[2],)).fetchone()
                    if not registration: raise RuntimeError("Registration for webhook not found")
                    payload.update({"reference_code": registration[0], "municipality": registration[1], "preferred_channel": registration[2], "patient_email": registration[3], "patient_phone": registration[4], "facility": {"code": registration[6], "name": registration[7], "address": registration[8], "municipality": registration[9], "province": registration[10], "email": registration[11]}})
                    if row[1] == "registration.ticket_requested":
                        public_url = os.getenv("ARCHIVE_PUBLIC_URL", "http://127.0.0.1:5173").rstrip("/")
                        payload["confirmation_url"] = f"{public_url}/confirm?reference={registration[0]}&token={registration[5]}"
                request = urllib.request.Request(webhook_url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "X-ARCHIVE-Event": row[1]}, method="POST")
                with urllib.request.urlopen(request, timeout=15) as response:
                    if response.status >= 300: raise RuntimeError(f"Make returned HTTP {response.status}")
                connection.execute("UPDATE webhook_outbox SET status='sent',attempts=attempts+1,sent_at=now() WHERE id=%s", (row[0],)); sent += 1
            except Exception as error:
                print(f"Webhook delivery failed for {row[3]} {row[4]}: {type(error).__name__}: {error}", file=sys.stderr, flush=True)
                connection.execute("UPDATE webhook_outbox SET status='failed',attempts=attempts+1 WHERE id=%s", (row[0],)); failed += 1
    return {"queued": len(rows), "sent": sent, "failed": failed}


if __name__ == "__main__":
    assert "patient_contacts" in SCHEMA and "webhook_outbox" in SCHEMA and "audit_events" in SCHEMA
    initialize()
