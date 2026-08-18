import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from playwright.async_api import Page

class BaseATSAdapter(ABC):
    def __init__(self, page: Page, resume_path: str, qa_agent: Any):
        self.page = page
        self.resume_path = os.path.abspath(resume_path)
        self.qa_agent = qa_agent

    @abstractmethod
    async def fill_form(self, job: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        """Fills standard details, uploads resume, and answers questions. Returns mapped fields and QA records."""
        pass

    @abstractmethod
    async def submit(self) -> bool:
        """Clicks the final submit button."""
        pass