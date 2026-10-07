from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)

# ==================================================
# SECRET KEY
# ==================================================

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "inventory_secret_123"
)


# ==================================================
# DATABASE PATH
# ==================================================

# Render Persistent Disk:
# Set DATABASE_DIR=/data in Render Environment Variables
#
# Local computer:
# project folder/database/inventory.db
#
# If DATABASE_DIR is not available,
# use local database folder.

DATABASE_DIR = os.environ.get(
    "DATABASE_DIR",
    os.path.join(os.getcwd(), "database")
)

os.makedirs(DATABASE_DIR, exist_ok=True)

DB_PATH = os.path.join(
    DATABASE_DIR,
    "inventory.db"
)


# ==================================================
# DATABASE CONNECTION
# ==================================================

def get_db():

    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    return conn


# ==================================================
# CREATE DATABASE
# ==================================================

def create_database():

    conn = get_db()

    cursor = conn.cursor()

    # USERS TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # PRODUCTS TABLE
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

    # SALES TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT,
            quantity INTEGER,
            total REAL,
            sale_date TEXT
        )
    """)

    # ==================================================
    # DEFAULT USER
    # ==================================================

    user = cursor.execute(
        """
        SELECT *
        FROM users
        WHERE username=?
        """,
        ("Ajith",)
    ).fetchone()

    if user is None:

        cursor.execute(
            """
            INSERT INTO users
            (username, password)
            VALUES (?, ?)
            """,
            ("Ajith", "ak")
        )

    conn.commit()

    conn.close()


# ==================================================
# LOGIN
# ==================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        conn = get_db()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE username=?
            AND password=?
            """,
            (
                username,
                password
            )
        ).fetchone()

        conn.close()

        if user:

            session.clear()

            session["user"] = user["username"]

            return redirect("/")

        return render_template(
            "login.html",
            error="Invalid username or password"
        )

    return render_template("login.html")


# ==================================================
# LOGOUT
# ==================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# ==================================================
# DASHBOARD
# ==================================================

@app.route("/")
def index():

    if "user" not in session:

        return redirect("/login")

    conn = get_db()

    total_products = conn.execute(
        """
        SELECT COUNT(*)
        FROM products
        """
    ).fetchone()[0]

    total_stock = conn.execute(
        """
        SELECT COALESCE(SUM(quantity), 0)
        FROM products
        """
    ).fetchone()[0]

    total_sales = conn.execute(
        """
        SELECT COALESCE(SUM(total), 0)
        FROM sales
        """
    ).fetchone()[0]

    low_stock = conn.execute(
        """
        SELECT COUNT(*)
        FROM products
        WHERE quantity <= 5
        """
    ).fetchone()[0]

    conn.close()

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

    conn = get_db()

    products = conn.execute(
        """
        SELECT *
        FROM products
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

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

        name = request.form.get(
            "name",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        quantity_text = request.form.get(
            "quantity",
            "0"
        )

        price_text = request.form.get(
            "price",
            "0"
        )

        # ------------------------------
        # VALIDATION
        # ------------------------------

        if not name:

            return render_template(
                "add product.html",
                error="Product name is required"
            )

        try:

            quantity = int(
                quantity_text
            )

            price = float(
                price_text
            )

        except ValueError:

            return render_template(
                "add product.html",
                error="Please enter valid quantity and price"
            )

        if quantity < 0:

            quantity = 0

        if price < 0:

            price = 0

        conn = get_db()

        conn.execute(
            """
            INSERT INTO products
            (
                name,
                category,
                quantity,
                price,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                name,
                category,
                quantity,
                price,
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )
        )

        conn.commit()

        conn.close()

        return redirect("/inventory")

    return render_template(
        "add product.html"
    )


# ==================================================
# SALES
# ==================================================

@app.route("/sales", methods=["GET", "POST"])
def sales():

    if "user" not in session:

        return redirect("/login")

    conn = get_db()

    # ==================================================
    # ADD SALE
    # ==================================================

    if request.method == "POST":

        try:

            product_id = int(
                request.form.get(
                    "product_id"
                )
            )

            quantity = int(
                request.form.get(
                    "quantity"
                )
            )

        except (ValueError, TypeError):

            conn.close()

            return redirect("/sales")

        product = conn.execute(
            """
            SELECT *
            FROM products
            WHERE id=?
            """,
            (product_id,)
        ).fetchone()

        if (
            product
            and quantity > 0
            and quantity <= product["quantity"]
        ):

            total = (
                quantity
                * product["price"]
            )

            conn.execute(
                """
                INSERT INTO sales
                (
                    product_name,
                    quantity,
                    total,
                    sale_date
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    product["name"],
                    quantity,
                    total,
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                )
            )

            conn.execute(
                """
                UPDATE products
                SET quantity = quantity - ?
                WHERE id=?
                """,
                (
                    quantity,
                    product_id
                )
            )

            conn.commit()

        conn.close()

        return redirect("/sales")

    # ==================================================
    # GET PRODUCTS
    # ==================================================

    products_list = conn.execute(
        """
        SELECT *
        FROM products
        ORDER BY name
        """
    ).fetchall()

    # ==================================================
    # GET SALES
    # ==================================================

    sales_data = conn.execute(
        """
        SELECT *
        FROM sales
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "sales.html",
        products=products_list,
        sales=sales_data
    )


# ==================================================
# USER
# ==================================================

@app.route("/user")
def user():

    if "user" not in session:

        return redirect("/login")

    username = session.get(
        "user"
    )

    return render_template(
        "user.html",
        username=username
    )


# ==================================================
# SETTINGS
# ==================================================

@app.route("/settings")
def settings():

    if "user" not in session:

        return redirect("/login")

    # FIXED:
    # Previously session.get("setting")
    # was incorrect.

    username = session.get(
        "user"
    )

    return render_template(
        "setting.html",
        username=username
    )


# ==================================================
# HEALTH CHECK
# ==================================================

@app.route("/health")
def health():

    return {
        "status": "ok",
        "database": DB_PATH
    }


# ==================================================
# CREATE DATABASE
# ==================================================

create_database()


# ==================================================
# START APPLICATION
# ==================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        )
    )
