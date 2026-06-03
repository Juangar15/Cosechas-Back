from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import tickets, webhook, franquicias, analytics

app = FastAPI(title="Chatbot Cosechas - Backend Stateless")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tickets.router)
app.include_router(webhook.router)
app.include_router(franquicias.router)
app.include_router(analytics.router)