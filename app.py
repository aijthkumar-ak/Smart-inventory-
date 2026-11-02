import os
import requests

from datetime import datetime, timezone
from functools import wraps

from flask import (
    Flask, request, jsonify, session,
    render_template, redirect, url_for, flash
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from supabase import create_client


# ==================================================
# 1. FLASK CONFIGURATION
# ==================================================

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("SECRET_KEY missing in Render")


# ==================================================
# 2. SUPABASE CONFIGURATION
# ==================================================

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase credentials missing")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# ==================================================
# 3. GEMINI CONFIGURATION
# ==================================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL",
    "gemini-2.5-flash"
)


def ask_gemini(question, history=None):

    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY missing")

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{GEMINI_MODEL}:generateContent"
        f"?key={GEMINI_API_KEY}"
    )

    contents = []

    if history:

        for item in history:

            role = (
                "model"
                if item.get("role") == "assistant"
                else "user"
            )

            contents.append({
                "role": role,
                "parts": [{
                    "text": str(item.get("content", ""))
                }]
            })

    contents.append({
        "role": "user",
        "parts": [{"text": question}]
    })

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048
        }
    }

    response = requests.post(
        url,
        json=payload,
        timeout=60
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Gemini API Error: {response.text}"
        )

    data = response.json()

    candidates = data.get("candidates", [])

    if not candidates:
        raise RuntimeError("Gemini returned no answer")

    parts = candidates[0].get(
        "content", {}
    ).get("parts", [])

    answer = " ".join(
        part.get("text", "")
        for part in parts
        if part.get("text")
    ).strip()

    if not answer:
        raise RuntimeError("Gemini response is empty")

    return answer


# ==================================================
# 4. LOGIN DECORATOR
# ==================================================

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if not session.get("user_id"):
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


def current_user_id():
    return str(session.get("user_id"))


# ==================================================
# 5. MEMORY FUNCTIONS
# ==================================================

def save_memory(role, content):

    supabase.table("memories").insert({

        "user_id": current_user_id(),

        "role": role,

        "content": content,

        "created_at": datetime.now(
            timezone.utc
        ).isoformat()

    }).execute()


