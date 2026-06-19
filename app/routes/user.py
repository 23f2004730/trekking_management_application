from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import current_user
from app import db
from app.models import Trek, Booking, User
from app.utils import trekker_required

user_bp = Blueprint('user', __name__)


# DASHBOARD
@user_bp.route('/dashboard')
@trekker_required
def dashboard():
    open_treks  = Trek.query.filter_by(status='Open').order_by(Trek.start_date).limit(4).all()
    my_bookings = (Booking.query
                   .filter_by(user_id=current_user.id)
                   .order_by(Booking.booking_date.desc())
                   .all())

    # Trek IDs the user currently has an active (non-cancelled) booking for
    booked_ids = {b.trek_id for b in my_bookings if b.status != 'Cancelled'}

    stats = {
        'available_treks' : Trek.query.filter_by(status='Open').count(),
        'total_bookings'  : len(my_bookings),
        'active_bookings' : sum(1 for b in my_bookings if b.status == 'Booked'),
        'completed_treks' : sum(1 for b in my_bookings if b.status == 'Completed'),
    }
    return render_template('user/dashboard.html',
                           open_treks=open_treks,
                           my_bookings=my_bookings[:5],
                           booked_ids=booked_ids,
                           stats=stats)


# BROWSE TREKS
@user_bp.route('/treks')
@trekker_required
def treks():
    q           = request.args.get('q', '').strip()
    diff_filter = request.args.get('difficulty', '').strip()
    loc_filter  = request.args.get('location', '').strip()

    # Only Open treks are visible to trekkers
    query = Trek.query.filter_by(status='Open')

    if q:
        query = query.filter(
            db.or_(
                Trek.name.ilike(f'%{q}%'),
                Trek.location.ilike(f'%{q}%'),
            )
        )
    if diff_filter:
        query = query.filter(Trek.difficulty == diff_filter)
    if loc_filter:
        query = query.filter(Trek.location.ilike(f'%{loc_filter}%'))

    all_treks = query.order_by(Trek.start_date.asc()).all()

    # Which of these treks has the user already actively booked?
    booked_ids = {
        b.trek_id
        for b in Booking.query
                         .filter_by(user_id=current_user.id)
                         .filter(Booking.status != 'Cancelled')
                         .all()
    }

    # Unique locations for the filter dropdown
    locations = sorted({t.location for t in Trek.query.filter_by(status='Open').all()})

    return render_template('user/treks.html',
                           treks=all_treks,
                           booked_ids=booked_ids,
                           locations=locations,
                           q=q,
                           diff_filter=diff_filter,
                           loc_filter=loc_filter)


# BOOK A TREK
@user_bp.route('/treks/<int:trek_id>/book', methods=['POST'])
@trekker_required
def book_trek(trek_id):
    trek = db.get_or_404(Trek, trek_id)

    # ── Guard: trek must be Open ──────────────────────────────────────────────
    if trek.status != 'Open':
        flash(f'"{trek.name}" is not open for booking (status: {trek.status}).', 'danger')
        return redirect(url_for('user.treks'))

    # ── Guard: slots must be available ───────────────────────────────────────
    if trek.available_slots <= 0:
        flash(f'"{trek.name}" is fully booked. No slots available.', 'danger')
        return redirect(url_for('user.treks'))

    # ── Guard: no duplicate active booking ───────────────────────────────────
    existing = Booking.query.filter_by(
        user_id=current_user.id,
        trek_id=trek_id
    ).filter(Booking.status != 'Cancelled').first()

    if existing:
        flash(f'You already have an active booking for "{trek.name}".', 'warning')
        return redirect(url_for('user.treks'))

    # ── Create booking + decrement slot ──────────────────────────────────────
    booking = Booking(
        user_id        = current_user.id,
        trek_id        = trek_id,
        status         = 'Booked',
        payment_status = 'Pending',
    )
    trek.available_slots -= 1
    db.session.add(booking)
    db.session.commit()

    flash(
        f'🎉 Successfully booked "{trek.name}"! '
        f'Booking #{booking.id} confirmed.', 'success'
    )
    return redirect(url_for('user.bookings'))


