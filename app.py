from flask import Flask, render_template, request, redirect, session
from supabase import create_client
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
from functools import wraps

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY")

if not app.secret_key:
    raise Exception("SECRET_KEY is missing in environment variables")

# ==================================================
# SUPABASE CONNECTION
# ==================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL:
    raise Exception("SUPABASE_URL is missing")

if not SUPABASE_KEY:
    raise Exception("SUPABASE_KEY is missing")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==================================================
# ADMIN SETTINGS
# Set these in Render Environment Variables
# ADMIN_USERNAME
# ADMIN_PASSWORD
# ==================================================

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")


# ==================================================
# LOGIN
# ==================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # ADMIN LOGIN
        if (
            ADMIN_USERNAME
            and ADMIN_PASSWORD
            and username == ADMIN_USERNAME
            and password == ADMIN_PASSWORD
        ):
            session.clear()
            session["user"] = username
            session["role"] = "admin"
            return redirect("/")

        # NORMAL USER LOGIN
        try:
            result = (
                supabase.table("users")
                .select("*")
                .eq("username", username)
                .execute()
            )

            if result.data:
                user_data = result.data[0]
                stored_password = user_data.get("password", "")

                password_valid = False

                # Support hashed passwords and existing plain-text passwords
                try:
                    password_valid = check_password_hash(
                        stored_password, password
                    )
                except (ValueError, TypeError):
                    password_valid = False

                if not password_valid:
                    password_valid = stored_password == password

                if password_valid:
                    session.clear()
                    session["user"] = user_data["username"]
                    session["role"] = user_data.get("role", "user")
                    return redirect("/")

            return render_template(
                "login.html",
                error="Invalid username or password"
            )

        except Exception as e:
            print("LOGIN ERROR:", str(e))
            return render_template(
                "login.html",
                error="Database connection error"
            )

    return render_template("login.html")


# ==================================================
# ADMIN REQUIRED
# ==================================================

def admin_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "user" not in session:
            return redirect("/login")

        if session.get("role") != "admin":
            return redirect("/")

        return function(*args, **kwargs)

    return wrapper


# ==================================================
# LOGOUT
# ==================================================

@app.route("/logout")
def logout():

    session.clear()
    return redirect("/login")


# ==================================================
# ADMIN DASHBOARD
# ==================================================

@app.route("/admin")
@admin_required
def admin_dashboard():

    try:
        result = (
            supabase.table("users")
            .select("id, username, role")
            .order("id", desc=True)
            .execute()
        )

        users = result.data or []

    except Exception as e:
        print("ADMIN ERROR:", str(e))
        users = []

    return render_template(
        "admin.html",
        users=users
    )


# ==================================================
# CREATE USER - ADMIN ONLY
# ==================================================

@app.route("/admin/create-user", methods=["GET", "POST"])
@admin_required
def create_user():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "user").strip().lower()

        if not username or not password:
            return render_template(
                "create_user.html",
                error="Username and password are required"
            )

        if role not in ("admin", "user"):
            role = "user"

        if len(password) < 8:
            return render_template(
                "create_user.html",
                error="Password must contain at least 8 characters"
            )

        try:
            existing = (
                supabase.table("users")
                .select("id")
                .eq("username", username)
                .execute()
            )

            if existing.data:
                return render_template(
                    "create_user.html",
                    error="Username already exists"
                )

            supabase.table("users").insert({
                "username": username,
                "password": generate_password_hash(password),
                "role": role
            }).execute()

            return redirect("/admin")

        except Exception as e:
            print("CREATE USER ERROR:", str(e))
            return render_template(
                "create_user.html",
                error="Unable to create user. Check database columns."
            )

    return render_template("create_user.html")


# ==================================================
# DELETE USER - ADMIN ONLY
# ==================================================

@app.route("/admin/delete-user/<int:user_id>", methods=["POST"])
@admin_required
def delete_user(user_id):

    try:
        result = (
            supabase.table("users")
            .select("id, username, role")
            .eq("id", user_id)
            .execute()
        )

        if result.data:
            target_user = result.data[0]

            if target_user.get("username") != ADMIN_USERNAME:
                if target_user.get("username") != session.get("user"):
                    supabase.table("users").delete().eq(
                        "id", user_id
                    ).execute()

    except Exception as e:
        print("DELETE USER ERROR:", str(e))

    return redirect("/admin")


# ==================================================
# DASHBOARD
# ==================================================

