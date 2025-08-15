from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Blueprint, abort, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_mail import Mail, Message
from datetime import datetime, timedelta, date
import re
import secrets
import unicodedata
from sqlalchemy import or_
import os
import uuid
from flask import current_app
from PIL import Image
import pillow_heif


def save_uploaded_image(file, subfolder, prefix="file_", allowed_extensions=None):
    """
    Feltöltött kép mentése egy adott mappába.

    :param file: Feltöltött fájl objektum (werkzeug.datastructures.FileStorage)
    :param subfolder: Mappa neve a static/uploads alatt (pl. 'company_logos', 'profile_pictures')
    :param prefix: Fájlnév előtag
    :param allowed_extensions: Engedélyezett kiterjesztések listája
    :return: (success, filename_or_error)
    """
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


app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ---------- Flask-Mail konfiguráció (helyi tesztelésnél üres jelszó OK) ----------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'alex.toth99@gmail.com'  # ide a saját gmail címed
app.config['MAIL_PASSWORD'] = ''  # ide az app password - most hagyjuk üresen

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
mail = Mail(app)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'heic'}

# -------------------------
# MODELS
# -------------------------
# a Company osztályban
class Company(db.Model):
    company_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    subscription_type = db.Column(db.String(50), default="free")
    country = db.Column(db.String(50))
    post_code = db.Column(db.String(20))
    street = db.Column(db.String(100))
    house_number = db.Column(db.String(20))
    tax_number = db.Column(db.String(50))
    admin_id = db.Column(db.Integer)
    created_at = db.Column(db.Date, default=date.today)
    slug = db.Column(db.String(200), unique=True, index=True, nullable=True)
    invite_codes = db.relationship('InviteCode', backref='company', lazy=True)
    users = db.relationship('User', back_populates='company')
    # Új mező a logóhoz
    logo_filename = db.Column(db.String(200), nullable=True)  # ha None → alapértelmezett kép


class User(db.Model, UserMixin):
    user_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    first_name = db.Column(db.String(150), nullable=False)
    last_name = db.Column(db.String(150), nullable=False)
    phone_number = db.Column(db.String(150), nullable=False)
    hashed_password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), default="freight_forwarder")
    company_id = db.Column(db.Integer, db.ForeignKey('company.company_id'), nullable=True)
    is_company_admin = db.Column(db.Boolean, default=False)
    common_user = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.Date, default=date.today)
    profile_picture = db.Column(db.String(200), nullable=True)
    company = db.relationship('Company', back_populates='users')

    def get_id(self):
        return str(self.user_id)

class InviteCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.company_id'), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    for_admin = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.Date, default=date.today)


class PasswordResetToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(128), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='reset_tokens')

    @staticmethod
    def generate_for_user(user, hours_valid=1):
        token = secrets.token_urlsafe(48)
        expires = datetime.utcnow() + timedelta(hours=hours_valid)
        prt = PasswordResetToken(token=token, user_id=user.user_id, expires_at=expires)
        db.session.add(prt)
        db.session.commit()
        return token

# -------------------------
# LOGIN MANAGER
# -------------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------------------------
# HELPERS
# -------------------------
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
    """
    Egyszerű slugify: eltávolítja az ékezeteket, kisbetűs, nem-alfanumerikus -> kötőjel
    (pl. "Cég Néve ÁÉ" -> "ceg-neve-ae")
    """
    if not value:
        return ''
    value = str(value)
    # normálás és ékezet eltávolítás
    value = unicodedata.normalize('NFKD', value)
    value = ''.join([c for c in value if not unicodedata.combining(c)])
    value = value.lower()
    # csak betűk, számok és szóköz/kötőjel maradjon
    value = re.sub(r'[^a-z0-9]+', '-', value)
    value = value.strip('-')
    return value


def make_unique_slug(name, company_id=None):
    base = slugify(name)
    if company_id:
        return f"{base}-{company_id}"
    # ha nincs id (például még nem flush-oltuk), próbáljunk számolni:
    candidate = base
    i = 1
    while Company.query.filter_by(slug=candidate).first():
        i += 1
        candidate = f"{base}-{i}"
    return candidate


