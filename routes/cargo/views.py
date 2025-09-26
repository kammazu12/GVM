# routes/cargo/views.py
import requests
import socketio
from flask_login import login_required, current_user
from flask import request, render_template, url_for, flash, jsonify, abort
from utils import get_nearby_major_city, GEONAMES_USERNAME
from . import cargo_bp
from models import *
from extensions import *

@cargo_bp.route('/delete_cargos', methods=['POST'])
@login_required
def delete_cargos():
    data = request.get_json(silent=True) or {}
    ids_to_delete = data.get('ids', [])

    if not ids_to_delete:
        return jsonify({'error': 'Nincs kiválasztva sor!'}), 400

    try:
        cargos = Cargo.query.filter(Cargo.cargo_id.in_(ids_to_delete)).all()
        deleted_ids = []
        for cargo in cargos:
            # Ownership check: only owner of the cargo can delete
            if cargo.user_id != current_user.user_id:
                continue

            # Manually delete related chat messages for offers on this cargo
            offer_ids = [o.offer_id for o in cargo.offers]
            if offer_ids:
                ChatMessage.query.filter(ChatMessage.offer_id.in_(offer_ids)).delete(synchronize_session=False)
                Offer.query.filter(Offer.offer_id.in_(offer_ids)).delete(synchronize_session=False)

            db.session.delete(cargo)
            deleted_ids.append(cargo.cargo_id)

        db.session.commit()
        return jsonify({'success': True, 'deleted_ids': deleted_ids})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@cargo_bp.route('/delete_cargo/<int:cargo_id>', methods=['DELETE'])
@login_required
def delete_cargo(cargo_id):
    cargo = db.session.get(Cargo, cargo_id)
    if not cargo:
        return jsonify({"success": False, "error": "Cargo not found"}), 404

    if cargo.user_id != current_user.user_id:
        return jsonify({"success": False, "error": "Forbidden"}), 403

    try:
        # Delete related messages and offers explicitly for safety
        offer_ids = [o.offer_id for o in cargo.offers]
        if offer_ids:
            ChatMessage.query.filter(ChatMessage.offer_id.in_(offer_ids)).delete(synchronize_session=False)
            Offer.query.filter(Offer.offer_id.in_(offer_ids)).delete(synchronize_session=False)

        db.session.delete(cargo)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@cargo_bp.route('/republish_cargos', methods=['POST'])
def republish_cargos():
    data = request.get_json()
    ids = data.get('ids', [])
    now = datetime.now()
    cooldown = timedelta(seconds=30)

    cargos = Cargo.query.filter(Cargo.cargo_id.in_(ids)).all()
    republished = []

    for cargo in cargos:
        if cargo.last_republished_at and now - cargo.last_republished_at < cooldown:
            continue  # kihagyjuk a fuvarokat, amelyek még cooldown alatt vannak
        cargo.created_at = now
        cargo.last_republished_at = now
        republished.append(cargo.cargo_id)

    db.session.commit()
    return jsonify({
        "success": True,
        "republished": republished,
        "now": now.strftime('%Y-%m-%d %H:%M:%S')
    })


