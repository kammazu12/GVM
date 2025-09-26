# routes/home/views.py
from flask import render_template, redirect, url_for
from flask_login import current_user, login_required
from . import home_bp
from models import Cargo

@home_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('home.home'))
    return redirect(url_for('login.login'))


@home_bp.route('/home', endpoint='home')
@login_required
def home():
    cargos = Cargo.query.filter_by(user_id=current_user.user_id).all()
    return render_template('home.html', cargos=cargos, user=current_user)
