from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Dealership Agent"
    debug: bool = True

    # MongoDB (env: MONGO_URI or MONGODB_URL, MONGO_DB_NAME or MONGODB_DB_NAME for Docker/Linode)
    mongodb_url: str = Field(
        default="mongodb://localhost:27017",
        validation_alias="MONGO_URI",
    )
    mongodb_db_name: str = Field(
        default="dealership_agent",
        validation_alias="MONGO_DB_NAME",
    )

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4"

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Deepgram
    deepgram_api_key: str = ""

    # MarketCheck (vehicle listings API)
    marketcheck_api_key: str = Field(default="", validation_alias="MARKETCHECK_API_KEY")

    # Foxit PDF Services (hackathon requirement: extract & analyze docs e.g. Carfax)
    foxit_client_id: str = Field(default="", validation_alias="FOXIT_CLIENT_ID")
    foxit_client_secret: str = Field(default="", validation_alias="FOXIT_CLIENT_SECRET")
    foxit_api_host: str = Field(
        default="https://na1.fusion.foxit.com",
        validation_alias="FOXIT_API_HOST",
    )

    # Server
    server_base_url: str = "http://localhost:8000"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",  # ignore extra env vars (e.g. TO_NUMBER, PORT from .env)
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