def get_chat_history(limit=20):

    result = (
        supabase.table("memories")
        .select("*")
        .eq("user_id", current_user_id())
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    messages = result.data or []

    messages.reverse()

    return messages


# ==================================================
# 6. REGISTER
# ==================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        if not username or not password:
            flash("Enter username and password")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must contain at least 6 characters")
            return render_template("register.html")

        try:

            existing = (
                supabase.table("users")
                .select("id")
                .eq("username", username)
                .limit(1)
                .execute()
            )

            if existing.data:
                flash("Username already exists")
                return render_template("register.html")

            result = supabase.table("users").insert({

                "username": username,

                "password": generate_password_hash(password)

            }).execute()

            if not result.data:
                raise RuntimeError("Registration failed")

            flash("Registration successful")

            return redirect(url_for("login"))

        except Exception as error:

            print("REGISTER ERROR:", error)

            flash("Registration failed. Check database setup.")

    return render_template("register.html")


# ==================================================
# 7. LOGIN
# ==================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        try:

            result = (
                supabase.table("users")
                .select("*")
                .eq("username", username)
                .limit(1)
                .execute()
            )

            users = result.data or []

            if not users:
                flash("Invalid username or password")
                return render_template("login.html")

            user = users[0]

            stored_password = user.get("password", "")

            try:

                valid = check_password_hash(
                    stored_password,
                    password
                )

            except Exception:

                valid = stored_password == password

            if valid or stored_password == password:

                session.clear()

                session["user_id"] = str(user["id"])

                session["username"] = username

                return redirect(url_for("dashboard"))

            flash("Invalid username or password")

        except Exception as error:

            print("LOGIN ERROR:", error)

            flash("Login failed. Check Supabase setup.")

    return render_template("login.html")


# ==================================================
# 8. LOGOUT
# ==================================================

@app.route("/logout", methods=["GET", "POST"])
@login_required
def logout():

    session.clear()

    return redirect(url_for("login"))


# ==================================================
# 9. MAIN AI DASHBOARD
# ==================================================

@app.route("/")
@login_required
def dashboard():

    return render_template(
        "index.html",
        username=session.get("username")
    )


# ==================================================
# 10. AI CHAT API
# ==================================================

@app.route("/api/chat", methods=["POST"])
@login_required
def ai_chat():

    try:

        data = request.get_json(silent=True) or {}

        question = data.get(
            "message", ""
        ).strip()

        if not question:

            return jsonify({
                "success": False,
                "error": "Please enter a message"
            }), 400

        history = get_chat_history(limit=10)

        answer = ask_gemini(
            question,
            history
        )

        save_memory("user", question)

        save_memory("assistant", answer)

        return jsonify({
            "success": True,
            "reply": answer
        })

    except Exception as error:

        print("AI CHAT ERROR:", error)

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ==================================================
# 11. CHAT HISTORY
# ==================================================

@app.route("/api/history")
@login_required
def chat_history():

    try:

        messages = get_chat_history(limit=100)

        return jsonify({
            "success": True,
            "messages": messages
        })

    except Exception as error:

        print("HISTORY ERROR:", error)

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ==================================================
# 12. CLEAR CHAT HISTORY
# ==================================================

@app.route("/api/history/clear", methods=["POST"])
@login_required
def clear_history():

    try:

        supabase.table("memories").delete().eq(
            "user_id",
            current_user_id()
        ).execute()

        return jsonify({
            "success": True,
            "message": "Chat history cleared"
        })

    except Exception as error:

        print("CLEAR HISTORY ERROR:", error)

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ==================================================
# 13. CREATE REMINDER
# ==================================================

@app.route("/api/reminders", methods=["POST"])
@login_required
def create_reminder():

    try:

        data = request.get_json(silent=True) or {}

        title = data.get("title", "").strip()

        remind_at = data.get("remind_at", "").strip()

        if not title or not remind_at:

            return jsonify({
                "success": False,
                "error": "Title and date/time required"
            }), 400

        supabase.table("reminders").insert({

            "user_id": current_user_id(),

            "title": title,

            "remind_at": remind_at,

            "completed": False,

            "created_at": datetime.now(
                timezone.utc
            ).isoformat()

        }).execute()

        return jsonify({
            "success": True,
            "message": "Reminder saved successfully"
        })

    except Exception as error:

        print("REMINDER ERROR:", error)

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ==================================================
# 14. GET REMINDERS
# ==================================================

@app.route("/api/reminders", methods=["GET"])
@login_required
def get_reminders():

    try:

        result = (
            supabase.table("reminders")
            .select("*")
            .eq("user_id", current_user_id())
            .order("remind_at")
            .execute()
        )

        return jsonify({
            "success": True,
            "reminders": result.data or []
        })

    except Exception as error:

        print("GET REMINDERS ERROR:", error)

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ==================================================
# 15. DELETE REMINDER
# ==================================================

@app.route("/api/reminders/<reminder_id>", methods=["DELETE"])
@login_required
def delete_reminder(reminder_id):

    try:

        supabase.table("reminders").delete().eq(
            "id",
            reminder_id
        ).eq(
            "user_id",
            current_user_id()
        ).execute()

        return jsonify({
            "success": True,
            "message": "Reminder deleted"
        })

    except Exception as error:

        print("DELETE REMINDER ERROR:", error)

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ==================================================
# 16. USER PROFILE
# ==================================================

@app.route("/user")
@login_required
def user():

    return jsonify({
        "username": session.get("username"),
        "user_id": current_user_id()
    })


# ==================================================
# 17. SETTINGS
# ==================================================

@app.route("/settings")
@login_required
def settings():

    return render_template(
        "setting.html",
        username=session.get("username")
    )


# ==================================================
# 18. HEALTH CHECK
# ==================================================

@app.route("/health")
def health():

    return jsonify({

        "status": "healthy",

        "app": "AI Digital Brain",

        "gemini_configured": bool(GEMINI_API_KEY),

        "supabase_configured": True

    })


# ==================================================
# 19. RUN APPLICATION
# ==================================================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )