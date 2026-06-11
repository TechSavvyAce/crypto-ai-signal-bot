from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration; override with environment variables."""

    model_config = SettingsConfigDict(env_prefix="CRYPTO_BOT_", env_file=".env", extra="ignore")

    log_level: str = "INFO"
    default_symbol: str = "BTC/USDT"
    paper_trading: bool = True

    # CCXT (public OHLCV works without keys; keys optional for private later)
    ccxt_exchange: str = "binance"
    ccxt_timeframe: str = "1m"
    ccxt_poll_interval: float = 2.0
    ccxt_api_key: str = ""
    ccxt_api_secret: str = ""
