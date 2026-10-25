from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://corpus:secret@localhost:5432/syntax_db"
    spacy_model: str = "en_core_web_sm"
    benepar_model: str = "benepar_en3"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
