# routes/vehicles/views.py
from flask import render_template, flash, redirect, url_for, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy import and_
from models import Vehicle, VehicleRoute
from utils import *
from . import vehicles_bp
import json
from flask import Blueprint, request, redirect, url_for, current_app
from flask_login import current_user
from datetime import datetime
import requests
from math import radians, sin, cos, sqrt, atan2
from extensions import db
from models import Vehicle, VehicleRoute, City


@vehicles_bp.route('/vehicles')
@login_required
@no_cache
def vehicles():
    templates = SavedVehicle.query.filter_by(
        user_id=current_user.user_id,
        save_type='template'
    ).all()

    templates_dict = []
    for t in templates:
        t_dict = {
            "id": t.id,
            "vehicle_type": t.vehicle_type,
            "structure": t.structure,
            "equipment": t.equipment,
            "cargo_securement": t.cargo_securement,
            "note": t.note,
            "description": t.description,
            "capacity_t": t.capacity_t,
            "volume_m3": t.volume_m3,
            "palette_exchange": t.palette_exchange,
            "oversize": t.oversize,
            "price": t.price,
            "currency": t.currency,
            "origin_country": t.origin_country,
            "origin_postcode": t.origin_postcode,
            "origin_city": t.origin_city,
            "origin_diff": t.origin_diff,
            "destination_country": t.destination_country,
            "destination_postcode": t.destination_postcode,
            "destination_city": t.destination_city,
            "destination_diff": t.destination_diff,
            "load_type": t.load_type,
            "save_type": t.save_type,
            "created_at": t.created_at,

        }
        templates_dict.append(t_dict)

        # --- Backend debug log ---
        print(f"[DEBUG] Vehicle template loaded: {t_dict}")

    return render_template(
        'vehicles.html',
        user=current_user,
        current_year=datetime.now().year,
        templates=templates_dict
    )


