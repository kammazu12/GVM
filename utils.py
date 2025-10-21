# utils.py
import math
from datetime import *
import os
import uuid
import unicodedata
import re
import requests
from flask import current_app, request, make_response
from functools import wraps
from flask_mail import Message
from PIL import Image
import pillow_heif
from google_auth_oauthlib.flow import Flow
from unidecode import unidecode
from extensions import *
from sqlalchemy import func, or_, and_
import threading
from models.city import City, CityZipcode
import logging
from datetime import datetime
import geojson
from models.cargo import *
from models.vehicle import *
from models.user import *
from models.company import *
from models.city import *
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
from dotenv import load_dotenv
load_dotenv()

GEONAMES_USERNAME = os.getenv("GEONAMES_USERNAME")
def get_google_flow():
    return Flow.from_client_secrets_file(
        os.getenv("GOOGLE_CLIENT_SECRET_FILE"),
        scopes=['https://www.googleapis.com/auth/gmail.readonly'],
        redirect_uri=os.getenv("GOOGLE_REDIRECT_URI")
    )

# flow = get_google_flow()
MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True") == "True"
MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "False") == "True"
MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER")

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'heic'}

email_cache = {}  # key: email_id, value: full message
user_tokens = {}  # key: email_id, value: full message


def no_cache(view):
    @wraps(view)
    def no_cache_view(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    return no_cache_view


def find_expired_items():
    from models.cargo import CargoLocation, Cargo

    """Lejárt rakományok és rakterek listázása"""
    today = date.today()

    # --- 1. Lejárt rakományok ---
    expired_cargos = (
        db.session.query(Cargo)
        .join(CargoLocation)
        .group_by(Cargo.cargo_id)
        .having(db.func.max(CargoLocation.end_date) < today)
        .all()
    )

    # --- 2. Lejárt rakterek ---
    expired_vehicles = Vehicle.query.filter(Vehicle.available_until < today).all()

    return expired_cargos, expired_vehicles


def init_google_auth():
    flow = get_google_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    return flow, authorization_url, state


def save_uploaded_image(file, subfolder, prefix="file_", allowed_extensions=None):
    if not file:
        return False, "Nincs fájl kiválasztva."
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if allowed_extensions and ext not in allowed_extensions:
        return False, "Érvénytelen fájlformátum."
    filename = f"{prefix}{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(current_app.root_path, 'static/uploads', subfolder)
    os.makedirs(save_path, exist_ok=True)
    try:
        if ext == 'heic':
            heif_image = pillow_heif.read_heif(file)
            image = Image.frombytes(heif_image.mode, heif_image.size, heif_image.data)
            filename = filename.rsplit('.', 1)[0] + '.jpg'
            image.save(os.path.join(save_path, filename), format='JPEG')
        else:
            file.save(os.path.join(save_path, filename))
    except Exception as e:
        return False, f"Hiba a mentés közben: {str(e)}"
    return True, filename


def is_valid_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number"
    return True, ""


def slugify(value: str) -> str:
    if not value:
        return ''
    value = unicodedata.normalize('NFKD', value)
    value = ''.join([c for c in value if not unicodedata.combining(c)])
    value = value.lower()
    value = re.sub(r'[^a-z0-9]+', '-', value)
    value = value.strip('-')
    return value


def make_unique_slug(name, company_id=None):
    base = slugify(name)
    if company_id:
        return f"{base}-{company_id}"
    candidate = base
    i = 1
    while Company.query.filter_by(slug=candidate).first():
        i += 1
        candidate = f"{base}-{i}"
    return candidate


def send_email(to_email, subject, body):
    try:
        msg = Message(subject, recipients=[to_email])
        msg.body = body
        mail.send(msg)
    except Exception as e:
        # csak logoljuk, hogy ne dobjon hibát a néma e-mail hívás
        print("Email küldési hiba:", e)


# GeoNames segédfüggvények (get_nearby_major_city)
def get_nearby_major_city(city_name, country_code):
    """
    Adott városnév + országkód alapján lekéri a legközelebbi >= 15000 lakosú várost.
    Visszaadja: (városnév, irányítószám) – ha nincs találat, az eredetit adja vissza.
    """
    logger.info(f"[GeoNames] Keresés: város='{city_name}', ország='{country_code}'")

    params = {
        "q": city_name,
        "country": country_code,
        "maxRows": 1,
        "username": GEONAMES_USERNAME
    }

    try:
        search = requests.get("http://api.geonames.org/searchJSON", params=params, timeout=5).json()
    except Exception as e:
        logger.error(f"[GeoNames] Hiba a keresésnél: {e}")
        return city_name, None  # fallback

    if not search.get("geonames"):
        logger.warning(f"[GeoNames] Nincs találat az eredeti városra: {city_name}")
        return city_name, None

    lat = float(search['geonames'][0]['lat'])
    lng = float(search['geonames'][0]['lng'])
    logger.debug(f"[GeoNames] Eredeti város koordinátái: lat={lat}, lng={lng}")

    # Keressük a legközelebbi nagy várost
    nearby_params = {
        "lat": lat,
        "lng": lng,
        "cities": "cities15000",  # csak 15.000+ fő
        "maxRows": 1,
        "username": GEONAMES_USERNAME
    }

    try:
        nearby = requests.get("http://api.geonames.org/findNearbyPlaceNameJSON", params=nearby_params, timeout=5).json()
    except Exception as e:
        logger.error(f"[GeoNames] Hiba a közeli nagyváros keresésnél: {e}")
        return city_name, None

    if nearby.get("geonames"):
        major = nearby['geonames'][0]
        major_city = major['name']

        # 🔑 fontos: itt külön lekérjük az irányítószámot
        postcode = get_postcode(major_city, country_code)

        logger.info(f"[GeoNames] Bújtatott város: {major_city} (eredeti: {city_name}), postcode={postcode}")
        return major_city, postcode

    logger.warning(f"[GeoNames] Nincs nagyváros találat, visszaadjuk az eredetit: {city_name}")
    return city_name, None


def get_postcode(city_name, country_code):
    """
    Lekéri a város irányítószámát:
    1️⃣ Először az adatbázisban keresi (City + CityZipcode)
    2️⃣ Ha nincs találat, fallback GeoNames API
    """
    # --- 1️⃣ DB keresés ---
    db_city = (
        db.session.query(City)
        .outerjoin(CityZipcode)
        .filter(City.city_name == city_name, City.country_code == country_code)
        .first()
    )

    if db_city:
        # Ha CityZipcode táblában van
        if db_city.zipcodes:
            return db_city.zipcodes[0].zipcode
        # Ha csak City.zipcode mező van kitöltve
        if db_city.zipcode:
            return db_city.zipcode

    # --- 2️⃣ GeoNames API fallback ---
    params = {
        "placename": city_name,
        "country": country_code,
        "maxRows": 1,
        "username": GEONAMES_USERNAME
    }
    try:
        result = requests.get("http://api.geonames.org/postalCodeSearchJSON", params=params, timeout=5).json()
        if result.get("postalCodes"):
            return result["postalCodes"][0]["postalCode"]
    except Exception as e:
        logger.error(f"[GeoNames] Hiba a postalCode lekérésnél: {e}")

    # Ha semmi nem található
    return None


def send_invite_email(email, code):
    """
    Küld egy e-mailt a meghívó kóddal.
    """
    msg = Message(
        subject="LogiAI cégmeghívó",
        recipients=[email],
    )
    msg.body = f"""
Szia!

Meghívást kaptál a LogiAI oldalra a cégedhez. Használd az alábbi kódot a regisztrációhoz:

Meghívó kód: {code}

A kód 1 órán belül lejár.
"""
    mail.send(msg)


# --- Per-helyszín dátum/idő mezők: a templateben minden helyszín indexált mezőket adunk ---
# Segédfüggvényes parse-erek
def parse_date(val):
    if val is None or val == '':
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    try:
        return date.fromisoformat(str(val))
    except Exception:
        try:
            return datetime.fromisoformat(str(val)).date()
        except Exception:
            return None


def parse_time(val):
    if val is None or val == '':
        return None
    if isinstance(val, time):
        return val
    try:
        return time.fromisoformat(str(val))
    except Exception:
        # próbáljuk HH:MM formátumot
        try:
            return datetime.strptime(str(val), "%H:%M").time()
        except Exception:
            return None


def parse_float(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def lookup_coords_local(country, city):
    """
    Keres az offline City táblában a város és az ország alapján.
    Visszaad: (lat, lng) vagy (None, None)
    """
    if not city:
        current_app.logger.debug("lookup_coords_local: nincs city -> None")
        return None, None

    q = City.query

    city_norm = unidecode(city.strip().lower())  # ékezetmentesít
    country_norm = (country or '').strip().upper()

    print(f"[DEBUG] Normalized city: '{city}' -> '{city_norm}'")

    current_app.logger.debug("lookup_coords_local input -> country=%r city=%r", country_norm, city_norm)

    # 1) pontos egyezés country-val
    if country_norm:
        res = (
            q.filter(func.lower(City.city_name) == city_norm.lower(),
                     func.lower(City.country_code) == country_norm.lower())
             .order_by(City.population.desc())
             .first()
        )
        if res:
            current_app.logger.debug("lookup_coords_local match (country+city exact): %s, %s, pop=%s",
                                     res.latitude, res.longitude, res.population)
            return float(res.latitude), float(res.longitude)
        else:
            current_app.logger.debug("lookup_coords_local no match (country+city exact)")

    # 2) pontos egyezés country nélkül
    res = (
        q.filter(func.lower(City.city_name) == city_norm.lower())
         .order_by(City.population.desc())
         .first()
    )
    if res:
        current_app.logger.debug("lookup_coords_local match (city exact): %s, %s, pop=%s",
                                 res.latitude, res.longitude, res.population)
        return float(res.latitude), float(res.longitude)
    else:
        current_app.logger.debug("lookup_coords_local no match (city exact)")

    # 3) startswith keresés country-val
    if country_norm:
        res = (
            q.filter(func.lower(City.city_name).like(city_norm.lower() + '%'),
                     func.lower(City.country_code) == country_norm.lower())
             .order_by(City.population.desc())
             .first()
        )
        if res:
            current_app.logger.debug("lookup_coords_local match (country+startswith): %s, %s, pop=%s",
                                     res.latitude, res.longitude, res.population)
            return float(res.latitude), float(res.longitude)
        else:
            current_app.logger.debug("lookup_coords_local no match (country+startswith)")

    # 4) startswith country nélkül
    res = (
        q.filter(func.lower(City.city_name).like(city_norm.lower() + '%'))
         .order_by(City.population.desc())
         .first()
    )
    if res:
        current_app.logger.debug("lookup_coords_local match (startswith): %s, %s, pop=%s",
                                 res.latitude, res.longitude, res.population)
        return float(res.latitude), float(res.longitude)
    else:
        current_app.logger.debug("lookup_coords_local no match (startswith)")

    current_app.logger.debug("lookup_coords_local: semmi találat -> None")
    return None, None


def lookup_coords_api(country, city):
    """
    Keres koordinátát a Geonames API-val.
    Visszaadja: (latitude, longitude) vagy (None, None)
    """
    if not city:
        return None, None

    city = city.strip()
    country = (country or '').strip()

    url = "http://api.geonames.org/searchJSON"
    params = {
        "q": city,
        "country": country if country else None,
        "maxRows": 1,
        "username": GEONAMES_USERNAME,
        "type": "json"
    }

    try:
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        if "geonames" in data and len(data["geonames"]) > 0:
            g = data["geonames"][0]
            lat = float(g.get("lat"))
            lng = float(g.get("lng"))
            current_app.logger.debug(
                "lookup_coords_api: found %s, %s -> %s, %s", city, country, lat, lng
            )
            return lat, lng
        else:
            current_app.logger.debug(
                "lookup_coords_api: no results for city=%r country=%r", city, country
            )
            return None, None

    except Exception as e:
        current_app.logger.exception(
            "lookup_coords_api: error calling API for city=%r country=%r", city, country
        )
        return None, None


def get_city_coords(country: str, postcode: str):
    from models import City  # ha külön modulban van
    city = City.query.filter_by(country=country, postcode=postcode).first()
    if city:
        return city.latitude, city.longitude
    return None, None


def spawn_background_geocode(loc_id, country, city, postcode):
    from models.cargo import CargoLocation
    """
    Új thread: külső geokódolóval próbálkozik, és ha talál, frissíti a CargoLocation-t
    Feltétel: a lokáció city/country/postcode nem változott a frissítés óta.
    """
    def worker():
        try:
            q = ', '.join([x for x in [postcode, city, country] if x])
            if not q:
                return
            res = requests.get(
                'https://nominatim.openstreetmap.org/search',
                params={'q': q, 'format': 'json', 'limit': 1},
                headers={'User-Agent': 'GVM-app'},
                timeout=6
            )
            if res.status_code != 200:
                return
            j = res.json()
            if not j:
                return
            lat = float(j[0]['lat'])
            lon = float(j[0]['lon'])
            # Re-open session to update (SQLAlchemy session-safety)
            sess_loc = CargoLocation.query.get(loc_id)
            if not sess_loc:
                return
            # Safety: only update if city/country/postcode unchanged
            if ( ( (sess_loc.city or '') == (city or '') ) and
                 ( (sess_loc.country or '') == (country or '') ) and
                 ( (sess_loc.postcode or '') == (postcode or '') ) ):
                sess_loc.latitude = lat
                sess_loc.longitude = lon
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
        except Exception:
            # silently ignore; ez csak fallback
            pass

    t = threading.Thread(target=worker, daemon=True)
    t.start()


def get_location_coords(country, city, postcode, lat_raw=None, lng_raw=None):
    """
    Visszaadja a (lat, lng) koordinátákat a következő prioritással:
    1) Lokális adatbázis (lookup_coords_local)
    2) Formból kapott értékek (lat_raw/lng_raw)
    3) Külső geokódoló API (lookup_coords_api)
    """
    # 1) próbáljuk a lokális DB-t
    lat, lng = lookup_coords_local(country, city)

    # 2) ha nincs, próbáljuk a formból
    try:
        if lat is None and lat_raw not in (None, ''):
            lat = float(lat_raw)
        if lng is None and lng_raw not in (None, ''):
            lng = float(lng_raw)
    except Exception:
        pass

    # 3) ha még mindig nincs, API fallback
    if lat is None or lng is None:
        lat_api, lng_api = lookup_coords_api(country, city)
        lat = lat or lat_api
        lng = lng or lng_api

    return lat, lng


def save_locations(new_cargo, loc_type, countries, postcodes, cities, hidden_flags):
    """
    loc_type: 'pickup' vagy 'dropoff'
    """
    from models.cargo import CargoLocation

    prefix_map = {
        'pickup': 'from',
        'dropoff': 'to'
    }
    prefix = prefix_map[loc_type]

    for i in range(len(countries)):
        country = countries[i] if i < len(countries) else None
        postcode = postcodes[i] if i < len(postcodes) else None
        city = cities[i] if i < len(cities) else None
        is_hidden = (hidden_flags[i] if i < len(hidden_flags) else False)

        masked_city, masked_postcode = (get_nearby_major_city(city, country) if is_hidden else (city, postcode))

        # Formból kapott lat/lng mezők (ha vannak)
        lat_raw = request.form.get(f'{prefix}_lat[{i}]') or request.form.get(f'{prefix}_lat[]')
        lng_raw = request.form.get(f'{prefix}_lng[{i}]') or request.form.get(f'{prefix}_lng[]')

        lat, lng = get_location_coords(country, masked_city, postcode, lat_raw, lng_raw)

        # dátum/idő mezők
        start_date = parse_date(request.form.get(f'{prefix}_start_date[{i}]') or request.form.get(f'{prefix}_start_date[]'))
        end_date   = parse_date(request.form.get(f'{prefix}_end_date[{i}]')   or request.form.get(f'{prefix}_end_date[]'))

        start_time_1 = parse_time(request.form.get(f'{prefix}_start_time_start[{i}]') or request.form.get(f'{prefix}_start_time_start[]'))
        start_time_2 = parse_time(request.form.get(f'{prefix}_start_time_end[{i}]')   or request.form.get(f'{prefix}_start_time_end[]'))
        end_time_1   = parse_time(request.form.get(f'{prefix}_end_time_start[{i}]')   or request.form.get(f'{prefix}_end_time_start[]'))
        end_time_2   = parse_time(request.form.get(f'{prefix}_end_time_end[{i}]')     or request.form.get(f'{prefix}_end_time_end[]'))

        location = CargoLocation(
            cargo_id=new_cargo.cargo_id,
            type=loc_type,
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


def save_template_locations(template_id, locations, type_):
    """
    Ment egy listát TemplateLocations táblába sablonhoz.
    locations = lista dict-ekből: {'city':..., 'country':..., 'postcode':..., 'is_hidden':...}
    type_ = 'pickup' vagy 'dropoff'
    """
    for loc in locations:
        location = TemplateLocations(
            template_id=template_id,
            type=type_,
            city=loc.get('city'),
            country=loc.get('country'),
            postcode=loc.get('postcode'),
            is_hidden=loc.get('is_hidden', False)
        )
        db.session.add(location)


def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def get_country_code_from_coords(lat, lon):
    geojson_path = 'static/geojson/countries'
    for fname in os.listdir(geojson_path):
        if not fname.endswith('.geojson'): continue
        country_code = fname.split('.')[0]
        with open(os.path.join(geojson_path, fname), encoding='utf-8') as f:
            gj = geojson.load(f)
            for feature in gj['features']:
                geom = feature.get('geometry')
                if geom and geom['type'] == 'Polygon':
                    coords = [pt for ring in geom['coordinates'] for pt in ring]
                    lats = [pt[1] for pt in coords]
                    lons = [pt[0] for pt in coords]
                    if min(lats)<=lat<=max(lats) and min(lons)<=lon<=max(lons):
                        return country_code
                elif geom and geom['type'] == 'MultiPolygon':
                    for poly in geom['coordinates']:
                        coords = [pt for ring in poly for pt in ring]
                        lats = [pt[1] for pt in coords]
                        lons = [pt[0] for pt in coords]
                        if min(lats)<=lat<=max(lats) and min(lons)<=lon<=max(lons):
                            return country_code
    return None


def add_nearby_cities_for_vehicle(vehicle: Vehicle):
    print(f"\n[DEBUG] Vehicle ID={vehicle.vehicle_id}")

    for ref_type in ["origin", "destination"]:
        diff = getattr(vehicle, f"{ref_type}_diff")
        if not diff or diff <= 0:
            print(f"[DEBUG] {ref_type}: nincs diff")
            continue

        ref_country = getattr(vehicle, f"{ref_type}_country")
        ref_postcode = getattr(vehicle, f"{ref_type}_postcode")
        ref_city_name = getattr(vehicle, f"{ref_type}_city")

        if not (ref_country and ref_postcode and ref_city_name):
            print(f"[DEBUG] {ref_type}: hiányos adatok")
            continue

        # Referencia város a City táblából
        ref_city = City.query.filter_by(
            country_code=ref_country,
            city_name=ref_city_name,
            zipcode=ref_postcode
        ).first()

        if not ref_city or ref_city.latitude is None or ref_city.longitude is None:
            print(f"[DEBUG] {ref_type}: nem található koordináta a City táblában {ref_city_name} ({ref_postcode})")
            continue

        ref_lat = ref_city.latitude
        ref_lon = ref_city.longitude
        print(f"[DEBUG] {ref_type}: diff={diff}, ref_city={ref_city_name}, lat={ref_lat}, lon={ref_lon}")

        # Bounding box
        lat_min = ref_lat - diff / 110
        lat_max = ref_lat + diff / 110
        lon_min = ref_lon - diff / (111 * math.cos(math.radians(ref_lat)))
        lon_max = ref_lon + diff / (111 * math.cos(math.radians(ref_lat)))

        nearby_cities = City.query.filter(
            City.country_code == ref_country,
            City.latitude.between(lat_min, lat_max),
            City.longitude.between(lon_min, lon_max)
        ).all()

        print(f"[DEBUG] {ref_type}: {len(nearby_cities)} város a bounding boxban")

        inserted_count = 0
        for c in nearby_cities:
            if c.latitude is None or c.longitude is None:
                continue

            dist = haversine(ref_lat, ref_lon, c.latitude, c.longitude)
            if dist > diff:
                print(f"[DEBUG]   {c.city_name} ({c.zipcode}) túl messze: {dist:.2f} km > {diff}")
                continue

            # Ellenőrizzük, hogy van-e már bent
            exists = NearbyCity.query.filter_by(
                reference_country=ref_country,
                reference_postcode=ref_postcode,
                reference_city=ref_city_name,
                city_name=c.city_name
            ).order_by(NearbyCity.radius_km.asc()).first()

            if exists:
                if exists.radius_km <= diff:
                    print(f"[DEBUG]   {c.city_name} ({c.zipcode}) már benne van kisebb/equal radius-szal: {exists.radius_km} km → SKIP")
                    continue
                else:
                    print(f"[DEBUG]   {c.city_name} ({c.zipcode}) létezik nagyobb radius-szal ({exists.radius_km} km), most hozzáadjuk {diff}-tel")

            else:
                print(f"[DEBUG]   {c.city_name} ({c.zipcode}) új → beszúrva diff={diff}, dist={dist:.2f} km")

            nearby = NearbyCity(
                country_code=c.country_code,
                zipcode=c.zipcode,
                city_name=c.city_name,
                lat=c.latitude,
                lon=c.longitude,
                reference_country=ref_country,
                reference_postcode=ref_postcode,
                reference_city=ref_city_name,
                radius_km=diff
            )
            db.session.add(nearby)
            inserted_count += 1

        db.session.commit()
        print(f"[DEBUG] {ref_type}: összesen {inserted_count} új város beszúrva")

    print(f"[LOG] NearbyCity-k feltöltve Vehicle ID={vehicle.vehicle_id}")


def fill_missing_city(location_data):
    """
    Ha a városmező hiányzik, próbáljuk kikeresni ország+irányítószám alapján.
    location_data: dict, tartalmazhat city, country, postcode, latitude, longitude
    """
    city_name = location_data.get("city")
    country = location_data.get("country")
    zipcode = location_data.get("postcode")

    if (not city_name or city_name.strip() == "") and country and zipcode:
        found_city = City.query.filter_by(country_code=country, zipcode=zipcode).first()
        if found_city:
            location_data["city"] = found_city.city_name
            location_data["latitude"] = found_city.latitude
            location_data["longitude"] = found_city.longitude

    return location_data


def get_blocked_company_ids(user):
    """
    Visszaadja a felhasználó számára tiltott cégek ID-jait.
    Tartalmazza azokat, akiket a user cég tiltott,
    illetve azokat, akik a user cégét tiltották.
    """
    blocked_ids = db.session.query(CompanyBlocklist.blocked_company_id).filter_by(
        blocker_company_id=user.company_id
    )
    blocked_by_others = db.session.query(CompanyBlocklist.blocker_company_id).filter_by(
        blocked_company_id=user.company_id
    )
    all_blocked = blocked_ids.union_all(blocked_by_others).all()
    return [id[0] for id in all_blocked]


def handle_company_block_fast(blocker_company_id, blocked_company_id):
    """
    Blokkol egy céget, és törli az összes offer-t (és a hozzá tartozó chat üzeneteket)
    a két cég felhasználói között, memóriaterhelés minimalizálása mellett.
    """
    from models.cargo import Cargo, CargoLocation, Offer
    # 1️⃣ Adjuk hozzá a tiltólistához
    new_block = CompanyBlocklist(
        blocker_company_id=blocker_company_id,
        blocked_company_id=blocked_company_id
    )
    db.session.add(new_block)
    db.session.flush()  # kell az új ID-hoz, ha más tábla hivatkozik rá

    # 2️⃣ Lekérjük a két cég felhasználóinak ID-jait
    user_ids_blocker = db.session.query(User.user_id).filter_by(company_id=blocker_company_id).subquery()
    user_ids_blocked = db.session.query(User.user_id).filter_by(company_id=blocked_company_id).subquery()

    # 3️⃣ Törlés: minden Offer, ahol a két cég felhasználói érintettek
    # mindkét irányban
    db.session.query(Offer).filter(
        or_(
            and_(
                Offer.offer_user_id.in_(user_ids_blocker),
                Offer.cargo.has(Cargo.user_id.in_(user_ids_blocked))
            ),
            and_(
                Offer.offer_user_id.in_(user_ids_blocked),
                Offer.cargo.has(Cargo.user_id.in_(user_ids_blocker))
            )
        )
    ).delete(synchronize_session=False)  # NAGYON FONTOS: gyors törlés

    # 4️⃣ Commit
    db.session.commit()

# --- Segédfüggvény járműadatokhoz ---
def serialize_vehicle(vehicle):
    if not vehicle:
        return None
    return {
        "vehicle_id": vehicle.vehicle_id,
        "license_plate": getattr(vehicle, "license_plate", ""),
        "vehicle_type": getattr(vehicle, "vehicle_type", ""),
        "structure": getattr(vehicle, "structure", ""),
        "capacity_t": getattr(vehicle, "capacity_t", ""),
        "volume_m3": getattr(vehicle, "volume_m3", ""),
        "origin_city": getattr(vehicle, "origin_city", ""),
        "destination_city": getattr(vehicle, "destination_city", "")
    }

