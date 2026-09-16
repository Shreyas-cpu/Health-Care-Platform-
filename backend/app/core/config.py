from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Find root .env
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE if ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PROJECT_NAME: str = "Digital Healthcare Services Platform"
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres_password@localhost:5432/healthcare_platform"
    SYNC_DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres_password@localhost:5432/healthcare_platform"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT Security
    JWT_SECRET_KEY: str = (
        "dev_insecure_jwt_secret_healthcare_platform_2026_change_in_prod"
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Razorpay
    RAZORPAY_KEY_ID: str = "rzp_test_healthcare_sandbox_key"
    RAZORPAY_KEY_SECRET: str = "rzp_test_healthcare_sandbox_secret"
    RAZORPAY_WEBHOOK_SECRET: str = "rzp_webhook_secret_placeholder"

    # S3 / MinIO
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_REGION: str = "ap-south-1"
    S3_BUCKET_DOCUMENTS: str = "doctor-documents"
    S3_BUCKET_PRESCRIPTIONS: str = "prescriptions"
    S3_BUCKET_PATIENT_DOCUMENTS: str = "patient-documents"
    S3_USE_SSL: bool = False

    # LiveKit
    LIVEKIT_URL: str = "ws://localhost:7880"
    LIVEKIT_API_KEY: str = "devkey"
    LIVEKIT_API_SECRET: str = "secret"

    # Email
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: str = "notifications@healthcare-platform.local"
    EMAILS_FROM_NAME: str = "Healthcare Platform"

    # Firebase Auth
    FIREBASE_PROJECT_ID: str = "healthcare-application-501f4"
    FIREBASE_CREDENTIALS_PATH: str | None = None
    FIREBASE_MOCK_AUTH: bool = True


settings = Settings()
