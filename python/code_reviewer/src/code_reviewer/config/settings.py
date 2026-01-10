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

        GITHUB_TOKEN=your_github_token_here (required)
        OPENAI_API_KEY=your_openai_key_here (required)

        # At least one issue tracking system is required:
        LINEAR_API_TOKEN=your_linear_api_key_here (optional)
        # OR
        JIRA_EMAIL=your_jira_email_here (optional, requires all 3 Jira vars)
        JIRA_DOMAIN=your_jira_domain_here (optional, requires all 3 Jira vars)
        JIRA_API_TOKEN=your_jira_api_token_here (optional, requires all 3 Jira vars)
    """

    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    LINEAR_KEY = os.getenv("LINEAR_API_TOKEN")
    JIRA_EMAIL = os.getenv("JIRA_EMAIL")
    JIRA_DOMAIN = os.getenv("JIRA_DOMAIN")
    JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    @classmethod
    def validate(cls):
        """Validate that required API keys are present.

        At least one issue tracking system (Jira or Linear) must be configured.
        """
        missing = []

        if not cls.GITHUB_TOKEN:
            missing.append("GITHUB_TOKEN")

        if not cls.OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY")

        if missing:
            error_msg = (
                f"Missing required environment variables: "
                f"{', '.join(missing)}\n"
                f"Please create a .env file with these variables."
            )
            raise ValueError(error_msg)

        has_linear = bool(cls.LINEAR_KEY)
        has_jira = all([cls.JIRA_EMAIL, cls.JIRA_DOMAIN, cls.JIRA_API_TOKEN])

        if not has_linear and not has_jira:
            error_msg = (
                "At least one issue tracking system must be configured:\n"
                "  - Linear: Provide LINEAR_API_TOKEN\n"
                "  - Jira: Provide JIRA_EMAIL, JIRA_DOMAIN, and JIRA_API_TOKEN\n"
                "Please update your .env file accordingly."
            )
            raise ValueError(error_msg)


config = Config()