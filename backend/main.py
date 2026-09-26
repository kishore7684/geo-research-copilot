# backend/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import create_db
from backend.routers import dataset, research, pipeline

app = FastAPI(
    title="GEO Research Copilot",
    description="AI-powered bioinformatics research assistant",
    version="0.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.on_event("startup")
def on_startup():
    create_db()

app.include_router(dataset.router)
app.include_router(research.router)
app.include_router(pipeline.router)

@app.get("/")
def root():
    return {"status": "running", "version": "0.3.0"}
