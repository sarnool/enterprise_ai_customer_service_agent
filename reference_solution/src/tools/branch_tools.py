"""Complete branch tools - REFERENCE SOLUTION"""
import json
from typing import Dict, Any, List, Optional
from pathlib import Path

def find_branch_info(city: Optional[str] = None, service: Optional[str] = None) -> List[Dict[str, Any]]:
    """Find branches by city or service."""
    path = Path("data/business_data/branch_directory.json")
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    branches = data["branches"]
    results = branches
    
    # Filter by city
    if city:
        results = [b for b in results if city.lower() in b["city"].lower()]
    
    # Filter by service
    if service:
        results = [b for b in results if service in b.get("services", [])]
    
    return results
