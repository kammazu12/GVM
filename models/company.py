from datetime import date, datetime
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

    def is_blocked_by(self, blocker_company_id):
        from models import CompanyBlocklist
        return (
                CompanyBlocklist.query
                .filter_by(blocker_company_id=blocker_company_id, blocked_company_id=self.company_id)
                .first()
                is not None
        )


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


class CompanyBlocklist(db.Model):
    __tablename__ = 'company_blocklist'
    id = db.Column(db.Integer, primary_key=True)
    blocker_company_id = db.Column(db.Integer, db.ForeignKey('company.company_id'), nullable=False)  # aki tilt
    blocked_company_id = db.Column(db.Integer, db.ForeignKey('company.company_id'), nullable=False)  # akit tiltottak
    created_at = db.Column(db.DateTime, default=datetime.now)

    blocker_company = db.relationship('Company', foreign_keys=[blocker_company_id], backref='blocked_companies')
    blocked_company = db.relationship('Company', foreign_keys=[blocked_company_id])
