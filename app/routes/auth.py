

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, StaffProfile

auth_bp = Blueprint('auth', __name__)


# Helper: send a logged-in user to their role-appropriate dashboard
def redirect_to_dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin.dashboard'))
    elif current_user.role == 'staff':
        if (current_user.staff_profile
                and current_user.staff_profile.status == 'Approved'):
            return redirect(url_for('staff.dashboard'))
        return redirect(url_for('auth.pending'))
    else:
        return redirect(url_for('user.dashboard'))


# Home / Index
@auth_bp.route('/')
def index():
    """Root URL: go to dashboard if logged in, else show login."""
    if current_user.is_authenticated:
        return redirect_to_dashboard()
    return redirect(url_for('auth.login'))


# Login
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect_to_dashboard()

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Please enter both username and password.', 'danger')
            return render_template('auth/login.html')

        user = User.query.filter_by(username=username).first()

        # Wrong username or password
        if not user or not user.check_password(password):
            flash('Invalid username or password. Please try again.', 'danger')
            return render_template('auth/login.html')

        # Blacklisted users — is_active returns False so Flask-Login
        # would reject them anyway, but we give a better message here
        if user.is_blacklisted:
            flash(
                'Your account has been suspended. '
                'Please contact the administrator.',
                'danger'
            )
            return render_template('auth/login.html')

        # ✅ All good — log in via Flask-Login (session cookie)
        login_user(user)
        flash(f'Welcome back, {user.full_name}!', 'success')
        return redirect_to_dashboard()

    return render_template('auth/login.html')


# Register
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Registration for Trekkers and Trek Staff.
    Admin cannot register — admin is pre-seeded in the database.
    Staff need admin approval before they can access the dashboard.
    """
    if current_user.is_authenticated:
        return redirect_to_dashboard()

    if request.method == 'POST':
        # ── 1. Collect form data
        username          = request.form.get('username', '').strip()
        email             = request.form.get('email', '').strip().lower()
        full_name         = request.form.get('full_name', '').strip()
        phone             = request.form.get('phone', '').strip()
        password          = request.form.get('password', '')
        confirm_password  = request.form.get('confirm_password', '')
        role              = request.form.get('role', 'trekker')

        # Staff-only fields (ignored when role == 'trekker')
        bio               = request.form.get('bio', '').strip()
        exp_raw           = request.form.get('experience_years', '0').strip()
        specialization    = request.form.get('specialization', '').strip()
        emergency_contact = request.form.get('emergency_contact', '').strip()

        # ── 2. Validate 
        errors = []

        if not all([username, email, full_name, password, confirm_password]):
            errors.append('All required fields must be filled in.')

        if role not in ('trekker', 'staff'):
            errors.append('Invalid role. Only Trekker or Trek Staff allowed.')

        if len(username) < 3:
            errors.append('Username must be at least 3 characters.')

        if password != confirm_password:
            errors.append('Passwords do not match.')

        if len(password) < 6:
            errors.append('Password must be at least 6 characters.')

        if User.query.filter_by(username=username).first():
            errors.append(f'Username "{username}" is already taken.')

        if User.query.filter_by(email=email).first():
            errors.append(f'Email "{email}" is already registered.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            # Pass form_data back so the user doesn't have to re-type everything
            return render_template('auth/register.html',
                                   form_data=request.form)

        # ── 3. Create User ────────────────────────────────────────────────
        user = User(
            username  = username,
            email     = email,
            full_name = full_name,
            phone     = phone or None,
            role      = role,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()           # generates user.id before the StaffProfile FK

        # ── 4. Create StaffProfile for staff registrants ──────────────────
        if role == 'staff':
            try:
                exp = max(0, int(exp_raw))
            except (ValueError, TypeError):
                exp = 0

            profile = StaffProfile(
                user_id           = user.id,
                bio               = bio or None,
                experience_years  = exp,
                specialization    = specialization or None,
                emergency_contact = emergency_contact or None,
                status            = 'Pending',   # admin must approve
            )
            db.session.add(profile)

        db.session.commit()

        if role == 'staff':
            flash(
                'Registration successful! Your application is pending admin approval. '
                'You will be notified once approved.',
                'info'
            )
        else:
            flash('Registration successful! You can now log in.', 'success')

        return redirect(url_for('auth.login'))

    # GET
    return render_template('auth/register.html', form_data={})


# Logout
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out. See you on the next trek! 🏔️', 'info')
    return redirect(url_for('auth.login'))


# Pending Approval (staff only)
@auth_bp.route('/pending')
@login_required
def pending():
    """Page shown to Trek Staff whose registration is awaiting admin approval."""
    if current_user.role != 'staff':
        return redirect_to_dashboard()
    # If already approved, go to dashboard
    if (current_user.staff_profile
            and current_user.staff_profile.status == 'Approved'):
        return redirect(url_for('staff.dashboard'))
    return render_template('auth/pending.html')