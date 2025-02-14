from flask import Flask
from flask_apscheduler import APScheduler
from flask_sqlalchemy import SQLAlchemy
from os import path
from flask_login import LoginManager
from flask_moment import Moment
import re
import os

db = SQLAlchemy()
DB_NAME = "database.db"
scheduler = APScheduler()

def create_app():
    app = Flask(__name__, static_folder='static')
    moment = Moment(app)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-for-local')
    # Add this custom filter
    @app.template_filter('regex_replace')
    def regex_replace(s, find, replace):
        return re.sub(find, replace, s)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
    db.init_app(app)

    from .views import views
    from .auth import auth

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')

    from .models import User, Note
    
    with app.app_context():
        db.create_all()

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))
    
    scheduler.init_app(app)
    scheduler.start()

    return app

def create_database(app):
    if not path.exists('website/' + DB_NAME):
        db.create_all(app=app)
        print('Created Database!')
