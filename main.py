from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from datetime import datetime
import re  # Regex a jelszó ellenőrzéshez

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# -------------------------
# MODELS
# -------------------------
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
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class User(db.Model, UserMixin):
    user_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    hashed_password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), default="common_user")
    company_id = db.Column(db.Integer, db.ForeignKey('company.company_id'))
    is_company_admin = db.Column(db.Boolean, default=False)
    common_user = db.Column(db.Boolean, default=True)

    def get_id(self):
        return str(self.user_id)

class InviteCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.company_id'), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# -------------------------
# LOGIN MANAGER
# -------------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------------------------
# PASSWORD VALIDATOR
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

@app.route('/register_create', methods=['GET', 'POST'])
def register_create():
    form_data = {}
    message = None

    if request.method == 'POST':
        form_data = request.form.to_dict()
        email = form_data.get('email')
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
                db.session.flush()

                hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
                user = User(
                    email=email,
                    hashed_password=hashed_pw,
                    company_id=company.company_id,
                    is_company_admin=True
                )
                db.session.add(user)
                db.session.commit()
                return redirect(url_for('login'))

    return render_template('register_create.html', message=message, form_data=form_data)

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

@app.route('/companies')
@login_required
def companies():
    return render_template('companies.html', user=current_user)

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

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