# tegye elérhetővé Jinja-ban is
app.jinja_env.globals['slugify'] = slugify

# -------------------------
# EMAIL KÜLDÉS FUNKCIÓ
# -------------------------
def send_email(to_email, subject, body):
    try:
        msg = Message(subject, sender=app.config['MAIL_USERNAME'], recipients=[to_email])
        msg.body = body
        mail.send(msg)
    except Exception as e:
        print(f"Email küldési hiba: {e}")

# -------------------------
# ROUTES
# -------------------------
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    message = None
    email = ""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.hashed_password, password):
            login_user(user)
            return redirect(url_for('home'))
        else:
            message = "Invalid credentials"
    return render_template('login.html', message=message, email=email)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# -------------------------
# FORGOT / RESET (token-based)
# -------------------------
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    message = None
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        # Biztonság: mindig ugyanazt az üzenetet küldjük vissza
        if user:
            token = PasswordResetToken.generate_for_user(user, hours_valid=1)
            reset_link = url_for('reset_password', token=token, _external=True)
            body = (
                f"Hello {user.first_name},\n\n"
                f"Kattints erre a linkre a jelszavad visszaállításához (a link 1 óráig érvényes):\n\n"
                f"{reset_link}\n\n"
                "Ha nem te kérted ezt, kérjük, hagyd figyelmen kívül ezt az üzenetet."
            )
            send_email(to_email=user.email, subject="Password Reset Request", body=body)
        message = "Password reset link has been sent to your email (if the address exists)."
    return render_template('forgot_password.html', message=message)