@vehicles_bp.route("/save", methods=["POST"])
@login_required
def save_vehicle():
    # -------------------------------
    # 1️⃣ Form mezők beolvasása
    # -------------------------------
    origin_city = request.form.get("origin_city")
    origin_postcode = request.form.get("origin_zip")
    origin_country = request.form.get("origin_country")
    origin_diff = parse_float(request.form.get("origin_diff"))

    destination_city = request.form.get("destination_city")
    destination_postcode = request.form.get("destination_zip")
    destination_country = request.form.get("destination_country")
    destination_diff_raw = request.form.get("destination_diff")

    available_from_str = request.form.get("available_from")
    available_until_str = request.form.get("available_until")

    vehicle_type = request.form.get("vehicle_type")
    structure = request.form.get("structure")
    description = request.form.get("description")
    equipment = request.form.getlist("equipment")
    securement = request.form.getlist("securement")
    license_plate = request.form.get("license_plate")
    public_license_plate = request.form.get("public_license") == "true"
    capacity_t = parse_float(request.form.get("capacity_t"))
    volume_m3 = parse_float(request.form.get("volume_m3"))
    palette_exchange = request.form.get("palette_exchange") == "true"
    oversize = request.form.get("oversize") == "true"
    price = parse_float(request.form.get("price"))
    currency = request.form.get("currency")
    load_type = request.form.get("load_type") == "true"
    load_type = "LTL" if load_type else "FTL"

    # -------------------------------
    # 2️⃣ Checkboxok
    # -------------------------------
    save_sablon = request.form.get("sablonCheckbox") == "on"
    save_longterm = request.form.get("longtermCheckbox") == "on"

    # -------------------------------
    # 3️⃣ destination_diff feldolgozása
    # -------------------------------
    diff_type = None
    destination_diff = None
    if destination_diff_raw == "any":
        diff_type = "any"
        destination_city = origin_city
        destination_postcode = origin_postcode
        destination_country = origin_country
        destination_diff = None
    else:
        try:
            destination_diff = float(destination_diff_raw) if destination_diff_raw else 0.0
            diff_type = "number"
        except (ValueError, TypeError):
            diff_type = "zero"
            destination_diff = 0.0

    # -------------------------------
    # 4️⃣ Vehicle mentése
    # -------------------------------
    new_vehicle = Vehicle(
        user_id=current_user.user_id,
        company_id=current_user.company_id,
        origin_city=origin_city,
        origin_postcode=origin_postcode,
        origin_country=origin_country,
        origin_diff=origin_diff,
        destination_city=destination_city,
        destination_postcode=destination_postcode,
        destination_country=destination_country,
        destination_diff=destination_diff,
        available_from=datetime.strptime(available_from_str, "%Y-%m-%d").date() if available_from_str else None,
        available_until=datetime.strptime(available_until_str, "%Y-%m-%d").date() if available_until_str else None,
        vehicle_type=vehicle_type,
        structure=structure,
        license_plate=license_plate,
        public_license_plate=public_license_plate,
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
    print(f"[LOG] Vehicle mentve: ID={new_vehicle.vehicle_id}, diff_type={diff_type}")

    # -------------------------------
    # 5️⃣ VehicleDestination mentése 'any' esetén
    # -------------------------------
    if diff_type == "any":
        selected_countries_json = request.form.get("selected_dest_countries")
        if selected_countries_json:
            try:
                selected_countries = json.loads(selected_countries_json)
                for code in selected_countries:
                    if code:
                        vd = VehicleDestination(vehicle_id=new_vehicle.vehicle_id, country=code)
                        db.session.add(vd)
                        print(f"[LOG] VehicleDestination mentve: {code}")
                db.session.commit()
            except Exception as e:
                print("[ERROR] Hibás JSON formátum az országlistánál:", e)
        return redirect(url_for("shipments"))

    # -------------------------------
    # 6️⃣ OSRM útvonal és VehicleRoute
    # -------------------------------
    pickup_city = City.query.filter_by(city_name=origin_city, country_code=origin_country).first()
    dropoff_city = City.query.filter_by(city_name=destination_city, country_code=destination_country).first()

    if not pickup_city or not dropoff_city:
        print("[ERROR] Nem található origin vagy destination város!")
        return redirect(url_for("shipments"))

    osrm_route_coords = []
    route_coords_input = request.form.get("routeCoordsInput")
    if route_coords_input:
        try:
            osrm_route_coords = json.loads(route_coords_input)
        except Exception as e:
            print("[ERROR] routeCoordsInput feldolgozási hiba:", e)

    if not osrm_route_coords:
        try:
            coord_string = f"{pickup_city.longitude},{pickup_city.latitude};{dropoff_city.longitude},{dropoff_city.latitude}"
            osrm_url = f"https://router.project-osrm.org/route/v1/driving/{coord_string}?overview=full&geometries=geojson"
            response = requests.get(osrm_url, timeout=10)
            data = response.json()
            if "routes" in data and len(data["routes"]) > 0:
                osrm_route_coords = [[lat, lon] for lon, lat in data["routes"][0]["geometry"]["coordinates"]]
        except Exception as e:
            print("[ERROR] OSRM hiba:", e)

    if not osrm_route_coords:
        osrm_route_coords = [[pickup_city.latitude, pickup_city.longitude],
                             [dropoff_city.latitude, dropoff_city.longitude]]

    # Bounding box + nearby cities
    lats = [lat for lat, lon in osrm_route_coords]
    lons = [lon for lat, lon in osrm_route_coords]
    min_lat, max_lat = min(lats) - 0.1, max(lats) + 0.1
    min_lon, max_lon = min(lons) - 0.1, max(lons) + 0.1

    cities_query = City.query.filter(
        City.latitude != None,
        City.longitude != None,
        City.latitude >= min_lat, City.latitude <= max_lat,
        City.longitude >= min_lon, City.longitude <= max_lon
    ).all()

    radius_km = 3
    nearby = []
    for city in cities_query:
        min_idx = None
        min_dist = float('inf')
        for idx, (lat, lon) in enumerate(osrm_route_coords):
            max_deg = radius_km / 111.0
            if abs(lat - city.latitude) > max_deg or abs(lon - city.longitude) > max_deg:
                continue
            dlat = radians(city.latitude - lat)
            dlon = radians(city.longitude - lon)
            a = sin(dlat / 2) ** 2 + cos(radians(lat)) * cos(radians(city.latitude)) * sin(dlon / 2) ** 2
            c = 2 * atan2(sqrt(a), sqrt(1 - a))
            dist = 6371 * c
            if dist <= radius_km and dist < min_dist:
                min_dist = dist
                min_idx = idx
        if min_idx is not None:
            nearby.append((min_idx, city))
    nearby.sort(key=lambda x: x[0])

    for stop_number, (_, city) in enumerate(nearby, start=1):
        route_entry = VehicleRoute(
            vehicle_id=new_vehicle.vehicle_id,
            stop_number=stop_number,
            country=city.country_code,
            postcode=city.zipcode,
            city=city.city_name
        )
        db.session.add(route_entry)
    db.session.commit()

    # -------------------------------
    # 7️⃣ SavedVehicle mentése a checkboxok alapján
    # -------------------------------
    saved_vehicles = []

    for save_type in (("template", save_sablon), ("long-term", save_longterm)):
        type_name, should_save = save_type
        if should_save:
            sv = SavedVehicle(
                user_id=current_user.user_id,
                vehicle_type=vehicle_type,
                structure=structure,
                equipment=",".join(equipment) if equipment else None,
                cargo_securement=",".join(securement) if securement else None,
                description=description,
                license_plate=license_plate,
                public_license_plate=public_license_plate,
                capacity_t=capacity_t,
                volume_m3=volume_m3,
                palette_exchange=palette_exchange,
                oversize=oversize,
                price=price,
                currency=currency,
                origin_country=origin_country,
                origin_postcode=origin_postcode,
                origin_city=origin_city,
                origin_diff=origin_diff,
                destination_country=destination_country,
                destination_postcode=destination_postcode,
                destination_city=destination_city,
                destination_diff=destination_diff,
                load_type=load_type,
                save_type=type_name
            )
            saved_vehicles.append(sv)

    if saved_vehicles:
        db.session.add_all(saved_vehicles)
        db.session.commit()
        print(f"[LOG] SavedVehicle rekordok mentve: {len(saved_vehicles)}")

    # -------------------------------
    # 8️⃣ NearbyCity feldolgozás (opcionális)
    # -------------------------------
    add_nearby_cities_for_vehicle(new_vehicle)

    return redirect(url_for("shipments"))


@vehicles_bp.route("/get_vehicle/<int:vehicle_id>")
@login_required
@no_cache
def get_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    if vehicle.company_id != current_user.company_id:
        return jsonify({"error": "Nincs hozzáférés"}), 403

    return jsonify({
        "vehicle_id": vehicle.vehicle_id,
        "vehicle_type": vehicle.vehicle_type,
        "structure": vehicle.structure,
        "equipment": vehicle.equipment or "",           # lehet None → üres string
        "cargo_securement": vehicle.cargo_securement or "",
        "description": vehicle.description or "",
        "license_plate": vehicle.license_plate or "",
        "public_license_plate": bool(vehicle.public_license_plate),
        "capacity_t": vehicle.capacity_t or "",
        "volume_m3": vehicle.volume_m3 or "",
        "available_from": vehicle.available_from.strftime('%Y-%m-%d') if vehicle.available_from else "",
        "available_until": vehicle.available_until.strftime('%Y-%m-%d') if vehicle.available_until else "",
        "palette_exchange": bool(vehicle.palette_exchange),
        "oversize": bool(vehicle.oversize),
        "price": vehicle.price or "",
        "currency": vehicle.currency or "",
        "origin_country": vehicle.origin_country or "",
        "origin_postcode": vehicle.origin_postcode or "",
        "origin_city": vehicle.origin_city or "",
        "origin_diff": vehicle.origin_diff or "",
        "destination_country": vehicle.destination_country or "",
        "destination_postcode": vehicle.destination_postcode or "",
        "destination_city": vehicle.destination_city or "",
        "destination_diff": vehicle.destination_diff or "",
        "load_type": vehicle.load_type or "FTL",       # default
        "created_at": vehicle.created_at.strftime('%Y-%m-%d %H:%M:%S')
    })


# TO BE DONE
@vehicles_bp.route("/update_vehicle", methods=['POST'])
@login_required
@no_cache
def update_vehicle():
    data = request.get_json()
    vehicle_id = data.get('vehicle_id')
    field = data.get('field')
    value = data.get('value')

    vehicle = Vehicle.query.get_or_404(vehicle_id)
    if vehicle.company_id != current_user.company_id:
        return jsonify({"error": "Nincs hozzáférés"}), 403

    # Csak engedélyezett mezők frissítése
    editable_fields = [
        "vehicle_type","structure","equipment","cargo_securement", "license_plate",
        "description","capacity_t","volume_m3","available_from","available_until",
        "palette_exchange","oversize", "public_license", "price","currency",
        "origin_country","origin_postcode","origin_city",
        "destination_country","destination_postcode","destination_city"
    ]

    # mezőnév mapping a táblázat headerből
    field_map = {
        "Jármű típusa":"vehicle_type",
        "Szerkezet":"structure",
        "Felszereltség":"equipment",
        "Rakomány rögzítése":"cargo_securement",
        "Leírás":"description",
        "Teher (t)":"capacity_t",
        "Hossz (m³)":"volume_m3",
        "Dátum":"available_from",  # egyszerűsítés, lehet két mező is
        "Ár":"price"
    }

    db_field = field_map.get(field, field)
    if db_field not in editable_fields:
        return jsonify({"error": "Nem szerkeszthető mező"}), 400

    # típuskonverzió
    try:
        if db_field in ["capacity_t","volume_m3","price"]:
            setattr(vehicle, db_field, float(value) if value else None)
        elif db_field in ["palette_exchange","oversize"]:
            setattr(vehicle, db_field, value.lower() in ["true","1","yes"])
        elif db_field in ["available_from","available_until"]:
            from datetime import datetime
            setattr(vehicle, db_field, datetime.strptime(value, "%Y-%m-%d").date() if value else None)
        else:
            setattr(vehicle, db_field, value)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify({"success": True})


# TO BE DONE?
@vehicles_bp.route("/delete/<int:vehicle_id>", methods=['DELETE'])
@login_required
@no_cache
def delete_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    if vehicle.company_id != current_user.company_id:
        return jsonify({"error": "Nincs hozzáférés"}), 403

    db.session.delete(vehicle)
    db.session.commit()
    return jsonify({"success": True})


@vehicles_bp.route('/delete_vehicles', methods=['POST'])
@login_required
@no_cache
def delete_vehicles():
    data = request.get_json(silent=True) or {}
    ids_to_delete = data.get('ids', [])

    if not ids_to_delete:
        return jsonify({'error': 'Nincs kiválasztva sor!'}), 400

    try:
        vehicles = Vehicle.query.filter(Vehicle.vehicle_id.in_(ids_to_delete)).all()
        deleted_ids = []
        for vehicle in vehicles:
            if vehicle.user_id != current_user.user_id:
                continue

            db.session.delete(vehicle)
            deleted_ids.append(vehicle.vehicle_id)

        db.session.commit()
        return jsonify({'success': True, 'deleted_ids': deleted_ids})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@vehicles_bp.route("/republish_vehicles", methods=["POST"])
@login_required
@no_cache
def republish_vehicles():
    """
    Újraközlés: a kiválasztott járműveket újra publikálja.
    """
    data = request.get_json()
    if not data or "ids" not in data:
        return jsonify({"error": "Nincsenek ID-k megadva!"}), 400

    vehicle_ids = data["ids"]
    republished = []

    for vid in vehicle_ids:
        vehicle = Vehicle.query.filter_by(vehicle_id=vid, user_id=current_user.user_id).first()
        if vehicle:
            vehicle.created_at = datetime.utcnow()  # újraközlés ideje
            db.session.add(vehicle)
            republished.append(vid)

    db.session.commit()
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"republished": republished, "now": now_str})


