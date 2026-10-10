import os
import tempfile
import pytest
from app.database import init_db, seed_db, get_db_connection
from app.services.member_service import MemberService
from app.services.loan_service import LoanService


@pytest.fixture
def test_db():
    """Provides a fresh isolated SQLite database file for each test."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_tool_crib.db')
    init_db(db_path)
    seed_db(db_path, force=True)
    yield db_path
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


@pytest.fixture
def member_service(test_db):
    return MemberService(db_path=test_db)


@pytest.fixture
def loan_service(test_db):
    return LoanService(db_path=test_db)
