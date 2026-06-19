from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user
from app import db
from app.models import User, Trek, Booking, StaffProfile
from app.utils import admin_required

admin_bp = Blueprint('admin', __name__)


# DASHBOARD
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    stats = {
        'total_treks'   : Trek.query.count(),
        'total_users'   : User.query.filter_by(role='trekker').count(),
        'total_staff'   : User.query.filter_by(role='staff').count(),
        'total_bookings': Booking.query.count(),
        'pending_staff' : StaffProfile.query.filter_by(status='Pending').count(),
        'open_treks'    : Trek.query.filter_by(status='Open').count(),
    }
    recent_bookings = (
        Booking.query
        .order_by(Booking.booking_date.desc())
        .limit(6).all()
    )
    pending_staff_list = (
        StaffProfile.query
        .filter_by(status='Pending')
        .join(User, StaffProfile.user_id == User.id)
        .order_by(User.created_at.desc())
        .all()
    )
    return render_template('admin/dashboard.html',
                           stats=stats,
                           recent_bookings=recent_bookings,
                           pending_staff_list=pending_staff_list)


# TREK MANAGEMENT
@admin_bp.route('/treks')
@admin_required
def treks():
    q              = request.args.get('q', '').strip()
    diff_filter    = request.args.get('difficulty', '').strip()
    status_filter  = request.args.get('status', '').strip()

    query = Trek.query
    if q:
        if q.isdigit():
            query = query.filter(Trek.id == int(q))
        else:
            query = query.filter(
                db.or_(
                    Trek.name.ilike(f'%{q}%'),
                    Trek.location.ilike(f'%{q}%'),
                )
            )
    if diff_filter:
        query = query.filter(Trek.difficulty == diff_filter)
    if status_filter:
        query = query.filter(Trek.status == status_filter)

    all_treks = query.order_by(Trek.created_at.desc()).all()
    approved_staff = _get_approved_staff()
    return render_template('admin/treks.html',
                           treks=all_treks,
                           approved_staff=approved_staff,
                           q=q, diff_filter=diff_filter,
                           status_filter=status_filter)


@admin_bp.route('/treks/add', methods=['GET', 'POST'])
@admin_required
def trek_add():
    approved_staff = _get_approved_staff()

    if request.method == 'POST':
        errors = _validate_trek_form(request.form, editing=False)
        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('admin/trek_form.html',
                                   trek=None, form_data=request.form,
                                   approved_staff=approved_staff, action='add')
        try:
            slots = int(request.form['total_slots'])
            trek = Trek(
                name        = request.form['name'].strip(),
                location    = request.form['location'].strip(),
                difficulty  = request.form['difficulty'],
                duration    = int(request.form['duration']),
                total_slots = slots,
                available_slots = slots,           # all slots open on creation
                status      = request.form.get('status', 'Pending'),
                start_date  = _parse_date(request.form['start_date']),
                end_date    = _parse_date(request.form['end_date']),
                description = request.form.get('description', '').strip() or None,
                price       = float(request.form.get('price') or 0),
                assigned_staff_id = _parse_optional_int(
                    request.form.get('assigned_staff_id')),
                created_by  = current_user.id,
            )
            db.session.add(trek)
            db.session.commit()
            flash(f'Trek "{trek.name}" created successfully!', 'success')
            return redirect(url_for('admin.treks'))
        except Exception as exc:
            db.session.rollback()
            flash(f'Error creating trek: {exc}', 'danger')

    return render_template('admin/trek_form.html',
                           trek=None, form_data={},
                           approved_staff=approved_staff, action='add')


@admin_bp.route('/treks/<int:trek_id>/edit', methods=['GET', 'POST'])
@admin_required
def trek_edit(trek_id):
    trek           = db.get_or_404(Trek, trek_id)
    approved_staff = _get_approved_staff()

    if request.method == 'POST':
        errors = _validate_trek_form(request.form, editing=True)
        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('admin/trek_form.html',
                                   trek=trek, form_data=request.form,
                                   approved_staff=approved_staff, action='edit')
        try:
            trek.name             = request.form['name'].strip()
            trek.location         = request.form['location'].strip()
            trek.difficulty       = request.form['difficulty']
            trek.duration         = int(request.form['duration'])
            trek.total_slots      = int(request.form['total_slots'])
            trek.available_slots  = int(request.form['available_slots'])
            trek.status           = request.form['status']
            trek.start_date       = _parse_date(request.form['start_date'])
            trek.end_date         = _parse_date(request.form['end_date'])
            trek.description      = request.form.get('description', '').strip() or None
            trek.price            = float(request.form.get('price') or 0)
            trek.assigned_staff_id = _parse_optional_int(
                request.form.get('assigned_staff_id'))
            db.session.commit()
            flash(f'Trek "{trek.name}" updated successfully!', 'success')
            return redirect(url_for('admin.treks'))
        except Exception as exc:
            db.session.rollback()
            flash(f'Error updating trek: {exc}', 'danger')

    return render_template('admin/trek_form.html',
                           trek=trek, form_data={},
                           approved_staff=approved_staff, action='edit')


