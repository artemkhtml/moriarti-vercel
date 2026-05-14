import os
from datetime import datetime

from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = normalize_database_url(DATABASE_URL)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
}

db = SQLAlchemy(app)


class PurchaseRequest(db.Model):
    __tablename__ = "purchase_requests"

    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False, default="шт")
    requested_by = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="new")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def as_dict(self):
        return {
            "id": self.id,
            "product_name": self.product_name,
            "quantity": self.quantity,
            "unit": self.unit,
            "requested_by": self.requested_by,
            "status": self.status,
            "created_at": self.created_at.isoformat() + "Z",
        }


class InventoryItem(db.Model):
    __tablename__ = "inventory_items"

    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(120), nullable=False, unique=True)
    current_stock = db.Column(db.Float, nullable=False, default=0)
    min_stock = db.Column(db.Float, nullable=False, default=0)
    unit = db.Column(db.String(20), nullable=False, default="шт")
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def as_dict(self):
        return {
            "id": self.id,
            "product_name": self.product_name,
            "current_stock": self.current_stock,
            "min_stock": self.min_stock,
            "unit": self.unit,
            "updated_at": self.updated_at.isoformat() + "Z",
        }


with app.app_context():
    db.create_all()


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ok", "database": "reachable"})
    except Exception as exc:
        return jsonify({"status": "degraded", "error": str(exc)}), 500


@app.get("/requests")
def list_requests():
    items = PurchaseRequest.query.order_by(PurchaseRequest.created_at.desc()).all()
    return jsonify([item.as_dict() for item in items])


@app.post("/requests")
def create_request():
    data = request.get_json(force=True)
    for field in ["product_name", "quantity", "requested_by"]:
        if field not in data or data[field] in [None, ""]:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    item = PurchaseRequest(
        product_name=data["product_name"],
        quantity=float(data["quantity"]),
        unit=data.get("unit", "шт"),
        requested_by=data["requested_by"],
        status=data.get("status", "new"),
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(item.as_dict()), 201


@app.put("/requests/<int:item_id>")
def update_request(item_id):
    item = PurchaseRequest.query.get(item_id)
    if item is None:
        return jsonify({"error": "Заявка не найдена"}), 404

    data = request.get_json(force=True)
    if "product_name" in data:
        item.product_name = data["product_name"]
    if "quantity" in data:
        item.quantity = float(data["quantity"])
    if "unit" in data:
        item.unit = data["unit"]
    if "requested_by" in data:
        item.requested_by = data["requested_by"]
    if "status" in data:
        item.status = data["status"]

    db.session.commit()
    return jsonify(item.as_dict()), 200


@app.delete("/requests/<int:item_id>")
def delete_request(item_id):
    item = PurchaseRequest.query.get(item_id)
    if item is None:
        return jsonify({"error": "Заявка не найдена"}), 404

    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Заявка удалена"}), 200


@app.get("/inventory")
def list_inventory():
    items = InventoryItem.query.order_by(InventoryItem.product_name.asc()).all()
    return jsonify([item.as_dict() for item in items])


@app.post("/inventory")
def create_inventory():
    data = request.get_json(force=True)
    for field in ["product_name", "current_stock", "min_stock"]:
        if field not in data or data[field] in [None, ""]:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    item = InventoryItem(
        product_name=data["product_name"],
        current_stock=float(data["current_stock"]),
        min_stock=float(data["min_stock"]),
        unit=data.get("unit", "шт"),
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(item.as_dict()), 201


@app.put("/inventory/<int:item_id>")
def update_inventory(item_id):
    item = InventoryItem.query.get(item_id)
    if item is None:
        return jsonify({"error": "Позиция склада не найдена"}), 404

    data = request.get_json(force=True)
    if "product_name" in data:
        item.product_name = data["product_name"]
    if "current_stock" in data:
        item.current_stock = float(data["current_stock"])
    if "min_stock" in data:
        item.min_stock = float(data["min_stock"])
    if "unit" in data:
        item.unit = data["unit"]

    db.session.commit()
    return jsonify(item.as_dict()), 200


@app.delete("/inventory/<int:item_id>")
def delete_inventory(item_id):
    item = InventoryItem.query.get(item_id)
    if item is None:
        return jsonify({"error": "Позиция склада не найдена"}), 404

    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "Позиция склада удалена"}), 200