@cargo_bp.route('/cargo', methods=["GET", "POST"])
@login_required
def cargo():
    if request.method == "POST":
        print(request.form.to_dict())

        # --- Helper: collect_values támogatja mind a name[] mind a name[index] formátumot ---
        def collect_values(base):
            # prefer base[] because getlist will return all values
            if base + '[]' in request.form:
                return request.form.getlist(base + '[]')
            pattern = re.compile(r'^' + re.escape(base) + r'\[(\d+)\]$')
            indexed = {}
            others = []
            for k in request.form.keys():
                m = pattern.match(k)
                if m:
                    indexed[int(m.group(1))] = request.form.get(k)
                elif k == base:
                    others.append(request.form.get(k))
            if indexed:
                return [indexed[i] for i in sorted(indexed.keys())]
            return others

        def split_city_string(s: str):
            """
            Bemenet: 'Nagykovácsi, HU (2094)'
            Kimenet: ('Nagykovácsi', 'HU', '2094')
            """
            city, country, postcode = None, None, None
            if not s:
                return None, None, None

            # Regex: City, CC (1234)
            match = re.match(r'^(.*?),\s*([A-Z]{2})\s*\(([\d\-]+)\)$', s.strip())
            if match:
                city = match.group(1).strip()
                country = match.group(2).strip()
                postcode = match.group(3).strip()
            else:
                # fallback: ha nincs pontos formátum
                city = s.strip()

            return city, country, postcode

        pickup_hidden_flags = [request.form.get('is_hidden_from') for _ in range(len(collect_values('from_city')))]
        dropoff_hidden_flags = [request.form.get('is_hidden_to') for _ in range(len(collect_values('to_city')))]

        # --- FEL/LE helyszínek (dinamikus tömbök) ---
        pickup_cities_raw = collect_values('from_city')
        pickup_countries = []
        pickup_postcodes = []
        pickup_cities = []

        for val in pickup_cities_raw:
            city, country, postcode = split_city_string(val)
            pickup_cities.append(city)
            pickup_countries.append(country)
            pickup_postcodes.append(postcode)


        dropoff_cities_raw = collect_values('to_city')
        dropoff_countries = []
        dropoff_postcodes = []
        dropoff_cities = []

        for val in dropoff_cities_raw:
            city, country, postcode = split_city_string(val)
            dropoff_cities.append(city)
            dropoff_countries.append(country)
            dropoff_postcodes.append(postcode)

        # Checkbox flagokat boolean-re alakítjuk
        pickup_hidden_flags = [(f == "true") for f in pickup_hidden_flags]
        dropoff_hidden_flags = [(f == "true") for f in dropoff_hidden_flags]

        print("[DEBUG split]", val, "->", city, country, postcode)

        # --- Általános űrlapmezők (ár, valuta, jármű, stb.) ---
        # Jármű
        vehicle_type = request.form.get("vehicle_type")
        structure = request.form.get("superstructure")

        # Felszereltség: a "kártyás" multiselect a formban egy hidden multiple select-et is kitölt,
        # így request.form.getlist('equipment') fog működni.
        equipment_list = request.form.getlist("equipment") or []
        equipment_str = ", ".join([v for v in equipment_list if v])

        # Rakományrögzítés (securement) - a hidden multiple select neve 'securement'
        securement_list = request.form.getlist("securement") or []
        securement_str = ", ".join([v for v in securement_list if v])

        # Certificates (ha van) - opcionális
        certificates_list = request.form.getlist("certificates") or []
        certificates_str = ", ".join([v for v in certificates_list if v])

        # Áru adatok
        description = request.form.get("description") or ""
        try:
            weight = float(request.form.get("weight")) if request.form.get("weight") else None
        except Exception:
            weight = None
        try:
            size = float(request.form.get("length")) if request.form.get("length") else None
        except Exception:
            size = None

        # Ár és valuta
        try:
            price_val = request.form.get("price")
            price = int(float(price_val)) if price_val not in (None, "") else None
        except Exception:
            price = None
        currency = request.form.get("currency") or None


        # Egyéb infok az áruról
        palette_exch = request.form.get("palette_exch") or False
        oversize = request.form.get("oversize") or False


        # Jármű megjegyzés + extra (palette/oversize) — összevonjuk a Cargo.note-ba
        vehicle_notes = request.form.get("vehicle_notes") or ""

        # Összefoglaló note (nem kötelező, de jól jön az adminban/megtekintéskor)
        note_parts = []
        if vehicle_notes:
            note_parts.append(vehicle_notes)
        note_final = "\n".join(note_parts) if note_parts else None

        # --- VALIDÁCIÓ per helyszín (egyszerű) ---
        errors = []

        # ellenőrizzük pickup dátumokat
        for i in range(len(pickup_countries)):
            s1 = parse_date(request.form.get(f'from_start_date[{i}]') or request.form.get(f'from_start_date[]'))
            s2 = parse_date(request.form.get(f'from_end_date[{i}]') or request.form.get(f'from_end_date[]'))
            if s1 and s2 and s2 < s1:
                errors.append(f"Felrakó #{i+1}: a záró dátum nem lehet korábbi, mint a kezdő dátum.")

            # ha akarsz órákra is validálni, akkor itt teheted meg (pl.: start_time_end >= start_time_start)
            # de gyakran a time-ok opcionálisak — most csak dátumokra ellenőrzünk

        # ellenőrizzük dropoff dátumokat
        for i in range(len(dropoff_countries)):
            s1 = parse_date(request.form.get(f'to_start_date[{i}]') or request.form.get(f'to_start_date[]'))
            s2 = parse_date(request.form.get(f'to_end_date[{i}]') or request.form.get(f'to_end_date[]'))
            if s1 and s2 and s2 < s1:
                errors.append(f"Lerakó #{i+1}: a záró dátum nem lehet korábbi, mint a kezdő dátum.")

        if errors:
            for e in errors:
                flash(e, "error")
            return jsonify({"success": False, "errors": errors})

        # --- MENTÉS: Cargo létrehozása (nem tartalmaz földrajzi mezőket) ---
        new_cargo = Cargo(
            company_id=current_user.company_id,
            user_id=current_user.user_id,
            description=description,
            weight=weight,
            size=size,
            price=price,
            currency=currency,
            palette_exchange=bool(palette_exch),
            oversize=bool(oversize),
            vehicle_type=vehicle_type,
            structure=structure,
            equipment=equipment_str,
            cargo_securement=securement_str,
            note=note_final,
            created_at=datetime.now()
        )

        db.session.add(new_cargo)
        db.session.flush()  # hogy legyen new_cargo.cargo_id
        print(pickup_hidden_flags)
        print(dropoff_hidden_flags)
        # --- Felrakók mentése (pickup) ---
        for i in range(len(pickup_countries)):
            country = pickup_countries[i]
            postcode = pickup_postcodes[i]
            city = pickup_cities[i]
            is_hidden = pickup_hidden_flags[i]

            # masked érték
            masked_city, masked_postcode = (get_nearby_major_city(city, country) if is_hidden else (city, postcode))
            print(f"[DEBUG] city={city}, country={country}, is_hidden={is_hidden}")
            masked_city, masked_postcode = (
                get_nearby_major_city(city, country or "HU") if is_hidden else (city, postcode))
            print(f"[DEBUG] masked_city={masked_city}, masked_postcode={masked_postcode}")

            try:
                lat_raw = request.form.get(f'from_lat[{i}]') or request.form.get('from_lat[]') or ""
                lng_raw = request.form.get(f'from_lng[{i}]') or request.form.get('from_lng[]') or ""
                lat = float(lat_raw) if lat_raw not in ("", None) else None
                lng = float(lng_raw) if lng_raw not in ("", None) else None
            except Exception:
                lat = None
                lng = None

            if not lat or not lng:
                db_city = (
                    db.session.query(City)
                    .outerjoin(CityZipcode, City.id == CityZipcode.city_id)
                    .filter(
                        City.city_name == masked_city,
                        City.country_code == country
                    )
                    .first()
                )
                if db_city:
                    lat = db_city.latitude
                    lng = db_city.longitude

            # dátum/idő mezők per helyszín
            start_date = parse_date(request.form.get(f'from_start_date[{i}]') or request.form.get(f'from_start_date[]'))
            end_date = parse_date(request.form.get(f'from_end_date[{i}]') or request.form.get(f'from_end_date[]'))

            # time mapping: from_start_time_start, from_start_time_end, from_end_time_start, from_end_time_end
            start_time_1 = parse_time(request.form.get(f'from_start_time_start[{i}]') or request.form.get(f'from_start_time_start[]'))
            start_time_2 = parse_time(request.form.get(f'from_start_time_end[{i}]') or request.form.get(f'from_start_time_end[]'))
            end_time_1 = parse_time(request.form.get(f'from_end_time_start[{i}]') or request.form.get(f'from_end_time_start[]'))
            end_time_2 = parse_time(request.form.get(f'from_end_time_end[{i}]') or request.form.get(f'from_end_time_end[]'))

            location = CargoLocation(
                type="pickup",
                country=country,
                postcode=postcode,
                city=city,
                is_hidden=is_hidden,
                masked_city=masked_city,
                masked_postcode=masked_postcode,
                latitude=lat,
                longitude=lng,
                start_date=start_date,
                end_date=end_date,
                start_time_1=start_time_1,
                start_time_2=start_time_2,
                end_time_1=end_time_1,
                end_time_2=end_time_2
            )

            new_cargo.locations.append(location)
            db.session.add(location)

        # --- Lerakók mentése (dropoff) ---
        for i in range(len(dropoff_countries)):
            country = dropoff_countries[i] if i < len(dropoff_countries) else None
            postcode = dropoff_postcodes[i] if i < len(dropoff_postcodes) else None
            city = dropoff_cities[i] if i < len(dropoff_cities) else None
            is_hidden = (dropoff_hidden_flags[i] if i < len(dropoff_hidden_flags) else False)

            masked_city, masked_postcode = (get_nearby_major_city(city, country) if is_hidden else (city, postcode))

            lat, lng = None, None
            try:
                lat_raw = request.form.get(f'to_lat[{i}]') or request.form.get('to_lat[]') or ""
                lng_raw = request.form.get(f'to_lng[{i}]') or request.form.get('to_lng[]') or ""
                lat = float(lat_raw) if lat_raw not in ("", None) else None
                lng = float(lng_raw) if lng_raw not in ("", None) else None
            except Exception:
                lat = None
                lng = None

            if not lat or not lng:
                db_city = (
                    db.session.query(City)
                    .outerjoin(CityZipcode, City.id == CityZipcode.city_id)
                    .filter(
                        City.city_name == masked_city,
                        City.country_code == country
                    )
                    .first()
                )
                if db_city:
                    lat = db_city.latitude
                    lng = db_city.longitude

                # NOTE: above line contains a defensive typo-guard in case g_lng missing.
                # In practice g_lat/g_lng come from geocode_location or None.

            # dátum/idő mezők per helyszín (to_*)
            start_date = parse_date(request.form.get(f'to_start_date[{i}]') or request.form.get(f'to_start_date[]'))
            end_date = parse_date(request.form.get(f'to_end_date[{i}]') or request.form.get(f'to_end_date[]'))

            start_time_1 = parse_time(request.form.get(f'to_start_time_start[{i}]') or request.form.get(f'to_start_time_start[]'))
            start_time_2 = parse_time(request.form.get(f'to_start_time_end[{i}]') or request.form.get(f'to_start_time_end[]'))
            end_time_1 = parse_time(request.form.get(f'to_end_time_start[{i}]') or request.form.get(f'to_end_time_start[]'))
            end_time_2 = parse_time(request.form.get(f'to_end_time_end[{i}]') or request.form.get(f'to_end_time_end[]'))

            location = CargoLocation(
                cargo_id=new_cargo.cargo_id,
                type="dropoff",
                country=country,
                postcode=postcode,
                city=city,
                is_hidden=is_hidden,
                masked_city=masked_city,
                masked_postcode=masked_postcode,
                latitude=lat,
                longitude=lng,
                start_date=start_date,
                end_date=end_date,
                start_time_1=start_time_1,
                start_time_2=start_time_2,
                end_time_1=end_time_1,
                end_time_2=end_time_2
            )
            db.session.add(location)

        save_template = request.form.get("sablonCheckbox")

        if save_template:  # ha be van pipálva, akkor elmentjük a sablonok közé
            new_template = Templates(
                user_id=current_user.user_id,
                weight=weight,
                size=size,
                price=price if price else None,
                currency=currency,
                description=description,
                vehicle_type=vehicle_type,
                structure=structure,
                equipment=equipment_str,
                cargo_securement=securement_str,
                note=note_final
            )
            db.session.add(new_template)
            db.session.flush()  # kell az ID-hoz

            # pickup-ok
            for i in range(len(pickup_countries)):
                loc = TemplateLocations(
                    template_id=new_template.id,
                    type="pickup",
                    country=pickup_countries[i],
                    postcode=pickup_postcodes[i],
                    city=pickup_cities[i],
                    is_hidden=pickup_hidden_flags[i] if i < len(pickup_hidden_flags) else False
                )
                db.session.add(loc)

            # dropoff-ok
            for i in range(len(dropoff_countries)):
                loc = TemplateLocations(
                    template_id=new_template.id,
                    type="dropoff",
                    country=dropoff_countries[i],
                    postcode=dropoff_postcodes[i],
                    city=dropoff_cities[i],
                    is_hidden=dropoff_hidden_flags[i] if i < len(dropoff_hidden_flags) else False
                )
                db.session.add(loc)

            db.session.commit()
            flash("Sablon elmentve!", "success")

        # --- Commit ---
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash("Hiba történt mentés közben: " + str(e), "error")
            return jsonify({"success": False, "error": str(e)})

        flash("Új rakomány sikeresen hozzáadva!", "success")
        return jsonify({"success": True})

    # GET ág: listák a sablon rendereléséhez
    vehicles = Vehicle.query.all()
    cargos = Cargo.query.filter_by(company_id=current_user.company_id).all()
    templates = Templates.query.filter_by(user_id=current_user.user_id).all()

    # GET ág végén, a render_template előtt
    templates_dict = []
    for t in templates:
        templates_dict.append({
            "id": t.id,
            "weight": t.weight,
            "size": t.size,
            "price": t.price,
            "currency": t.currency,
            "description": t.description,
            "vehicle_type": t.vehicle_type,
            "structure": t.structure,
            "equipment": t.equipment,  # ha string pl. "2. sofőr, ADR"
            "cargo_securement": t.cargo_securement,
            "note": t.note,
            "locations": [
                {
                    "type": loc.type,
                    "country": loc.country,
                    "postcode": loc.postcode,
                    "city": loc.city,
                    "is_hidden": loc.is_hidden,
                }
                for loc in t.locations
            ]
        })

    return render_template("cargo.html", user=current_user, vehicles=vehicles, cargos=cargos, templates=templates_dict)


