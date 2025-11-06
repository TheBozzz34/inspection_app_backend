from fastapi import FastAPI
from . import models
from .database import engine
from .routers import users, templates, inspections
from fastapi.middleware.cors import CORSMiddleware

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Rally Maintenance Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # change in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(templates.router)
app.include_router(inspections.router)
