from flask import request, jsonify
from matching import find_matches_for_cargo
from models import Cargo, Vehicle
from . import matching_bp

# routes/matching.py
@matching_bp.route("/find_matches", methods=["POST"])
def find_matches():
    # print("=== Backend log: /find_matches called ===")
    # print("request.json:", request.json)

    data = request.json
    cargo_id = data.get("cargo_id")
    if not cargo_id:
        return jsonify({"error": "cargo_id missing"}), 400

    cargo = Cargo.query.get(cargo_id)
    if not cargo:
        return jsonify({"error": "Cargo not found"}), 404

    matches = find_matches_for_cargo(cargo)  # már objektum tömb: {"vehicle_id":..,"score":..}

    # Backend log
    # print("=== Backend log: matches visszaküldés előtt ===")
    # for m in matches:
    #     print(f"Vehicle {m['vehicle_id']}, score={m['score']}")

    return jsonify({"matches": matches})



