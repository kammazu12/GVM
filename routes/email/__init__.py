# routes/email/__init__.py
from flask import Blueprint

email_bp = Blueprint('email', __name__, url_prefix='/email')

from . import views  # a view-ek itt kerülnek betöltésre (nem main-t hívunk)
