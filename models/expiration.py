# -------------------------------------------------------
# MODELL: Lejárt rakomány / raktér értesítés
# -------------------------------------------------------
from datetime import datetime
from extensions import *

class ExpiredNotification(db.Model):
    __tablename__ = "expired_notification"

    id = db.Column(db.Integer, primary_key=True)

    # --- kapcsolatok ---
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    item_id = db.Column(db.Integer, nullable=False)
    item_type = db.Column(db.String(20), nullable=False)  # 'cargo' vagy 'storage'

    created_at = db.Column(db.DateTime, default=datetime.now)
    resolved = db.Column(db.Boolean, default=False, index=True)

    # --- visszamutató kapcsolat ---
    user = db.relationship("User", backref=db.backref("expired_notifications", cascade="all, delete-orphan"))

    # --- egyedi index, hogy ne legyen duplikált bejegyzés ---
    __table_args__ = (
        db.UniqueConstraint("user_id", "item_id", "item_type", "resolved", name="uq_expired_active_item"),
        db.Index("ix_expired_user", "user_id"),
        db.Index("ix_expired_item", "item_id", "item_type"),
    )

    def __repr__(self):
        return f"<ExpiredNotification user={self.user_id}, item={self.item_id} ({self.item_type})>"