@admin_bp.route('/treks/<int:trek_id>/delete', methods=['POST'])
@admin_required
def trek_delete(trek_id):
    trek = db.get_or_404(Trek, trek_id)
    name = trek.name

    # Block deletion if there are active bookings
    active = Booking.query.filter_by(
        trek_id=trek_id, status='Booked'
    ).count()
    if active:
        flash(
            f'Cannot delete "{name}" — it has {active} active booking(s). '
            'Cancel bookings first.', 'danger'
        )
        return redirect(url_for('admin.treks'))

    db.session.delete(trek)
    db.session.commit()
    flash(f'Trek "{name}" has been deleted.', 'success')
    return redirect(url_for('admin.treks'))


@admin_bp.route('/treks/<int:trek_id>/assign', methods=['POST'])
@admin_required
def trek_assign(trek_id):
    """Quick staff assignment directly from the treks list page."""
    trek     = db.get_or_404(Trek, trek_id)
    staff_id = _parse_optional_int(request.form.get('staff_id'))

    if staff_id:
        staff = db.get_or_404(User, staff_id)
        if staff.role != 'staff' or not staff.staff_profile \
                or staff.staff_profile.status != 'Approved':
            flash('Selected user is not an approved Trek Staff.', 'danger')
            return redirect(url_for('admin.treks'))
        trek.assigned_staff_id = staff.id
        flash(f'"{staff.full_name}" assigned to "{trek.name}".', 'success')
    else:
        trek.assigned_staff_id = None
        flash(f'Staff removed from "{trek.name}".', 'info')

    db.session.commit()
    return redirect(url_for('admin.treks'))


# USER (TREKKER) MANAGEMENT
@admin_bp.route('/users')
@admin_required
def users():
    q = request.args.get('q', '').strip()
    query = User.query.filter_by(role='trekker')
    if q:
        if q.isdigit():
            query = query.filter(User.id == int(q))
        else:
            query = query.filter(
                db.or_(
                    User.username.ilike(f'%{q}%'),
                    User.full_name.ilike(f'%{q}%'),
                    User.email.ilike(f'%{q}%'),
                )
            )
    all_users = query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users, q=q)


@admin_bp.route('/users/<int:user_id>/blacklist', methods=['POST'])
@admin_required
def user_blacklist(user_id):
    user = db.get_or_404(User, user_id)
    if user.role != 'trekker':
        flash('This action is only for Trekker accounts.', 'danger')
        return redirect(url_for('admin.users'))

    user.is_blacklisted = not user.is_blacklisted
    db.session.commit()
    verb = 'blacklisted' if user.is_blacklisted else 'reactivated'
    flash(f'User "{user.username}" has been {verb}.', 'success')
    return redirect(url_for('admin.users'))


# TREK STAFF MANAGEMENT
@admin_bp.route('/staff')
@admin_required
def staff_list():
    q             = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()

    query = User.query.filter_by(role='staff')
    if q:
        if q.isdigit():
            query = query.filter(User.id == int(q))
        else:
            query = query.filter(
                db.or_(
                    User.username.ilike(f'%{q}%'),
                    User.full_name.ilike(f'%{q}%'),
                )
            )
    if status_filter:
        query = (query
                 .join(StaffProfile, User.id == StaffProfile.user_id)
                 .filter(StaffProfile.status == status_filter))

    all_staff = query.order_by(User.created_at.desc()).all()
    return render_template('admin/staff.html',
                           staff=all_staff, q=q,
                           status_filter=status_filter)


@admin_bp.route('/staff/<int:user_id>/approve', methods=['POST'])
@admin_required
def staff_approve(user_id):
    user = db.get_or_404(User, user_id)
    if not user.staff_profile:
        flash('Staff profile not found.', 'danger')
        return redirect(url_for('admin.staff_list'))

    user.staff_profile.status      = 'Approved'
    user.staff_profile.approved_by = current_user.id
    user.staff_profile.approved_at = datetime.utcnow()
    user.is_blacklisted = False
    db.session.commit()
    flash(f'Trek Staff "{user.full_name}" approved successfully.', 'success')
    return redirect(url_for('admin.staff_list'))


@admin_bp.route('/staff/<int:user_id>/reject', methods=['POST'])
@admin_required
def staff_reject(user_id):
    """Reject a pending staff registration."""
    user = db.get_or_404(User, user_id)
    if not user.staff_profile:
        flash('Staff profile not found.', 'danger')
        return redirect(url_for('admin.staff_list'))

    user.staff_profile.status = 'Blacklisted'
    db.session.commit()
    flash(f'Staff "{user.full_name}" registration rejected.', 'warning')
    return redirect(url_for('admin.staff_list'))


