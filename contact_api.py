# ============================================================
# contact_api.py — Contact & Partner Ad Submission API
# AmmoniteID v1.0
# ============================================================
# Endpoints:
#   GET  /api/contact/captcha         — Generate math captcha
#   POST /api/contact/submit          — Submit contact form (email only)
#   POST /api/contact/submit-partner  — Submit partner ad campaign (email + DB)
# ============================================================

import os
import io
import json
import uuid
import hmac
import hashlib
import random
import smtplib
import sqlite3
from time import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Form, UploadFile, File, Request
from fastapi.responses import JSONResponse
from database import DB_PATH

contact_router = APIRouter()

# ── Configuration ─────────────────────────────────────────────
ADMIN_EMAIL = "ammoniteidadmin@gmail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
CAPTCHA_SECRET = os.environ.get("CAPTCHA_SECRET", "ammonite_captcha_2026")

# ── Rate Limiting (in-memory) ─────────────────────────────────
_contact_attempts = defaultdict(list)
_partner_attempts = defaultdict(list)

CONTACT_RATE_LIMIT = 3       # max per window
CONTACT_RATE_WINDOW = 3600   # 1 hour
PARTNER_RATE_LIMIT = 2       # max per window
PARTNER_RATE_WINDOW = 86400  # 24 hours


def _is_rate_limited(store: dict, ip: str, limit: int, window: int) -> bool:
    now = time()
    store[ip] = [t for t in store[ip] if now - t < window]
    if len(store[ip]) >= limit:
        return True
    store[ip].append(now)
    return False


# ── Captcha ───────────────────────────────────────────────────
def _generate_captcha():
    """Generate a simple math captcha and its HMAC token."""
    a = random.randint(1, 12)
    b = random.randint(1, 12)
    question = f"{a} + {b}"
    answer = str(a + b)
    # Create HMAC so we can verify without server-side session storage
    token = hmac.new(
        CAPTCHA_SECRET.encode(),
        f"{question}={answer}".encode(),
        hashlib.sha256
    ).hexdigest()
    return question, answer, token


