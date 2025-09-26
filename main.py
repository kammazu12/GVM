# BIG APP FOR FREIGHTS
from flask import Flask, render_template
from flask_login import login_required
from sockets import *
from extensions import *
from routes import blueprints
from utils import *
from models import *
from config import *

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
app = Flask(__name__)
app.config['BABEL_DEFAULT_LOCALE'] = 'hu'
app.config['BABEL_SUPPORTED_LOCALES'] = ['hu', 'en', 'de']
app.config.from_object(Config)
with app.app_context():
    db.init_app(app)
bcrypt.init_app(app)
mail.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login.login'
socketio.init_app(app, cors_allowed_origins="*")

for bp in blueprints:
    app.register_blueprint(bp)

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

@app.route('/shipments')
@login_required
def shipments():
    cargos = Cargo.query.order_by(Cargo.created_at.desc()).all()
    return render_template('shipments.html', user=current_user, cargos=cargos)


# -------------------------
# RUN APP
# -------------------------
if __name__ == "__main__":
    print(app.url_map)
    with app.app_context():
        db.create_all()
    # print(app.url_map)
    socketio.run(app, 'localhost', 5000, debug=True)
