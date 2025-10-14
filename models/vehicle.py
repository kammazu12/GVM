from datetime import datetime
from email.policy import default

from extensions import db

class Vehicle(db.Model):
    vehicle_id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.company_id", ondelete='CASCADE'))
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete='SET NULL'), nullable=True)

    license_plate = db.Column(db.String(10), unique=True, nullable=False)   # nem fog megjelenni a felületen, csak ajánlat elfogadásakor
    public_license_plate = db.Column(db.Boolean, default=False)  # látható-e a rendszám a felületen
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

    company = db.relationship('Company', back_populates='vehicles')
    routes = db.relationship('VehicleRoute', back_populates='vehicle', cascade="all, delete-orphan", lazy=True)
    offers = db.relationship('Offer', back_populates='vehicle', lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.now())


class VehicleRoute(db.Model):
    # Egy-egy településről tárolja el sorrendben, hogy melyik útvonalon van rajta és melyik jármű teszi meg az utat.
    id = db.Column(db.Integer, primary_key=True)                        # saját azonosító
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicle.vehicle_id", ondelete='CASCADE'))     # melyik járműhöz tartozik
    stop_number = db.Column(db.Integer, nullable=False)                 # hanyadik állomás
    country = db.Column(db.String(2), nullable=False)                   # országkód
    postcode = db.Column(db.String(20), nullable=False)                 # irányítószám
    city = db.Column(db.String(100), nullable=False)                    # település

    vehicle = db.relationship('Vehicle', back_populates='routes')


class NearbyCity(db.Model):
    # Egy adott jármű eredeti vagy cél településéhez közeli városokat tárolja el, hogy a keresés gyorsabb legyen.
    id = db.Column(db.Integer, primary_key=True)
    country_code = db.Column(db.String(2), nullable=False)              # város országkódja
    zipcode = db.Column(db.String(20), nullable=False)                  # város irányítószáma
    city_name = db.Column(db.String(100), nullable=False)               # város neve
    lat = db.Column(db.Float, nullable=False)                           # város szélességi foka
    lon = db.Column(db.Float, nullable=False)                           # város hosszúsági foka
    reference_country = db.Column(db.String(2), nullable=False)         # referencia település országkódja (jármű eredeti vagy cél települése)
    reference_postcode = db.Column(db.String(20), nullable=False)       # referencia település irányítószáma
    reference_city = db.Column(db.String(100), nullable=False)          # referencia település neve
    radius_km = db.Column(db.Integer, nullable=False, default=50)       # hány km-es körzetben van ez a város (pl. 50 km)


class VehicleDestination(db.Model):
    __tablename__ = "vehicle_destination"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicle.vehicle_id"), nullable=False)
    country = db.Column(db.String(2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())

    vehicle = db.relationship("Vehicle", backref=db.backref("extra_destinations", cascade="all, delete-orphan"))


class SavedVehicle(db.Model):
    __tablename__ = "saved_vehicles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete='SET NULL'), nullable=False)

    vehicle_type = db.Column(db.String(30), nullable=False)
    structure = db.Column(db.String(30), nullable=True)
    equipment = db.Column(db.String(255), nullable=True)
    cargo_securement = db.Column(db.String(150), nullable=True)
    description = db.Column(db.Text, default="Nincs leírás")

    capacity_t = db.Column(db.Float, nullable=True)
    volume_m3 = db.Column(db.Float, nullable=True)
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
    destination_diff = db.Column(db.Integer, nullable=True)
    load_type = db.Column(db.String(3), nullable=True, default="FTL")
    note = db.Column(db.String, nullable=True)  # felhasználó által megjegyzésként hozzáadott szöveg

    save_type = db.Column(db.String(20), nullable=False)  # 'template' vagy 'long_term'
    created_at = db.Column(db.DateTime, default=datetime.now())
