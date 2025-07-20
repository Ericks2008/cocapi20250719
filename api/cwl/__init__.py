from flask import Blueprint

cwl_bp = Blueprint('cwl', __name__, url_prefix='/api/cwl')

# Import routes here to associate them with the blueprint
from . import routes

