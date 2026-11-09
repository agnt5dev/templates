"""Onboarding drip: a durable multi-day email sequence you can crash on purpose."""
from onboarding_drip.functions import (
    build_report,
    check_activity,
    research_company,
    send_email,
    write_email,
)
from onboarding_drip.workflows import onboard_customer

__all__ = [
    "onboard_customer",
    "research_company",
    "write_email",
    "send_email",
    "check_activity",
    "build_report",
]