@vehicles_bp.route("/api/list")
@login_required
@no_cache
def vehicles_api():
    """
    API a járművekhez JSON-ban
    """
    vehicles = Vehicle.query.filter_by(company_id=current_user.company_id).all()

    print(f"[LOG] Vállalat járművei: {len(vehicles)}")

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


@vehicles_bp.route("/api/eu-countries")
@login_required
def eu_countries():
    countries = Country.query.with_entities(
        Country.id, Country.name, Country.code, Country.flag_url, Country.region
    ).all()
    print(countries)

    result = []
    for idx, c in enumerate(countries):
        if c is None:
            print(f"[WARNING] countries listában None elem: index={idx}")
            continue

        code = getattr(c, "code", None)
        name = getattr(c, "name", None)
        flag_url = getattr(c, "flag_url", "")
        region = getattr(c, "region", None)

        # Szűrés csak EU országokra
        if region != "EU":
            continue

        if not code or not name:
            print(
                f"[WARNING] hiányzó mező egy Country rekordnál: id={getattr(c, 'id', 'unknown')}, code={code}, name={name}"
            )
            continue

        result.append({"code": code, "name": name, "flag_url": flag_url})
        print(f"[LOG] EU ország hozzáadva: {name} ({code})")

    print(f"[LOG] Összes EU ország JSON-ba: {len(result)}")
    return jsonify(result)


