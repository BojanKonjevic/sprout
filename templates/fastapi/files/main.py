from fastapi import FastAPI

from .database import lifespan

app = FastAPI(lifespan=lifespan)


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok"}
