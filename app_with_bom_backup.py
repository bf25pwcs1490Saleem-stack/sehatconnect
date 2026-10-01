from flask import Flask, render_template, request, redirect, url_for, session, flash
import json
import os
import shutil
import tempfile
import threading
from datetime import datetime, timedelta
import time
app = Flask(__name__)
app.secret_key = "sehatconnect_secret_key_2026"

DOCTORS_FILE = "doctors.json"
APPOINTMENTS_FILE = "appointments.json"
ADMIN_PASSWORD = "admin123"

# ==================== ADMIN ACCOUNTS ====================
ADMINS = {
    "admin": {
        "name": "Team Lead",
        "password": "admin123",
        "role": "superadmin"
    },
    "member1": {
        "name": "Team Member 1",
        "password": "member1@2026",
        "role": "admin"
    },
    "member2": {
        "name": "Team Member 2",
        "password": "member2@2026",
        "role": "admin"
    },
    "member3": {
        "name": "Team Member 3",
        "password": "member3@2026",
        "role": "admin"
    },
}

ADMIN_PASSWORD = "admin123"


# ---------------- HELPERS ----------------
def load_data(file):
    """Load JSON. If corrupted, try backup."""
    if not os.path.exists(file):
        return []

    # Try main file first
    try:
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data is None:
                raise ValueError("File is None")
            return data
    except Exception as e:
        print(f"[LOAD ERROR] {file}: {e}")

        # Try latest backup
        try:
            if os.path.exists("backups"):
                prefix = os.path.basename(file) + "."
                backups = sorted(
                    [b for b in os.listdir("backups") if b.startswith(prefix)],
                    reverse=True
                )
                for b in backups:
                    try:
                        with open(f"backups/{b}", "r", encoding="utf-8") as f:
                            data = json.load(f)
                            if data is not None:
                                print(f"[RECOVERED] {file} from backup {b}")
                                return data
                    except:
                        continue
        except:
            pass

        return []

# Thread-safe file lock
_file_lock = threading.Lock()


def save_data(file, data):
    """Atomic, safe save with automatic backup."""
    with _file_lock:
        try:
            # Create backups folder if missing
            if not os.path.exists("backups"):
                os.makedirs("backups")

            # Backup existing file (keep latest 5)
            if os.path.exists(file):
                try:
                    backup_name = f"backups/{os.path.basename(file)}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
                    shutil.copy2(file, backup_name)

                    # Keep only last 5 backups
                    prefix = os.path.basename(file) + "."
                    backups = sorted(
                        [f for f in os.listdir("backups") if f.startswith(prefix)],
                        reverse=True
                    )
                    for old in backups[5:]:
                        try:
                            os.remove(f"backups/{old}")
                        except:
                            pass
                except:
                    pass

            # Atomic write: write to temp file, then rename
            dir_name = os.path.dirname(os.path.abspath(file)) or "."
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=dir_name,
                delete=False, suffix=".tmp"
            ) as tmp:
                json.dump(data, tmp, indent=2, ensure_ascii=False)
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_path = tmp.name

            # Atomic replace
            os.replace(tmp_path, file)

        except Exception as e:
            print(f"[SAVE ERROR] {file}: {e}")
            # If save fails, try to restore from latest backup
            try:
                prefix = os.path.basename(file) + "."
                backups = sorted(
                    [f for f in os.listdir("backups") if f.startswith(prefix)],
                    reverse=True
                )
                if backups:
                    shutil.copy2(f"backups/{backups[0]}", file)
                    print(f"[RESTORE] Restored {file} from backup {backups[0]}")
            except:
                pass


def next_id(data):
    if not data:
        return 1
    return max(item["id"] for item in data) + 1
def check_auto_confirm(appointments):
    """Auto-confirm appointments waiting over 2 minutes."""
    if not isinstance(appointments, list):
        return []

    changed = False
    now = datetime.now()

    for a in appointments:
        if not isinstance(a, dict):
            continue
        if a.get("status") == "Requested":
            try:
                req_time_str = a.get("requested_at", "")
                if req_time_str:
                    req_time = datetime.fromisoformat(req_time_str)
                else:
                    req_time = now
            except Exception:
                req_time = now

            if (now - req_time).total_seconds() >= 120:
                a["status"] = "Auto-Confirmed"
                changed = True

    if changed:
        try:
            save_data(APPOINTMENTS_FILE, appointments)
        except Exception as e:
            print(f"[AUTO-CONFIRM SAVE ERROR] {e}")

    return appointments
    doctors = load_data(DOCTORS_FILE)
    total_doctors = len(doctors)
    total_appointments = len(load_data(APPOINTMENTS_FILE))
    specialties = sorted(set(d["specialty"] for d in doctors))
    return render_template("index.html",
                           total_doctors=total_doctors,
                           total_appointments=total_appointments,
                           specialties=specialties)