@vehicles_bp.route('/<vehicle_id>/details')
def vehicle_details(vehicle_id):
    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle:
        abort(404, description="Vehicle not found")

    # pickup város
    pickup_city = City.query.filter_by(
        city_name=vehicle.origin_city,
        country_code=vehicle.origin_country
    ).first()

    # dropoff város
    dropoff_city = City.query.filter_by(
        city_name=vehicle.destination_city,
        country_code=vehicle.destination_country
    ).first()

    pickups, dropoffs = [], []

    # pickup adatok
    if pickup_city:
        pickups.append({
            "lat": pickup_city.latitude,
            "lng": pickup_city.longitude,
            "city": pickup_city.city_name,
            "masked_city": pickup_city.city_name,
            "country": pickup_city.country_code,
            "radiusKm": vehicle.origin_diff
        })

    # dropoff adatok
    if dropoff_city:
        dropoffs.append({
            "lat": dropoff_city.latitude,
            "lng": dropoff_city.longitude,
            "city": dropoff_city.city_name,
            "masked_city": dropoff_city.city_name,
            "country": dropoff_city.country_code,
            "radiusKm": vehicle.destination_diff
        })

    # --- EXTRA ORSZÁGOK (VehicleDestination táblából) ---
    extra_destinations = []
    if vehicle.destination_diff is None:  # csak ha országlista alapján dolgozunk
        extra_records = VehicleDestination.query.filter_by(vehicle_id=vehicle.vehicle_id).all()
        extra_destinations = [r.country for r in extra_records]

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
        route_cities=route_cities,
        extra_destinations=extra_destinations  # ← EZ ÚJ!
    )


