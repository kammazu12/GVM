# sockets.py
from flask import request
from extensions import *
from flask_socketio import join_room
from flask_login import current_user
from models import Cargo, Offer, ChatMessage

@socketio.on("connect")
def handle_connect():
    print(f"User connected: {request.sid}")


@socketio.on('join')
def handle_join(data):
    room = data['room']
    join_room(room)


@socketio.on("send_message")
def handle_send_message(data):
    """
    Server-side validation and persistence of chat messages.
    Expects data with: cargo_id, offer_id, message. The sender is taken from current_user.
    """
    try:
        if not current_user.is_authenticated:
            return  # ignore unauthenticated socket events

        cargo_id = int(data.get("cargo_id"))
        offer_id = int(data.get("offer_id"))
        msg_text = (data.get("message") or "").strip()
        if not msg_text:
            return

        # Validate offer and cargo, and participants
        offer = Offer.query.get(offer_id)
        cargo = Cargo.query.get(cargo_id)
        if not offer or not cargo or offer.cargo_id != cargo.cargo_id:
            return

        # Only the offer creator or the cargo owner may send messages
        participants = {offer.offer_user_id, cargo.user_id}
        if current_user.user_id not in participants:
            return

        # Derive recipient from participants
        from_user_id = current_user.user_id
        to_user_id = (participants - {from_user_id}).pop()

        # Persist message
        msg = ChatMessage(
            cargo_id=cargo.cargo_id,
            offer_id=offer.offer_id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            message=msg_text
        )
        db.session.add(msg)
        db.session.commit()

        # Emit to per-offer room so any open windows receive it
        room = f"chat_{cargo.cargo_id}_{offer.offer_id}"
        socketio.emit("receive_message", {
            "cargo_id": cargo.cargo_id,
            "offer_id": offer.offer_id,
            "message": msg_text,
            "from_user_id": from_user_id,
            "to_user_id": to_user_id,
            "created_at": msg.created_at.isoformat()
        }, room=room)
    except Exception:
        db.session.rollback()
        raise
