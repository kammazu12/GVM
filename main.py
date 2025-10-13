# BIG APP FOR FREIGHTS
from flask import Flask, render_template, session, redirect, url_for, g
from flask_login import login_required
from models.cargo import CargoLocation
from sockets import *
from extensions import *
from routes import blueprints
from utils import *
from models import *
from config import *
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import date, datetime
import os

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
app = Flask(__name__)
app.config['BABEL_DEFAULT_LOCALE'] = 'hu'
app.config['BABEL_SUPPORTED_LOCALES'] = ['hu', 'en', 'de']
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB
app.config.from_object(Config)
# --- DATABASE_URL fix Renderhez ---
uri = app.config["SQLALCHEMY_DATABASE_URI"]
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = uri

with app.app_context():
    db.init_app(app)
bcrypt.init_app(app)
mail.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login.login'
socketio.init_app(app, cors_allowed_origins="*")
port = int(os.environ.get("PORT", 5000))

PROTECTED_ENDPOINTS = []
for bp in blueprints:
    app.register_blueprint(bp)
    for rule in app.url_map.iter_rules():
        if rule.endpoint.startswith(bp.name + "."):
            PROTECTED_ENDPOINTS.append(rule.endpoint)

PUBLIC_ENDPOINTS = ['login.login',
                    'register.register_create',
                    'register.register_choice',
                    'register.register_join',
                    'register.register_check_tax_number',
                    'static', 'profile.forgot_password',
                    'profile.reset_password', 'profile.reset_password_token',]
PROTECTED_ENDPOINTS = [ep for ep in PROTECTED_ENDPOINTS if ep not in PUBLIC_ENDPOINTS]

# print("\n--- ROUTES ---")
# for rule in app.url_map.iter_rules():
#     print(rule, rule.methods)
# print("--------------\n")


# -------------------------
# LOGIN MANAGER
# -------------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def get_locale():
    # ha a felhasználó beállította a nyelvet a profiljában:
    if current_user.is_authenticated and current_user.settings:
        return current_user.settings.language or "hu"
    # különben a böngésző nyelvi beállításai alapján
    return request.accept_languages.best_match(app.config.get("LANGUAGES"))
babel.init_app(app, locale_selector=get_locale)


def notify_expired_items():
    # --- csak dátum szintű összehasonlítás, nem időpont ---
    now = date.today()
    yesterday = now - timedelta(days=1)

    print(f"[SCHEDULER] Lejárt elemek keresése (<= {yesterday})...")

    # --- Lejárt rakományok (Cargo) ---
    expired_cargo_ids = (
        db.session.query(CargoLocation.cargo_id)
        .filter(CargoLocation.type == "dropoff")
        .filter(CargoLocation.end_date <= yesterday)
        .distinct()
        .all()
    )
    expired_cargo_ids = [cid[0] for cid in expired_cargo_ids]

    print(f"Lejárt rakományok: {expired_cargo_ids}")

    for cargo_id in expired_cargo_ids:
        cargo = Cargo.query.get(cargo_id)
        if not cargo:
            continue

        existing = ExpiredNotification.query.filter_by(
            item_id=cargo.cargo_id,
            item_type="cargo",
            resolved=False
        ).first()

        if not existing:
            notif = ExpiredNotification(
                user_id=cargo.user_id,
                item_id=cargo.cargo_id,
                item_type="cargo"
            )
            db.session.add(notif)

    # --- Lejárt rakterek (Vehicle) ---
    expired_vehicles = Vehicle.query.filter(
        Vehicle.available_until != None,
        Vehicle.available_until <= yesterday
    ).all()

    print(f"Lejárt rakterek: {[v.vehicle_id for v in expired_vehicles]}")

    for vehicle in expired_vehicles:
        existing = ExpiredNotification.query.filter_by(
            item_id=vehicle.vehicle_id,
            item_type="storage",
            resolved=False
        ).first()

        if not existing:
            notif = ExpiredNotification(
                user_id=vehicle.user_id,
                item_id=vehicle.vehicle_id,
                item_type="storage"
            )
            db.session.add(notif)

    db.session.commit()
    print(f"[SCHEDULER] Lejárt értesítések frissítve ({len(expired_cargo_ids)} cargo, {len(expired_vehicles)} vehicle).")


def delete_expired_offers():
    now = datetime.now()
    expired_records = OfferAutoDelete.query.filter(OfferAutoDelete.delete_at <= now).all()

    for record in expired_records:
        offer = Offer.query.get(record.offer_id)
        if offer:
            db.session.delete(offer)
        db.session.delete(record)

    db.session.commit()
    print(f"[Scheduler] {len(expired_records)} lejárt ajánlat törölve ({now})")


# ------------------------- LEJÁRT FUVAROK, RAKTÉREK ÉS AJÁNLATOK TÖRLÉSE  -------------------------
def start_scheduler(app):
    scheduler = BackgroundScheduler()

    # Napi törlés (fuvarok, rakterek)
    scheduler.add_job(
        func=lambda: app.app_context().push() or notify_expired_items(),
        trigger="interval",
        minutes=3,
        timezone="Europe/Budapest"
    )

    # Óránkénti törlés (lejárt ajánlatok)
    scheduler.add_job(
        func=lambda: app.app_context().push() or delete_expired_offers(),
        trigger="interval",
        minutes=1,
        timezone="Europe/Budapest"
    )

    scheduler.start()
    print("Scheduler started:")
    print(" - delete_expired -> every day at 00:01")
    print(" - delete_expired_offers -> every hour")


