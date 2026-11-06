"""The Shoppie support backend."""

from fastapi import FastAPI

app = FastAPI(title="Shoppie")


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}
