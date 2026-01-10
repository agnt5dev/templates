"""Configuration settings loaded from environment variables.

Uses python-dotenv to load .env file automatically.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration.

    Loads sensitive data from environment variables.
    Create a .env file with these variables:

        GROQ_API_KEY=your_groq_api_key_here
        E2B_API_KEY=your_e2b_api_key_here
        OPENAI_API_KEY=your_openai_key_here  # Optional
    """

    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    E2B_API_KEY = os.getenv("E2B_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Optional, for future use

    @classmethod
    def validate(cls):
        """Validate that required API keys are present."""
        missing = []

        if not cls.GROQ_API_KEY:
            missing.append("GROQ_API_KEY")
        if not cls.E2B_API_KEY:
            missing.append("E2B_API_KEY")

        if missing:
            raise ValueError(
                f"Missing required environment variables: "
                f"{', '.join(missing)}\n"
                f"Please create a .env file with these variables."
            )


config = Config()