@admin_bp.route('/staff/<int:user_id>/blacklist', methods=['POST'])
@admin_required
def staff_blacklist(user_id):
    """Toggle blacklist for an approved staff member."""
    user = db.get_or_404(User, user_id)
    if not user.staff_profile:
        flash('Staff profile not found.', 'danger')
        return redirect(url_for('admin.staff_list'))

    if user.staff_profile.status == 'Blacklisted':
        user.staff_profile.status = 'Approved'
        user.is_blacklisted = False
        flash(f'Staff "{user.full_name}" reactivated.', 'success')
    else:
        user.staff_profile.status = 'Blacklisted'
        user.is_blacklisted = True
        flash(f'Staff "{user.full_name}" blacklisted.', 'warning')

    db.session.commit()
    return redirect(url_for('admin.staff_list'))


# BOOKING RECORDS (read-only view for admin)
@admin_bp.route('/bookings')
@admin_required
def bookings():
    q             = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()

    query = (Booking.query
             .join(User, Booking.user_id == User.id)
             .join(Trek, Booking.trek_id == Trek.id))

    if q:
        query = query.filter(
            db.or_(
                User.username.ilike(f'%{q}%'),
                User.full_name.ilike(f'%{q}%'),
                Trek.name.ilike(f'%{q}%'),
            )
        )
    if status_filter:
        query = query.filter(Booking.status == status_filter)

    all_bookings = query.order_by(Booking.booking_date.desc()).all()
    return render_template('admin/bookings.html',
                           bookings=all_bookings,
                           q=q, status_filter=status_filter)



# PER-TREK BOOKING HISTORY  (M6)
@admin_bp.route('/treks/<int:trek_id>/bookings')
@admin_required
def trek_bookings(trek_id):
    """Full booking history for a single trek — all participants, all statuses."""
    trek = db.get_or_404(Trek, trek_id)

    bookings = (
        Booking.query
        .filter_by(trek_id=trek_id)
        .join(User, Booking.user_id == User.id)
        .order_by(Booking.booking_date.desc())
        .all()
    )

    stats = {
        'total'    : len(bookings),
        'booked'   : sum(1 for b in bookings if b.status == 'Booked'),
        'completed': sum(1 for b in bookings if b.status == 'Completed'),
        'cancelled': sum(1 for b in bookings if b.status == 'Cancelled'),
    }

    return render_template('admin/trek_bookings.html',
                           trek=trek, bookings=bookings, stats=stats)

# PRIVATE HELPERS
def _get_approved_staff():
    """Return all approved staff users for assignment dropdowns."""
    return (User.query
            .join(StaffProfile, User.id == StaffProfile.user_id)
            .filter(StaffProfile.status == 'Approved')
            .order_by(User.full_name)
            .all())


def _parse_date(value):
    """Parse a YYYY-MM-DD string into a date object."""
    return datetime.strptime(value.strip(), '%Y-%m-%d').date()


def _parse_optional_int(value):
    """Return int if value is a non-empty digit string, else None."""
    return int(value) if value and str(value).strip().isdigit() else None


def _validate_trek_form(form, editing=False):
    """Server-side validation for trek add/edit. Returns list of error strings."""
    errors = []
    name          = form.get('name', '').strip()
    location      = form.get('location', '').strip()
    difficulty    = form.get('difficulty', '')
    duration_raw  = form.get('duration', '')
    slots_raw     = form.get('total_slots', '')
    start_raw     = form.get('start_date', '')
    end_raw       = form.get('end_date', '')
    price_raw     = form.get('price', '0')

    if not name:
        errors.append('Trek name is required.')
    if not location:
        errors.append('Location is required.')
    if difficulty not in ('Easy', 'Moderate', 'Hard'):
        errors.append('Difficulty must be Easy, Moderate, or Hard.')

    try:
        if int(duration_raw) < 1:
            errors.append('Duration must be at least 1 day.')
    except (ValueError, TypeError):
        errors.append('Duration must be a valid whole number.')

    try:
        if int(slots_raw) < 1:
            errors.append('Total slots must be at least 1.')
    except (ValueError, TypeError):
        errors.append('Total slots must be a valid whole number.')

    if editing:
        try:
            if int(form.get('available_slots', 0)) < 0:
                errors.append('Available slots cannot be negative.')
        except (ValueError, TypeError):
            errors.append('Available slots must be a valid whole number.')

    start = end = None
    try:
        start = _parse_date(start_raw)
    except (ValueError, AttributeError):
        errors.append('Start date is required (YYYY-MM-DD).')
    try:
        end = _parse_date(end_raw)
    except (ValueError, AttributeError):
        errors.append('End date is required (YYYY-MM-DD).')
    if start and end and end < start:
        errors.append('End date must be on or after the start date.')

    try:
        if float(price_raw or 0) < 0:
            errors.append('Price cannot be negative.')
    except (ValueError, TypeError):
        errors.append('Price must be a valid number.')

    return errors