@app.context_processor
def inject_user_and_unseen_count():
    user = current_user if current_user.is_authenticated else None
    unseen_count = 0
    if user:
        unseen_count = (
            db.session.query(Offer)
            .join(Cargo, Offer.cargo_id == Cargo.cargo_id)
            .filter(Cargo.user_id == user.user_id, Offer.seen == False)
            .count()
        )
    return dict(user=user, unseen_incoming_offers_count=unseen_count)

# tegye elérhetővé Jinja-ban is
app.jinja_env.globals['slugify'] = slugify

# -------------------------
# ROUTES
# -------------------------
@app.before_request
def check_session():
    # A PROTECTED_ENDPOINTS ellenőrzés megmarad
    if request.endpoint in PROTECTED_ENDPOINTS:
        # Ha a felhasználó nincs belépve, irány a login
        if not current_user.is_authenticated:
            return redirect(url_for('login.login'))


@app.before_request
def check_expired_items():
    if not current_user.is_authenticated:
        return

    # Ha már ellenőriztük ebben a sessionben, ne futtassuk újra
    if getattr(g, "_expired_checked", False):
        return

    g._expired_checked = True

    # Van-e lejárt rakomány vagy raktér
    pending = ExpiredNotification.query.filter_by(
        user_id=current_user.user_id,
        resolved=False
    ).all()

    if pending:
        # frontend oldalon websocket fogja kezelni
        for notif in pending:
            socketio.emit("show_expired_modal", {
                "item_id": notif.item_id,
                "item_type": notif.item_type
            }, room=f"user_{current_user.user_id}")


@app.after_request
def disable_bfcache(response):
    # Normál cache tiltás
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    # BFCACHE tiltás (ez az, amit a böngészők figyelnek!)
    response.headers["Cache-Control"] += ", private, no-transform"

    # Extra biztonság: mindig új session küldése
    response.headers["Cache-Control"] += ", must-revalidate"

    return response


@app.route('/shipments')
@login_required
@no_cache
def shipments():
    blocked_ids = get_blocked_company_ids(current_user)

    cargos = Cargo.query.filter(~Cargo.company_id.in_(blocked_ids)) \
                        .order_by(Cargo.created_at.desc()) \
                        .all()

    return render_template(
        'shipments.html',
        user=current_user,
        cargos=cargos,
        current_year=date.today().year
    )


BATCH_SIZE = 1000

def process_countries_or_cities(filepath):
    records_added = 0
    batch = []

    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue  # üres sor vagy komment

            parts = line.split("\t")  # GeoNames TSV
            if len(parts) < 9:
                print(f"Skipping malformed line: {line[:50]}...")
                continue

            try:
                city_id = int(parts[0])       # ID numerikus
                city_name = parts[1]          # város neve
                latitude = float(parts[4])
                longitude = float(parts[5])
                country_code = parts[8]       # kétbetűs ország kód
            except ValueError as e:
                print(f"Skipping line due to conversion error: {line[:50]}...")
                continue

            # Ellenőrizzük, hogy létezik-e a rekord
            if City.query.filter_by(id=city_id).first():
                continue

            city = City(
                id=city_id,
                city_name=city_name,
                latitude=latitude,
                longitude=longitude,
                zipcode=0,            # ha nincs a fájlban
                country_code=country_code
            )
            batch.append(city)

            if len(batch) >= BATCH_SIZE:
                db.session.bulk_save_objects(batch)
                db.session.commit()
                records_added += len(batch)
                batch = []

    # Maradék batch mentése
    if batch:
        db.session.bulk_save_objects(batch)
        db.session.commit()
        records_added += len(batch)

    print(f"{records_added} records added from {os.path.basename(filepath)}")
    return records_added
    records_added = 0
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")  # GeoNames txt fájlok tab-delimited
            if len(parts) < 2:
                continue

            # Felismerjük, hogy ország vagy város
            if "allCountries" in filepath:
                # Város feltöltés
                city_id = parts[0]
                city_name = parts[1]
                country_code = parts[8]  # GeoNames formátum
                # ellenőrzés
                if not City.query.filter_by(id=city_id).first():
                    city = City(id=city_id, city_name=city_name, country_code=country_code)
                    db.session.add(city)
                    records_added += 1
            else:
                # Ország feltöltés
                country_code = parts[0]
                country_name = parts[1]
                if not Country.query.filter_by(code=country_code).first():
                    country = Country(code=country_code, name=country_name)
                    db.session.add(country)
                    records_added += 1

    db.session.commit()
    return records_added

UPLOAD_FOLDER = "/tmp/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "Nincs fájl a POST-ban", 400

    file = request.files['file']
    if file.filename == '':
        return "Üres fájl név", 400

    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    # Hívjuk a feldolgozó függvényt
    if "Countries" in file.filename or "alternateNames" in file.filename:
        records_added = process_countries_or_cities(filepath)
    else:
        records_added = 0

    return f"File sikeresen feltöltve és {records_added} rekord hozzáadva!"


# -------------------------
# RUN APP
# -------------------------
if __name__ == "__main__":
    # print(app.url_map)
    with app.app_context():
        db.create_all()
    start_scheduler(app)
    # app.run(debug=True)
    print("[DB URI]:", app.config["SQLALCHEMY_DATABASE_URI"])
    socketio.run(app, '0.0.0.0', port=port, debug=True)
