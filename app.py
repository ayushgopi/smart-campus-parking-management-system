from datetime import datetime
from functools import wraps
import os
import sqlite3

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "parking.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "smart-campus-dev-secret-key"
)
app.config["DATABASE"] = DATABASE
app.config["MIN_PASSWORD_LENGTH"] = 6
app.config["PASSWORD_HASH_METHOD"] = "pbkdf2:sha256"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_db(query, params=(), one=False, commit=False):
    db = get_db()
    cursor = db.execute(query, params)
    if commit:
        db.commit()
        return cursor
    rows = cursor.fetchall()
    return (rows[0] if rows else None) if one else rows


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'user')),
            last_login TEXT
        );

        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            vehicle_number TEXT NOT NULL UNIQUE,
            owner_name TEXT NOT NULL,
            vehicle_type TEXT NOT NULL CHECK(vehicle_type IN ('Car', 'Bike')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_number TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL CHECK(status IN ('Available', 'Occupied')) DEFAULT 'Available',
            slot_type TEXT NOT NULL CHECK(slot_type IN ('Car', 'Bike'))
        );

        CREATE TABLE IF NOT EXISTS parking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            slot_id INTEGER NOT NULL,
            entry_time TEXT NOT NULL,
            exit_time TEXT,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id),
            FOREIGN KEY (slot_id) REFERENCES slots(id)
        );
        """
    )

    admin = db.execute("SELECT id FROM users WHERE username = ?", ("admin",)).fetchone()
    if admin is None:
        db.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (
                "admin",
                generate_password_hash(
                    "admin123", method=app.config["PASSWORD_HASH_METHOD"]
                ),
                "admin",
            ),
        )
        db.commit()
        admin = db.execute("SELECT id FROM users WHERE username = ?", ("admin",)).fetchone()

    migrate_user_login_tracking(db)
    migrate_vehicle_ownership(db, admin["id"])


def migrate_user_login_tracking(db):
    columns = db.execute("PRAGMA table_info(users)").fetchall()
    column_names = {column["name"] for column in columns}
    if "last_login" not in column_names:
        db.execute("ALTER TABLE users ADD COLUMN last_login TEXT")
        db.commit()


def migrate_vehicle_ownership(db, admin_id):
    columns = db.execute("PRAGMA table_info(vehicles)").fetchall()
    column_names = {column["name"] for column in columns}
    if "user_id" not in column_names:
        db.execute("ALTER TABLE vehicles ADD COLUMN user_id INTEGER")

    db.execute(
        """
        UPDATE vehicles
        SET user_id = (
            SELECT users.id
            FROM users
            WHERE LOWER(users.username) = LOWER(vehicles.owner_name)
            LIMIT 1
        )
        WHERE user_id IS NULL
          AND EXISTS (
            SELECT 1
            FROM users
            WHERE LOWER(users.username) = LOWER(vehicles.owner_name)
          )
        """
    )
    db.execute("UPDATE vehicles SET user_id = ? WHERE user_id IS NULL", (admin_id,))
    db.commit()


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if session.get("user_id") is None:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(**kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if session.get("user_id") is None:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("You do not have permission to access that page.", "error")
            return redirect(url_for("dashboard"))
        return view(**kwargs)

    return wrapped_view


@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        g.user = query_db("SELECT id, username, role FROM users WHERE id = ?", (user_id,), one=True)


@app.context_processor
def inject_now():
    return {"current_year": datetime.now().year}


def fetch_dashboard_stats():
    vehicle_filter = ""
    vehicle_params = ()
    if session.get("role") != "admin":
        vehicle_filter = " WHERE user_id = ?"
        vehicle_params = (session["user_id"],)

    total_vehicles = query_db(
        f"SELECT COUNT(*) AS count FROM vehicles{vehicle_filter}", vehicle_params, one=True
    )["count"]
    total_slots = query_db("SELECT COUNT(*) AS count FROM slots", one=True)["count"]
    available_slots = query_db(
        "SELECT COUNT(*) AS count FROM slots WHERE status = 'Available'", one=True
    )["count"]
    occupied_slots = query_db(
        "SELECT COUNT(*) AS count FROM slots WHERE status = 'Occupied'", one=True
    )["count"]
    active_parking = query_db(
        """
        SELECT parking.id, vehicles.vehicle_number, vehicles.owner_name, vehicles.vehicle_type,
               slots.slot_number, slots.slot_type, parking.entry_time
        FROM parking
        JOIN vehicles ON parking.vehicle_id = vehicles.id
        JOIN slots ON parking.slot_id = slots.id
        WHERE parking.exit_time IS NULL
          AND (? = 'admin' OR vehicles.user_id = ?)
        ORDER BY parking.entry_time DESC
        """,
        (session.get("role"), session.get("user_id")),
    )
    recent_history = query_db(
        """
        SELECT vehicles.vehicle_number, vehicles.owner_name, vehicles.vehicle_type,
               slots.slot_number, parking.entry_time, parking.exit_time
        FROM parking
        JOIN vehicles ON parking.vehicle_id = vehicles.id
        JOIN slots ON parking.slot_id = slots.id
        WHERE (? = 'admin' OR vehicles.user_id = ?)
        ORDER BY COALESCE(parking.exit_time, parking.entry_time) DESC
        LIMIT 5
        """,
        (session.get("role"), session.get("user_id")),
    )
    return {
        "total_vehicles": total_vehicles,
        "total_slots": total_slots,
        "available_slots": available_slots,
        "occupied_slots": occupied_slots,
        "active_parking": active_parking,
        "recent_history": recent_history,
    }


@app.route("/")
def index():
    if g.user:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = "user"

        error = None
        if not username:
            error = "Username is required."
        elif username.lower() == "admin":
            error = "The username admin is reserved."
        elif len(password) < app.config["MIN_PASSWORD_LENGTH"]:
            error = (
                f"Password must be at least {app.config['MIN_PASSWORD_LENGTH']} characters long."
            )
        elif query_db("SELECT id FROM users WHERE username = ?", (username,), one=True):
            error = "That username is already taken."

        if error:
            flash(error, "error")
        else:
            query_db(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (
                    username,
                    generate_password_hash(
                        password, method=app.config["PASSWORD_HASH_METHOD"]
                    ),
                    role,
                ),
                commit=True,
            )
            flash("Registration successful. Please log in.", "success")
            return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = query_db("SELECT * FROM users WHERE username = ?", (username,), one=True)

        if user is None or not check_password_hash(user["password"], password):
            flash("Invalid username or password.", "error")
        else:
            login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            query_db(
                "UPDATE users SET last_login = ? WHERE id = ?",
                (login_time, user["id"]),
                commit=True,
            )
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash(f"Welcome back, {user['username']}.", "success")
            return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/admin/users")
@admin_required
def admin_users():
    users = query_db(
        """
        SELECT username, role, last_login
        FROM users
        ORDER BY
            CASE WHEN role = 'admin' THEN 0 ELSE 1 END,
            username ASC
        """
    )
    return render_template("users.html", users=users)


@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    stats = fetch_dashboard_stats()
    return render_template("dashboard.html", stats=stats)


@app.route("/vehicles", methods=("GET", "POST"))
@login_required
def vehicles():
    if request.method == "POST":
        vehicle_number = request.form.get("vehicle_number", "").strip().upper()
        owner_name = request.form.get("owner_name", "").strip()
        vehicle_type = request.form.get("vehicle_type", "").strip()

        error = None
        if not vehicle_number or not owner_name:
            error = "Vehicle number and owner name are required."
        elif vehicle_type not in {"Car", "Bike"}:
            error = "Please select a valid vehicle type."
        elif query_db(
            "SELECT id FROM vehicles WHERE vehicle_number = ?", (vehicle_number,), one=True
        ):
            error = "This vehicle number is already registered."

        if error:
            flash(error, "error")
        else:
            query_db(
                """
                INSERT INTO vehicles (user_id, vehicle_number, owner_name, vehicle_type)
                VALUES (?, ?, ?, ?)
                """,
                (session["user_id"], vehicle_number, owner_name, vehicle_type),
                commit=True,
            )
            flash("Vehicle registered successfully.", "success")
            return redirect(url_for("vehicles"))

    if session.get("role") == "admin":
        vehicle_rows = query_db(
            """
            SELECT vehicles.*, users.username AS account_username
            FROM vehicles
            LEFT JOIN users ON vehicles.user_id = users.id
            ORDER BY vehicles.id DESC
            """
        )
    else:
        vehicle_rows = query_db(
            """
            SELECT vehicles.*, users.username AS account_username
            FROM vehicles
            LEFT JOIN users ON vehicles.user_id = users.id
            WHERE vehicles.user_id = ?
            ORDER BY vehicles.id DESC
            """,
            (session["user_id"],),
        )
    active_vehicle_ids = {
        row["vehicle_id"]
        for row in query_db("SELECT vehicle_id FROM parking WHERE exit_time IS NULL")
    }
    return render_template(
        "vehicles.html", vehicles=vehicle_rows, active_vehicle_ids=active_vehicle_ids
    )


@app.route("/vehicles/<int:vehicle_id>/delete", methods=("POST",))
@admin_required
def delete_vehicle(vehicle_id):
    vehicle = query_db("SELECT id FROM vehicles WHERE id = ?", (vehicle_id,), one=True)
    if vehicle is None:
        flash("Vehicle not found.", "error")
        return redirect(url_for("vehicles"))

    active_parking = query_db(
        "SELECT id FROM parking WHERE vehicle_id = ? AND exit_time IS NULL",
        (vehicle_id,),
        one=True,
    )
    if active_parking:
        flash("Cannot delete a vehicle while it is parked.", "error")
        return redirect(url_for("vehicles"))

    query_db("DELETE FROM vehicles WHERE id = ?", (vehicle_id,), commit=True)
    flash("Vehicle deleted successfully.", "success")
    return redirect(url_for("vehicles"))


@app.route("/slots", methods=("GET", "POST"))
@login_required
def slots():
    if request.method == "POST":
        if session.get("role") != "admin":
            flash("Only admins can add parking slots.", "error")
            return redirect(url_for("slots"))

        slot_number = request.form.get("slot_number", "").strip().upper()
        slot_type = request.form.get("slot_type", "").strip()

        error = None
        if not slot_number:
            error = "Slot number is required."
        elif slot_type not in {"Car", "Bike"}:
            error = "Please select a valid slot type."
        elif query_db("SELECT id FROM slots WHERE slot_number = ?", (slot_number,), one=True):
            error = "That slot number already exists."

        if error:
            flash(error, "error")
        else:
            query_db(
                "INSERT INTO slots (slot_number, status, slot_type) VALUES (?, 'Available', ?)",
                (slot_number, slot_type),
                commit=True,
            )
            flash("Parking slot added successfully.", "success")
            return redirect(url_for("slots"))

    slot_rows = query_db("SELECT * FROM slots ORDER BY slot_number ASC")
    return render_template("slots.html", slots=slot_rows)


@app.route("/slots/<int:slot_id>/delete", methods=("POST",))
@admin_required
def delete_slot(slot_id):
    slot = query_db("SELECT * FROM slots WHERE id = ?", (slot_id,), one=True)
    if slot is None:
        flash("Slot not found.", "error")
        return redirect(url_for("slots"))
    if slot["status"] == "Occupied":
        flash("Cannot delete an occupied slot.", "error")
        return redirect(url_for("slots"))

    query_db("DELETE FROM slots WHERE id = ?", (slot_id,), commit=True)
    flash("Parking slot deleted successfully.", "success")
    return redirect(url_for("slots"))


@app.route("/allocation", methods=("GET", "POST"))
@login_required
def allocation():
    if request.method == "POST":
        vehicle_id = request.form.get("vehicle_id", type=int)
        slot_id = request.form.get("slot_id", type=int)

        vehicle = query_db(
            """
            SELECT *
            FROM vehicles
            WHERE id = ?
              AND (? = 'admin' OR user_id = ?)
            """,
            (vehicle_id, session.get("role"), session.get("user_id")),
            one=True,
        )
        slot = query_db("SELECT * FROM slots WHERE id = ?", (slot_id,), one=True)
        active_vehicle = query_db(
            "SELECT id FROM parking WHERE vehicle_id = ? AND exit_time IS NULL",
            (vehicle_id,),
            one=True,
        )
        active_slot = query_db(
            "SELECT id FROM parking WHERE slot_id = ? AND exit_time IS NULL",
            (slot_id,),
            one=True,
        )

        error = None
        if vehicle is None or slot is None:
            error = "Please select a valid vehicle and slot."
        elif active_vehicle:
            error = "This vehicle is already parked."
        elif active_slot or slot["status"] == "Occupied":
            error = "This slot is already occupied."
        elif vehicle["vehicle_type"] != slot["slot_type"]:
            error = "Vehicle type and slot type must match."

        if error:
            flash(error, "error")
        else:
            query_db(
                """
                INSERT INTO parking (vehicle_id, slot_id, entry_time, exit_time)
                VALUES (?, ?, ?, NULL)
                """,
                (vehicle_id, slot_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                commit=True,
            )
            query_db(
                "UPDATE slots SET status = 'Occupied' WHERE id = ?",
                (slot_id,),
                commit=True,
            )
            flash("Slot allocated successfully.", "success")
            return redirect(url_for("allocation"))

    available_vehicles = query_db(
        """
        SELECT *
        FROM vehicles
        WHERE id NOT IN (
            SELECT vehicle_id FROM parking WHERE exit_time IS NULL
        )
        AND (? = 'admin' OR user_id = ?)
        ORDER BY vehicle_number ASC
        """,
        (session.get("role"), session.get("user_id")),
    )
    available_slots = query_db(
        "SELECT * FROM slots WHERE status = 'Available' ORDER BY slot_number ASC"
    )
    active_allocations = query_db(
        """
        SELECT parking.id, vehicles.vehicle_number, vehicles.owner_name, vehicles.vehicle_type,
               slots.slot_number, slots.slot_type, parking.entry_time
        FROM parking
        JOIN vehicles ON parking.vehicle_id = vehicles.id
        JOIN slots ON parking.slot_id = slots.id
        WHERE parking.exit_time IS NULL
          AND (? = 'admin' OR vehicles.user_id = ?)
        ORDER BY parking.entry_time DESC
        """,
        (session.get("role"), session.get("user_id")),
    )
    return render_template(
        "allocation.html",
        vehicles=available_vehicles,
        slots=available_slots,
        active_allocations=active_allocations,
    )


@app.route("/parking/<int:parking_id>/exit", methods=("POST",))
@login_required
def record_exit(parking_id):
    parking_record = query_db(
        """
        SELECT parking.*
        FROM parking
        JOIN vehicles ON parking.vehicle_id = vehicles.id
        WHERE parking.id = ?
          AND parking.exit_time IS NULL
          AND (? = 'admin' OR vehicles.user_id = ?)
        """,
        (parking_id, session.get("role"), session.get("user_id")),
        one=True,
    )
    if parking_record is None:
        flash("Active parking record not found.", "error")
        return redirect(url_for("allocation"))

    exit_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    query_db(
        "UPDATE parking SET exit_time = ? WHERE id = ?",
        (exit_time, parking_id),
        commit=True,
    )
    query_db(
        "UPDATE slots SET status = 'Available' WHERE id = ?",
        (parking_record["slot_id"],),
        commit=True,
    )
    flash("Vehicle exit recorded and slot is now available.", "success")
    return redirect(url_for("allocation"))


@app.route("/history")
@login_required
def history():
    history_rows = query_db(
        """
        SELECT vehicles.vehicle_number, vehicles.owner_name, vehicles.vehicle_type,
               slots.slot_number, slots.slot_type, parking.entry_time, parking.exit_time
        FROM parking
        JOIN vehicles ON parking.vehicle_id = vehicles.id
        JOIN slots ON parking.slot_id = slots.id
        WHERE (? = 'admin' OR vehicles.user_id = ?)
        ORDER BY COALESCE(parking.exit_time, parking.entry_time) DESC
        """,
        (session.get("role"), session.get("user_id")),
    )
    return render_template("history.html", history=history_rows)


with app.app_context():
    init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
