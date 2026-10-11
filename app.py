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
app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024  # 3 MB upload limit (doctor photos)

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


# ---------------- PUBLIC ROUTES ----------------
@app.route("/")
def index():
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
            "specialty": doctor["specialty"],
            "date": date,
            "time": time,
            "note": note,
            "status": "Pending"
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
    return render_template("admin.html",
                           doctors=doctors,
                           appointments=appointments)


# ---------------- DOCTOR PHOTO UPLOAD ----------------
PHOTO_DIR = os.path.join(app.static_folder, "doctors")


def _detect_image_ext(data):
    """Return 'jpg' / 'png' / 'webp' from the file CONTENT (never trust the filename), else None."""
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def delete_doctor_photo(doctor):
    """Delete the doctor's uploaded photo file (if any)."""
    old = doctor.get("photo")
    if old:
        try:
            os.remove(os.path.join(PHOTO_DIR, os.path.basename(old)))
        except OSError:
            pass


def save_doctor_photo(doctor, file_storage):
    """Save an uploaded photo and set doctor["photo"].
    Returns an error message, or None on success. The caller must save the doctors file."""
    if not file_storage or not file_storage.filename:
        return "No photo selected."
    data = file_storage.read()
    ext = _detect_image_ext(data)
    if not ext:
        return "Please upload a JPG, PNG or WEBP image."
    os.makedirs(PHOTO_DIR, exist_ok=True)
    filename = f"doctor_{doctor['id']}_{int(time.time())}.{ext}"
    with open(os.path.join(PHOTO_DIR, filename), "wb") as f:
        f.write(data)
    delete_doctor_photo(doctor)  # remove the previous photo
    doctor["photo"] = filename
    return None


@app.route("/admin/doctor/<int:doctor_id>/photo", methods=["POST"])
def upload_doctor_photo(doctor_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    doctors = load_data(DOCTORS_FILE)
    doctor = next((d for d in doctors if d["id"] == doctor_id), None)
    if not doctor:
        flash("Doctor not found.", "error")
        return redirect(url_for("admin_dashboard"))
    error = save_doctor_photo(doctor, request.files.get("photo"))
    if error:
        flash(error, "error")
    else:
        save_data(DOCTORS_FILE, doctors)
        flash(f"Photo updated for {doctor['name']}.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/doctor/<int:doctor_id>/photo/remove", methods=["POST"])
def remove_doctor_photo(doctor_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    doctors = load_data(DOCTORS_FILE)
    doctor = next((d for d in doctors if d["id"] == doctor_id), None)
    if not doctor:
        flash("Doctor not found.", "error")
    elif not doctor.get("photo"):
        flash("This doctor has no uploaded photo.", "error")
    else:
        delete_doctor_photo(doctor)
        doctor.pop("photo", None)
        save_data(DOCTORS_FILE, doctors)
        flash(f"Photo removed for {doctor['name']}.", "success")
    return redirect(url_for("admin_dashboard"))


@app.errorhandler(413)
def photo_too_large(e):
    flash("Photo is too large. Maximum size is 3 MB.", "error")
    return redirect(url_for("admin_dashboard"))


# ---------------- DOCTOR PROFILE DETAILS ----------------
# Optional text fields shown in the "Details" popup (name -> max length)
DETAIL_FIELDS = {
    "qualification": 120,   # e.g. MBBS, FCPS (Cardiology)
    "university": 120,      # where the doctor studied
    "hospital": 120,        # current hospital / clinic
    "pmdc": 40,             # PMDC registration number
    "languages": 120,
    "about": 600,
}


def apply_doctor_details(doctor, form):
    """Copy the optional profile fields from a submitted form onto the doctor dict.
    Empty values are removed so they simply do not show on the website."""
    for key, limit in DETAIL_FIELDS.items():
        value = form.get(key, "").strip()[:limit]
        if value:
            doctor[key] = value
        else:
            doctor.pop(key, None)
    years = form.get("experience", "").strip()
    if years.isdigit() and 0 <= int(years) <= 70:
        doctor["experience"] = int(years)
    else:
        doctor.pop("experience", None)


@app.route("/admin/doctor/<int:doctor_id>/details", methods=["POST"])
def update_doctor_details(doctor_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    doctors = load_data(DOCTORS_FILE)
    doctor = next((d for d in doctors if d["id"] == doctor_id), None)
    if not doctor:
        flash("Doctor not found.", "error")
    else:
        apply_doctor_details(doctor, request.form)
        save_data(DOCTORS_FILE, doctors)
        flash(f"Details updated for {doctor['name']}.", "success")
    return redirect(url_for("admin_dashboard"))


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
    photo = request.files.get("photo")
    photo_error = save_doctor_photo(doctor, photo) if photo and photo.filename else None
    apply_doctor_details(doctor, request.form)
    doctors.append(doctor)
    save_data(DOCTORS_FILE, doctors)
    flash(f"Doctor added: {name}", "success")
    if photo_error:
        flash(f"Photo not saved: {photo_error}", "error")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/remove-doctor/<int:doctor_id>", methods=["POST"])
def remove_doctor(doctor_id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    doctors = load_data(DOCTORS_FILE)
    for d in doctors:
        if d["id"] == doctor_id:
            delete_doctor_photo(d)
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


if __name__ == "__main__":
    # Debug OFF for production / live use — prevents auto-restart data loss
    app.run(host="0.0.0.0", port=5000, debug=False)