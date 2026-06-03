from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    PORT: int = Field(default=8080, description="The port the gateway binds to.")
    DRAGONFLY_URL: str = Field(default="redis://localhost:6379/0", description="Connection string for Dragonfly store.")
    
    # Provider Keys
    OPENAI_API_KEY: str = Field(default="mock-openai-key")
    ANTHROPIC_API_KEY: str = Field(default="mock-anthropic-key")
    
    # Routing Policy
    PRIMARY_PROVIDER: str = Field(default="openai")
    SECONDARY_PROVIDER: str = Field(default="anthropic")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