@cargo_bp.route('/offer', methods=['POST'])
@login_required
def offer_create():
    cargo_id = request.form.get('cargo_id')
    price = request.form.get('price')
    pickup_date = request.form.get('pickup_date')
    arrival_date = request.form.get('delivery_date')

    if not cargo_id or not price:
        return jsonify(success=False, message="Hiányzó adat"), 400

    try:
        cargo_id_int = int(cargo_id)
        price_val = float(price)
    except (ValueError, TypeError):
        return jsonify(success=False, message="Érvénytelen adat"), 400

    cargo = Cargo.query.get(cargo_id_int)
    if not cargo:
        return jsonify(success=False, message="A rakomány nem található"), 404

    # ---- Ellenőrizzük, van-e már ajánlat ugyanattól a felhasználótól ----
    existing_offer = Offer.query.filter_by(cargo_id=cargo.cargo_id, offer_user_id=current_user.user_id).first()

    if existing_offer:
        # Felülírjuk az előző ajánlatot
        existing_offer.price = price_val
        existing_offer.currency = request.form.get('currency', 'EUR')
        existing_offer.note = request.form.get('note', '')
        existing_offer.pickup_date = datetime.strptime(pickup_date, "%Y-%m-%d")
        existing_offer.arrival_date = datetime.strptime(arrival_date, "%Y-%m-%d")
        existing_offer.created_at = datetime.now()
        existing_offer.seen = False
        db.session.commit()
        offer = existing_offer
    else:
        # Új ajánlat létrehozása
        offer = Offer(
            cargo_id=cargo.cargo_id,
            offer_user_id=current_user.user_id,
            price=price_val,
            currency=request.form.get('currency', 'EUR'),
            note=request.form.get('note', ''),
            pickup_date=datetime.strptime(pickup_date, "%Y-%m-%d"),
            arrival_date=datetime.strptime(arrival_date, "%Y-%m-%d"),
            created_at=datetime.now(),
            seen=False
        )
        db.session.add(offer)
        db.session.commit()

    offer_user = User.query.get(offer.offer_user_id)
    profile_pic = offer_user.profile_picture if offer_user and offer_user.profile_picture else 'default.png'

    # pickup és dropoff helyek
    origin = destination = ""
    if cargo.locations:
        for loc in cargo.locations:
            if loc.type == "pickup":
                origin = loc.city
            elif loc.type == "dropoff":
                destination = loc.city

    # ---- valós idejű értesítés ----
    notification_data = {
        'offer_id': offer.offer_id,
        'cargo_id': cargo.cargo_id,
        'from_user_id': offer.offer_user_id,
        'to_user_id': cargo.user_id,
        'from_user': f"{current_user.first_name} {current_user.last_name}",
        'user_company': getattr(offer_user.company, 'name', '') if offer_user.company else '',
        'profile_picture': url_for('static', filename='uploads/profile_pictures/' + profile_pic),
        'price': offer.price,
        'currency': offer.currency,
        'note': offer.note,
        'origin': origin,
        'destination': destination,
        'pickup_date': offer.pickup_date.strftime('%Y-%m-%d') if offer.pickup_date else '',
        'arrival_date': offer.arrival_date.strftime('%Y-%m-%d') if offer.arrival_date else '',
    }
    room = f'user_{cargo.user_id}'
    socketio.emit('new_offer', notification_data, room=room)

    return jsonify(success=True, offer_id=offer.offer_id), 201


