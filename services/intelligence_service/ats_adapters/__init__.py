from playwright.async_api import Page
from typing import Any
from services.intelligence_service.ats_adapters.base_adapter import BaseATSAdapter
from services.intelligence_service.ats_adapters.greenhouse_adapter import GreenhouseAdapter
from services.intelligence_service.ats_adapters.lever_adapter import LeverAdapter
from services.intelligence_service.ats_adapters.ashby_adapter import AshbyAdapter
from services.intelligence_service.ats_adapters.generic_adapter import GenericHeuristicAdapter

def get_adapter_for_job(ats_provider: str, page: Page, resume_path: str, qa_agent: Any) -> BaseATSAdapter:
    provider = (ats_provider or "").lower()
    if "greenhouse" in provider:
        return GreenhouseAdapter(page, resume_path, qa_agent)
    elif "lever" in provider:
        return LeverAdapter(page, resume_path, qa_agent)
    elif "ashby" in provider:
        return AshbyAdapter(page, resume_path, qa_agent)
    else:
        return GenericHeuristicAdapter(page, resume_path, qa_agent)