from flask import Flask
from flask_apscheduler import APScheduler
from flask_sqlalchemy import SQLAlchemy
from os import path
from flask_login import LoginManager
from flask_moment import Moment
import os

db = SQLAlchemy()
scheduler = APScheduler()

def create_app():
    app = Flask(__name__, static_folder='static')
    moment = Moment(app)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-for-local')
    
    # Get the database URL from environment variables
    database_url = os.getenv('POSTGRES_URL')
    
    # Clean and format the database URL
    if database_url:
        # Remove any supa-related components completely
        database_url = database_url.replace('supa://', 'postgresql://')
        database_url = database_url.replace('?supa=', '?')
        # Ensure proper postgresql prefix
        if not database_url.startswith('postgresql://'):
            database_url = f'postgresql://{database_url}'    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    from .views import views
    from .auth import auth

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')

    from .models import User
    
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
    if not path.exists('website/database.db'):
        db.create_all(app=app)
        print('Created Database!')
        