@cargo_bp.route('/get_cargo/<int:cargo_id>')
@login_required
def get_cargo(cargo_id):
    cargo = Cargo.query.get(cargo_id)
    if not cargo:
        return jsonify({'error': 'Nem található rakomány'}), 404

    # rendezett pickup & dropoff listák (id növekvő)
    pickups = [l for l in sorted(cargo.locations, key=lambda x: x.id) if l.type == 'pickup']
    dropoffs = [l for l in sorted(cargo.locations, key=lambda x: x.id) if l.type == 'dropoff']

    def loc_to_dict(loc):
        return {
            'id': loc.id,
            'type': loc.type,
            'country': loc.country or "",
            'postcode': loc.postcode or "",
            'city': loc.city or "",
            'is_hidden': bool(loc.is_hidden),
            'masked_city': loc.masked_city or "",
            'masked_postcode': loc.masked_postcode or "",
            'latitude': loc.latitude if loc.latitude is not None else "",
            'longitude': loc.longitude if loc.longitude is not None else "",
            'start_date': loc.start_date.isoformat() if loc.start_date else "",
            'end_date': loc.end_date.isoformat() if loc.end_date else "",
            'start_time_1': loc.start_time_1.isoformat() if loc.start_time_1 else "",
            'start_time_2': loc.start_time_2.isoformat() if loc.start_time_2 else "",
            'end_time_1': loc.end_time_1.isoformat() if loc.end_time_1 else "",
            'end_time_2': loc.end_time_2.isoformat() if loc.end_time_2 else "",
        }

    cargo_data = {
        'cargo_id': cargo.cargo_id or 0,
        'company_id': cargo.company_id or 0,
        'user_id': cargo.user_id or 0,
        'description': cargo.description or "",
        'weight': cargo.weight or 0,
        'length': cargo.size or 0,
        'price': cargo.price or 0,
        'currency': cargo.currency or "",
        'vehicle_type': cargo.vehicle_type or "",
        'palette_exchange': cargo.palette_exchange or False,
        'oversize': cargo.oversize or False,
        # structure/stucture compatibility
        'structure': getattr(cargo, 'structure', None) or getattr(cargo, 'stucture', '') or "",
        'equipment': cargo.equipment or "",
        'cargo_securement': cargo.cargo_securement or "",
        'note': cargo.note or "",
        'pickups': [loc_to_dict(l) for l in pickups],
        'dropoffs': [loc_to_dict(l) for l in dropoffs],
        'created_at': cargo.created_at.isoformat() if cargo.created_at else ""
    }
    return jsonify(cargo_data)


