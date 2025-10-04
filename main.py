from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database.databse import Base, engine
from app.api import api_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Employee Expense Management API",
    description="A comprehensive API for managing employee expenses and companies",
    version="1.0.0",
)

origins = [
    "http://localhost:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

@app.get("/")
def read_root():
    return {
        "message": "Welcome to the Employee Expense Management API",
        "version": "1.0.0",
    }