from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_mail import Mail, Message
from datetime import datetime, timedelta, date
import re
import random
import string
import secrets
import unicodedata
from sqlalchemy import or_

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

# -------------------------
# MODELS
# -------------------------
class Company(db.Model):
    company_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(160), unique=True, nullable=True)  # új mező (nullable a migrációhoz)
    subscription_type = db.Column(db.String(50), default="free")
    country = db.Column(db.String(50))
    post_code = db.Column(db.String(20))
    street = db.Column(db.String(100))
    house_number = db.Column(db.String(20))
    tax_number = db.Column(db.String(50))
    admin_id = db.Column(db.Integer)
    created_at = db.Column(db.Date, default=date.today)


class User(db.Model, UserMixin):
    user_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    first_name = db.Column(db.String(150), nullable=False)
    last_name = db.Column(db.String(150), nullable=False)
    phone_number = db.Column(db.String(150), nullable=False)
    hashed_password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), default="freight_forwarder")
    company_id = db.Column(db.Integer, db.ForeignKey('company.company_id'))
    is_company_admin = db.Column(db.Boolean, default=False)
    common_user = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.Date, default=date.today)

    # kapcsolat a céghez; backref létrehozza a company.users-t
    company = db.relationship('Company', backref='users')

    def get_id(self):
        return str(self.user_id)

class InviteCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.company_id'), nullable=False)
    role = db.Column(db.String(50), nullable=False)
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


def generate_unique_slug(name):
    base = slugify(name) or 'company'
    slug_candidate = base
    i = 2
    # add loop to guarantee uniqueness
    while Company.query.filter_by(slug=slug_candidate).first() is not None:
        slug_candidate = f"{base}-{i}"
        i += 1
    return slug_candidate

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

                company = Company(
                    name=form_data.get('company_name'),
                    country=form_data.get('country'),
                    post_code=form_data.get('post_code'),
                    street=form_data.get('street'),
                    house_number=form_data.get('house_number'),
                    tax_number=form_data.get('tax_number'),
                    subscription_type=form_data.get('subscription_type')
                )
                # generáljuk és beállítjuk a slugot mielőtt flush-olunk
                company.slug = generate_unique_slug(company.name)

                db.session.add(company)
                db.session.flush()

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

@app.route('/register_join', methods=['GET', 'POST'])
def register_join():
    form_data = {}
    message = None

    if request.method == 'POST':
        form_data = request.form.to_dict()
        email = form_data.get('email')
        password = form_data.get('password')
        confirm_password = form_data.get('confirm_password')
        invite_code_str = form_data.get('invite_code')

        if password != confirm_password:
            message = "Passwords do not match."
        else:
            valid, msg = is_valid_password(password)
            if not valid:
                message = msg
            elif User.query.filter_by(email=email).first():
                message = "This email is already registered."
            else:
                invite = InviteCode.query.filter_by(code=invite_code_str, is_used=False).first()
                if not invite or invite.expires_at < datetime.utcnow():
                    message = "Invalid or expired invite code."
                else:
                    hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
                    user = User(
                        email=email,
                        first_name=form_data.get('first_name') or form_data.get('full_name',''),
                        last_name=form_data.get('last_name') or '',
                        phone_number=form_data.get('phone_number') or '',
                        hashed_password=hashed_pw,
                        company_id=invite.company_id,
                        role=invite.role,
                        is_company_admin=False
                    )

                    db.session.add(user)
                    invite.is_used = True
                    db.session.commit()
                    return redirect(url_for('login'))

    return render_template('register_join.html', message=message, form_data=form_data)

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

@app.route('/search_companies')
@login_required
def search_companies():
    q = request.args.get('q', '').strip()
    if q:
        results = Company.query.filter(
            (Company.name.ilike(f'%{q}%')) |
            (Company.tax_number.ilike(f'%{q}%')) |
            (Company.country.ilike(f'%{q}%'))
        ).all()
    else:
        results = Company.query.all()

    companies_data = []
    for c in results:
        emp_count = len(c.users) if getattr(c, 'users', None) else 0

        companies_data.append({
            'company_id': c.company_id,
            'name': c.name or '',
            'country': c.country or '',
            'post_code': c.post_code or '',
            'street': c.street or '',
            'house_number': c.house_number or '',
            'tax_number': c.tax_number or '',
            'created_at': c.created_at.strftime('%Y-%m-%d') if c.created_at else '',
            'employee_count': emp_count
        })
    return jsonify(companies_data)

# -------------------------
# COMPANY PROFILE by slug (company name without accents)
# -------------------------
@app.route('/company/<slug>')
@login_required
def company_profile(slug):
    company = Company.query.filter_by(slug=slug).first_or_404()
    return render_template('company_profile.html', company=company)


@app.route("/profile")
@login_required
def profile():
    user = current_user
    return render_template("profile.html", user=user)

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
