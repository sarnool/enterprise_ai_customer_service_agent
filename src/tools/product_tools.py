"""
Product catalog business tool.
"""
import json
from typing import Dict, Any, Optional
from pathlib import Path

def load_business_data(filename: str) -> Dict[str, Any]:
    """Load business data JSON file."""
    path = Path("data/business_data") / filename
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_product_catalog(category: Optional[str] = None) -> Dict[str, Any]:
    """
    Get product catalog information.

    If `category` is provided, returns only that category
    ({category: []} if it doesn't exist); otherwise the full catalog.
    """
    catalog = load_business_data("product_catalog.json")

    if category:
        return {category: catalog.get(category, [])}
    return catalog
