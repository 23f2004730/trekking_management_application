import os

# Base directory of the project
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """
    Central configuration for the Flask application.
    All settings are defined here and loaded via app.config.from_object(Config).
    """

    SECRET_KEY = os.environ.get("SECRET_KEY", "trek-secret-key-change-in-production")

    # SQLite database path — stored inside the /instance folder
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "instance", "trek.db")

    # Disable modification tracking — saves memory, not needed here
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Debug mode — set to False in production
    DEBUG = True