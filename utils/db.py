# app/utils/db.py
import sqlite3 # Assuming you are using sqlite3, adjust if using psycopg2, mysql.connector etc.
from flask import g, current_app # If you adopt the more robust Flask connection pattern later
import os

# Example of a more robust Flask pattern for DB connection
# (This would involve registering a teardown function in __init__.py)
def get_db():
    if 'db' not in g:
        DATABASE_PATH = current_app.config.get('DATABASE_PATH')
        #DATABASE_PATH = os.path.join(os.environ.get('DATABASE_PATH'), 'database.db')
        g.db = sqlite3.connect(DATABASE_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