@cargo_bp.route('/update_cargo/<int:cargo_id>', methods=['POST'])
@login_required
def update_cargo(cargo_id):
    # JSON expected
    try:
        data = request.get_json(force=True)
    except Exception as e:
        current_app.logger.exception("JSON parse error in update_cargo")
        return jsonify({'error': 'Nem sikerült JSON-t olvasni.', 'details': str(e)}), 400

    if data is None:
        return jsonify({'error': 'Nincs payload'}), 400

    cargo = Cargo.query.get(cargo_id)
    if not cargo:
        return jsonify({'error': 'Nem található rakomány'}), 404

    updated = []
    errors = []

    # --- egyszerű cargo mezők ---
    # támogatott mezők: length, weight, price, currency, description, vehicle_type, structure/stucture, note
    if 'length' in data:
        try:
            cargo.size = float(data.get('length')) if data.get('length') not in (None, '') else None
            updated.append('size')
        except Exception:
            errors.append('Hibás length érték')

    if 'weight' in data:
        try:
            cargo.weight = float(data.get('weight')) if data.get('weight') not in (None, '') else None
            updated.append('weight')
        except Exception:
            errors.append('Hibás weight érték')

    if 'price' in data:
        try:
            cargo.price = int(float(data.get('price'))) if data.get('price') not in (None, '') else None
            updated.append('price')
        except Exception:
            errors.append('Hibás price érték')

    if 'currency' in data:
        cargo.currency = data.get('currency') or ''
        updated.append('currency')

    if 'description' in data:
        cargo.description = data.get('description') or ''
        updated.append('description')

    if 'vehicle_type' in data:
        cargo.vehicle_type = data.get('vehicle_type') or ''
        updated.append('vehicle_type')

    # support both spellings
    if 'structure' in data:
        cargo.structure = data.get('structure') or ''
        updated.append('structure')
    elif 'stucture' in data:
        cargo.structure = data.get('stucture') or ''
        updated.append('structure')

    # equipment can be array or string
    if 'equipment' in data:
        ev = data.get('equipment')
        if isinstance(ev, list):
            cargo.equipment = ', '.join([str(x) for x in ev if x])
        elif ev is None:
            cargo.equipment = ''
        else:
            cargo.equipment = str(ev)
        updated.append('equipment')

    if 'cargo_securement' in data:
        cargo.cargo_securement = data.get('cargo_securement') or ''
        updated.append('cargo_securement')

    if 'note' in data:
        cargo.note = data.get('note') or ''
        updated.append('note')

    if 'palette_exchange' in data:
        cargo.palette_exchange = bool(data.get('palette_exchange'))
        updated.append('palette_exchange')

    if 'oversize' in data:
        cargo.oversize = bool(data.get('oversize'))
        updated.append('oversize')

    # --- Lokációk kezelése ---
    # 1) Ha payload tartalmaz 'locations' tömböt, akkor abból dolgozunk:
    #    - ha id van -> update
    #    - ha nincs id -> create új lokáció
    #    - ha 'delete_ids' van -> töröljük azokat
    # 2) Ha nincs locations, de vannak from_/to_ mezők, akkor első pickup / utolsó dropoff frissítése

    # Helper: safe accessor for location attribute names used in payloads
    def set_loc_field(loc, key, val):
        if key in ('start_date','end_date'):
            setattr(loc, key, parse_date(val))
        elif key.startswith('start_time') or key.startswith('end_time'):
            setattr(loc, key, parse_time(val))
        else:
            setattr(loc, key, val)

    # Törlendő id-k
    if isinstance(data.get('delete_ids'), list):
        for del_id in data.get('delete_ids'):
            try:
                lid = int(del_id)
                loc_obj = CargoLocation.query.get(lid)
                if loc_obj and loc_obj.cargo_id == cargo.cargo_id:
                    db.session.delete(loc_obj)
                    updated.append(f'delete_location_{lid}')
            except Exception:
                continue

    # process explicit locations array (előnyben)
    if isinstance(data.get('locations'), list):
        incoming_locations = data.get('locations')
        incoming_ids = set()
        for loc_item in incoming_locations:
            if 'id' in loc_item and loc_item['id']:
                incoming_ids.add(int(loc_item['id']))

        # Delete locations that are in DB but not in the incoming payload
        existing_locs = {l.id: l for l in CargoLocation.query.filter_by(cargo_id=cargo.cargo_id).all()}
        for loc_id, loc in existing_locs.items():
            if loc_id not in incoming_ids:
                db.session.delete(loc)
                updated.append(f'deleted_location_{loc_id}')

        # Now process the incoming locations as before
        for loc_item in incoming_locations:
            lid = loc_item.get('id')
            ltype = loc_item.get('type') or 'pickup'
            if lid:
                loc = CargoLocation.query.get(int(lid))
                if not loc or loc.cargo_id != cargo.cargo_id:
                    current_app.logger.debug("Lokáció nincs vagy nem tartozik a cargo-hoz: %s", lid)
                    continue
                # update fields
                city_changed = False
                postcode_changed = False
                country_changed = False
                is_hidden_changed = False
                for k,v in loc_item.items():
                    if k == 'id' or k == 'type':
                        continue
                    if k in ('country','postcode','city','is_hidden','masked_city','masked_postcode',
                             'start_date','end_date','start_time_1','start_time_2', 'end_time_1','end_time_2'):
                        try:
                            if k == 'is_hidden':
                                v_bool = bool(v)
                                if getattr(loc, 'is_hidden', False) != v_bool:
                                    is_hidden_changed = True
                                loc.is_hidden = v_bool
                            elif k == 'city':
                                if getattr(loc, 'city', None) != v:
                                    city_changed = True
                                loc.city = v
                            elif k == 'postcode':
                                if getattr(loc, 'postcode', None) != v:
                                    postcode_changed = True
                                loc.postcode = v
                            elif k == 'country':
                                if getattr(loc, 'country', None) != v:
                                    country_changed = True
                                loc.country = v
                            else:
                                set_loc_field(loc, k, v)
                        except Exception as ex:
                            current_app.logger.debug("Nem sikerült beállítani lokáció mezőt %s=%r (%s)", k, v, ex)
                # --- Always update coordinates from payload if present, else geocode ---
                lat = loc_item.get('latitude')
                lng = loc_item.get('longitude')
                if lat not in (None, '') and lng not in (None, ''):
                    try:
                        loc.latitude = float(lat)
                        loc.longitude = float(lng)
                    except Exception:
                        loc.latitude = None
                        loc.longitude = None
                else:
                    city_obj = City.query.filter_by(
                        city_name=loc.city,
                        country_code=loc.country
                    ).first()
                    if city_obj:
                        loc.latitude = getattr(city_obj, "latitude", None)
                        loc.longitude = getattr(city_obj, "longitude", None)
                    else:
                        loc.latitude = None
                        loc.longitude = None

                # --- Masked fields logic (unchanged) ---
                if city_changed or postcode_changed or country_changed or is_hidden_changed:
                    if not loc.is_hidden:
                        loc.masked_city = loc.city
                        loc.masked_postcode = loc.postcode
                    else:
                        loc.masked_city, loc.masked_postcode = get_nearby_major_city(loc.city, loc.country)
                updated.append(f'location_{loc.id}')
            else:
                # create new location
                try:
                    is_hidden = bool(loc_item.get('is_hidden', False))
                    city = loc_item.get('city') or ''
                    country = loc_item.get('country') or ''
                    postcode = loc_item.get('postcode') or ''
                    if not is_hidden:
                        masked_city = city
                        masked_postcode = postcode
                    else:
                        masked_city, masked_postcode = get_nearby_major_city(city, country)
                    # Use lat/lng from payload if present, else geocode
                    lat = loc_item.get('latitude')
                    lng = loc_item.get('longitude')
                    if lat in (None, '') or lng in (None, ''):
                        city_obj = City.query.filter_by(
                            city_name=city,
                            country_code=country
                        ).first()
                        if city_obj:
                            lat = getattr(city_obj, "latitude", None)
                            lng = getattr(city_obj, "longitude", None)
                        else:
                            lat, lng = None, None
                    new_loc = CargoLocation(
                        cargo_id = cargo.cargo_id,
                        type = ltype,
                        country = country,
                        postcode = postcode,
                        city = city,
                        is_hidden = is_hidden,
                        masked_city = masked_city,
                        masked_postcode = masked_postcode,
                        latitude = float(lat) if lat not in (None, '') else None,
                        longitude = float(lng) if lng not in (None, '') else None,
                        start_date = parse_date(loc_item.get('start_date')),
                        end_date = parse_date(loc_item.get('end_date')),
                        start_time_1 = parse_time(loc_item.get('start_time_1')),
                        start_time_2 = parse_time(loc_item.get('start_time_2')),
                        end_time_1 = parse_time(loc_item.get('end_time_1')),
                        end_time_2 = parse_time(loc_item.get('end_time_2')),
                    )
                    db.session.add(new_loc)
                    db.session.flush()
                    updated.append(f'new_location_{new_loc.id}')
                except Exception as ex:
                    current_app.logger.exception("Hiba új lokáció létrehozásakor")
                    errors.append(f'Hiba új lokáció létrehozásakor: {str(ex)}')
    else:
        # nincs explicit locations tömb -> kezeljük a legacy mezőket (from_/to_ stb.)
        # Frissítjük az első pickupot és az utolsó dropoffot (ha léteznek)
        pickups = [l for l in sorted(cargo.locations, key=lambda x: x.id) if l.type == 'pickup']
        dropoffs = [l for l in sorted(cargo.locations, key=lambda x: x.id) if l.type == 'dropoff']

        first_pickup = pickups[0] if pickups else None
        last_dropoff = dropoffs[-1] if dropoffs else None

        # from_ mezők -> first_pickup
        from_keys = ('from_country','from_postcode','from_city','is_hidden_from',
                     'from_start_date','from_start_time_start','from_start_time_end',
                     'from_end_date','from_end_time_start','from_end_time_end',
                     'masked_origin_city','masked_origin_postcode','from_lat','from_lng')
        if any(k in data for k in from_keys) and first_pickup:
            if 'from_country' in data: first_pickup.country = data.get('from_country') or ''
            if 'from_postcode' in data: first_pickup.postcode = data.get('from_postcode') or ''
            if 'from_city' in data: first_pickup.city = data.get('from_city') or ''
            if 'is_hidden_from' in data: first_pickup.is_hidden = bool(data.get('is_hidden_from'))
            if 'masked_origin_city' in data: first_pickup.masked_city = data.get('masked_origin_city') or ''
            if 'masked_origin_postcode' in data: first_pickup.masked_postcode = data.get('masked_origin_postcode') or ''
            if 'from_lat' in data:
                try: first_pickup.latitude = float(data.get('from_lat'))
                except Exception: pass
            if 'from_lng' in data:
                try: first_pickup.longitude = float(data.get('from_lng'))
                except Exception: pass
            # dátum/idő lefordítása
            if 'from_start_date' in data: first_pickup.start_date = parse_date(data.get('from_start_date'))
            if 'from_start_time_start' in data: first_pickup.start_time_1 = parse_time(data.get('from_start_time_start'))
            if 'from_start_time_end' in data: first_pickup.start_time_2 = parse_time(data.get('from_start_time_end'))
            if 'from_end_date' in data: first_pickup.end_date = parse_date(data.get('from_end_date'))
            if 'from_end_time_start' in data: first_pickup.end_time_1 = parse_time(data.get('from_end_time_start'))
            if 'from_end_time_end' in data: first_pickup.end_time_2 = parse_time(data.get('from_end_time_end'))
            updated.append('first_pickup')

        # to_ mezők -> last_dropoff
        to_keys = ('to_country','to_postcode','to_city','is_hidden_to',
                   'to_start_date','to_start_time_start','to_start_time_end',
                   'to_end_date','to_end_time_start','to_end_time_end',
                   'masked_destination_city','masked_destination_postcode','to_lat','to_lng')
        if any(k in data for k in to_keys) and last_dropoff:
            if 'to_country' in data: last_dropoff.country = data.get('to_country') or ''
            if 'to_postcode' in data: last_dropoff.postcode = data.get('to_postcode') or ''
            if 'to_city' in data: last_dropoff.city = data.get('to_city') or ''
            if 'is_hidden_to' in data: last_dropoff.is_hidden = bool(data.get('is_hidden_to'))
            if 'masked_destination_city' in data: last_dropoff.masked_city = data.get('masked_destination_city') or ''
            if 'masked_destination_postcode' in data: last_dropoff.masked_postcode = data.get('masked_destination_postcode') or ''
            if 'to_lat' in data:
                try: last_dropoff.latitude = float(data.get('to_lat'))
                except Exception: pass
            if 'to_lng' in data:
                try: last_dropoff.longitude = float(data.get('to_lng'))
                except Exception: pass
            # dátum/idő
            if 'to_start_date' in data: last_dropoff.start_date = parse_date(data.get('to_start_date'))
            if 'to_start_time_start' in data: last_dropoff.start_time_1 = parse_time(data.get('to_start_time_start'))
            if 'to_start_time_end' in data: last_dropoff.start_time_2 = parse_time(data.get('to_start_time_end'))
            if 'to_end_date' in data: last_dropoff.end_date = parse_date(data.get('to_end_date'))
            if 'to_end_time_start' in data: last_dropoff.end_time_1 = parse_time(data.get('to_end_time_start'))
            if 'to_end_time_end' in data: last_dropoff.end_time_2 = parse_time(data.get('to_end_time_end'))
            updated.append('last_dropoff')

    if errors:
        return jsonify({'error': 'Hiba a mezők feldolgozásakor', 'details': errors}), 400

    # commit once
    try:
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        current_app.logger.exception("Adatbázis mentés sikertelen update_cargo")
        return jsonify({'error': 'Adatbázis mentés sikertelen', 'details': str(ex)}), 500

    # készítsük össze a visszaküldött objektumot (ugyanaz struktúra mint get_cargo)
    # újra lekérjük a lokációkat
    pickups = [l for l in sorted(cargo.locations, key=lambda x: x.id) if l.type == 'pickup']
    dropoffs = [l for l in sorted(cargo.locations, key=lambda x: x.id) if l.type == 'dropoff']

    def loc_to_dict(loc):
        return {
            'id': loc.id,
            'type': loc.type,
            'country': loc.country or "",
            'postcode': loc.postcode or "",
            'city': loc.city or "",
            'is_hidden': bool(loc.is_hidden),
            'masked_city': loc.masked_city or "",
            'masked_postcode': loc.masked_postcode or "",
            'latitude': loc.latitude if loc.latitude is not None else "",
            'longitude': loc.longitude if loc.longitude is not None else "",
            'start_date': loc.start_date.isoformat() if loc.start_date else "",
            'end_date': loc.end_date.isoformat() if loc.end_date else "",
            'start_time_1': loc.start_time_1.isoformat() if loc.start_time_1 else "",
            'start_time_2': loc.start_time_2.isoformat() if loc.start_time_2 else "",
            'end_time_1': loc.end_time_1.isoformat() if loc.end_time_1 else "",
            'end_time_2': loc.end_time_2.isoformat() if loc.end_time_2 else "",
        }

    cargo_data = {
        'cargo_id': cargo.cargo_id or 0,
        'company_id': cargo.company_id or 0,
        'user_id': cargo.user_id or 0,
        'description': cargo.description or "",
        'weight': cargo.weight or 0,
        'length': cargo.size or 0,
        'price': cargo.price or 0,
        'currency': cargo.currency or "",
        'vehicle_type': cargo.vehicle_type or "",
        'structure': getattr(cargo, 'structure', None) or getattr(cargo, 'stucture', '') or "",
        'equipment': cargo.equipment or "",
        'cargo_securement': cargo.cargo_securement or "",
        'note': cargo.note or "",
        'pickups': [loc_to_dict(l) for l in pickups],
        'dropoffs': [loc_to_dict(l) for l in dropoffs],
        'updated_fields': updated
    }

    return jsonify({'success': True, 'cargo': cargo_data})


