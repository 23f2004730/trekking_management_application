from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# Extensions — initialised here, bound to app in create_app()
db = SQLAlchemy()
login_manager = LoginManager()


def create_app():
    """
    Application Factory Pattern.
    Creates and configures the Flask app instance.
    This pattern makes the app easier to test and avoids circular imports.
    """
    app = Flask(__name__)

    # Load configuration from config.py
    app.config.from_object("config.Config")

    # Bind extensions to the app
    db.init_app(app)
    login_manager.init_app(app)

    # Where to redirect unauthenticated users
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    
    from app import models

 
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return db.session.get(User, int(user_id))

    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.staff import staff_bp
    from app.routes.user import user_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(staff_bp, url_prefix="/staff")
    app.register_blueprint(user_bp, url_prefix="/user")

    return app