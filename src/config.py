"""Configuration loading from environment variables."""

import os
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class SystemConfig:
    """System configuration."""
    google_project_id: str
    google_location: str
    document_ai_processor_id: str
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"
    temp_dir: str = "./tmp"
    retry_attempts: int = 3


def load_config(env_file: Optional[str] = None) -> SystemConfig:
    """
    Load system configuration from environment variables.
    
    Args:
        env_file: Optional path to .env file. If None, uses default .env
        
    Returns:
        SystemConfig object with loaded configuration
        
    Raises:
        ValueError: If required environment variables are missing
    """
    # Load environment variables from .env file
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()
    
    # Required environment variables
    required_vars = [
        "GOOGLE_PROJECT_ID",
        "GOOGLE_LOCATION",
        "DOCUMENT_AI_PROCESSOR_ID",
        "GEMINI_API_KEY"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )
    
    # Load configuration with defaults for optional values
    config = SystemConfig(
        google_project_id=os.getenv("GOOGLE_PROJECT_ID"),
        google_location=os.getenv("GOOGLE_LOCATION"),
        document_ai_processor_id=os.getenv("DOCUMENT_AI_PROCESSOR_ID"),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        gemini_model=os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash"),
        temp_dir=os.getenv("TEMP_DIR", "./tmp"),
        retry_attempts=int(os.getenv("RETRY_ATTEMPTS", "3"))
    )
    
    return config