@app.route("/doctors")
def doctors():
    all_doctors = load_data(DOCTORS_FILE)
    keyword = request.args.get("q", "").strip().lower()
    specialty = request.args.get("specialty", "").strip()
    area = request.args.get("area", "").strip()

    result = all_doctors
    if keyword:
        result = [d for d in result
                  if keyword in d["name"].lower()
                  or keyword in d["specialty"].lower()
                  or keyword in d.get("area", "").lower()]
    if specialty:
        result = [d for d in result if d["specialty"] == specialty]
    if area:
        result = [d for d in result if d.get("area", "") == area]

    specialties = sorted(set(d["specialty"] for d in all_doctors))
    areas = sorted(set(d.get("area", "") for d in all_doctors if d.get("area")))

    return render_template("doctors.html",
                           doctors=result,
                           specialties=specialties,
                           areas=areas,
                           q=keyword,
                           selected_specialty=specialty,
                           selected_area=area)


@app.route("/book/<int:doctor_id>", methods=["GET", "POST"])
def book(doctor_id):
    doctors = load_data(DOCTORS_FILE)
    doctor = next((d for d in doctors if d["id"] == doctor_id), None)
    if not doctor:
        flash("Doctor not found.", "error")
        return redirect(url_for("doctors"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        date = request.form.get("date", "").strip()
        time = request.form.get("time", "").strip()
        note = request.form.get("note", "").strip()

        if not name or not phone or not date or not time:
            flash("Please fill all required fields.", "error")
            return render_template("book.html", doctor=doctor)

        appointments = load_data(APPOINTMENTS_FILE)

        for a in appointments:
            if (a["doctor_id"] == doctor_id
                    and a["date"] == date
                    and a["time"].lower() == time.lower()):
                flash("This slot is already booked. Please choose another time.", "error")
                return render_template("book.html", doctor=doctor)

                new_appt = {
            "id": next_id(appointments),
            "patient_name": name,
            "phone": phone,
            "doctor_id": doctor_id,
            "doctor_name": doctor["name"],
            "doctor_email": doctor.get("email", ""),
            "doctor_phone": doctor.get("phone", ""),
            "specialty": doctor["specialty"],
            "date": date,
            "time": time,
            "note": note,
            "fee": doctor.get("fee", 0),
            "status": "Requested",
            "payment_status": "Unpaid",
            "payment_method": "",
            "payment_ref": "",
            "paid_at": "",
            "requested_at": datetime.now().isoformat()
        }
        appointments.append(new_appt)
        save_data(APPOINTMENTS_FILE, appointments)
        flash(f"Appointment booked! Your ID is #{new_appt['id']}", "success")
        return redirect(url_for("my_appointments", phone=phone))

    return render_template("book.html", doctor=doctor)


@app.route("/my-appointments")
def my_appointments():
    phone = request.args.get("phone", "").strip()
    appointments = []
    if phone:
        all_a = load_data(APPOINTMENTS_FILE)
        appointments = [a for a in all_a if a["phone"] == phone]
    return render_template("my_appointments.html",
                           appointments=appointments,
                           phone=phone)


@app.route("/cancel/<int:appt_id>", methods=["POST"])
def cancel(appt_id):
    appointments = load_data(APPOINTMENTS_FILE)
    appointments = [a for a in appointments if a["id"] != appt_id]
    save_data(APPOINTMENTS_FILE, appointments)
    flash("Appointment cancelled.", "success")
    phone = request.form.get("phone", "")
    return redirect(url_for("my_appointments", phone=phone))


# ---------------- ADMIN ROUTES ----------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        pwd = request.form.get("password", "")

        # Check username + password
        if username in ADMINS and ADMINS[username]["password"] == pwd:
            session["admin"] = True
            session["admin_username"] = username
            session["admin_name"] = ADMINS[username]["name"]
            session["admin_role"] = ADMINS[username]["role"]
            flash(f"Welcome, {ADMINS[username]['name']}!", "success")
            return redirect(url_for("admin_dashboard"))

        # Fallback: password only (for backward compatibility)
        if pwd == ADMIN_PASSWORD:
            session["admin"] = True
            session["admin_username"] = "admin"
            session["admin_name"] = "Admin"
            session["admin_role"] = "superadmin"
            flash("Welcome, Admin!", "success")
            return redirect(url_for("admin_dashboard"))

        flash("Wrong username or password.", "error")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    flash("Logged out.", "success")
    return redirect(url_for("index"))


@app.route("/admin")
def admin_dashboard():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    doctors = load_data(DOCTORS_FILE)
    appointments = load_data(APPOINTMENTS_FILE)
    appointments = check_auto_confirm(appointments)

    # ============ DASHBOARD STATS ============
    from datetime import datetime as dt

    today_str = dt.now().strftime("%Y-%m-%d")

    total_doctors = len(doctors)
    total_appointments = len(appointments)
    today_appointments = len([a for a in appointments if a.get("date") == today_str])
    pending_payments = len([a for a in appointments
                            if a.get("payment_status") in ("Unpaid", "Pending Verification")])

    # ============ LINE CHART — Last 7 Days ============
    chart_labels = []
    chart_data = []
    for i in range(6, -1, -1):
        day = dt.now() - timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        label = day.strftime("%a")
        count = len([a for a in appointments if a.get("date") == day_str])
        chart_labels.append(label)
        chart_data.append(count)

    # ============ DOUGHNUT — Specialties ============
    specialty_counts = {}
    for d in doctors:
        spec = d.get("specialty", "Other")
        specialty_counts[spec] = specialty_counts.get(spec, 0) + 1

    # If no doctors, show placeholder
    if not specialty_counts:
        specialty_counts = {"No Data": 1}

    specialty_labels = list(specialty_counts.keys())
    specialty_data = list(specialty_counts.values())

    # ============ RECENT APPOINTMENTS ============
    recent_appointments = sorted(
        appointments,
        key=lambda x: x.get("id", 0),
        reverse=True
    )[:8]

    # ============ UPCOMING ============
    upcoming = [
        a for a in appointments
        if a.get("date", "") >= today_str
        and a.get("status") not in ("Rejected", "Refunded", "Cancelled - Refund Pending")
    ]
    upcoming = sorted(upcoming, key=lambda x: (x.get("date", ""), x.get("time", "")))[:5]

    return render_template("admin.html",
                           doctors=doctors,
                           appointments=appointments,
                           total_doctors=total_doctors,
                           total_appointments=total_appointments,
                           today_appointments=today_appointments,
                           pending_payments=pending_payments,
                           pending_count=pending_payments,
                           chart_labels=chart_labels,
                           chart_data=chart_data,
                           specialty_labels=specialty_labels,
                           specialty_data=specialty_data,
                           recent_appointments=recent_appointments,
                           upcoming=upcoming,
                           now=dt.now())

@app.route("/admin/add-doctor", methods=["POST"])
def add_doctor():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    doctors = load_data(DOCTORS_FILE)
    name = request.form.get("name", "").strip()
    specialty = request.form.get("specialty", "").strip()
    area = request.form.get("area", "").strip()
    days = request.form.get("days", "").strip()
    time = request.form.get("time", "").strip()
    try:
        fee = int(request.form.get("fee", 0))
    except:
        fee = 0

    if not name or not specialty:
        flash("Name and Specialty are required.", "error")
        return redirect(url_for("admin_dashboard"))

    doctor = {
        "id": next_id(doctors),
        "name": name,
        "specialty": specialty,
        "area": area,
        "days": [d.strip() for d in days.split(",") if d.strip()],
        "time": time,
        "fee": fee
    }
    doctors.append(doctor)
    save_data(DOCTORS_FILE, doctors)
    flash(f"Doctor added: {name}", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/remove-doctor/<int:doctor_id>", methods=["POST"])
def remove_doctor(doctor_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    doctors = load_data(DOCTORS_FILE)
    doctors = [d for d in doctors if d["id"] != doctor_id]
    save_data(DOCTORS_FILE, doctors)
    flash("Doctor removed.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/appointment/<int:appt_id>/done", methods=["POST"])
def mark_done(appt_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    appointments = load_data(APPOINTMENTS_FILE)
    for a in appointments:
        if a["id"] == appt_id:
            a["status"] = "Done"
    save_data(APPOINTMENTS_FILE, appointments)
    flash("Marked as done.", "success")
    return redirect(url_for("admin_dashboard"))
    flash("Marked as done.", "success")
    return redirect(url_for("admin_dashboard"))# ==================== FEEDBACK ROUTES ====================
@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        rating = request.form.get("rating", "5")
        message = request.form.get("message", "").strip()
        doctor_name = request.form.get("doctor_name", "").strip()

        if not name or not message:
            flash("Name and message are required.", "error")
            return render_template("feedback.html")

        feedbacks = load_data("feedbacks.json")
        if not isinstance(feedbacks, list):
            feedbacks = []

        new_fb = {
            "id": len(feedbacks) + 1,
            "name": name,
            "phone": phone,
            "rating": rating,
            "message": message,
            "doctor_name": doctor_name,
            "time": datetime.now().isoformat()
        }
        feedbacks.append(new_fb)
        save_data("feedbacks.json", feedbacks)

        flash("Thank you for your feedback! ✅", "success")
        return redirect(url_for("feedback"))

    return render_template("feedback.html")


# ==================== REFUND ROUTES ====================
@app.route("/admin/feedback-refunds")
def admin_feedback_refunds():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    feedbacks = load_data("feedbacks.json")
    if not isinstance(feedbacks, list):
        feedbacks = []

    refunds = load_data("refunds.json")
    if not isinstance(refunds, list):
        refunds = []

    # List of paid appointments available for refund
    appointments = load_data(APPOINTMENTS_FILE)
    refundable = [a for a in appointments if a.get("payment_status") == "Paid"]

    return render_template("admin_feedback_refunds.html",
                           feedbacks=feedbacks,
                           refunds=refunds,
                           refundable=refundable)


@app.route("/admin/appointment/<int:appt_id>/refund", methods=["POST"])
def refund_appointment(appt_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    appointments = load_data(APPOINTMENTS_FILE)
    target = next((a for a in appointments if a["id"] == appt_id), None)

    if not target:
        flash("Appointment not found.", "error")
        return redirect(url_for("admin_feedback_refunds"))

    if target.get("payment_status") != "Paid":
        flash("⛔ Cannot refund: not a paid appointment.", "error")
        return redirect(url_for("admin_feedback_refunds"))

    # Mark appointment as refunded
    target["payment_status"] = "Refunded"
    target["status"] = "Refunded"
    target["refunded_at"] = datetime.now().isoformat()
    target["refunded_by"] = session.get("admin_name", "Admin")
    target["refund_amount"] = target.get("fee", 0)
    save_data(APPOINTMENTS_FILE, appointments)

    # Save to refunds log
    refunds = load_data("refunds.json")
    if not isinstance(refunds, list):
        refunds = []

    refunds.append({
        "id": len(refunds) + 1,
        "appt_id": appt_id,
        "patient_name": target.get("patient_name"),
        "phone": target.get("phone"),
        "doctor_name": target.get("doctor_name"),
        "amount": target.get("fee", 0),
        "method": target.get("payment_method", "N/A"),
        "refunded_by": session.get("admin_name", "Admin"),
        "refunded_at": datetime.now().isoformat()
    })
    save_data("refunds.json", refunds)

    flash(f"✅ Refunded Rs. {target.get('fee', 0)} to {target.get('patient_name')}.", "success")
    return redirect(url_for("admin_feedback_refunds"))


if __name__ == "__main__":
    # Debug OFF for production / live use — prevents auto-restart data loss
    app.run(host="0.0.0.0", port=5000, debug=False)
# ==================== APPOINTMENT ACTION ROUTES ====================

@app.route("/admin/appointment/<int:appt_id>/accept", methods=["POST"])
def accept_appointment(appt_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    appointments = load_data(APPOINTMENTS_FILE) or []
    for a in appointments:
        if isinstance(a, dict) and a.get("id") == appt_id:
            a["status"] = "Confirmed"
    save_data(APPOINTMENTS_FILE, appointments)
    flash("Appointment confirmed.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/appointment/<int:appt_id>/reject", methods=["POST"])
def reject_appointment(appt_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    appointments = load_data(APPOINTMENTS_FILE) or []
    for a in appointments:
        if isinstance(a, dict) and a.get("id") == appt_id:
            a["status"] = "Rejected"
    save_data(APPOINTMENTS_FILE, appointments)
    flash("Appointment rejected.", "success")
    return redirect(url_for("admin_dashboard"))



@app.route("/admin/appointment/<int:appt_id>/verify-payment", methods=["POST"])
def verify_payment(appt_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    appointments = load_data(APPOINTMENTS_FILE) or []
    for a in appointments:
        if isinstance(a, dict) and a.get("id") == appt_id:
            a["payment_status"] = "Paid"
            a["status"] = "Paid"
    save_data(APPOINTMENTS_FILE, appointments)
    flash("Payment verified.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/appointment/<int:appt_id>/reject-payment", methods=["POST"])
def reject_payment(appt_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    appointments = load_data(APPOINTMENTS_FILE) or []
    for a in appointments:
        if isinstance(a, dict) and a.get("id") == appt_id:
            a["payment_status"] = "Unpaid"
            a["status"] = "Confirmed"
            a["payment_ref"] = ""
    save_data(APPOINTMENTS_FILE, appointments)
    flash("Payment rejected.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/appointment/<int:appt_id>/refund", methods=["POST"])
def refund_appointment(appt_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    appointments = load_data(APPOINTMENTS_FILE) or []
    target = None
    for a in appointments:
        if isinstance(a, dict) and a.get("id") == appt_id:
            target = a
            break
    if not target:
        flash("Appointment not found.", "error")
        return redirect(url_for("admin_dashboard"))

    if target.get("payment_status") != "Paid":
        flash("Cannot refund: not a paid appointment.", "error")
        return redirect(url_for("admin_dashboard"))

    target["payment_status"] = "Refunded"
    target["status"] = "Refunded"
    target["refunded_at"] = datetime.now().isoformat()
    target["refunded_by"] = session.get("admin_name", "Admin")
    target["refund_amount"] = target.get("fee", 0)
    save_data(APPOINTMENTS_FILE, appointments)

    refunds = load_data("refunds.json")
    if not isinstance(refunds, list):
        refunds = []
    refunds.append({
        "id": len(refunds) + 1,
        "appt_id": appt_id,
        "patient_name": target.get("patient_name"),
        "phone": target.get("phone"),
        "doctor_name": target.get("doctor_name"),
        "amount": target.get("fee", 0),
        "method": target.get("payment_method", "N/A"),
        "refunded_by": session.get("admin_name", "Admin"),
        "refunded_at": datetime.now().isoformat()
    })
    save_data("refunds.json", refunds)

    flash(f"Refunded Rs. {target.get('fee', 0)}.", "success")
    return redirect(url_for("admin_feedback_refunds") if "admin_feedback_refunds" in [r.endpoint for r in app.url_map.iter_rules()] else url_for("admin_dashboard"))


# ==================== OTHER ADMIN PAGES ====================

@app.route("/admin/analytics")
def admin_analytics():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    data = load_data(ANALYTICS_FILE) or {}
    visits = data.get("visits", []) if isinstance(data, dict) else []
    total = data.get("total", len(visits)) if isinstance(data, dict) else len(visits)
    now = datetime.now()
    last_24h = [v for v in visits if v.get("time") and (now - datetime.fromisoformat(v["time"])).total_seconds() < 86400]
    page_counts = {}
    for v in visits:
        p = v.get("path", "/")
        page_counts[p] = page_counts.get(p, 0) + 1
    device_counts = {"Mobile": 0, "Desktop": 0, "Tablet": 0}
    for v in visits:
        d = v.get("device", "Desktop")
        device_counts[d] = device_counts.get(d, 0) + 1
    unique_ips = len(set(v.get("ip", "") for v in visits if v.get("ip")))
    recent = sorted(visits, key=lambda x: x.get("time", ""), reverse=True)[:20]
    sorted_pages = sorted(page_counts.items(), key=lambda x: x[1], reverse=True)
    return render_template("analytics.html",
                           total=total, last_24h=len(last_24h),
                           unique_ips=unique_ips, page_counts=sorted_pages,
                           device_counts=device_counts, recent=recent)


@app.route("/admin/backups")
def admin_backups():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    if not os.path.exists("backups"):
        os.makedirs("backups")
    files = sorted(os.listdir("backups"), reverse=True)
    return render_template("backups.html", files=files)


@app.route("/admin/audit")
def admin_audit():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    logs = load_data("audit_log.json")
    if not isinstance(logs, list):
        logs = []
    logs = sorted(logs, key=lambda x: x.get("time", ""), reverse=True)[:100]
    return render_template("audit.html", logs=logs)


@app.route("/admin/team")
def admin_team():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    team = []
    for username, info in ADMINS.items():
        team.append({"username": username, "name": info["name"], "role": info["role"]})
    return render_template("team.html", team=team)


