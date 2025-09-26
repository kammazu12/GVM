# routes/chat/__init__.py
from flask import Blueprint

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

from . import views  # a view-ek itt kerülnek betöltésre (nem main-t hívunk)
