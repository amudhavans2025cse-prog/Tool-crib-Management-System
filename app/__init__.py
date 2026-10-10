import os
from flask import Flask, session, g

from app.database import init_db, seed_db, get_db_connection
from app.models import User


def create_app(test_config=None):
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'tool-crib-secret-sat-2026'),
        DATABASE=os.environ.get('TOOL_CRIB_DB_PATH', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tool_crib.db')),
    )

    if test_config:
        app.config.update(test_config)

    # Initialize and seed database if not exists
    with app.app_context():
        init_db(app.config['DATABASE'])
        seed_db(app.config['DATABASE'])

    # Context processor to inject current logged in user & role to all templates
    @app.context_processor
    def inject_user():
        user_id = session.get('user_id')
        role = session.get('role')
        user_name = session.get('user_name')
        current_user = None
        if user_id:
            conn = get_db_connection(app.config['DATABASE'])
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            current_user = User.from_row(row) if row else None
            conn.close()
        return {
            'current_user': current_user,
            'session_user_id': user_id,
            'session_role': role,
            'session_user_name': user_name
        }

    # Template filter for formatting currency
    @app.template_filter('currency')
    def currency_filter(amount):
        try:
            return f"₹{float(amount):,.2f}"
        except (ValueError, TypeError):
            return "₹0.00"

    # Register blueprints
    from app.routes.auth_routes import auth_bp
    from app.routes.member_routes import member_bp
    from app.routes.admin_routes import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(member_bp)
    app.register_blueprint(admin_bp)

    return app
