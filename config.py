import os
from datetime import timedelta
from dotenv import load_dotenv

# Load .env
load_dotenv()


class Config:
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")

    # Disable tracking
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT secret
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

    # Token expires in 12 hours
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)