@cargo_bp.route('/api/cities')
def search_cities():
    q = request.args.get("q", "").strip()
    if not q or len(q) < 2:
        return jsonify([])

    cities = (
        db.session.query(City)
        .outerjoin(AlterName, City.id == AlterName.city_id)
        .filter(
            (City.city_name.ilike(f"%{q}%")) |
            (AlterName.alternames.ilike(f"%{q}%")) |
            (db.cast(City.zipcode, db.String).ilike(f"%{q}%"))
        )
        .limit(20)
        .all()
    )

    return jsonify([
        {
            "id": c.id,
            "city_name": c.city_name,
            "zipcode": c.zipcode,
            "latitude": c.latitude,
            "longitude": c.longitude,
            "country_code": c.country_code
        }
        for c in cities
    ])


@cargo_bp.route('/offer/mark_seen/<int:offer_id>', methods=['POST'])
@login_required
def mark_offer_seen(offer_id):
    offer = Offer.query.filter_by(offer_id=offer_id, offer_user_id=current_user.user_id).first()
    print("mark_offer_seen called!", offer_id)
    offer = Offer.query.get(offer_id)
    print("Offer from DB:", offer)
    if not offer:
        return jsonify({"success": False, "error": "Offer not found"}), 404

    if offer.cargo.user_id != current_user.user_id:
        return jsonify({"success": False, "error": "Not allowed"}), 403
    print(offer)

    if not offer.seen:
        offer.seen = True
        db.session.commit()

    return jsonify({"success": True})


