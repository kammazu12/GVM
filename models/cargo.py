from datetime import datetime, date, timedelta
from utils import *
from extensions import *

class Cargo(db.Model):
    cargo_id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.company_id', ondelete='CASCADE'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id', ondelete='CASCADE'))

    company = db.relationship("Company", back_populates="cargos")
    posted_by = db.relationship("User", back_populates="cargos")

    # Rakomány adatok
    weight = db.Column(db.Float)
    size = db.Column(db.Float)
    price = db.Column(db.Integer)
    currency = db.Column(db.String(3))
    palette_exchange = db.Column(db.Boolean, default=False)
    oversize = db.Column(db.Boolean, default=False)
    description = db.Column(db.Text, default="Nincs leírás")

    # Jármű adatok
    vehicle_type = db.Column(db.String(30))
    structure = db.Column(db.String(30))
    equipment = db.Column(db.String(200))
    cargo_securement = db.Column(db.String(150))
    note = db.Column(db.String(500))

    # Kapcsolatok
    locations = db.relationship("CargoLocation", back_populates="cargo", cascade="all, delete-orphan")
    offers = db.relationship("Offer", back_populates="cargo", lazy=True, cascade="all, delete-orphan")

    # Egyéb
    created_at = db.Column(db.DateTime, default=datetime.now)
    last_republished_at = db.Column(db.DateTime, nullable=True)
    is_template = db.Column(db.Boolean, default=False)


class CargoLocation(db.Model):
    __tablename__ = "cargo_location"

    id = db.Column(db.Integer, primary_key=True)
    cargo_id = db.Column(db.Integer, db.ForeignKey("cargo.cargo_id", ondelete="CASCADE"), nullable=False)
    cargo = db.relationship("Cargo", back_populates="locations")

    # pickup vagy dropoff
    type = db.Column(db.String(8), nullable=False)

    # cím adatok
    country = db.Column(db.String(3))
    postcode = db.Column(db.String(20))
    city = db.Column(db.String(85))
    is_hidden = db.Column(db.Boolean, default=False)
    masked_city = db.Column(db.String(85), nullable=True)
    masked_postcode = db.Column(db.String(20), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    # Időpontok
    start_date = db.Column(db.Date)
    start_time_1 = db.Column(db.Time)
    start_time_2 = db.Column(db.Time)

    end_date = db.Column(db.Date)
    end_time_1 = db.Column(db.Time)
    end_time_2 = db.Column(db.Time)


class Templates(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id', ondelete='CASCADE'))

    # Rakomány adatok
    weight = db.Column(db.Float)
    size = db.Column(db.Float)
    price = db.Column(db.Integer)
    currency = db.Column(db.String(3))
    description = db.Column(db.Text, default="Nincs leírás")

    # Jármű adatok
    vehicle_type = db.Column(db.String(30))
    structure = db.Column(db.String(30))
    equipment = db.Column(db.String(200))
    cargo_securement = db.Column(db.String(150))
    note = db.Column(db.String(500))

    # Kapcsolatok
    locations = db.relationship("TemplateLocations", back_populates="cargo", cascade="all, delete-orphan")


class TemplateLocations(db.Model):
    __tablename__ = "template_locations"

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey("templates.id", ondelete="CASCADE"), nullable=False)
    cargo = db.relationship("Templates", back_populates="locations")

    type = db.Column(db.String(8), nullable=False)  # pickup/dropoff

    # cím adatok
    country = db.Column(db.String(3))
    postcode = db.Column(db.String(20))
    city = db.Column(db.String(85))
    is_hidden = db.Column(db.Boolean, default=False)
    masked_city = db.Column(db.String(85), nullable=True)
    masked_postcode = db.Column(db.String(20), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)


class Offer(db.Model):
    offer_id = db.Column(db.Integer, primary_key=True)
    cargo_id = db.Column(db.Integer, db.ForeignKey('cargo.cargo_id', ondelete='CASCADE'))
    offer_user_id = db.Column(db.Integer, db.ForeignKey('user.user_id', ondelete='CASCADE'))        # ajánlattevő ID-ja

    price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default="EUR")
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.now)

    note = db.Column(db.Text, default="")
    pickup_date = db.Column(db.DateTime, default=datetime.now)
    arrival_date = db.Column(db.DateTime, default=lambda: datetime.combine(date.today() + timedelta(days=1), datetime.min.time()))

    cargo = db.relationship('Cargo', back_populates='offers')
    offer_user = db.relationship('User', back_populates='offers')

    seen = db.Column(db.Boolean, default=False)


class OfferAutoDelete(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    offer_id = db.Column(db.Integer, db.ForeignKey('offer.offer_id', ondelete='CASCADE'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    delete_at = db.Column(db.DateTime, nullable=False)
