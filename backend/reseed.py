"""Reset the database to the seed data: uv run -m backend.reseed."""

from backend import db

if __name__ == "__main__":
    with db.session() as conn:
        db.seed(conn)
    print("Reseeded the claims queue.")
