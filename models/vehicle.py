from datetime import datetime

from twisted.plugins.twisted_reactors import default

from extensions import db

class Vehicle(db.Model):
    vehicle_id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.company_id", ondelete='CASCADE'))
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id", ondelete='SET NULL'), nullable=True)

    # license_plate = db.Column(db.String(10), unique=True, nullable=False)   # nem fog megjelenni a felületen, csak ajánlat elfogadásakor
    vehicle_type = db.Column(db.String(30), nullable=False)  # pl. "kamion", "furgon"
    structure = db.Column(db.String(30), nullable=True)     # pl. "ponyva", "dobozos", "hűtős"
    equipment = db.Column(db.String(255), nullable=True)    # pl. "rakodó rámpa, emelőhátfal"
    cargo_securement = db.Column(db.String(150), nullable=True) # pl. "rakonca", "spanifer"
    description = db.Column(db.Text, default="Nincs leírás")

    capacity_t = db.Column(db.Float, nullable=True)         # hány tonnát képes elvinni
    volume_m3 = db.Column(db.Float, nullable=True)          # raktér mérete
    available_from = db.Column(db.Date, nullable=True)
    available_until = db.Column(db.Date, nullable=True)
    palette_exchange = db.Column(db.Boolean, default=False)
    oversize = db.Column(db.Boolean, default=False)
    price = db.Column(db.Float, nullable=True)
    currency = db.Column(db.String(3), nullable=True)
    origin_country = db.Column(db.String(2))
    origin_postcode = db.Column(db.String(20))
    origin_city = db.Column(db.String(100))
    origin_diff = db.Column(db.Integer, nullable=True)
    destination_country = db.Column(db.String(2))
    destination_postcode = db.Column(db.String(20))
    destination_city = db.Column(db.String(100))
    destination_diff = db.Column(db.Integer, nullable=True)  # pl. +25 km

    load_type = db.Column(db.String(3), nullable=True, default="FTL")  # pl. FTL / LTL

    created_at = db.Column(db.DateTime, default=datetime.now())

    company = db.relationship('Company', back_populates='vehicles')
