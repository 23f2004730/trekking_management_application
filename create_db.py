from datetime import date, datetime
from app import create_app, db
from app.models import User, Trek, Booking, StaffProfile

app = create_app()

with app.app_context():

    # STEP 1 — Create all tables-
    db.create_all()
    print("\n All database tables created successfully.\n")
    print("   Tables: users, treks, bookings, staff_profiles")
    print("-" * 55)

    # STEP 2 — Seed Admin (pre-existing superuser, no registration allowed)
    if not User.query.filter_by(role="admin").first():
        admin = User(
            username  = "admin",
            email     = "admin@trekapp.com",
            full_name = "System Administrator",
            phone     = "9000000000",
            role      = "admin",
        )
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
        print(" Admin seeded")
        print("   username : admin")
        print("   password : admin123")
    else:
        print("ℹ️  Admin already exists — skipping.")
    print("-" * 55)


    # STEP 3 — Seed sample Trekkers (Users)

    trekkers_data = [
        dict(username="arjun",  email="arjun@mail.com",  full_name="Arjun Sharma",    phone="9111111111"),
        dict(username="priya",  email="priya@mail.com",  full_name="Priya Nair",      phone="9222222222"),
        dict(username="rahul",  email="rahul@mail.com",  full_name="Rahul Verma",     phone="9333333333"),
    ]
    for t in trekkers_data:
        if not User.query.filter_by(username=t["username"]).first():
            u = User(role="trekker", **t)
            u.set_password("password123")
            db.session.add(u)
    db.session.commit()
    print(" Sample trekkers seeded (password: password123)")
    print("   Users: arjun, priya, rahul")
    print("-" * 55)

    # STEP 4 — Seed sample Staff members + their profiles
    admin_user = User.query.filter_by(role="admin").first()

    staff_data = [
        dict(
            username="ravi_guide", email="ravi@staff.com",
            full_name="Ravi Kumar",  phone="9444444444",
            profile=dict(bio="Expert trekker with 8 years experience.",
                         experience_years=8, specialization="High Altitude",
                         emergency_contact="9444444445", status="Approved")
        ),
        dict(
            username="meena_guide", email="meena@staff.com",
            full_name="Meena Pillai", phone="9555555555",
            profile=dict(bio="Forest trek specialist, certified guide.",
                         experience_years=5, specialization="Forest",
                         emergency_contact="9555555556", status="Pending")
        ),
    ]
    for s in staff_data:
        if not User.query.filter_by(username=s["username"]).first():
            user = User(
                username  = s["username"],
                email     = s["email"],
                full_name = s["full_name"],
                phone     = s["phone"],
                role      = "staff",
            )
            user.set_password("staffpass123")
            db.session.add(user)
            db.session.flush()   # get user.id before commit

            pdata = s["profile"]
            sp = StaffProfile(
                user_id           = user.id,
                bio               = pdata["bio"],
                experience_years  = pdata["experience_years"],
                specialization    = pdata["specialization"],
                emergency_contact = pdata["emergency_contact"],
                status            = pdata["status"],
                approved_by       = admin_user.id if pdata["status"] == "Approved" else None,
                approved_at       = datetime.utcnow() if pdata["status"] == "Approved" else None,
            )
            db.session.add(sp)
    db.session.commit()
    print(" Sample staff seeded (password: staffpass123)")
    print("   Staff : ravi_guide (Approved), meena_guide (Pending)")
    print("-" * 55)

    # STEP 5 — Seed sample Treks
    ravi = User.query.filter_by(username="ravi_guide").first()

    treks_data = [
        dict(
            name="Kedarnath Trek", location="Uttarakhand",
            difficulty="Hard", duration=6,
            total_slots=20, available_slots=15,
            status="Open",
            start_date=date(2025, 10, 1), end_date=date(2025, 10, 6),
            description="A challenging high-altitude trek to the Kedarnath temple.",
            price=4500.0, assigned_staff_id=ravi.id
        ),
        dict(
            name="Valley of Flowers", location="Himachal Pradesh",
            difficulty="Moderate", duration=4,
            total_slots=15, available_slots=15,
            status="Open",
            start_date=date(2025, 9, 15), end_date=date(2025, 9, 18),
            description="Stunning alpine meadows bursting with wildflowers.",
            price=3000.0, assigned_staff_id=ravi.id
        ),
        dict(
            name="Coorg Forest Walk", location="Karnataka",
            difficulty="Easy", duration=2,
            total_slots=25, available_slots=25,
            status="Approved",
            start_date=date(2025, 11, 5), end_date=date(2025, 11, 6),
            description="A serene walk through the coffee plantations of Coorg.",
            price=1500.0, assigned_staff_id=None
        ),
        dict(
            name="Roopkund Skeleton Lake", location="Uttarakhand",
            difficulty="Hard", duration=8,
            total_slots=12, available_slots=12,
            status="Pending",
            start_date=date(2025, 12, 1), end_date=date(2025, 12, 8),
            description="A mysterious high-altitude glacial lake with ancient skeletons.",
            price=6000.0, assigned_staff_id=None
        ),
        dict(
            name="Hampta Pass", location="Himachal Pradesh",
            difficulty="Moderate", duration=5,
            total_slots=18, available_slots=0,
            status="Closed",
            start_date=date(2025, 8, 10), end_date=date(2025, 8, 14),
            description="A dramatic crossover between Kullu and Lahaul valleys.",
            price=3500.0, assigned_staff_id=ravi.id
        ),
    ]
    for t in treks_data:
        if not Trek.query.filter_by(name=t["name"]).first():
            trek = Trek(created_by=admin_user.id, **t)
            db.session.add(trek)
    db.session.commit()
    print(" Sample treks seeded")
    print("   Treks : Kedarnath (Open·Hard), Valley of Flowers (Open·Moderate),")
    print("           Coorg Forest Walk (Approved·Easy), Roopkund (Pending·Hard),")
    print("           Hampta Pass (Closed·Moderate)")
    print("-" * 55)

    # Seed a sample Booking (arjun books Kedarnath)
    arjun     = User.query.filter_by(username="arjun").first()
    kedarnath = Trek.query.filter_by(name="Kedarnath Trek").first()

    if arjun and kedarnath:
        exists = Booking.query.filter_by(
            user_id=arjun.id, trek_id=kedarnath.id
        ).first()
        if not exists:
            booking = Booking(
                user_id        = arjun.id,
                trek_id        = kedarnath.id,
                status         = "Booked",
                payment_status = "Paid",
            )
            db.session.add(booking)
            # Reflect slot reduction
            kedarnath.available_slots -= 1
            db.session.commit()
            print(" Sample booking seeded: arjun → Kedarnath Trek")
        else:
            print("ℹ  Sample booking already exists — skipping.")

    print("-" * 55)
    print("\n Database ready!  Run  python run.py  to start the app.")
    print("\n Login credentials:")
    print("   Admin   → username: admin       | password: admin123")
    print("   Staff   → username: ravi_guide  | password: staffpass123")
    print("   Trekker → username: arjun       | password: password123")
    print()