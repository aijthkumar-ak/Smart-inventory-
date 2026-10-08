from flask import Flask, render_template, request, redirect, session
from supabase import create_client
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
# SUPABASE CONNECTION
# ==================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print("====================================")
print("SUPABASE CONNECTION CHECK")
print("SUPABASE_URL exists:", bool(SUPABASE_URL))
print("SUPABASE_KEY exists:", bool(SUPABASE_KEY))
print("====================================")

if not SUPABASE_URL:
    raise Exception("SUPABASE_URL is missing in Render Environment Variables")

if not SUPABASE_KEY:
    raise Exception("SUPABASE_KEY is missing in Render Environment Variables")

try:
    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )

    print("Supabase client created successfully")

except Exception as e:
    print("Supabase connection error:", str(e))
    raise


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

        try:

            result = (
                supabase
                .table("users")
                .select("*")
                .eq("username", username)
                .eq("password", password)
                .execute()
            )

            if result.data:

                session.clear()

                session["user"] = result.data[0]["username"]

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

    try:

        products_result = (
            supabase
            .table("products")
            .select("*")
            .execute()
        )

        sales_result = (
            supabase
            .table("sales")
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
            1
            for p in products
            if int(p.get("quantity") or 0) <= 5
        )

        return render_template(
            "index.html",
            total_products=total_products,
            total_stock=total_stock,
            total_sales=total_sales,
            low_stock=low_stock
        )

    except Exception as e:

        print("DASHBOARD ERROR:", str(e))

        return render_template(
            "index.html",
            total_products=0,
            total_stock=0,
            total_sales=0,
            low_stock=0
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
            supabase
            .table("products")
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

        if not name:

            return render_template(
                "add product.html",
                error="Product name is required"
            )

        try:

            quantity = int(quantity_text)
            price = float(price_text)

        except ValueError:

            return render_template(
                "add product.html",
                error="Please enter valid quantity and price"
            )

        if quantity < 0:
            quantity = 0

        if price < 0:
            price = 0

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

    if request.method == "POST":

        try:

            product_id = int(
                request.form.get("product_id")
            )

            quantity = int(
                request.form.get("quantity")
            )

        except (ValueError, TypeError):

            return redirect("/sales")

        try:

            product_result = (
                supabase
                .table("products")
                .select("*")
                .eq("id", product_id)
                .execute()
            )

            if not product_result.data:
                return redirect("/sales")

            product = product_result.data[0]

            current_quantity = int(
                product.get("quantity") or 0
            )

            price = float(
                product.get("price") or 0
            )

            if (
                quantity > 0
                and quantity <= current_quantity
            ):

                total = quantity * price

                # SAVE SALE

                supabase.table("sales").insert({
                    "product_name": product["name"],
                    "quantity": quantity,
                    "total": total,
                    "sale_date": datetime.now().isoformat()
                }).execute()

                # UPDATE STOCK

                supabase.table("products").update({
                    "quantity": current_quantity - quantity
                }).eq(
                    "id",
                    product_id
                ).execute()

        except Exception as e:

            print("SALES ERROR:", str(e))

        return redirect("/sales")

    # GET PRODUCTS

    try:

        products_result = (
            supabase
            .table("products")
            .select("*")
            .order("name")
            .execute()
        )

        products_list = products_result.data or []

    except Exception as e:

        print("PRODUCT LIST ERROR:", str(e))

        products_list = []

    # GET SALES

    try:

        sales_result = (
            supabase
            .table("sales")
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
# USER
# ==================================================

@app.route("/user")
def user():

    if "user" not in session:
        return redirect("/login")

    username = session.get("user")

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

    username = session.get("user")

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
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=False
    )
