# routes/chat/views.py
from flask import jsonify
from flask_login import login_required
from . import chat_bp
from models import *  # vagy ahogy nálad importálódik
from sqlalchemy import asc

@chat_bp.route("/chat_history/<int:cargo_id>/<int:offer_id>")
@login_required
def chat_history(cargo_id, offer_id):
    messages = ChatMessage.query.filter_by(
        cargo_id=cargo_id, offer_id=offer_id
    ).order_by(asc(getattr(ChatMessage, 'created_at', getattr(ChatMessage, 'timestamp', 'id')))).all()

    out = []
    for m in messages:
        created = getattr(m, "created_at", getattr(m, "timestamp", getattr(m, "created", None)))
        if created:
            created = created.isoformat()
        out.append({
            "from_user_id": m.from_user_id,
            "to_user_id": getattr(m, "to_user_id", None),
            "message": m.message,
            "created_at": created
        })

    # Új rész: offer info betöltése
    offer = Offer.query.get_or_404(offer_id)
    cargo = Cargo.query.get(offer.cargo_id)
    user = User.query.get(offer.offer_user_id)

    origin, destination = "", ""
    if cargo and cargo.locations:
        for loc in cargo.locations:
            if loc.type == "pickup":
                origin = loc.city
            elif loc.type == "dropoff":
                destination = loc.city

    offer_data = {
        "offer_id": offer.offer_id,
        "cargo_id": offer.cargo_id,
        "from_user_id": offer.offer_user_id,
        "to_user_id": cargo.user_id if cargo else None,
        "from_user": f"{user.first_name} {user.last_name}" if user else "Ismeretlen",
        "user_company": user.company.name if user and user.company else "",
        "profile_picture": f"/static/uploads/profile_pictures/{user.profile_picture}" if user and user.profile_picture else "/static/uploads/profile_pictures/default.png",
        "price": offer.price,
        "currency": offer.currency,
        "note": offer.note,
        "origin": origin,
        "destination": destination,
        "pickup_date": offer.pickup_date.strftime('%Y-%m-%d') if offer.pickup_date else "",
        "arrival_date": offer.arrival_date.strftime('%Y-%m-%d') if offer.arrival_date else "",
    }

    return jsonify({"messages": out, "offer": offer_data})



@chat_bp.route('/offer_info/<int:offer_id>')
@login_required
def offer_info(offer_id):
    offer = Offer.query.get_or_404(offer_id)
    cargo = Cargo.query.get(offer.cargo_id)
    user = User.query.get(offer.offer_user_id)

    origin = None
    destination = None

    if cargo and cargo.locations:
        for loc in cargo.locations:
            if loc.type == "pickup":
                origin = loc.city
            elif loc.type == "dropoff":
                destination = loc.city

    return jsonify({
        "offer_id": offer.offer_id,
        "cargo_id": offer.cargo_id,
        "from_user_id": offer.offer_user_id,
        "to_user_id": cargo.user_id if cargo else None,
        "from_user": f"{user.first_name} {user.last_name}" if user else "Ismeretlen",
        "user_company": user.company.name if user and user.company else "",
        "profile_picture": f"/static/uploads/profile_pictures/{user.profile_picture}" if user and user.profile_picture else "/static/uploads/profile_pictures/default.png",
        "price": offer.price,
        "currency": offer.currency,
        "note": offer.note,
        "origin": origin or "",
        "destination": destination or "",
        "pickup_date": offer.pickup_date.strftime('%Y-%m-%d') if offer.pickup_date else "",
        "arrival_date": offer.arrival_date.strftime('%Y-%m-%d') if offer.arrival_date else "",
    })
