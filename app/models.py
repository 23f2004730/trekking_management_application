from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name     = db.Column(db.String(120), nullable=False)
    phone         = db.Column(db.String(20),  nullable=True)

    role          = db.Column(db.String(20), nullable=False)

    is_blacklisted = db.Column(db.Boolean, default=False, nullable=False)

    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    staff_profile = db.relationship(
        "StaffProfile",
        foreign_keys="StaffProfile.user_id",
        backref="user",       
        uselist=False,        
        lazy=True,
        cascade="all, delete-orphan"
    )

    # One-to-many: a trekker can have many bookings
    bookings = db.relationship(
        "Booking",
        foreign_keys="Booking.user_id",
        backref="trekker",    
        lazy=True,
        cascade="all, delete-orphan"
    )

    # One-to-many: a staff member can be assigned to many treks
    assigned_treks = db.relationship(
        "Trek",
        foreign_keys="Trek.assigned_staff_id",
        backref="assigned_staff", 
        lazy=True
    )

    @property
    def is_active(self):
        """Blacklisted users are considered inactive by Flask-Login."""
        return not self.is_blacklisted

    def set_password(self, password):
        """Hash and store password using Werkzeug's PBKDF2-SHA256."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Return True if the plain-text password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == "admin"

    def is_staff(self):
        return self.role == "staff"

    def is_trekker(self):
        return self.role == "trekker"

    def __repr__(self):
        return f"<User {self.username!r} | role={self.role}>"

class Trek(db.Model):
    __tablename__ = "treks"

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(200), nullable=False)
    location    = db.Column(db.String(200), nullable=False)

    
    difficulty  = db.Column(db.String(20), nullable=False)

    duration    = db.Column(db.Integer, nullable=False)   

    total_slots     = db.Column(db.Integer, nullable=False)
    available_slots = db.Column(db.Integer, nullable=False)

    assigned_staff_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True
    )

    status      = db.Column(db.String(20), default="Pending", nullable=False)

    start_date  = db.Column(db.Date, nullable=False)
    end_date    = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text, nullable=True)
    price       = db.Column(db.Float, default=0.0)

    
    created_by  = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    bookings = db.relationship(
        "Booking",
        backref="trek",      
        lazy=True,
        cascade="all, delete-orphan"
    )


    creator = db.relationship(
        "User",
        foreign_keys=[created_by]
    )

    
    @property
    def booked_count(self):
        """Number of active (non-cancelled) bookings for this trek."""
        return sum(1 for b in self.bookings if b.status != "Cancelled")

    @property
    def is_full(self):
        """True when no slots are left."""
        return self.available_slots <= 0

    @property
    def is_bookable(self):
        """A trek is bookable only when it's Open and has slots."""
        return self.status == "Open" and not self.is_full

    def __repr__(self):
        return f"<Trek {self.name!r} | status={self.status}>"



class Booking(db.Model):
    __tablename__ = "bookings"

    id           = db.Column(db.Integer, primary_key=True)

    user_id      = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )

    trek_id      = db.Column(
        db.Integer, db.ForeignKey("treks.id"), nullable=False
    )

    booking_date = db.Column(db.DateTime, default=datetime.utcnow)

    status       = db.Column(db.String(20), default="Booked", nullable=False)

    payment_status = db.Column(db.String(20), default="Pending", nullable=False)

    notes        = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return (
            f"<Booking #{self.id} | "
            f"user={self.user_id} trek={self.trek_id} | "
            f"status={self.status}>"
        )



class StaffProfile(db.Model):
    __tablename__ = "staff_profiles"

    id           = db.Column(db.Integer, primary_key=True)

    user_id      = db.Column(
        db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False
    )

    bio              = db.Column(db.Text, nullable=True)
    experience_years = db.Column(db.Integer, default=0)
    emergency_contact = db.Column(db.String(20), nullable=True)

    specialization   = db.Column(db.String(100), nullable=True)

    status       = db.Column(db.String(20), default="Pending", nullable=False)

    approved_by  = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True
    )
    approved_at  = db.Column(db.DateTime, nullable=True)

    approver = db.relationship("User", foreign_keys=[approved_by])

    def __repr__(self):
        return f"<StaffProfile | user_id={self.user_id} | status={self.status}>"