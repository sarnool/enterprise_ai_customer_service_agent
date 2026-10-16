"""Input validation utilities."""
from typing import Optional

def validate_query(query: str) -> Optional[str]:
    """Validate user query input."""
    if not query or not query.strip():
        return "Query cannot be empty"
    if len(query) > 1000:
        return "Query too long (max 1000 characters)"
    return None

def sanitize_input(text: str) -> str:
    """Sanitize user input."""
    return text.strip()
