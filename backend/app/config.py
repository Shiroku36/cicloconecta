import os
from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "CicloConecta API"
    version: str = "0.1.0"
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    environment: str = os.getenv("ENVIRONMENT", "development")
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
        ).split(",")
        if origin.strip()
    ]

    # Path to data/cities
    data_dir: Path = (
        Path(os.getenv("DATA_DIR"))
        if os.getenv("DATA_DIR")
        else Path(__file__).resolve().parent.parent.parent / "data" / "cities"
    )


settings = Settings()
