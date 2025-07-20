from flask import Blueprint

player_bp = Blueprint('player', __name__, url_prefix='/api/player')

# Import routes here to associate them with the blueprint
from . import routes

