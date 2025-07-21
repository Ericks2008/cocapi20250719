from flask import Flask
# from flask import Flask, jsonify, render_template, request, make_response
# import urllib.request
# import json
# import sqlite3
# import re
# from datetime import datetime, timedelta
# from ast import literal_eval
# import copy
import os
from .utils.logging_config import configure_logging

# app = Flask(__name__)
app = Flask(__name__, instance_relative_config=True)

# Determine which config to load (e.g., from environment variable)
env = os.environ.get('FLASK_ENV', 'production')
if env == 'production':
    from .config import ProductionConfig
    app.config.from_object(ProductionConfig)
else: # default to development
    from .config import DevelopmentConfig
    app.config.from_object(DevelopmentConfig)

# --- Now configure logging with the loaded config ---
configure_logging(app)

SECRET_KEY = app.config.get('SECRET_KEY')
APIKEY = app.config.get('APIKEY')
DATABASE_PATH = app.config.get('DATABASE_PATH')

from .api.cwl import cwl_bp
from .api.clan import clan_bp
from .api.player import player_bp
app.register_blueprint(cwl_bp)
app.register_blueprint(clan_bp)
app.register_blueprint(player_bp)


if __name__ == "__main__":
    app.run()


