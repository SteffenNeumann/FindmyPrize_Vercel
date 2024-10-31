"""
This module defines the database models for the application.

The `Note` model represents a note that is associated with a user. It has an `id`, `data`, `date`, and `user_id` field.

The `User` model represents a user of the application. It has an `id`, `email`, `password`, `first_name`, and `notes` field.

The `ScraperResult` model represents the result of a web scraping operation. It has an `id`, `data`, `date_created`, `store`, `price`, `user_id`, `product`, `target_price`, `city`, `country`, `email_notification`, and `user` field.

The `ScraperSchedule` model represents a scheduled web scraping operation. It has an `id`, `user_id`, `interval`, `active`, `last_run`, `next_run`, `product`, `target_price`, `city`, `country`, `email_notification`, and `user` field.

The `SavedSearch` model represents a saved search that a user has created. It has an `id`, `user_id`, `product`, `target_price`, `city`, `country`, `email_notification`, `date_created`, `user`, `schedule_type`, `schedule_time`, and `schedule_days` field.
"""
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
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))
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
    schedule_type = db.Column(db.String(20))
    schedule_time = db.Column(db.Time)
    schedule_days = db.Column(db.String(100))  # Store as comma-separated days
    interval_value = db.Column(db.Integer)
    interval_unit = db.Column(db.String(10))  # 'minutes' or 'hours'    last_run = db.Column(db.DateTime)