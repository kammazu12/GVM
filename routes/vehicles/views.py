# routes/vehicles/views.py
from flask import render_template, flash, redirect, url_for, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy import and_

from models import Vehicle
from utils import *
from . import vehicles_bp

@vehicles_bp.route('/vehicles')
@login_required
def vehicles():
    return render_template('vehicles.html', user=current_user)


@vehicles_bp.route("/vehicles/save", methods=["POST"])
def save_vehicle():
    # Form mezők beolvasása
    origin_city = request.form.get("origin_city")
    origin_postcode = request.form.get("origin_zip")
    origin_country = request.form.get("origin_country")
    origin_diff = request.form.get("origin_diff")

    destination_city = request.form.get("destination_city")
    destination_postcode = request.form.get("destination_zip")
    destination_country = request.form.get("destination_country")
    destination_diff = request.form.get("destination_diff")

    available_from_str = request.form.get("available_from")
    available_until_str = request.form.get("available_until")

    available_from = datetime.strptime(available_from_str, "%Y-%m-%d").date() if available_from_str else None
    available_until = datetime.strptime(available_until_str, "%Y-%m-%d").date() if available_until_str else None

    vehicle_type = request.form.get("vehicle_type")
    superstructure = request.form.get("superstructure")
    description = request.form.get("description")
    equipment = request.form.getlist("equipment")
    securement = request.form.getlist("securement")
    capacity_t = parse_float(request.form.get("capacity_t"))
    volume_m3 = parse_float(request.form.get("volume_m3"))
    palette_exchange = request.form.get("palette_exchange") == "true"
    oversize = request.form.get("oversize") == "true"
    price = request.form.get("price")
    currency = request.form.get("currency")
    load_type = request.form.get("load_type")

    # --- LOG az adatoknál ---
    print("[Backend] origin:", origin_city, origin_postcode, origin_country, origin_diff)
    print("[Backend] destination:", destination_city, destination_postcode, destination_country, destination_diff)
    print("[Backend] vehicle_type:", vehicle_type, "capacity_t:", capacity_t, "volume_m3:", volume_m3)

    # Mentés
    new_vehicle = Vehicle(
        user_id=current_user.user_id,
        company_id=current_user.company_id,
        origin_city=origin_city,
        origin_postcode=origin_postcode,
        origin_country=origin_country,
        origin_diff=origin_diff if origin_diff != "any" else None,
        destination_city=destination_city,
        destination_postcode=destination_postcode,
        destination_country=destination_country,
        destination_diff=destination_diff if destination_diff != "any" else None,
        available_from=available_from,
        available_until=available_until,
        vehicle_type=vehicle_type,
        structure=superstructure,
        description=description,
        equipment=",".join(equipment) if equipment else None,
        cargo_securement=",".join(securement) if securement else None,
        capacity_t=capacity_t,
        volume_m3=volume_m3,
        palette_exchange=palette_exchange,
        oversize=oversize,
        price=price,
        currency=currency,
        load_type=load_type
    )

    db.session.add(new_vehicle)
    db.session.commit()

    print("[Backend] A jármű sikeresen mentve lett!")
    return redirect(url_for("shipments"))


@vehicles_bp.route("/list")
@login_required
def vehicles_list():
    """
    Járművek listázása a táblázathoz
    """
    # Lekérjük az összes járművet a felhasználó cégéhez tartozóan
    vehicles = Vehicle.query.filter_by(company_id=current_user.company_id).all()

    return render_template("vehicles_list.html", vehicles=vehicles)


@vehicles_bp.route("/api/list")
@login_required
def vehicles_api():
    """
    API a járművekhez JSON-ban
    """
    vehicles = Vehicle.query.filter_by(company_id=current_user.company_id).all()

    vehicles_data = []
    for v in vehicles:
        vehicles_data.append({
            "id": v.vehicle_id,
            "vehicle_type": v.vehicle_type,
            "structure": v.structure,
            "equipment": v.equipment,
            "cargo_securement": v.cargo_securement,
            "description": v.description,
            "capacity_t": v.capacity_t,
            "volume_m3": v.volume_m3,
            "available_from": v.available_from.strftime("%Y-%m-%d") if v.available_from else "",
            "available_until": v.available_until.strftime("%Y-%m-%d") if v.available_until else "",
            "origin_city": v.origin_city,
            "origin_postcode": v.origin_postcode,
            "origin_country": v.origin_country,
            "origin_diff": v.origin_diff,
            "destination_city": v.destination_city,
            "destination_postcode": v.destination_postcode,
            "destination_country": v.destination_country,
            "destination_diff": v.destination_diff,
            "palette_exchange": v.palette_exchange,
            "oversize": v.oversize,
            "price": v.price,
            "currency": v.currency,
            "load_type": v.load_type,
            "created_at": v.created_at.strftime("%Y-%m-%d %H:%M:%S") if v.created_at else ""
        })

    return jsonify(vehicles_data)


