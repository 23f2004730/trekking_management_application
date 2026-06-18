from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import current_user
from app import db
from app.models import Trek, Booking, User
from app.utils import staff_required

staff_bp = Blueprint('staff', __name__)

# Statuses staff members are allowed to set
# (Pending and Approved are admin-only)
STAFF_ALLOWED_STATUSES = ['Open', 'Closed', 'Completed']


# DASHBOARD — overview of all assigned treks
@staff_bp.route('/dashboard')
@staff_required
def dashboard():
    assigned_treks = Trek.query.filter_by(
        assigned_staff_id=current_user.id
    ).order_by(Trek.start_date.asc()).all()

    # Aggregate stats
    total_participants = sum(
        Booking.query.filter_by(trek_id=t.id)
                     .filter(Booking.status != 'Cancelled')
                     .count()
        for t in assigned_treks
    )
    open_count = sum(1 for t in assigned_treks if t.status == 'Open')
    completed_count = sum(1 for t in assigned_treks if t.status == 'Completed')

    stats = {
        'total_treks'      : len(assigned_treks),
        'open_treks'       : open_count,
        'completed_treks'  : completed_count,
        'total_participants': total_participants,
    }

    return render_template('staff/dashboard.html',
                           assigned_treks=assigned_treks,
                           stats=stats)


# TREK DETAIL — view + manage a single assigned trek
@staff_bp.route('/treks/<int:trek_id>')
@staff_required
def trek_detail(trek_id):
    trek = _get_assigned_trek(trek_id)

    # All bookings for this trek (any status), newest first
    bookings = (Booking.query
                .filter_by(trek_id=trek_id)
                .join(User, Booking.user_id == User.id)
                .order_by(Booking.booking_date.desc())
                .all())

    active_count    = sum(1 for b in bookings if b.status != 'Cancelled')
    cancelled_count = sum(1 for b in bookings if b.status == 'Cancelled')
    completed_count = sum(1 for b in bookings if b.status == 'Completed')

    return render_template('staff/trek_detail.html',
                           trek=trek,
                           bookings=bookings,
                           active_count=active_count,
                           cancelled_count=cancelled_count,
                           completed_count=completed_count,
                           allowed_statuses=STAFF_ALLOWED_STATUSES)


# UPDATE TREK — change status and/or available slots
@staff_bp.route('/treks/<int:trek_id>/update', methods=['POST'])
@staff_required
def trek_update(trek_id):
    trek = _get_assigned_trek(trek_id)

    new_status = request.form.get('status', '').strip()
    new_slots  = request.form.get('available_slots', '').strip()
    changed    = False

    # ── Status update 
    if new_status and new_status != trek.status:
        if new_status not in STAFF_ALLOWED_STATUSES:
            flash(f'Invalid status. You can only set: {", ".join(STAFF_ALLOWED_STATUSES)}.', 'danger')
            return redirect(url_for('staff.trek_detail', trek_id=trek_id))
        # Prevent reopening a Completed trek
        if trek.status == 'Completed' and new_status != 'Completed':
            flash('A Completed trek cannot be reopened.', 'danger')
            return redirect(url_for('staff.trek_detail', trek_id=trek_id))
        # Pending / Approved treks must be made Open or Closed by staff only if admin approved
        if trek.status in ('Pending',) and new_status == 'Open':
            flash('Trek must be Approved by Admin before it can be opened.', 'warning')
            return redirect(url_for('staff.trek_detail', trek_id=trek_id))

        trek.status = new_status
        changed = True

    # ── Slots update 
    if new_slots != '':
        try:
            slots_val = int(new_slots)
        except ValueError:
            flash('Available slots must be a whole number.', 'danger')
            return redirect(url_for('staff.trek_detail', trek_id=trek_id))

        if slots_val < 0:
            flash('Available slots cannot be negative.', 'danger')
            return redirect(url_for('staff.trek_detail', trek_id=trek_id))
        if slots_val > trek.total_slots:
            flash(
                f'Available slots ({slots_val}) cannot exceed '
                f'total slots ({trek.total_slots}).', 'danger'
            )
            return redirect(url_for('staff.trek_detail', trek_id=trek_id))

        trek.available_slots = slots_val
        changed = True

    if changed:
        db.session.commit()
        flash('Trek updated successfully.', 'success')
    else:
        flash('No changes detected.', 'info')

    return redirect(url_for('staff.trek_detail', trek_id=trek_id))


# COMPLETE BOOKING — mark one participant's booking as Completed
@staff_bp.route('/treks/<int:trek_id>/bookings/<int:booking_id>/complete',
                methods=['POST'])
@staff_required
def complete_booking(trek_id, booking_id):
    trek    = _get_assigned_trek(trek_id)
    booking = db.get_or_404(Booking, booking_id)

    # Security: booking must belong to this trek
    if booking.trek_id != trek.id:
        flash('Booking does not belong to this trek.', 'danger')
        return redirect(url_for('staff.trek_detail', trek_id=trek_id))

    if booking.status != 'Booked':
        flash(f'Booking is already "{booking.status}" — cannot mark as Completed.', 'warning')
        return redirect(url_for('staff.trek_detail', trek_id=trek_id))

    booking.status = 'Completed'
    db.session.commit()
    flash(
        f'Booking #{booking.id} for {booking.trekker.full_name} '
        f'marked as Completed.', 'success'
    )
    return redirect(url_for('staff.trek_detail', trek_id=trek_id))


# PRIVATE HELPER
def _get_assigned_trek(trek_id):
    """
    Fetch a trek and verify the current staff member is assigned to it.
    Returns the Trek object or flashes an error and aborts.
    """
    trek = db.get_or_404(Trek, trek_id)
    if trek.assigned_staff_id != current_user.id:
        flash('You are not assigned to this trek.', 'danger')
        abort(403)
    return trek