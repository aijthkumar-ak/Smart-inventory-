from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)

# Vercel Environment Variable-ல் SECRET_KEY set செய்யலாம்
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "smart_inventory_secret_123"
)


# ---------------- DATABASE ----------------

def get_db():
    # Vercel-ல் /tmp மட்டுமே writable
    db_path = "/tmp/inventory.db"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def create_database():

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            quantity INTEGER DEFAULT 0,
            price REAL DEFAULT 0,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT,
            quantity INTEGER,
            total REAL,
            sale_date TEXT
        )
    """)

    # Default admin account
    user = cursor.execute(
        "SELECT * FROM users WHERE username=?",
        ("admin",)
    ).fetchone()

    if user is None:
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            ("admin", "admin123")
        )

    conn.commit()
    conn.close()


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db()

        user = conn.execute(
            """
            SELECT * FROM users
            WHERE username=? AND password=?
            """,
            (username, password)
        ).fetchone()

        conn.close()

        if user:
            session.clear()
            session["user"] = username
            return redirect("/")

        return render_template(
            "login.html",
            error="Invalid username or password"
        )

    return render_template("login.html")


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# ---------------- DASHBOARD ----------------

@app.route("/")
def index():

    if "user" not in session:
        return redirect("/login")

    conn = get_db()

    total_products = conn.execute(
        "SELECT COUNT(*) FROM products"
    ).fetchone()[0]

    total_stock = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM products"
    ).fetchone()[0]

    total_sales = conn.execute(
        "SELECT COALESCE(SUM(total), 0) FROM sales"
    ).fetchone()[0]

    low_stock = conn.execute(
        "SELECT COUNT(*) FROM products WHERE quantity <= 5"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "index.html",
        total_products=total_products,
        total_stock=total_stock,
        total_sales=total_sales,
        low_stock=low_stock
    )


# ---------------- INVENTORY ----------------

@app.route("/inventory")
def inventory():

    if "user" not in session:
        return redirect("/login")

    conn = get_db()

    products = conn.execute(
        "SELECT * FROM products ORDER BY id DESC"
    ).fetchall()

    conn.close()

    return render_template(
        "inventory.html",
        products=products
    )


# ---------------- ADD PRODUCT ----------------

@app.route("/products", methods=["GET", "POST"])
def products():

    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":

        name = request.form.get("name")
        category = request.form.get("category")
        quantity = request.form.get("quantity")
        price = request.form.get("price")

        if not quantity:
            quantity = 0

        if not price:
            price = 0

        conn = get_db()

        conn.execute(
            """
            INSERT INTO products
            (name, category, quantity, price, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                name,
                category,
                int(quantity),
                float(price),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        )

        conn.commit()
        conn.close()

        return redirect("/inventory")

    return render_template("add product.html")


# ---------------- SALES ----------------

@app.route("/sales", methods=["GET", "POST"])
def sales():

    if "user" not in session:
        return redirect("/login")

    conn = get_db()

    if request.method == "POST":

        product_id = request.form.get("product_id")
        quantity = int(request.form.get("quantity"))

        product = conn.execute(
            "SELECT * FROM products WHERE id=?",
            (product_id,)
        ).fetchone()

        if product and quantity > 0 and quantity <= product["quantity"]:

            total = quantity * product["price"]

            conn.execute(
                """
                INSERT INTO sales
                (product_name, quantity, total, sale_date)
                VALUES (?, ?, ?, ?)
                """,
                (
                    product["name"],
                    quantity,
                    total,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
            )

            conn.execute(
                """
                UPDATE products
                SET quantity = quantity - ?
                WHERE id=?
                """,
                (quantity, product_id)
            )

            conn.commit()

        conn.close()

        return redirect("/sales")

    products_list = conn.execute(
        "SELECT * FROM products ORDER BY name"
    ).fetchall()

    sales_data = conn.execute(
        "SELECT * FROM sales ORDER BY id DESC"
    ).fetchall()

    conn.close()

    return render_template(
        "sales.html",
        products=products_list,
        sales=sales_data
    )


# ---------------- START ----------------

create_database()
