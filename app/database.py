import os
import sqlite3
from datetime import datetime

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tool_crib.db')


def get_db_connection(db_path=None):
    """Establishes an SQLite database connection with row factory and foreign keys enabled."""
    path = db_path or os.environ.get('TOOL_CRIB_DB_PATH') or DEFAULT_DB_PATH
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path=None):
    """Initializes the database schema if tables do not exist."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # 1. users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('Member', 'Admin')),
        phone TEXT NOT NULL,
        membership_status TEXT NOT NULL CHECK(membership_status IN ('ACTIVE', 'INACTIVE', 'SUSPENDED'))
    );
    """)

    # 2. items table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
        available INTEGER NOT NULL DEFAULT 1 CHECK(available IN (0, 1)),
        created_at TEXT NOT NULL
    );
    """)

    # 3. loan_requests table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS loan_requests (
        id TEXT PRIMARY KEY,
        member_id TEXT NOT NULL,
        item_id TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('REQUESTED', 'ISSUED', 'CANCELLED', 'REJECTED')),
        created_at TEXT NOT NULL,
        FOREIGN KEY (member_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
    );
    """)

    # 4. loans table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS loans (
        id TEXT PRIMARY KEY,
        request_id TEXT,
        member_id TEXT NOT NULL,
        item_id TEXT NOT NULL,
        item_title_snapshot TEXT NOT NULL,
        issue_date TEXT NOT NULL,
        due_date TEXT NOT NULL,
        return_date TEXT,
        status TEXT NOT NULL CHECK(status IN ('ISSUED', 'RETURNED')),
        FOREIGN KEY (request_id) REFERENCES loan_requests(id) ON DELETE SET NULL,
        FOREIGN KEY (member_id) REFERENCES users(id) ON DELETE RESTRICT,
        FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE RESTRICT
    );
    """)

    # 5. loan_status_history table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS loan_status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference_id TEXT NOT NULL,
        actor_id TEXT NOT NULL,
        old_status TEXT,
        new_status TEXT NOT NULL,
        event_at TEXT NOT NULL
    );
    """)

    conn.commit()
    conn.close()


def seed_db(db_path=None, force=False):
    """Seeds the initial required sample data if not already seeded."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Check if items already exist
    cursor.execute("SELECT COUNT(*) FROM items")
    item_count = cursor.fetchone()[0]

    if item_count == 0 or force:
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Insert / Update Required Synthetic Users: 2 Members, 1 Admin
        users_data = [
            ('M101', 'Alice Johnson', 'Member', '9876543210', 'ACTIVE'),
            ('M102', 'Bob Smith', 'Member', '9123456780', 'ACTIVE'),
            ('A101', 'Librarian Admin', 'Admin', '9000000000', 'ACTIVE')
        ]
        cursor.executemany("""
            INSERT OR REPLACE INTO users (id, name, role, phone, membership_status)
            VALUES (?, ?, ?, ?, ?)
        """, users_data)

        # Insert Required Initial Tool Records:
        # I101 | Tool A | Available
        # I102 | Tool B | Available
        # I103 | Tool C | Unavailable
        # I104 | Tool D | Available
        items_data = [
            ('I101', 'Tool A', 'Precision Hand Tools', 1, 1, now_str),
            ('I102', 'Tool B', 'Measuring Instruments', 1, 1, now_str),
            ('I103', 'Tool C', 'Machining & Diagnostic', 1, 0, now_str),
            ('I104', 'Tool D', 'Cutting & Fabrication', 1, 1, now_str)
        ]
        cursor.executemany("""
            INSERT OR REPLACE INTO items (id, title, category, active, available, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, items_data)

        conn.commit()

    conn.close()
