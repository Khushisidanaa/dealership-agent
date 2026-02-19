import os
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Dealership Agent"
    debug: bool = True

    # MongoDB (env: MONGODB_URL or MONGO_URI, MONGODB_DB_NAME or MONGO_DB_NAME)
    mongodb_url: str = Field(default="mongodb://localhost:27017")
    mongodb_db_name: str = Field(default="dealership_agent")

    @model_validator(mode="before")
    @classmethod
    def mongo_from_alternate_env(cls, data):
        # Accept MONGO_URI / MONGO_DB_NAME (e.g. Docker) as well as MONGODB_URL / MONGODB_DB_NAME
        if isinstance(data, dict):
            url = data.get("mongodb_url") or os.environ.get("MONGO_URI") or os.environ.get("MONGODB_URL")
            if url is not None:
                data = {**data, "mongodb_url": url}
            db = data.get("mongodb_db_name") or os.environ.get("MONGO_DB_NAME") or os.environ.get("MONGODB_DB_NAME")
            if db is not None:
                data = {**data, "mongodb_db_name": db}
        return data

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
    # Google Maps (Geocoding + Places API for dealership search) ## DROP THIS BROOOO
    google_maps_api_key: str = Field(default="", validation_alias="GOOGLE_MAPS_API_KEY")

    # Foxit PDF Services (hackathon requirement: extract & analyze docs e.g. Carfax)
    foxit_client_id: str = Field(default="", validation_alias="FOXIT_CLIENT_ID")
    foxit_client_secret: str = Field(default="", validation_alias="FOXIT_CLIENT_SECRET")
    foxit_api_host: str = Field(
        default="https://na1.fusion.foxit.com",
        validation_alias="FOXIT_API_HOST",
    )

    # Server
    server_base_url: str = "http://127.0.0.1:5000"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",  # ignore env vars that don't match any field (e.g. TO_NUMBER, PORT, MONGODB_*)
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