def _verify_captcha(question: str, user_answer: str, token: str) -> bool:
    """Verify captcha answer against HMAC token."""
    if not question or not user_answer or not token:
        return False
    # Reconstruct expected parts from the question
    try:
        parts = question.replace(" ", "").split("+")
        expected_answer = str(int(parts[0]) + int(parts[1]))
    except (ValueError, IndexError):
        return False
    # Check user gave right answer
    if user_answer.strip() != expected_answer:
        return False
    # Verify HMAC token matches
    expected_token = hmac.new(
        CAPTCHA_SECRET.encode(),
        f"{question}={expected_answer}".encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(token, expected_token)


# ── Email Sending ─────────────────────────────────────────────
def _send_email(subject: str, body_html: str, reply_to: str = None,
                attachment_data: bytes = None, attachment_name: str = None):
    """Send email via Gmail SMTP."""
    if not GMAIL_APP_PASSWORD:
        print("⚠️ GMAIL_APP_PASSWORD not set — email not sent")
        print(f"   Subject: {subject}")
        print(f"   Body preview: {body_html[:200]}")
        return False

    msg = MIMEMultipart()
    msg["From"] = ADMIN_EMAIL
    msg["To"] = ADMIN_EMAIL
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to

    msg.attach(MIMEText(body_html, "html"))

    # Attach logo if provided
    if attachment_data and attachment_name:
        img = MIMEImage(attachment_data)
        img.add_header("Content-Disposition", "attachment", filename=attachment_name)
        msg.attach(img)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(ADMIN_EMAIL, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print(f"✅ Email sent: {subject}")
        return True
    except Exception as e:
        print(f"❌ Email failed: {e}")
        return False


def _get_client_ip(request: Request) -> str:
    """Get client IP from request, checking forwarded headers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── Endpoints ─────────────────────────────────────────────────

@contact_router.get("/api/contact/captcha")
async def get_captcha():
    """Generate a new math captcha for the contact forms."""
    question, answer, token = _generate_captcha()
    return {
        "question": question,
        "token": token
    }


@contact_router.post("/api/contact/submit")
async def submit_contact(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    subject: str = Form(...),
    message: str = Form(...),
    captcha_question: str = Form(""),
    captcha_answer: str = Form(""),
    captcha_token: str = Form(""),
    website_url_verify: str = Form("")  # Honeypot field
):
    """
    Submit a simple contact form.
    Sends email to admin only — no database entry.
    """
    ip = _get_client_ip(request)

    # ── Honeypot check ────────────────────────────────────
    if website_url_verify:
        # Bot filled in the hidden field — silently reject
        return JSONResponse({"status": "success", "message": "Thank you for your message!"})

    # ── Rate limit ────────────────────────────────────────
    if _is_rate_limited(_contact_attempts, ip, CONTACT_RATE_LIMIT, CONTACT_RATE_WINDOW):
        raise HTTPException(
            status_code=429,
            detail="Too many submissions. Please try again later."
        )

    # ── Captcha verify ────────────────────────────────────
    if not _verify_captcha(captcha_question, captcha_answer, captcha_token):
        raise HTTPException(status_code=400, detail="Incorrect captcha answer. Please try again.")

    # ── Basic validation ──────────────────────────────────
    if not name.strip() or not email.strip() or not message.strip():
        raise HTTPException(status_code=400, detail="Name, email and message are required.")
    if len(message) > 5000:
        raise HTTPException(status_code=400, detail="Message too long (max 5000 characters).")

    # ── Save to database (primary inbox) ──────────────────
    msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    timestamp = datetime.utcnow().isoformat()

    try:
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        c.execute("""
            INSERT INTO contact_messages (
                id, name, email, subject, message, ip_address, submitted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (msg_id, name.strip(), email.strip(), subject.strip(), message.strip(), ip, timestamp))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ DB insert failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to save message. Please try again.")

    # ── Attempt email (bonus notification, not required) ──
    ts_readable = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    body_html = f"""
    <h2>New Contact Form Submission</h2>
    <table style="border-collapse:collapse;width:100%;max-width:600px;">
        <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold;width:120px;">Name</td>
            <td style="padding:8px;border:1px solid #ddd;">{name}</td></tr>
        <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold;">Email</td>
            <td style="padding:8px;border:1px solid #ddd;"><a href="mailto:{email}">{email}</a></td></tr>
        <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold;">Subject</td>
            <td style="padding:8px;border:1px solid #ddd;">{subject or '(none)'}</td></tr>
        <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold;">Message</td>
            <td style="padding:8px;border:1px solid #ddd;">{message}</td></tr>
    </table>
    <p style="color:#999;margin-top:15px;">ID: {msg_id} | Submitted: {ts_readable} | IP: {ip}</p>
    """

    email_sent = _send_email(
        subject=f"AmmoniteID Contact: {subject or 'New Message'}",
        body_html=body_html,
        reply_to=email
    )

    return JSONResponse({
        "status": "success",
        "message": "Thank you for your message! We'll get back to you soon.",
        "email_sent": email_sent,
        "message_id": msg_id
    })


@contact_router.post("/api/contact/submit-partner")
async def submit_partner_ad(
    request: Request,
    business_name: str = Form(...),
    website_url: str = Form(...),
    contact_email: str = Form(...),
    phone: str = Form(""),
    address: str = Form(""),
    description: str = Form(...),
    special_offer: str = Form(""),
    banner_color: str = Form(""),
    duration_type: str = Form("indefinite"),
    start_date: str = Form(""),
    end_date: str = Form(""),
    frequency: str = Form("standard"),
    category: str = Form("other"),
    notes: str = Form(""),
    confirm_accurate: str = Form(""),
    confirm_offer_valid: str = Form(""),
    confirm_website_works: str = Form(""),
    confirm_logo_permission: str = Form(""),
    confirm_terms: str = Form(""),
    captcha_question: str = Form(""),
    captcha_answer: str = Form(""),
    captcha_token: str = Form(""),
    website_url_verify: str = Form(""),  # Honeypot
    logo: Optional[UploadFile] = File(None)
):
    """
    Submit partner ad campaign form.
    Sends email to admin AND saves to partner_submissions table.
    """
    ip = _get_client_ip(request)

    # ── Honeypot check ────────────────────────────────────
    if website_url_verify:
        return JSONResponse({"status": "success", "message": "Thank you! We'll review your submission."})

    # ── Rate limit ────────────────────────────────────────
    if _is_rate_limited(_partner_attempts, ip, PARTNER_RATE_LIMIT, PARTNER_RATE_WINDOW):
        raise HTTPException(
            status_code=429,
            detail="Too many submissions. Please try again tomorrow."
        )

    # ── Captcha verify ────────────────────────────────────
    if not _verify_captcha(captcha_question, captcha_answer, captcha_token):
        raise HTTPException(status_code=400, detail="Incorrect captcha answer. Please try again.")

    # ── Validation ────────────────────────────────────────
    if not business_name.strip() or not website_url.strip() or not contact_email.strip():
        raise HTTPException(status_code=400, detail="Business name, website URL and email are required.")
    if len(business_name) > 50:
        raise HTTPException(status_code=400, detail="Business name too long (max 50 characters).")
    if len(description) > 150:
        raise HTTPException(status_code=400, detail="Description too long (max 150 characters).")
    if len(notes) > 300:
        raise HTTPException(status_code=400, detail="Notes too long (max 300 characters).")

    # ── Legal checkboxes ──────────────────────────────────
    if not all([confirm_accurate, confirm_offer_valid, confirm_website_works,
                confirm_logo_permission, confirm_terms]):
        raise HTTPException(status_code=400, detail="All legal confirmations are required.")

    # ── Process logo ──────────────────────────────────────
    logo_data = None
    logo_filename = None
    if logo and logo.filename:
        # Validate file type
        allowed = (".png", ".jpg", ".jpeg")
        if not logo.filename.lower().endswith(allowed):
            raise HTTPException(status_code=400, detail="Logo must be PNG or JPG format.")
        # Read and resize
        raw = await logo.read()
        if len(raw) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Logo file too large (max 5MB).")
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(raw))
            img = img.convert("RGBA") if img.mode != "RGBA" else img
            img.thumbnail((50, 50), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            logo_data = buf.getvalue()
            logo_filename = f"logo_{business_name[:20].replace(' ', '_')}.png"
        except ImportError:
            # PIL not available — use raw image
            logo_data = raw
            logo_filename = logo.filename
        except Exception:
            logo_data = raw
            logo_filename = logo.filename

    # ── Save to database ──────────────────────────────────
    submission_id = f"ps_{uuid.uuid4().hex[:12]}"
    timestamp = datetime.utcnow().isoformat()

    try:
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        c.execute("""
            INSERT INTO partner_submissions (
                id, business_name, website_url, email, phone, address,
                description, special_offer, banner_color,
                duration_type, start_date, end_date,
                frequency, category, notes,
                submitted_at, ip_address, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (
            submission_id, business_name.strip(), website_url.strip(),
            contact_email.strip(), phone.strip(), address.strip(),
            description.strip(), special_offer.strip(), banner_color.strip(),
            duration_type, start_date, end_date,
            frequency, category, notes.strip(),
            timestamp, ip
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ DB insert failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to save submission. Please try again.")

    # ── Send email to admin ───────────────────────────────
    freq_labels = {"standard": "Standard (1x)", "frequent": "Frequent (2x)", "very_frequent": "Very Frequent (3x)"}
    dur_label = "Monthly subscription (indefinite)" if duration_type == "indefinite" else f"Limited: {start_date} to {end_date}"

    body_html = f"""
    <h2>New Partner Ad Campaign Submission</h2>
    <p style="color:#2c5f2d;font-weight:bold;">Submission ID: {submission_id}</p>

    <h3 style="color:#2c5f2d;margin-top:20px;">Business Information</h3>
    <table style="border-collapse:collapse;width:100%;max-width:600px;">
        <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold;width:150px;">Business Name</td>
            <td style="padding:8px;border:1px solid #ddd;">{business_name}</td></tr>
        <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold;">Website</td>
            <td style="padding:8px;border:1px solid #ddd;"><a href="{website_url}">{website_url}</a></td></tr>
        <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold;">Email</td>
            <td style="padding:8px;border:1px solid #ddd;"><a href="mailto:{contact_email}">{contact_email}</a></td></tr>
        <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold;">Phone</td>
            <td style="padding:8px;border:1px solid #ddd;">{phone or '—'}</td></tr>
        <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold;">Address</td>
            <td style="padding:8px;border:1px solid #ddd;">{address or '—'}</td></tr>
    </table>

    <h3 style="color:#2c5f2d;margin-top:20px;">Ad Content</h3>
    <table style="border-collapse:collapse;width:100%;max-width:600px;">
        <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold;width:150px;">Description</td>
            <td style="padding:8px;border:1px solid #ddd;">{description}</td></tr>
        <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold;">Special Offer</td>
            <td style="padding:8px;border:1px solid #ddd;">{special_offer or '—'}</td></tr>
        <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold;">Banner Color</td>
            <td style="padding:8px;border:1px solid #ddd;">
                <span style="display:inline-block;width:20px;height:20px;background:{banner_color or '#F5F1E8'};border:1px solid #ccc;vertical-align:middle;border-radius:3px;"></span>
                {banner_color or 'Default'}
            </td></tr>
        <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold;">Logo</td>
            <td style="padding:8px;border:1px solid #ddd;">{'Attached' if logo_data else 'Not provided'}</td></tr>
    </table>

    <h3 style="color:#2c5f2d;margin-top:20px;">Campaign Settings</h3>
    <table style="border-collapse:collapse;width:100%;max-width:600px;">
        <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold;width:150px;">Duration</td>
            <td style="padding:8px;border:1px solid #ddd;">{dur_label}</td></tr>
        <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold;">Frequency</td>
            <td style="padding:8px;border:1px solid #ddd;">{freq_labels.get(frequency, frequency)}</td></tr>
        <tr><td style="padding:8px;border:1px solid #ddd;font-weight:bold;">Category</td>
            <td style="padding:8px;border:1px solid #ddd;">{category}</td></tr>
    </table>

    {f'<h3 style="color:#2c5f2d;margin-top:20px;">Notes</h3><p>{notes}</p>' if notes else ''}

    <hr style="margin:20px 0;border:1px solid #eee;">
    <p style="color:#999;">Submitted: {timestamp} | IP: {ip}</p>
    <p style="color:#2c5f2d;font-weight:bold;">Review this submission in the Admin Panel → Partners → Pending Submissions</p>
    """

    _send_email(
        subject=f"New Partner Ad: {business_name}",
        body_html=body_html,
        reply_to=contact_email,
        attachment_data=logo_data,
        attachment_name=logo_filename
    )

    return JSONResponse({
        "status": "success",
        "message": "Thank you! Your ad campaign submission has been received. We'll review it and get back to you soon.",
        "submission_id": submission_id
    })


# ── Admin Endpoints for Partner Submissions ───────────────────

@contact_router.get("/api/admin/partner-submissions")
async def list_partner_submissions(status: str = "all"):
    """List partner ad submissions for admin review."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if status == "all":
        c.execute("SELECT * FROM partner_submissions ORDER BY submitted_at DESC")
    else:
        c.execute("SELECT * FROM partner_submissions WHERE status = ? ORDER BY submitted_at DESC", (status,))

    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return {"submissions": rows, "count": len(rows)}


@contact_router.get("/api/admin/partner-submissions/{submission_id}")
async def get_partner_submission(submission_id: str):
    """Get single partner submission details."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM partner_submissions WHERE id = ?", (submission_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Submission not found")
    return dict(row)


@contact_router.put("/api/admin/partner-submissions/{submission_id}")
async def update_partner_submission(submission_id: str, request: Request):
    """Admin edits a pending submission before approval."""
    data = await request.json()
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    # Only allow editing if still pending
    c.execute("SELECT status FROM partner_submissions WHERE id = ?", (submission_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Submission not found")
    if row[0] != "pending":
        conn.close()
        raise HTTPException(status_code=400, detail="Can only edit pending submissions")

    editable_fields = [
        "business_name", "website_url", "email", "phone", "address",
        "description", "special_offer", "banner_color",
        "duration_type", "start_date", "end_date",
        "frequency", "category", "notes", "admin_notes"
    ]

    updates = []
    values = []
    for field in editable_fields:
        if field in data:
            updates.append(f"{field} = ?")
            values.append(data[field])

    if updates:
        values.append(submission_id)
        c.execute(f"UPDATE partner_submissions SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()

    conn.close()
    return {"status": "updated", "submission_id": submission_id}


@contact_router.post("/api/admin/partner-submissions/{submission_id}/approve")
async def approve_partner_submission(submission_id: str, request: Request):
    """
    Approve a partner submission and create an active partner entry.
    Copies submission data into the partners table.
    """
    data = await request.json()
    admin_uid = data.get("admin_uid", "unknown")

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Get submission
    c.execute("SELECT * FROM partner_submissions WHERE id = ?", (submission_id,))
    sub = c.fetchone()
    if not sub:
        conn.close()
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub["status"] != "pending":
        conn.close()
        raise HTTPException(status_code=400, detail="Submission already processed")

    sub = dict(sub)
    now = datetime.utcnow().isoformat()
    partner_id = f"p_{uuid.uuid4().hex[:12]}"

    # Map frequency to rotation_weight
    weight_map = {"standard": 1, "frequent": 2, "very_frequent": 3}
    rotation_weight = weight_map.get(sub.get("frequency", "standard"), 1)

    # Map duration to expires_at
    expires_at = None
    if sub.get("duration_type") == "limited" and sub.get("end_date"):
        expires_at = sub["end_date"]

    # Insert into partners table
    c.execute("""
        INSERT INTO partners (
            partner_id, name, url, email, phone, description, offer,
            bg_color, anchor, status, active,
            rotation_weight, category, created_at, updated_at,
            submission_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 1, ?, ?, ?, ?, ?)
    """, (
        partner_id,
        sub.get("business_name", ""),
        sub.get("website_url", ""),
        sub.get("email", ""),
        sub.get("phone", ""),
        sub.get("description", ""),
        sub.get("special_offer", ""),
        sub.get("banner_color", "rgba(255,255,255,1.0)"),
        sub.get("website_url", ""),
        rotation_weight,
        sub.get("category", "other"),
        now, now,
        submission_id
    ))

    # Add expires_at if limited duration
    if expires_at:
        c.execute("UPDATE partners SET expires_at = ? WHERE partner_id = ?", (expires_at, partner_id))

    # Update submission status
    c.execute("""
        UPDATE partner_submissions SET
            status = 'approved', reviewed_by = ?, reviewed_at = ?,
            admin_notes = ?
        WHERE id = ?
    """, (admin_uid, now, data.get("admin_notes", ""), submission_id))

    # Audit log
    c.execute("""
        INSERT INTO audit_log (action, admin_id, target_user_id, details, timestamp)
        VALUES ('partner_submission_approved', ?, ?, ?, ?)
    """, (admin_uid, sub.get("email", ""),
          json.dumps({"submission_id": submission_id, "partner_id": partner_id,
                      "business_name": sub.get("business_name", "")}), now))

    conn.commit()
    conn.close()

    return {
        "status": "approved",
        "partner_id": partner_id,
        "submission_id": submission_id,
        "message": f"Partner '{sub.get('business_name')}' approved and now active"
    }


@contact_router.post("/api/admin/partner-submissions/{submission_id}/reject")
async def reject_partner_submission(submission_id: str, request: Request):
    """Reject a partner submission with feedback."""
    data = await request.json()
    admin_uid = data.get("admin_uid", "unknown")
    reason = data.get("reason", "")
    now = datetime.utcnow().isoformat()

    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    c.execute("SELECT status, business_name FROM partner_submissions WHERE id = ?", (submission_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Submission not found")
    if row[0] != "pending":
        conn.close()
        raise HTTPException(status_code=400, detail="Submission already processed")

    c.execute("""
        UPDATE partner_submissions SET
            status = 'rejected', reviewed_by = ?, reviewed_at = ?,
            admin_notes = ?
        WHERE id = ?
    """, (admin_uid, now, reason, submission_id))

    # Audit log
    c.execute("""
        INSERT INTO audit_log (action, admin_id, target_user_id, details, timestamp)
        VALUES ('partner_submission_rejected', ?, ?, ?, ?)
    """, (admin_uid, "",
          json.dumps({"submission_id": submission_id, "business_name": row[1], "reason": reason}), now))

    conn.commit()
    conn.close()

    return {"status": "rejected", "submission_id": submission_id}


# ── Partner Soft Delete / Restore / Permanent Delete ──────────

@contact_router.post("/api/admin/partners/{partner_id}/soft-delete")
async def soft_delete_partner(partner_id: str, request: Request):
    """Soft delete a partner — 30-day grace period before permanent removal."""
    data = await request.json()
    admin_uid = data.get("admin_uid", "unknown")
    now = datetime.utcnow().isoformat()

    # Calculate grace period expiry (30 days from now)
    from datetime import timedelta
    grace_expires = (datetime.utcnow() + timedelta(days=30)).isoformat()

    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    c.execute("SELECT name, status FROM partners WHERE partner_id = ?", (partner_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Partner not found")

    c.execute("""
        UPDATE partners SET
            status = 'soft_deleted', active = 0,
            deletion_scheduled = 1,
            deletion_scheduled_at = ?,
            deletion_grace_period_expires = ?
        WHERE partner_id = ?
    """, (now, grace_expires, partner_id))

    c.execute("""
        INSERT INTO audit_log (action, admin_id, target_user_id, details, timestamp)
        VALUES ('partner_soft_deleted', ?, ?, ?, ?)
    """, (admin_uid, partner_id,
          json.dumps({"partner_id": partner_id, "business_name": row[0], "grace_expires": grace_expires}), now))

    conn.commit()
    conn.close()

    return {
        "status": "soft_deleted",
        "partner_id": partner_id,
        "business_name": row[0],
        "grace_expires": grace_expires,
        "message": f"'{row[0]}' marked for deletion. Restore within 30 days."
    }


@contact_router.post("/api/admin/partners/{partner_id}/restore")
async def restore_partner(partner_id: str, request: Request):
    """Restore a soft-deleted partner — one click, back to active."""
    data = await request.json()
    admin_uid = data.get("admin_uid", "unknown")
    now = datetime.utcnow().isoformat()

    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    c.execute("SELECT name, status FROM partners WHERE partner_id = ?", (partner_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Partner not found")
    if row[1] != "soft_deleted":
        conn.close()
        raise HTTPException(status_code=400, detail="Partner is not soft-deleted")

    c.execute("""
        UPDATE partners SET
            status = 'active', active = 1,
            deletion_scheduled = 0,
            deletion_scheduled_at = NULL,
            deletion_grace_period_expires = NULL
        WHERE partner_id = ?
    """, (partner_id,))

    c.execute("""
        INSERT INTO audit_log (action, admin_id, target_user_id, details, timestamp)
        VALUES ('partner_restored', ?, ?, ?, ?)
    """, (admin_uid, partner_id,
          json.dumps({"partner_id": partner_id, "business_name": row[0]}), now))

    conn.commit()
    conn.close()

    return {
        "status": "restored",
        "partner_id": partner_id,
        "business_name": row[0],
        "message": f"'{row[0]}' restored and reactivated"
    }


@contact_router.delete("/api/admin/partners/{partner_id}/permanent")
async def permanent_delete_partner(partner_id: str, request: Request):
    """
    Permanently delete a partner. Requires confirm_business_name to match.
    Cannot be undone.
    """
    data = await request.json()
    admin_uid = data.get("admin_uid", "unknown")
    confirm_name = data.get("confirm_business_name", "")
    reason = data.get("reason", "")
    now = datetime.utcnow().isoformat()

    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    c.execute("SELECT name, submission_id FROM partners WHERE partner_id = ?", (partner_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Partner not found")

    # Require exact business name match
    if confirm_name.strip().lower() != row[0].strip().lower():
        conn.close()
        raise HTTPException(status_code=400, detail="Business name does not match. Permanent deletion cancelled.")

    submission_id = row[1]

    # Audit log BEFORE delete
    c.execute("""
        INSERT INTO audit_log (action, admin_id, target_user_id, details, timestamp)
        VALUES ('partner_deleted_permanent', ?, ?, ?, ?)
    """, (admin_uid, partner_id,
          json.dumps({"partner_id": partner_id, "business_name": row[0],
                      "submission_id": submission_id, "reason": reason}), now))

    # Delete partner
    c.execute("DELETE FROM partners WHERE partner_id = ?", (partner_id,))

    # Also delete linked submission if exists
    if submission_id:
        c.execute("DELETE FROM partner_submissions WHERE id = ?", (submission_id,))

    conn.commit()
    conn.close()

    return {
        "status": "permanently_deleted",
        "partner_id": partner_id,
        "business_name": row[0],
        "message": f"'{row[0]}' permanently deleted. This cannot be undone."
    }


@contact_router.delete("/api/admin/partners/{partner_id}/permanent")
async def permanent_delete_partner(partner_id: str, request: Request):
    """
    Permanently delete a partner. Requires confirm_business_name to match.
    Cannot be undone.
    """
    data = await request.json()
    admin_uid = data.get("admin_uid", "unknown")
    confirm_name = data.get("confirm_business_name", "")
    reason = data.get("reason", "")
    now = datetime.utcnow().isoformat()

    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    c.execute("SELECT name, submission_id FROM partners WHERE partner_id = ?", (partner_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Partner not found")

    # Require exact business name match
    if confirm_name.strip().lower() != row[0].strip().lower():
        conn.close()
        raise HTTPException(status_code=400, detail="Business name does not match. Permanent deletion cancelled.")

    submission_id = row[1]

    # Audit log BEFORE delete
    c.execute("""
        INSERT INTO audit_log (action, admin_id, target_user_id, details, timestamp)
        VALUES ('partner_deleted_permanent', ?, ?, ?, ?)
    """, (admin_uid, partner_id,
          json.dumps({"partner_id": partner_id, "business_name": row[0],
                      "submission_id": submission_id, "reason": reason}), now))

    # Delete partner
    c.execute("DELETE FROM partners WHERE partner_id = ?", (partner_id,))

    # Also delete linked submission if exists
    if submission_id:
        c.execute("DELETE FROM partner_submissions WHERE id = ?", (submission_id,))

    conn.commit()
    conn.close()

    return {
        "status": "permanently_deleted",
        "partner_id": partner_id,
        "business_name": row[0],
        "message": f"'{row[0]}' permanently deleted. This cannot be undone."
    }


@contact_router.get("/api/admin/partners/deleted")
async def list_deleted_partners():
    """List all soft-deleted partners with grace period info."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT * FROM partners
        WHERE status = 'soft_deleted'
        ORDER BY deletion_scheduled_at DESC
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    # Add computed fields
    now = datetime.utcnow()
    for row in rows:
        if row.get("deletion_grace_period_expires"):
            try:
                expires = datetime.fromisoformat(row["deletion_grace_period_expires"])
                days_left = max(0, (expires - now).days)
                row["days_until_permanent"] = days_left
                row["grace_expired"] = days_left <= 0
            except (ValueError, TypeError):
                row["days_until_permanent"] = 0
                row["grace_expired"] = True

    return {"deleted_partners": rows, "count": len(rows)}


# ── Contact Messages (Admin Inbox) ────────────────────────────

@contact_router.get("/api/admin/contact-messages")
async def list_contact_messages(limit: int = 50, offset: int = 0):
    """Get all contact form submissions for admin inbox."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Get total count
    c.execute("SELECT COUNT(*) FROM contact_messages")
    total = c.fetchone()[0]

    # Get paginated messages (newest first)
    c.execute("""
        SELECT * FROM contact_messages
        ORDER BY submitted_at DESC
        LIMIT ? OFFSET ?
    """, (limit, offset))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    return {
        "messages": rows,
        "total": total,
        "count": len(rows),
        "limit": limit,
        "offset": offset
    }


@contact_router.get("/api/admin/contact-messages/{message_id}")
async def get_contact_message(message_id: str):
    """Get single contact message details."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM contact_messages WHERE id = ?", (message_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Message not found")
    return dict(row)


# ── Auto-Delete Expired Grace Periods ─────────────────────────

def auto_delete_expired_partner_ads():
    """
    Delete partners whose 30-day grace period has expired.
    Called daily by scheduler in main.py.
    """
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    now = datetime.utcnow().isoformat()

    c.execute("""
        SELECT partner_id, name, submission_id FROM partners
        WHERE deletion_scheduled = 1
        AND deletion_grace_period_expires < ?
    """, (now,))
    expired = c.fetchall()

    for partner_id, name, submission_id in expired:
        c.execute("""
            INSERT INTO audit_log (action, admin_id, target_user_id, details, timestamp)
            VALUES ('partner_deleted_auto_grace_expired', 'system', ?, ?, ?)
        """, (partner_id, json.dumps({"partner_id": partner_id, "business_name": name}), now))

        c.execute("DELETE FROM partners WHERE partner_id = ?", (partner_id,))
        if submission_id:
            c.execute("DELETE FROM partner_submissions WHERE id = ?", (submission_id,))

    conn.commit()
    conn.close()

    count = len(expired)
    if count > 0:
        print(f"🗑️ Auto-deleted {count} expired partner ads")
    return {"auto_deleted": count}
