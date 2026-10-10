from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from app.database import get_db_connection
from app.models import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'Admin':
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('member.dashboard'))
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    conn = get_db_connection(current_app.config['DATABASE'])
    cursor = conn.cursor()

    if request.method == 'POST':
        user_id = request.form.get('user_id', '').strip()
        cursor.execute("SELECT * FROM users WHERE UPPER(id) = UPPER(?)", (user_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            flash(f"User with ID '{user_id}' not found. Please choose from the available sample accounts.", "danger")
            return redirect(url_for('auth.login'))

        user = User.from_row(row)
        session['user_id'] = user.id
        session['user_name'] = user.name
        session['role'] = user.role
        session['phone'] = user.phone
        session['membership_status'] = user.membership_status

        flash(f"Welcome, {user.name}! Logged in as {user.role}.", "success")
        if user.role == 'Admin':
            return redirect(url_for('admin.dashboard'))
        else:
            return redirect(url_for('member.dashboard'))

    cursor.execute("SELECT * FROM users ORDER BY role DESC, id ASC")
    users = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return render_template('login.html', users=users)


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for('auth.login'))
