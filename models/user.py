from flask_login import UserMixin
from extensions import db
from datetime import date, datetime, timedelta
import secrets

class User(db.Model, UserMixin):
    __tablename__ = "users"
    user_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    first_name = db.Column(db.String(150), nullable=False)
    last_name = db.Column(db.String(150), nullable=False)
    phone_number = db.Column(db.String(150), nullable=False)
    hashed_password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), default="freight_forwarder")
    company_id = db.Column(
        db.Integer,
        db.ForeignKey('company.company_id', ondelete='CASCADE')
    )
    is_company_admin = db.Column(db.Boolean, default=False)
    common_user = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.Date, default=date.today)
    profile_picture = db.Column(db.String(200), nullable=True)
    company = db.relationship('Company', back_populates='users')
    cargos = db.relationship('Cargo', back_populates='posted_by', cascade='all, delete-orphan', foreign_keys='Cargo.user_id')
    offers = db.relationship('Offer', back_populates='offer_user', cascade='all, delete-orphan', foreign_keys='Offer.offer_user_id')
    sent_messages = db.relationship('ChatMessage', foreign_keys='ChatMessage.from_user_id', cascade='all, delete-orphan', back_populates='sender')
    received_messages = db.relationship('ChatMessage', foreign_keys='ChatMessage.to_user_id', cascade='all, delete-orphan', back_populates='receiver')

    # Cascade törlés beállítása
    settings = db.relationship(
        "UserSettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )

    def get_id(self):
        return str(self.user_id)


class PasswordResetToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(128), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())

    user = db.relationship('User', backref='reset_tokens')

    @staticmethod
    def generate_for_user(user, hours_valid=1):
        token = secrets.token_urlsafe(48)
        expires = datetime.now() + timedelta(hours=hours_valid)
        prt = PasswordResetToken(token=token, user_id=user.user_id, expires_at=expires)
        db.session.add(prt)
        db.session.commit()
        return token


class UserSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), unique=True)
    dark_mode = db.Column(db.Boolean, default=False)
    colorblind = db.Column(db.Boolean, default=False)
    low_quality = db.Column(db.Boolean, default=False)
    language = db.Column(db.String(5), default="hu")

    user = db.relationship("User", back_populates="settings")
