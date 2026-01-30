from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from flask import redirect
from openpyxl import Workbook
from flask import send_file
import io
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash





app = Flask(__name__)

# DATABASE CONFIG
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///furniture.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(200))
    role = db.Column(db.String(20))  # ADMIN / MANAGER / WORKER
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    phone = db.Column(db.String(30))
    city = db.Column(db.String(50))

    orders = db.relationship("Order", backref="client", lazy=True)

# MODEL
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    width = db.Column(db.Float)
    height = db.Column(db.Float)
    material = db.Column(db.String(50))
    furniture_type = db.Column(db.String(50))
    price = db.Column(db.Float)


    status = db.Column(db.String(20), default="NEW")

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"))


# CREATE DATABASE
with app.app_context():
    db.drop_all()
    db.create_all()


# HOME PAGE
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form["username"]).first()
        if user and check_password_hash(user.password, request.form["password"]):
            login_user(user)
            return redirect("/dashboard")
    return render_template("login.html")

# CALCULATOR
@app.route("/calc")
def calc():
    name = request.args.get("name")
    phone = request.args.get("phone")
    city = request.args.get("city")

    width = float(request.args.get("width"))
    height = float(request.args.get("height"))
    furniture_type = request.args.get("type")
    material = request.args.get("material")

    prices = {
        "ldsp": 150,
        "mdf": 250,
        "wood": 400
    }

    type_coef = {
        "cabinet": 1.0,
        "wardrobe": 1.2,
        "kitchen": 1.5
    }

    price_per_m2 = prices[material]
    coef = type_coef[furniture_type]

    area = width * height
    price = area * price_per_m2 * coef

    # SAVE ORDER
    # 1. SAVE CLIENT
    client = Client(
        name=name,
        phone=phone,
        city=city
    )

    db.session.add(client)
    db.session.commit()  # 👈 ВАЖНО! тут появляется client.id

    # ПРОВЕРКА (можешь временно оставить)
    print("CLIENT ID:", client.id)

    # 2. SAVE ORDER
    order = Order(
        width=width,
        height=height,
        material=material,
        furniture_type=furniture_type,
        price=price,
        client_id=client.id
    )

    db.session.add(order)
    db.session.commit()

    return render_template("result.html",
                           furniture_type=furniture_type,
                           material=material,
                           area=area,
                           price=price)

# ADMIN CRM PAGE
@app.route("/orders")
@login_required
def orders():
    all_orders = Order.query.all()
    return render_template("orders.html", orders=all_orders)

@app.route("/order/<int:order_id>/status/<status>")
def change_status(order_id, status):
    order = Order.query.get_or_404(order_id)

    allowed_statuses = ["NEW", "IN_WORK", "PRODUCTION", "DONE"]
    if status not in allowed_statuses:
        return "Invalid status"

    order.status = status
    db.session.commit()

    return redirect("/orders")

@app.route("/dashboard")
def dashboard():
    total_orders = Order.query.count()
    total_revenue = db.session.query(db.func.sum(Order.price)).scalar() or 0

    new_count = Order.query.filter_by(status="NEW").count()
    in_work_count = Order.query.filter_by(status="IN_WORK").count()
    production_count = Order.query.filter_by(status="PRODUCTION").count()
    done_count = Order.query.filter_by(status="DONE").count()

    return render_template(
        "dashboard.html",
        total_orders=total_orders,
        total_revenue=total_revenue,
        new_count=new_count,
        in_work_count=in_work_count,
        production_count=production_count,
        done_count=done_count
    )

@app.route("/export")
def export_excel():
    wb = Workbook()
    ws = wb.active
    ws.title = "Orders"

    ws.append([
        "ID", "Client", "Phone", "City",
        "Type", "Material", "Width", "Height",
        "Price", "Status"
    ])

    orders = Order.query.all()
    for o in orders:
        ws.append([
            o.id,
            o.client.name,
            o.client.phone,
            o.client.city,
            o.furniture_type,
            o.material,
            o.width,
            o.height,
            o.price,
            o.status
        ])

    file = io.BytesIO()
    wb.save(file)
    file.seek(0)

    return send_file(
        file,
        as_attachment=True,
        download_name="orders.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )



if __name__ == "__main__":
    app.run(debug=True, port=0)
