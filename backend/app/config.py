import os

from pydantic import AliasChoices, Field, model_validator
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
            # Strip AWS credential values in case .env has "KEY = value" (leading space in value)
            ak = data.get("aws_access_key_id")
            if ak is not None and isinstance(ak, str):
                data = {**data, "aws_access_key_id": ak.strip()}
            sk = data.get("aws_secret_access_key")
            if sk is not None and isinstance(sk, str):
                data = {**data, "aws_secret_access_key": sk.strip()}
            # Strip Nova Act hackathon API key (e.g. "KEY = value" in .env)
            nk = data.get("aws_nova_hackathon_api_key")
            if nk is not None and isinstance(nk, str):
                data = {**data, "aws_nova_hackathon_api_key": nk.strip()}
        return data

    # Chat / LLM: Amazon Bedrock (DeepSeek) — used for requirements extraction, summaries, rankings
    bedrock_chat_model_id: str = Field(
        default="deepseek.v3.2",
        validation_alias="BEDROCK_CHAT_MODEL_ID",
    )
    bedrock_region: str = Field(default="us-east-1", validation_alias="BEDROCK_REGION")

    # Legacy OpenAI (optional fallback; prefer Bedrock)
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4", validation_alias="OPENAI_MODEL")

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Deepgram (legacy; voice now uses Nova Sonic when configured)
    deepgram_api_key: str = ""

    # Nova Sonic (voice agent: Twilio + Amazon Nova Sonic, same flow as Deepgram)
    # Uses same AWS credentials as Nova Act (ACCESS_KEY / SECRET_ACCRESS_KEY or AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)
    nova_sonic_model_id: str = Field(
        default="amazon.nova-sonic-v1:0",
        validation_alias="NOVA_SONIC_MODEL_ID",
    )
    nova_sonic_region: str = Field(
        default="us-east-1",
        validation_alias="NOVA_SONIC_REGION",
    )
    # Optional hackathon key from organizers (e.g. AWS_KEY); IAM credentials above are used for Bedrock
    aws_key: str = Field(default="", validation_alias="AWS_KEY")

    # MarketCheck (vehicle listings API)
    marketcheck_api_key: str = Field(default="", validation_alias="MARKETCHECK_API_KEY")
    # Google Maps (Geocoding + Places API for dealership search) ## DROP THIS BROOOO
    google_maps_api_key: str = Field(default="", validation_alias="GOOGLE_MAPS_API_KEY")

    # Car search provider: "nova_act" (AWS Nova Act / Bedrock) or "marketcheck". Default "" = use nova_act when configured, else marketcheck.
    car_search_provider: str = Field(
        default="",
        validation_alias="CAR_SEARCH_PROVIDER",
    )
    # Nova Act (AWS): workflow + model for deployed workflow runs (us-east-1 only)
    nova_act_workflow_name: str = Field(default="", validation_alias="NOVA_ACT_WORKFLOW_NAME")
    nova_act_model_id: str = Field(
        default="us.amazon.nova-2-lite-v1:0",
        validation_alias="NOVA_ACT_MODEL_ID",
    )
    nova_act_region: str = Field(default="us-east-1", validation_alias="NOVA_ACT_REGION")
    # Optional: S3 bucket/prefix where deployed workflow writes result JSON (to read listings)
    nova_act_result_s3_bucket: str = Field(default="", validation_alias="NOVA_ACT_RESULT_S3_BUCKET")
    nova_act_result_s3_prefix: str = Field(default="", validation_alias="NOVA_ACT_RESULT_S3_PREFIX")
    # Nova API key (hackathon; used if Nova REST API is configured elsewhere)
    aws_nova_hackathon_api_key: str = Field(
        default="",
        validation_alias="AWS_NOVA_HACKATHON_API_KEY",
    )
    # AWS credentials for Nova Act / Bedrock (optional)
    # Accept AWS_ACCESS_KEY_ID or ACCESS_KEY; AWS_SECRET_ACCESS_KEY or SECRET_ACCRESS_KEY
    aws_access_key_id: str = Field(
        default="",
        validation_alias=AliasChoices("AWS_ACCESS_KEY_ID", "ACCESS_KEY"),
    )
    aws_secret_access_key: str = Field(
        default="",
        validation_alias=AliasChoices("AWS_SECRET_ACCESS_KEY", "SECRET_ACCRESS_KEY"),
    )

    # Foxit PDF Services (hackathon requirement: extract & analyze docs e.g. Carfax)
    foxit_client_id: str = Field(default="", validation_alias="FOXIT_CLIENT_ID")
    foxit_client_secret: str = Field(default="", validation_alias="FOXIT_CLIENT_SECRET")
    foxit_api_host: str = Field(
        default="https://na1.fusion.foxit.com",
        validation_alias="FOXIT_API_HOST",
    )

    # Server / ngrok
    server_base_url: str = "http://127.0.0.1:8000"
    to_number: str = ""
    port: int = 8000

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",  # ignore env vars that don't match any field (e.g. TO_NUMBER, PORT, MONGODB_*)
    }


_settings_instance: Settings = None  # type: ignore[assignment]


def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
