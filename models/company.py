from datetime import date
from extensions import db

class Company(db.Model):
    __tablename__ = "company"
    company_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    subscription_type = db.Column(db.String(50), default="free")
    country = db.Column(db.String(50))
    post_code = db.Column(db.String(20))
    street = db.Column(db.String(100))
    house_number = db.Column(db.String(20))
    tax_number = db.Column(db.String(50))
    admin_id = db.Column(db.Integer)
    created_at = db.Column(db.Date, default=date.today)
    slug = db.Column(db.String(200), unique=True, index=True, nullable=True)
    invite_codes = db.relationship('InviteCode', backref='company', lazy=True, cascade='all, delete-orphan')
    users = db.relationship('User', back_populates='company', cascade='all, delete-orphan', passive_deletes=True)
    cargos = db.relationship('Cargo', back_populates='company', cascade='all, delete-orphan')
    vehicles = db.relationship('Vehicle', back_populates='company', cascade='all, delete-orphan')
    logo_filename = db.Column(db.String(200), nullable=True)


class InviteCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    company_id = db.Column(
        db.Integer,
        db.ForeignKey('company.company_id', ondelete='CASCADE'),
        nullable=True
    )
    role = db.Column(db.String(50), nullable=False)
    for_admin = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.Date, default=date.today)
