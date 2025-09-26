# routes/login/views.py
from flask_login import login_user, login_required, current_user, logout_user
from flask import request, render_template, redirect, url_for, session
from utils import *
from . import login_bp
from models import *
from extensions import *
from google_auth_oauthlib.flow import Flow

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

@login_bp.route('/login', endpoint='login', methods=['GET', 'POST'])
def login():
    message = None
    email = ""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.hashed_password, password):
            login_user(user)
            return redirect(url_for('home.home'))
        else:
            message = "Invalid credentials"
    return render_template('login.html', message=message, email=email)

@login_bp.route('/login-google', endpoint='login_google')
@login_required
def login_google():
    flow = Flow.from_client_secrets_file(
        'client_secret.json',
        scopes=SCOPES,
        redirect_uri=current_app.config['GOOGLE_REDIRECT_URI']
    )

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )

    session['state'] = state
    return redirect(authorization_url)

@login_bp.route('/oauth2callback', endpoint='oauth2callback')
@login_required
def oauth2callback():
    state = session.get('state')
    flow = Flow.from_client_secrets_file(
        'client_secret.json',
        scopes=SCOPES,
        redirect_uri=current_app.config['GOOGLE_REDIRECT_URI'],
        state=state
    )
    flow.fetch_token(authorization_response=request.url)

    creds = flow.credentials
    # Mentés ideiglenesen dict-be, user_id alapján
    user_tokens[current_user.user_id] = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes
    }
    return redirect(url_for('cargo.cargo'))


@login_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login.login'))
