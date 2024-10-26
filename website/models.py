from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func
from geopy.exc import GeocoderTimedOut
from geopy.geocoders import Nominatim
from functools import partial
import time

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(10000))
    date = db.Column(db.DateTime(timezone=True), default=func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    first_name = db.Column(db.String(150))
    notes = db.relationship('Note')

class ScraperResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(10000))
    date_created = db.Column(db.DateTime, default=func.now())
    store = db.Column(db.String(100))
    price = db.Column(db.Float)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    product = db.Column(db.String(200))
    target_price = db.Column(db.Float)
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))
    email_notification = db.Column(db.Boolean, default=True)
    user = db.relationship('User')

class ScraperSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    interval = db.Column(db.Integer)  # minutes between runs
    active = db.Column(db.Boolean, default=True)
    last_run = db.Column(db.DateTime)
    next_run = db.Column(db.DateTime)
    product = db.Column(db.String(200))
    target_price = db.Column(db.Float)
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))
    email_notification = db.Column(db.Boolean, default=True)
    user = db.relationship('User')

class SavedSearch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    product = db.Column(db.String(200))
    target_price = db.Column(db.Float)
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))
    email_notification = db.Column(db.Boolean, default=True)
    date_created = db.Column(db.DateTime, default=func.now())
    user = db.relationship('User')