@app.route('/check_tax_number')
def check_tax_number():
    tax = request.args.get('tax_number', '').strip()
    if not tax:
        return jsonify({'exists': False})
    exists = Company.query.filter_by(tax_number=tax).first() is not None
    return jsonify({'exists': exists})


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    message = None
    prt = PasswordResetToken.query.filter_by(token=token).first()
    if prt is None or prt.expires_at < datetime.utcnow():
        flash("The password reset link is invalid or has expired.", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if new_password != confirm_password:
            message = "Passwords do not match."
            return render_template('reset_password.html', message=message)
        valid, msg = is_valid_password(new_password)
        if not valid:
            message = msg
            return render_template('reset_password.html', message=message)

        user = prt.user
        user.hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        db.session.delete(prt)  # token egyszeri használat
        db.session.commit()
        flash("Your password has been reset. Please log in with your new password.", "success")
        return redirect(url_for('login'))

    return render_template('reset_password.html', message=message)

# -------------------------
# REGISTRATION (CREATE & JOIN)
# -------------------------
@app.route('/register_create', methods=['GET', 'POST'])
def register_create():
    form_data = {}
    message = None

    if request.method == 'POST':
        form_data = request.form.to_dict()
        email = form_data.get('email')
        phone = form_data.get('phone_number')
        first_name = form_data.get('first_name')
        last_name = form_data.get('last_name')
        password = form_data.get('password')
        confirm_password = form_data.get('confirm_password')

        if password != confirm_password:
            message = "Passwords do not match."
        else:
            valid, msg = is_valid_password(password)
            if not valid:
                message = msg
            elif User.query.filter_by(email=email).first():
                message = "This email is already registered."
            else:
                # Ellenőrizzük backend oldalon is az adószámot — ha létezik, figyelmeztetünk, de engedjük regisztrálni:
                existing_company = Company.query.filter_by(tax_number=form_data.get('tax_number')).first()
                if existing_company:
                    # flash üzenet a felhasználónak — a frontend is jelzi
                    flash('Ez az adószám már regisztrálva van.', 'error')
                    return render_template('register_create.html', message='Ez az adószám már regisztrálva van.',
                                           form_data=form_data)

                # amikor új company-t hozol létre:
                company = Company(
                    name=form_data.get('company_name'),
                    country=form_data.get('country'),
                    post_code=form_data.get('post_code'),
                    street=form_data.get('street'),
                    house_number=form_data.get('house_number'),
                    tax_number=form_data.get('tax_number'),
                    subscription_type=form_data.get('subscription_type')
                )
                db.session.add(company)
                db.session.flush()  # <-- ekkor kap company.company_id-t

                # most állítsd be a slugot garantáltan egyedire:
                company.slug = make_unique_slug(company.name, company.company_id)

                hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
                user = User(
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    phone_number=phone,
                    hashed_password=hashed_pw,
                    company_id=company.company_id,
                    is_company_admin=True
                )


                db.session.add(user)
                db.session.commit()

                send_email(
                    to_email=email,
                    subject="Registration Successful",
                    body=f"Hello {first_name},\n\nYou have successfully registered the company {company.name}\nThank you for joining us!"
                )

                return redirect(url_for('login'))

    return render_template('register_create.html', message=message, form_data=form_data)

@app.route('/register_choice')
def register_choice():
    return render_template('register_choice.html')


@app.route('/register/join', methods=['GET', 'POST'])
def register_join():
    warning = None

    if request.method == 'POST':
        email = request.form.get('email')
        phone = request.form.get('phone_number')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        invite_code_input = request.form.get('invite_code')

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            warning = "Ezzel az e-mail címmel már van regisztrált felhasználó."
            return render_template('register_join.html', warning=warning)

        # Jelszó ellenőrzés
        if password != confirm_password:
            warning = "A jelszavak nem egyeznek."
            return render_template('register_join.html', warning=warning)

        if len(password) < 8 or not any(c.isdigit() for c in password) or not any(c.islower() for c in password) or not any(c.isupper() for c in password):
            warning = "A jelszó nem felel meg a szabályoknak."
            return render_template('register_join.html', warning=warning)

        # Meghívó ellenőrzése
        invite = InviteCode.query.filter_by(code=invite_code_input).first()
        if not invite:
            warning = "A meghívó kód érvénytelen."
            return render_template('register_join.html', warning=warning)

        if invite.is_used:
            warning = "Ez a meghívó kód már felhasználásra került."
            return render_template('register_join.html', warning=warning)

        if invite.expires_at < datetime.now():
            warning = "Ez a meghívó kód lejárt."
            return render_template('register_join.html', warning=warning)

        # Felhasználó létrehozása
        new_user = User(
            email=email,
            phone_number=phone,
            first_name=first_name,
            last_name=last_name,
            hashed_password=bcrypt.generate_password_hash(password).decode('utf-8'),
            company_id=invite.company_id,
            role=invite.role,
            is_company_admin = invite.for_admin
        )

        db.session.add(new_user)

        # Meghívó jelzése felhasználtként
        invite.is_used = True
        db.session.commit()

        flash("Sikeresen csatlakoztál a céghez!", "success")
        return redirect(url_for('login'))  # vagy hová szeretnéd irányítani

    return render_template('register_join.html', warning=warning)


# -------------------------
# CHANGE PASSWORD (profile -> change)
# -------------------------
@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    message = None

    if request.method == 'POST':
        current_pwd = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not bcrypt.check_password_hash(current_user.hashed_password, current_pwd):
            message = "Current password is incorrect."
            return render_template('change_password.html', message=message)

        if new_password != confirm_password:
            message = "Passwords do not match."
            return render_template('change_password.html', message=message)

        valid, msg = is_valid_password(new_password)
        if not valid:
            message = msg
            return render_template('change_password.html', message=message)

        current_user.hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        db.session.commit()

        flash("Your password has been updated.", "success")
        return redirect(url_for('profile'))

    return render_template('change_password.html', message=message)

# -------------------------
# DASHBOARD ROUTES WITH SIDEBAR
# -------------------------
@app.route('/home')
@login_required
def home():
    return render_template('home.html', user=current_user)

@app.route('/shipments')
@login_required
def shipments():
    return render_template('shipments.html', user=current_user)

@app.route('/cargo')
@login_required
def cargo():
    return render_template('cargo.html', user=current_user)

@app.route('/vehicles')
@login_required
def vehicles():
    return render_template('vehicles.html', user=current_user)

@app.route('/companies/')
@app.route('/companies')
@login_required
def companies():
    search = request.args.get('search', '').strip()
    query = Company.query
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Company.name.ilike(search_term),
                Company.tax_number.ilike(search_term),
                Company.country.ilike(search_term)
            )
        )
    companies = query.all()
    return render_template('companies.html', user=current_user, companies=companies, search=search)