@cargo_bp.route('/offers/accept/<int:offer_id>', methods=['POST'])
def accept_offer(offer_id):
    print(f"[ACCEPT] Offer {offer_id} elfogadási kérelem érkezett")
    offer = Offer.query.get_or_404(offer_id)
    cargo = Cargo.query.get_or_404(offer.cargo_id)
    print(f"[ACCEPT] Cargo ID: {cargo.cargo_id}, Cargo owner: {cargo.user_id}, Current user: {current_user.user_id}")

    if cargo.user_id != current_user.user_id:
        print(f"[ACCEPT] Jogosultsági hiba: user {current_user.user_id} nem a cargo tulaj")
        return jsonify({"success": False, "error": "Nincs jogosultság."}), 403

    offer.status = "accepted"
    print(f"[ACCEPT] Cargo {cargo.cargo_id} státusz -> accepted")

    auto_delete = OfferAutoDelete(
        offer_id=offer.offer_id,
        created_at=datetime.now(),
        delete_at=datetime.now() + timedelta(hours=24)
    )
    db.session.add(auto_delete)
    db.session.commit()

    print(f"[ACCEPT] Offer {offer_id} és Cargo {cargo.cargo_id} frissítve, OfferAutoDelete létrehozva")
    return jsonify({"success": True})


