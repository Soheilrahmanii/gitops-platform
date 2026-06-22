"""
FastAPI entrypoint.

Registers routers and configures CORS so the plain-HTML frontend
served on port 8081 can call the API on port 8000 without browser blocks.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import provision

app = FastAPI(
    title="GitOps Platform API",
    version="0.1.0",
    description="Self-service provisioning: GitHub repo, K8s namespace, ArgoCD app.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8081"],  # frontend origin
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

app.include_router(provision.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
