import os
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from generator import PortfolioGenerationError, generate_portfolio


load_dotenv()

app = FastAPI(title="APolo Portfolio API", version="1.0.0")

origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class GeneratePortfolioRequest(BaseModel):
    jobType: Literal["developer", "designer", "cv"]
    careerLevel: Literal["entry", "three_plus", "five_plus", "ten_plus"]
    request: str = Field(min_length=5, max_length=2000)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "openai": "configured" if os.getenv("OPENAI_API_KEY") else "missing_key",
    }


@app.post("/api/portfolio/generate")
def create_portfolio(payload: GeneratePortfolioRequest) -> dict:
    try:
        return generate_portfolio(
            job_type=payload.jobType,
            career_level=payload.careerLevel,
            request=payload.request.strip(),
        )
    except PortfolioGenerationError as exc:
        status_code = 503 if "OPENAI_API_KEY" in str(exc) else 422
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="AI 포트폴리오 생성 중 오류가 발생했습니다.",
        ) from exc
