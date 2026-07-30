from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]


app = FastAPI(
    title="GeoLens API",
    description="API foundation for GeoLens.",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    """Report process-level API health."""
    return HealthResponse(status="ok")
