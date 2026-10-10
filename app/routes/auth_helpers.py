from functools import wraps
from flask import session, redirect, url_for, flash, abort, current_app
from app.database import get_db_connection
from app.models import User


def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    conn = get_db_connection(current_app.config['DATABASE'])
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return User.from_row(row) if row else None


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash("Please select a role / log in to access this page.", "warning")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash("Please log in as Administrator.", "warning")
            return redirect(url_for('auth.login'))
        if session.get('role') != 'Admin':
            flash("Access denied: Administrator privileges required.", "danger")
            return redirect(url_for('member.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def member_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash("Please log in as Member.", "warning")
            return redirect(url_for('auth.login'))
        if session.get('role') != 'Member':
            flash("Access denied: Member view required.", "warning")
            return redirect(url_for('admin.dashboard'))
        return f(*args, **kwargs)
    return decorated_function
