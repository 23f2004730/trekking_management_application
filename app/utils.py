from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user


def admin_required(f):
    """Allow only Admin users. Everyone else is sent back to login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('auth.login'))
        if current_user.role != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def staff_required(f):
    """
    Allow only Trek Staff whose profile status is 'Approved'.
    Pending staff → pending page. Others → login.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('auth.login'))
        if current_user.role != 'staff':
            flash('Trek Staff access required.', 'danger')
            return redirect(url_for('auth.login'))
        # Staff profile must exist and be Approved
        if (not current_user.staff_profile
                or current_user.staff_profile.status != 'Approved'):
            return redirect(url_for('auth.pending'))
        return f(*args, **kwargs)
    return decorated


def trekker_required(f):
    """Allow only Trekker (user) role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('auth.login'))
        if current_user.role != 'trekker':
            flash('Please log in as a Trekker to access this page.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated