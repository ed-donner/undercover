import pytest

from backend import db


@pytest.fixture(autouse=True)
def _fresh_database():
    """Reset the database before every test, so each one starts from the seed."""
    db.reset_database()
