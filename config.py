# config.py
import os

# Get the project root directory
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    """Base configuration."""
    # ... other common config variables ...
    # SECRET_KEY = os.environ.get('SECRET_KEY') or 'default-secret-key'
    SECRET_KEY = os.urandom(24).hex()
    APIKEY = os.environ.get('APIKEY')
    # Define a default log directory relative to the project root
    # Note: Using basedir is a good practice for non-instance files
    LOG_DIR = os.path.join(basedir, 'logs') 
    LOG_LEVEL = 'INFO'
    # DATABASE_PATH = os.path.join(basedir, 'instance', 'app.db')
    DATABASE_PATH = os.path.join(os.environ.get('DATABASE_PATH'), 'database.db')

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    LOG_LEVEL = 'DEBUG' # Log more for development
    # You might want logs in a temporary dev folder:
    # LOG_DIR = os.path.join(basedir, 'dev_logs') 
    LOG_DIR = '/var/www/flaskcocapisite.com/logs'
    
class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    LOG_LEVEL = 'INFO' # Log less for production
    # Use an absolute path for production logs
    #LOG_DIR = '/var/log/your_flask_app' 
    LOG_DIR = '/var/www/flaskcocapisite.com/logs'
    # Ensure this directory is writable by the Apache user (e.g., www-data)
    # This value would be read via os.environ.get('DATABASE_URL') for a remote database.

