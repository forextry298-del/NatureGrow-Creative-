import os
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-before-deploying")
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "naturegrow.db"))

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_error=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            interest TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please sign in to continue.", "info")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        interest = request.form.get("interest", "").strip()

        if not all([full_name, username, phone, email, password, interest]):
            flash("Please complete every field.", "error")
            return render_template("signup.html")
        if len(password) < 8:
            flash("Use a password with at least 8 characters.", "error")
            return render_template("signup.html")
        try:
            cur = db().execute(
                "INSERT INTO users (full_name, username, phone, email, password_hash, interest) VALUES (?, ?, ?, ?, ?, ?)",
                (full_name, username, phone, email, generate_password_hash(password), interest)
            )
            db().commit()
            session["user_id"] = cur.lastrowid
            session["full_name"] = full_name
            return redirect(url_for("dashboard"))
        except sqlite3.IntegrityError:
            flash("That username or email is already registered.", "error")
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = db().execute(
            "SELECT * FROM users WHERE lower(email)=? OR lower(username)=?",
            (identifier, identifier)
        ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["full_name"] = user["full_name"]
            return redirect(url_for("dashboard"))
        flash("The email/username or password is incorrect.", "error")
    return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    user = db().execute("SELECT full_name, username, email, phone, interest, created_at FROM users WHERE id=?",
                        (session["user_id"],)).fetchone()
    return render_template("dashboard.html", user=user)

@app.route("/logout")
def logout():
    session.clear()
    flash("You have signed out.", "info")
    return redirect(url_for("login"))

@app.route("/health")
def health():
    return {"status": "ok", "app": "NatureGrow Creative"}

with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