@vehicles_bp.route('/<vehicle_id>/details')
def vehicle_details(vehicle_id):
    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle:
        abort(404, description="Vehicle not found")

    # pickup
    pickup_city = City.query.filter_by(
        city_name=vehicle.origin_city,
        country_code=vehicle.origin_country
    ).first()

    # dropoff
    dropoff_city = City.query.filter_by(
        city_name=vehicle.destination_city,
        country_code=vehicle.destination_country
    ).first()

    pickups, dropoffs = [], []
    if pickup_city:
        pickups.append({
            "lat": pickup_city.latitude,
            "lng": pickup_city.longitude,
            "city": pickup_city.city_name,
            "masked_city": pickup_city.city_name,
            "country": pickup_city.country_code,
            "radiusKm": vehicle.origin_diff
        })
    if dropoff_city:
        dropoffs.append({
            "lat": dropoff_city.latitude,
            "lng": dropoff_city.longitude,
            "city": dropoff_city.city_name,
            "masked_city": dropoff_city.city_name,
            "country": dropoff_city.country_code,
            "radiusKm": vehicle.destination_diff
        })

    # útvonal számítás
    route_coords, route_distance_km, route_duration_text, route_cities = [], None, None, []
    if pickup_city and dropoff_city and pickup_city.latitude and dropoff_city.latitude:
        dist = haversine(pickup_city.latitude, pickup_city.longitude,
                         dropoff_city.latitude, dropoff_city.longitude)
        route_distance_km = round(dist, 1)
        hours = dist / 80.0  # átlag 80 km/h
        h = int(hours)
        m = int((hours - h) * 60)
        route_duration_text = f"{h} óra {m} perc"
        route_coords = [
            [pickup_city.latitude, pickup_city.longitude],
            [dropoff_city.latitude, dropoff_city.longitude]
        ]
        route_cities = [pickup_city.city_name, dropoff_city.city_name]

    return render_template(
        'vehicle_details.html',
        vehicle=vehicle,
        pickups_json=pickups,
        dropoffs_json=dropoffs,
        route_coords=route_coords,
        route_distance_km=route_distance_km,
        route_duration_text=route_duration_text,
        route_cities=route_cities
    )


@vehicles_bp.route('/cities_near_route_country', methods=['POST'])
def cities_near_route_country():
    """
    POST JSON: {"route": [[lat, lon], ...], "radius_km": 1, "country_codes": ["HU","DE",...]}
    Visszaadja országonként a településeket sorrendben (felrakótól lerakóig),
    csak a route bounding box-ában keresve a városokat.
    """
    data = request.get_json()
    route = data.get("route", [])
    radius_km = data.get("radius_km", 1)
    country_codes = data.get("country_codes", [])

    if not route or len(route) < 2 or not country_codes:
        return jsonify([])

    # Bounding box a route köré (kicsit nagyobb, mint a radius)
    lats = [lat for lat, lon in route]
    lons = [lon for lat, lon in route]
    min_lat, max_lat = min(lats)-0.1, max(lats)+0.1
    min_lon, max_lon = min(lons)-0.1, max(lons)+0.1

    response = []

    for country in country_codes:
        # Csak az adott ország városai + route bounding box
        cities_query = City.query.filter(
            City.latitude != None,
            City.longitude != None,
            City.country_code == country,
            and_(City.latitude >= min_lat, City.latitude <= max_lat),
            and_(City.longitude >= min_lon, City.longitude <= max_lon)
        ).all()

        nearby = []
        for city in cities_query:
            min_idx = None
            min_dist = float('inf')
            for idx, (lat, lon) in enumerate(route):
                dist = haversine(lat, lon, city.latitude, city.longitude)
                if dist <= radius_km and dist < min_dist:
                    min_dist = dist
                    min_idx = idx
            if min_idx is not None:
                nearby.append((min_idx, city))

        nearby.sort(key=lambda x: x[0])
        country_cities = [{"city_name": c.city_name, "latitude": c.latitude, "longitude": c.longitude} for _, c in nearby]
        response.append({"country": country, "cities": country_cities})

    return jsonify(response)