@app.route('/my_company')
@login_required
def my_company():
    if not current_user.company_id:
        flash("Nem tartozol egyetlen céghez sem.", "warning")
        return redirect(url_for('companies'))

    company = Company.query.get(current_user.company_id)
    if not company:
        flash("A céged nem található.", "danger")
        return redirect(url_for('companies'))

    return render_template(
        'my_company.html',
        company=company,
        is_company_admin=current_user.is_company_admin,
        now=datetime.now(),
        current_user_role = current_user.role,  # ez kell az Owner feltételhez
        current_user_id = current_user.user_id  # ez kell az Owner feltételhez
    )


company_bp = Blueprint('company', __name__)
@app.route("/company/<int:company_id>/promote/<int:user_id>", methods=["POST"])
@login_required
def promote_user(company_id, user_id):
    company = Company.query.get(company_id)
    if not company:
        return {"success": False, "error": "Cég nem található."}, 404

    # Csak adminok vagy Owner
    if (not current_user.is_company_admin and current_user.role != "Owner") or current_user.company_id != company_id:
        return jsonify({"success": False, "error": "Nincs jogosultságod."}), 403

    user = User.query.get(user_id)
    if not user or user not in company.users:
        return {"success": False, "error": "Felhasználó nem található."}, 404

    # Ha Owner, át tudja adni vagy elvenni az admin jogot
    if current_user.role == "owner":
        user.is_company_admin = not user.is_company_admin
    else:
        # Simán csak admin tudja adni
        user.is_company_admin = True

    db.session.commit()
    return jsonify({"success": True})

@app.route("/company/<int:company_id>/remove/<int:user_id>", methods=["POST"])
@login_required
def remove_user(company_id, user_id):
    company = Company.query.get(company_id)
    if not company:
        return jsonify({"success": False, "error": "Cég nem található."}), 404

    # Csak adminok vagy Owner
    if (not current_user.is_company_admin and current_user.role != "Owner") or current_user.company_id != company_id:
        return jsonify({"success": False, "error": "Nincs jogosultságod."}), 403

    user = User.query.get(user_id)
    if not user or user.company_id != company_id:
        return jsonify({"success": False, "error": "Felhasználó nem található a cégnél."}), 404

    user.company_id = None
    user.is_company_admin = False
    db.session.commit()
    return jsonify({"success": True})


@app.route('/upload_company_logo', methods=['POST'])
@login_required
def upload_company_logo():
    if not current_user.is_company_admin or not current_user.company_id:
        return {"success": False, "error": "Nincs jogosultságod."}, 403

    success, result = save_uploaded_image(
        request.files.get('logo'),
        subfolder='company_logos',
        prefix='company_',
        allowed_extensions=ALLOWED_EXTENSIONS
    )

    if not success:
        return {"success": False, "error": result}, 400

    company = Company.query.get(current_user.company_id)
    company.logo_filename = result
    db.session.commit()

    return {"success": True, "filename": result}


@app.route('/generate_invite', methods=['POST'])
@login_required
def generate_invite():
    if not current_user.is_company_admin or not current_user.company_id:
        flash("Nincs jogosultságod meghívó létrehozásához.", "danger")
        return redirect(url_for('my_company'))

    # Kód generálása és ellenőrzés
    while True:
        code = secrets.token_urlsafe(8)  # kb. 11 karakter
        if not InviteCode.query.filter_by(code=code).first():
            break  # kilép a while-ból, kód már egyedi

    role = request.form.get('role', 'user')  # alapértelmezett: user
    for_admin = bool(request.form.get('for_admin'))  # checkbox értéke

    invite = InviteCode(
        code=code,
        company_id=current_user.company_id,
        role=role,
        for_admin=for_admin,
        expires_at=datetime.now() + timedelta(hours=1),  # 1 óráig érvényes
        is_used=False
    )

    db.session.add(invite)
    db.session.commit()

    flash(f"Meghívó létrehozva: {code}", "success")
    return redirect(url_for('my_company'))


