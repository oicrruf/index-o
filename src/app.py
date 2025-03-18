from fastapi import FastAPI
from src.controllers import router as api_router

app = FastAPI()

app.include_router(api_router)

@app.get("/health")
def health_check():
    return {"status": "ok"}