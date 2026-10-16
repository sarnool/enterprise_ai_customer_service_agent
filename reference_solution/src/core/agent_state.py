"""Agent state management for LangGraph workflow."""
from typing import TypedDict, List, Dict, Any, Optional
from dataclasses import dataclass

class AgentState(TypedDict):
    """State for the agent workflow."""
    query: str
    intent: Optional[str]
    confidence: float
    retrieved_docs: List[Dict[str, Any]]
    tool_results: Optional[Dict[str, Any]]
    response: Optional[str]
    citations: List[str]
    needs_clarification: bool
    needs_escalation: bool
    clarification_question: Optional[str]
    escalation_reason: Optional[str]

@dataclass
class RetrievedDocument:
    """Structure for retrieved documents."""
    content: str
    source: str
    score: float
    metadata: Dict[str, Any]
