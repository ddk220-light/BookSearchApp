from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    library_card_number: str = ""
    library_pin: str = ""
    google_books_api_key: str = ""
    anthropic_api_key: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
