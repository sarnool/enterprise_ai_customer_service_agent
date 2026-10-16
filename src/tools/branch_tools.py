"""
Branch finder tool.
"""
import json
from typing import Dict, Any, List, Optional
from pathlib import Path

def find_branch_info(city: Optional[str] = None, service: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Find branch information by city or service.

    City matching is a case-insensitive substring match; service matching
    is exact. Filters are combined when both are given.

    Args:
        city: City name to filter
        service: Service type to filter (e.g., "Foreign Exchange", "Locker Facility")

    Returns:
        List of matching branches with details
    """
    path = Path("data/business_data/branch_directory.json")
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    branches = data["branches"]

    if city:
        branches = [b for b in branches if city.lower() in b["city"].lower()]
    if service:
        branches = [b for b in branches if service in b.get("services", [])]
    return branches