@cargo_bp.route('/offers/decline/<int:offer_id>', methods=['POST'])
def decline_offer(offer_id):
    print(f"[DECLINE] Offer {offer_id} elutasítási kérelem érkezett")
    offer = Offer.query.get_or_404(offer_id)
    cargo = Cargo.query.get_or_404(offer.cargo_id)
    print(f"[DECLINE] Cargo ID: {cargo.cargo_id}, Cargo owner: {cargo.user_id}, Current user: {current_user.user_id}")

    if cargo.user_id != current_user.user_id:
        print(f"[DECLINE] Jogosultsági hiba: user {current_user.user_id} nem a cargo tulaj")
        return jsonify({"success": False, "error": "Nincs jogosultság."}), 403

    offer.status = "declined"
    print(f"[DECLINE] Cargo {cargo.cargo_id} státusz -> declined")

    db.session.add(cargo)

    auto_delete = OfferAutoDelete(
        offer_id=offer.offer_id,
        created_at=datetime.now(),
        delete_at=datetime.now() + timedelta(hours=24)
    )
    db.session.add(auto_delete)
    db.session.commit()

    print(f"[DECLINE] Offer {offer_id} és Cargo {cargo.cargo_id} frissítve, OfferAutoDelete létrehozva")
    return jsonify({"success": True})


@cargo_bp.route("/offer/update/<int:offer_id>", methods=["POST"])
@login_required
def update_offer(offer_id):
    offer = Offer.query.get_or_404(offer_id)

    # Csak az ajánlattevő módosíthat
    if offer.offer_user_id != current_user.user_id:
        abort(403)

    data = request.get_json()
    try:
        offer.pickup_date = datetime.strptime(data.get("pickup_date"), "%Y-%m-%d").date()
        offer.arrival_date = datetime.strptime(data.get("arrival_date"), "%Y-%m-%d").date()
        offer.price = float(data.get("price"))
        offer.currency = data.get("currency")
        offer.note = data.get("note")
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@cargo_bp.route("<int:cargo_id>/details")
def cargo_details(cargo_id):
    cargo = Cargo.query.get_or_404(cargo_id)
    return render_template("cargo_details.html", cargo=cargo)


@cargo_bp.route('/geocode_location')
def geocode_location_api():
    country = request.args.get('country', '')
    city = request.args.get('city', '')
    postcode = request.args.get('postcode', '')
    try:
        q = ', '.join([x for x in [postcode, city, country] if x])
        if not q:
            return jsonify({'lat': None, 'lng': None, 'error': 'No query'}), 400
        res = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={'q': q, 'format': 'json', 'limit': 1},
            headers={'User-Agent': 'GVM-app'},
            timeout=5
        )
        if res.status_code == 200:
            j = res.json()
            if j:
                return jsonify({'lat': float(j[0]['lat']), 'lng': float(j[0]['lon'])})
        return jsonify({'lat': None, 'lng': None, 'error': 'Not found'}), 404
    except Exception as e:
        return jsonify({'lat': None, 'lng': None, 'error': str(e)}), 500


@cargo_bp.route("/ajax/city_search")
def city_search():
    term = request.args.get("q", "").strip()
    if len(term) < 2:
        return jsonify([])

    words = term.lower().split()
    has_number = any(re.search(r'\d', w) for w in words)

    query = db.session.query(City).outerjoin(CityZipcode, City.id == CityZipcode.city_id)

    for w in words:
        if len(w) == 2:  # országkód
            query = query.filter(City.country_code.ilike(w))
        elif re.search(r'\d', w):  # bármilyen számjegy a szóban → zip
            query = query.filter(CityZipcode.zipcode.ilike(f"%{w}%"))
        else:
            query = query.filter(City.city_name.ilike(f"%{w}%"))

    # Rendezés
    if has_number:
        query = query.order_by(CityZipcode.zipcode.asc(), City.city_name.asc())
    else:
        query = query.order_by(City.city_name.asc())

    results = query.limit(10).all()

    data = []
    for city in results:
        zipcodes = [zc.zipcode for zc in city.zipcodes] if city.zipcodes else []
        first_zip = zipcodes[0] if zipcodes else city.zipcode
        data.append({
            "id": city.id,
            "city_name": city.city_name,
            "country_code": city.country_code,
            "zipcode": first_zip
        })

    return jsonify(data)


