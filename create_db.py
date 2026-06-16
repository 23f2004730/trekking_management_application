# create_db.py — Database Initialisation & Admin Seeding
# Run this ONCE before starting the app: python create_db.py
# This script:
#   1. Creates all database tables defined in models.py
#   2. Seeds a default Admin user if one doesn't exist yet

from app import create_app, db

app = create_app()

with app.app_context():
    db.create_all()
    print("✅ Database tables created successfully.")
    
    print("ℹ️  Admin seeding will be available after Milestone 1.")
    print("\n🚀 Database initialised. Run 'python run.py' to start the app.")