@vehicles_bp.route('/cities_near_route', methods=['POST'])
def cities_near_route():
    """
    POST JSON: {"route": [[lat, lon], ...], "radius_km": 1}
    Visszaadja az összes települést sorrendben, amin keresztül a route megy.
    Gyorsított verzió:
      - route ritkítása
      - gyors bounding box szűrés városonként
    """
    data = request.get_json()
    route = data.get("route", [])
    radius_km = data.get("radius_km", 1)

    if not route or len(route) < 2:
        return jsonify([])

    # ---- route ritkítás ----
    def simplify_route(points, max_points=200):
        if len(points) <= max_points:
            return points
        step = max(1, len(points) // max_points)
        return points[::step]

    route = simplify_route(route)

    # ---- bounding box az egész útvonal köré ----
    lats = [lat for lat, lon in route]
    lons = [lon for lat, lon in route]
    min_lat, max_lat = min(lats) - 0.1, max(lats) + 0.1
    min_lon, max_lon = min(lons) - 0.1, max(lons) + 0.1

    # ---- DB lekérdezés ----
    cities_query = City.query.filter(
        City.latitude != None,
        City.longitude != None,
        City.latitude >= min_lat, City.latitude <= max_lat,
        City.longitude >= min_lon, City.longitude <= max_lon
    ).all()

    # ---- gyors előszűrés távolság becsléssel ----
    def approx_distance_ok(lat1, lon1, lat2, lon2, radius_km):
        # ~111 km ~ 1 fok szélesség
        max_deg = radius_km / 111.0
        return abs(lat1 - lat2) <= max_deg and abs(lon1 - lon2) <= max_deg

    # ---- települések vizsgálata ----
    nearby = []
    for city in cities_query:
        min_idx = None
        min_dist = float('inf')

        for idx, (lat, lon) in enumerate(route):
            if not approx_distance_ok(lat, lon, city.latitude, city.longitude, radius_km):
                continue  # túl messze, nem kell számolni

            dist = haversine(lat, lon, city.latitude, city.longitude)
            if dist <= radius_km and dist < min_dist:
                min_dist = dist
                min_idx = idx

        if min_idx is not None:
            nearby.append((min_idx, city))

    # ---- sorrend az útvonal mentén ----
    nearby.sort(key=lambda x: x[0])

    city_list = [
        {
            "city_name": c.city_name,
            "latitude": c.latitude,
            "longitude": c.longitude
        }
        for _, c in nearby
    ]

    return jsonify(city_list)


@vehicles_bp.route("/geojson/countries_list")
def geojson_countries_list():
    folder = os.path.join(current_app.static_folder, "geojson/countries")
    files = [f for f in os.listdir(folder) if f.endswith(".json")]
    return jsonify(files)


# GET: betölti egy mentett jármű sablon adatait JSON-ban
@vehicles_bp.route('/template/<int:template_id>', methods=['GET'])
@login_required
@no_cache
def load_vehicle_template(template_id):
    template = SavedVehicle.query.filter_by(
        id=template_id,
        user_id=current_user.user_id,
        save_type='template'   # csak sablonok
    ).first()

    if not template:
        return jsonify({"success": False, "error": "Sablon nem található"})

    return jsonify({
        "success": True,
        "template": {
            "id": template.id,
            "vehicle_type": template.vehicle_type,
            "structure": template.structure,
            "equipment": template.equipment,
            "cargo_securement": template.cargo_securement,
            "description": template.description,
            "capacity_t": template.capacity_t,
            "volume_m3": template.volume_m3,
            "palette_exchange": template.palette_exchange,
            "oversize": template.oversize,
            "price": template.price,
            "currency": template.currency,
            "origin_country": template.origin_country,
            "origin_postcode": template.origin_postcode,
            "origin_city": template.origin_city,
            "origin_diff": template.origin_diff,
            "destination_country": template.destination_country,
            "destination_postcode": template.destination_postcode,
            "destination_city": template.destination_city,
            "destination_diff": template.destination_diff,
            "load_type": template.load_type
        }
    })


@vehicles_bp.route('/template/delete/<int:template_id>', methods=['POST'])
@login_required
@no_cache
def delete_vehicle_template(template_id):
    template = SavedVehicle.query.filter_by(
        id=template_id,
        user_id=current_user.user_id,
        save_type='template'
    ).first()

    if not template:
        return jsonify({'success': False, 'error': 'A sablon nem található.'})

    db.session.delete(template)
    db.session.commit()
    return jsonify({'success': True})
