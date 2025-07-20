from flask import Blueprint

clan_bp = Blueprint('clan', __name__, url_prefix='/api/clan')

# Import routes here to associate them with the blueprint
from . import routes

