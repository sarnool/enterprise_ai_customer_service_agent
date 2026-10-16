"""Complete eligibility tools - REFERENCE SOLUTION"""
from typing import Dict, Any
import json
from pathlib import Path

def check_eligibility(product_type: str, customer_data: Dict[str, Any]) -> Dict[str, bool]:
    """Check product eligibility."""
    path = Path("data/business_data/eligibility_rules.json")
    with open(path, 'r', encoding='utf-8') as f:
        rules = json.load(f)
    
    # Find product rules
    for category in rules.values():
        if product_type in category:
            requirements = category[product_type]
            
            # Simple validation
            if "min_age" in requirements:
                if customer_data.get("age", 0) < requirements["min_age"]:
                    return {"eligible": False, "reason": "Minimum age not met"}
            
            return {"eligible": True, "documents": requirements.get("documents", [])}
    
    return {"eligible": False, "reason": "Product not found"}