# MY BOOKINGS
@user_bp.route('/bookings')
@trekker_required
def bookings():
    q             = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()

    query = (Booking.query
             .filter_by(user_id=current_user.id)
             .join(Trek, Booking.trek_id == Trek.id))

    if q:
        query = query.filter(Trek.name.ilike(f'%{q}%'))
    if status_filter:
        query = query.filter(Booking.status == status_filter)

    my_bookings = query.order_by(Booking.booking_date.desc()).all()

    return render_template('user/bookings.html',
                           bookings=my_bookings,
                           q=q,
                           status_filter=status_filter)


# CANCEL A BOOKING
@user_bp.route('/bookings/<int:booking_id>/cancel', methods=['POST'])
@trekker_required
def cancel_booking(booking_id):
    booking = db.get_or_404(Booking, booking_id)

    # Security: booking must belong to this user
    if booking.user_id != current_user.id:
        abort(403)

    if booking.status != 'Booked':
        flash(
            f'Cannot cancel — booking is already "{booking.status}".', 'warning'
        )
        return redirect(url_for('user.bookings'))

    # Cancel + restore the slot
    booking.status = 'Cancelled'
    trek = db.session.get(Trek, booking.trek_id)
    if trek and trek.status not in ('Completed',):
        trek.available_slots += 1

    db.session.commit()
    flash(
        f'Booking #{booking.id} for "{booking.trek.name}" has been cancelled. '
        f'Slot restored.', 'info'
    )
    return redirect(url_for('user.bookings'))


# TREKKING HISTORY
@user_bp.route('/history')
@trekker_required
def history():
    # Full history — all bookings ordered newest first
    all_bookings = (Booking.query
                    .filter_by(user_id=current_user.id)
                    .join(Trek, Booking.trek_id == Trek.id)
                    .order_by(Booking.booking_date.desc())
                    .all())

    completed = [b for b in all_bookings if b.status == 'Completed']
    cancelled = [b for b in all_bookings if b.status == 'Cancelled']
    active    = [b for b in all_bookings if b.status == 'Booked']

    stats = {
        'completed': len(completed),
        'cancelled': len(cancelled),
        'active'   : len(active),
        'total'    : len(all_bookings),
    }

    return render_template('user/history.html',
                           all_bookings=all_bookings,
                           stats=stats)


# PROFILE — view and edit
@user_bp.route('/profile', methods=['GET', 'POST'])
@trekker_required
def profile():
    if request.method == 'POST':
        errors = []

        full_name = request.form.get('full_name', '').strip()
        email     = request.form.get('email', '').strip()
        phone     = request.form.get('phone', '').strip()

        # ── Basic field validation ────────────────────────────────────────────
        if not full_name:
            errors.append('Full name is required.')
        if not email:
            errors.append('Email is required.')
        else:
            # Email must be unique (allow own email)
            clash = User.query.filter(
                User.email == email,
                User.id != current_user.id
            ).first()
            if clash:
                errors.append('That email address is already in use.')

        # ── Password change (optional — only if new_password is provided) ─────
        new_password     = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        current_password = request.form.get('current_password', '').strip()
        change_password  = bool(new_password)

        if change_password:
            if not current_password:
                errors.append('Enter your current password to set a new one.')
            elif not current_user.check_password(current_password):
                errors.append('Current password is incorrect.')
            if len(new_password) < 6:
                errors.append('New password must be at least 6 characters.')
            if new_password != confirm_password:
                errors.append('New password and confirmation do not match.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('user/profile.html', form_data=request.form)

        # ── Apply updates ─────────────────────────────────────────────────────
        current_user.full_name = full_name
        current_user.email     = email
        current_user.phone     = phone or None
        if change_password:
            current_user.set_password(new_password)

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('user.profile'))

    return render_template('user/profile.html', form_data={})