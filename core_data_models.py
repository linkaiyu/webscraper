from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel
from enum import Enum
from datetime import datetime

class ActionType(str, Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    SCROLL = "scroll"
    TYPE = "type"
    WAIT = "wait"
    EXTRACT = "extract"
    LOOP = "loop"
    CONDITION = "condition"
    PAGINATE = "paginate"

class SelectorStrategy(str, Enum):
    CSS = "css"
    XPATH = "xpath"
    TEXT = "text"
    ROLE = "role"
    DATA_ATTR = "data_attr"
    MULTIPLE = "multiple"  # Try multiple selectors

class NavigationAction(BaseModel):
    """Single user action captured"""
    id: str
    type: ActionType
    description: str  # User's natural language description
    selector: Optional[str] = None
    selector_strategies: Optional[List[SelectorStrategy]] = None
    value: Optional[str] = None  # Text to type, URL to navigate
    wait_for: Optional[str] = None  # Element to wait for
    timeout: int = 30000
    screenshot_before: bool = False
    screenshot_after: bool = False
    metadata: Dict[str, Any] = {}

class PageStructure(BaseModel):
    """Structure of a page at a specific point"""
    url: str
    title: str
    detected_patterns: Dict[str, Any]  # Products, pagination, etc.
    interactive_elements: List[Dict[str, Any]]
    forms: List[Dict[str, Any]]
    dynamic_elements: List[str]  # Elements that change
    load_triggers: List[str]  # What triggers new content
    timestamp: datetime

class WorkflowStep(BaseModel):
    """A step in the automation workflow"""
    id: str
    order: int
    action: NavigationAction
    page_structure: Optional[PageStructure] = None
    success_criteria: Optional[str] = None
    fallback_actions: Optional[List[NavigationAction]] = None
    timeout: int = 30000
    retry_count: int = 3

class PaginationPattern(BaseModel):
    """Captured pagination behavior"""
    type: str  # "next_prev", "numbered", "infinite_scroll", "load_more"
    trigger_selector: Optional[str] = None
    max_pages: Optional[int] = None
    stop_condition: Optional[str] = None
    next_button_selector: Optional[str] = None
    page_number_selector: Optional[str] = None
    current_page_selector: Optional[str] = None
    load_more_selector: Optional[str] = None
    scroll_trigger: Optional[str] = None  # "bottom", "threshold"
    observed_patterns: List[Dict[str, Any]] = []

class ExtractionSchema(BaseModel):
    """What to extract from detail pages"""
    fields: Dict[str, Dict[str, Any]]  # field_name -> {selector, type, ...}
    relationships: Optional[Dict[str, Any]] = None
    validation_rules: Optional[Dict[str, Any]] = None

class ScraperWorkflow(BaseModel):
    """Complete captured workflow"""
    id: str
    name: str
    description: str
    entry_url: str
    steps: List[WorkflowStep]
    pagination: PaginationPattern
    extraction: ExtractionSchema
    variables: Dict[str, Any] = {}
    generated_by: str = "copilot"
    generated_at: datetime = datetime.now()
    site_fingerprint: str  # Hash to identify site
    version: int = 1