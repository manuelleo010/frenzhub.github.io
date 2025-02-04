import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Session lasts 15 minutes of inactivity.
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=15)
    # Upload folder for media files
    UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