@app.route("/")
def index():

    if "user" not in session:
        return redirect("/login")

    try:
        products_result = (
            supabase.table("products")
            .select("*")
            .execute()
        )

        sales_result = (
            supabase.table("sales")
            .select("*")
            .execute()
        )

        products = products_result.data or []
        sales = sales_result.data or []

        total_products = len(products)

        total_stock = sum(
            int(p.get("quantity") or 0)
            for p in products
        )

        total_sales = sum(
            float(s.get("total") or 0)
            for s in sales
        )

        low_stock = sum(
            1 for p in products
            if int(p.get("quantity") or 0) <= 5
        )

    except Exception as e:
        print("DASHBOARD ERROR:", str(e))
        total_products = 0
        total_stock = 0
        total_sales = 0
        low_stock = 0

    return render_template(
        "index.html",
        total_products=total_products,
        total_stock=total_stock,
        total_sales=total_sales,
        low_stock=low_stock
    )


# ==================================================
# INVENTORY
# ==================================================

@app.route("/inventory")
def inventory():

    if "user" not in session:
        return redirect("/login")

    try:
        result = (
            supabase.table("products")
            .select("*")
            .order("id", desc=True)
            .execute()
        )

        products = result.data or []

    except Exception as e:
        print("INVENTORY ERROR:", str(e))
        products = []

    return render_template(
        "inventory.html",
        products=products
    )


# ==================================================
# ADD PRODUCT
# ==================================================

@app.route("/products", methods=["GET", "POST"])
def products():

    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        quantity_text = request.form.get("quantity", "0")
        price_text = request.form.get("price", "0")

        if not name:
            return render_template(
                "add product.html",
                error="Product name is required"
            )

        try:
            quantity = int(quantity_text)
            price = float(price_text)

            if quantity < 0 or price < 0:
                raise ValueError

        except ValueError:
            return render_template(
                "add product.html",
                error="Enter a valid quantity and price"
            )

        try:
            supabase.table("products").insert({
                "name": name,
                "category": category,
                "quantity": quantity,
                "price": price,
                "created_at": datetime.now().isoformat()
            }).execute()

            return redirect("/inventory")

        except Exception as e:
            print("ADD PRODUCT ERROR:", str(e))
            return render_template(
                "add product.html",
                error="Unable to save product"
            )

    return render_template("add product.html")


# ==================================================
# SALES
# ==================================================

@app.route("/sales", methods=["GET", "POST"])
def sales():

    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":

        try:
            product_id = int(request.form.get("product_id"))
            quantity = int(request.form.get("quantity"))

            if quantity <= 0:
                return redirect("/sales")

            product_result = (
                supabase.table("products")
                .select("*")
                .eq("id", product_id)
                .execute()
            )

            if not product_result.data:
                return redirect("/sales")

            product = product_result.data[0]
            current_quantity = int(product.get("quantity") or 0)
            price = float(product.get("price") or 0)

            if quantity <= current_quantity:

                total = quantity * price

                supabase.table("sales").insert({
                    "product_name": product["name"],
                    "quantity": quantity,
                    "total": total,
                    "sale_date": datetime.now().isoformat()
                }).execute()

                supabase.table("products").update({
                    "quantity": current_quantity - quantity
                }).eq("id", product_id).execute()

        except Exception as e:
            print("SALES ERROR:", str(e))

        return redirect("/sales")

    try:
        products_result = (
            supabase.table("products")
            .select("*")
            .order("name")
            .execute()
        )

        products_list = products_result.data or []

    except Exception as e:
        print("PRODUCT LIST ERROR:", str(e))
        products_list = []

    try:
        sales_result = (
            supabase.table("sales")
            .select("*")
            .order("id", desc=True)
            .execute()
        )

        sales_data = sales_result.data or []

    except Exception as e:
        print("SALES LIST ERROR:", str(e))
        sales_data = []

    return render_template(
        "sales.html",
        products=products_list,
        sales=sales_data
    )


# ==================================================
# USER PROFILE
# ==================================================

@app.route("/user")
def user():

    if "user" not in session:
        return redirect("/login")

    return render_template(
        "user.html",
        username=session.get("user"),
        role=session.get("role", "user")
    )


# ==================================================
# SETTINGS
# ==================================================

@app.route("/settings")
def settings():

    if "user" not in session:
        return redirect("/login")

    return render_template(
        "setting.html",
        username=session.get("user")
    )


# ==================================================
# HEALTH CHECK
# ==================================================

@app.route("/health")
def health():

    return {
        "status": "ok",
        "database": "Supabase",
        "supabase_url_loaded": bool(SUPABASE_URL),
        "supabase_key_loaded": bool(SUPABASE_KEY)
    }


# ==================================================
# START APPLICATION
# ==================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )