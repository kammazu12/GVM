from datetime import datetime
from extensions import db

class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    message_id = db.Column(db.Integer, primary_key=True)
    # kényelmi alias a frontend/REST kód miatt
    @property
    def id(self):
        return self.message_id

    cargo_id = db.Column(db.Integer, db.ForeignKey("cargo.cargo_id", ondelete="CASCADE"), nullable=False)
    offer_id = db.Column(db.Integer, db.ForeignKey("offer.offer_id", ondelete="CASCADE"), nullable=False)

    from_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete='CASCADE'), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete='CASCADE'), nullable=False)

    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())  # referencia a függvényre!

    # Kapcsolatok (választható)
    cargo = db.relationship("Cargo", backref=db.backref("chat_messages", cascade="all, delete-orphan"), lazy=True)
    offer = db.relationship("Offer", backref=db.backref("chat_messages", cascade="all, delete-orphan"), lazy=True)

    sender = db.relationship("User", foreign_keys=[from_user_id], back_populates="sent_messages")
    receiver = db.relationship("User", foreign_keys=[to_user_id], back_populates="received_messages")