@app.route('/search_companies')
@login_required
def search_companies():
    query = request.args.get('q', '').strip()
    if query:
        results = Company.query.filter(
            (Company.name.ilike(f'%{query}%')) |
            (Company.tax_number.ilike(f'%{query}%')) |
            (Company.country.ilike(f'%{query}%'))
        ).all()
    else:
        results = Company.query.all()

    companies_data = []
    for c in results:
        # számoljuk az alkalmazottak számát (company.users backref alapján)
        emp_count = len(c.users) if hasattr(c, 'users') and c.users is not None else 0

        # készítünk egy slugot (egyszerű, nem ír a DB-be)
        s = slugify(c.name)  # ha szükséges, tehetsz utána '-<id>'-t hogy garantáltan egyedi legyen: f"{s}-{c.company_id}"
        companies_data.append({
            'company_id': c.company_id,
            'name': c.name,
            'slug': c.slug or make_unique_slug(c.name, c.company_id),
            'country': c.country,
            'post_code': c.post_code,
            'street': c.street,
            'house_number': c.house_number,
            'tax_number': c.tax_number,
            'created_at': c.created_at.strftime('%Y-%m-%d') if c.created_at else '',
            'employee_count': emp_count
        })
    return jsonify(companies_data)

@app.route('/company/<slug>')
@login_required
def company_profile(slug):
    # ha számjegyekből áll (pl. valami id-s fallback), kíséreljük az id szerinti lekérést is:
    if slug.isdigit():
        company = Company.query.get(int(slug))
        if not company:
            abort(404)
        return render_template('company_profile.html', company=company)

    # elsődleges: keresés slug mező alapján
    company = Company.query.filter_by(slug=slug).first()
    if company:
        return render_template('company_profile.html', company=company)

    # ha nem található, próbáljuk a slug végén lévő -<id> kinyerését (további fallback)
    import re
    m = re.search(r'-(\d+)$', slug)
    if m:
        cid = int(m.group(1))
        company = Company.query.get(cid)
        if company:
            return render_template('company_profile.html', company=company)

    abort(404)

@app.route("/company/<company_slug>/<email>")
@login_required
def user_profile(company_slug, email):
    # Cég lekérése a slug alapján
    company = Company.query.filter_by(slug=company_slug).first_or_404()

    # Felhasználó lekérése a cégből az email alapján
    user = User.query.filter_by(email=email, company_id=company.company_id).first_or_404()

    # Nincs szerkesztés
    return render_template("user_profile.html", user=user)

@app.route("/profile")
@login_required
def profile():
    user = current_user
    return render_template("profile.html", user=user)

@app.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    user = current_user
    if request.method == "POST":
        # Űrlap adatainak beolvasása
        user.first_name = request.form.get("first_name").strip()
        user.last_name = request.form.get("last_name").strip()
        user.phone_number = request.form.get("phone_number").strip()
        new_email = request.form.get("email").strip()

        # Ha email változott, ellenőrizzük hogy nincs-e már foglalt
        if new_email != user.email:
            if User.query.filter_by(email=new_email).first():
                flash("Ez az e-mail cím már használatban van!", "error")
                return redirect(url_for("edit_profile"))
            user.email = new_email

        db.session.commit()
        flash("Profil sikeresen frissítve!", "success")
        return redirect(url_for("profile"))

    return render_template("edit_profile.html", user=user)
@app.route('/upload_profile_picture', methods=['POST'])
@login_required
def upload_profile_picture():
    success, result = save_uploaded_image(
        request.files.get('profile_picture'),
        subfolder='profile_pictures',
        prefix=f"user_{current_user.user_id}_",
        allowed_extensions=ALLOWED_EXTENSIONS
    )

    if not success:
        return {"success": False, "error": result}, 400

    # régi kép törlése, ha nem default
    old_path = os.path.join(current_app.root_path, 'static/uploads/profile_pictures', current_user.profile_picture or "")
    if current_user.profile_picture and os.path.exists(old_path) and current_user.profile_picture != "default.png":
        try:
            os.remove(old_path)
        except Exception:
            pass

    current_user.profile_picture = result
    db.session.commit()

    return {"success": True, "filename": result}



@app.route('/statistics')
@login_required
def statistics():
    return render_template('statistics.html', user=current_user)

# -------------------------
# RUN APP
# -------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
