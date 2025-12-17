"""
Configuration management for BrowserFreak
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class BrowserConfig(BaseModel):
    """Browser-related configuration"""

    headless: bool = Field(default=False, description="Run browser in headless mode")
    channel: str = Field(default="chrome", description="Browser channel to use")
    user_data_dir: Optional[str] = Field(
        default=None, description="Persistent browser data directory"
    )
    default_timeout: int = Field(
        default=5000, description="Default timeout for browser operations (ms)"
    )
    page_load_timeout: int = Field(default=30000, description="Page load timeout (ms)")
    slow_mo: int = Field(default=0, description="Slow down operations by specified milliseconds")


class AgentConfig(BaseModel):
    """Agent-related configuration"""

    max_iterations: int = Field(default=5, description="Maximum iterations for agent workflow")
    use_real_browser: bool = Field(
        default=False, description="Use real browser instead of mock mode"
    )
    enable_security_checks: bool = Field(
        default=True, description="Enable security checks for destructive actions"
    )
    enable_logging: bool = Field(default=True, description="Enable detailed logging")
    log_level: str = Field(default="INFO", description="Logging level")


class AnthropicConfig(BaseModel):
    """Anthropic API configuration"""

    api_key: Optional[SecretStr] = Field(default=None, description="Anthropic API key")
    model: str = Field(default="claude-3-5-sonnet-20240620", description="Anthropic model to use")
    temperature: float = Field(default=0.0, description="Temperature for API calls")
    max_tokens: int = Field(default=4096, description="Maximum tokens for API responses")
    timeout: int = Field(default=60, description="API request timeout (seconds)")

    @field_validator("api_key", mode="before")
    @classmethod
    def validate_api_key(cls, v):
        if v is None or v == "your-anthropic-api-key-here":
            return None
        return v

    @property
    def is_available(self) -> bool:
        """Check if Anthropic API is properly configured"""
        return self.api_key is not None and self.api_key.get_secret_value() != ""


class UIConfig(BaseModel):
    """Streamlit UI configuration"""

    page_title: str = Field(
        default="AI Browser Automation Agent", description="Streamlit page title"
    )
    page_icon: str = Field(default="🤖", description="Streamlit page icon")
    layout: str = Field(default="wide", description="Streamlit layout")
    sidebar_state: str = Field(default="auto", description="Sidebar initial state")


class Settings(BaseModel):
    """Main application settings"""

    # Sub-configurations
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    ui: UIConfig = Field(default_factory=UIConfig)

    model_config = ConfigDict(extra="ignore")

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from environment variables and .env file"""
        # Load environment variables from .env file if it exists
        from dotenv import load_dotenv

        load_dotenv()

        # Create settings from environment
        return cls()


# Global settings instance
settings = Settings.from_env()
