"""
Eligibility checker tool.
"""
from typing import Dict, Any, List, Optional
import json
from pathlib import Path

def _check_requirements(requirements: Dict[str, Any], customer_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check customer_data against one set of requirements.

    Numeric "min_<field>" / "max_<field>" rules are compared against
    customer_data["<field>"] (e.g. min_age -> age, min_credit_score ->
    credit_score). Rules whose field isn't in customer_data are reported as
    unverified rather than failed.
    """
    failed: List[str] = []
    unverified: List[str] = []

    for rule, limit in requirements.items():
        if not isinstance(limit, (int, float)) or not rule.startswith(("min_", "max_")):
            continue
        field = rule[4:]
        if field not in customer_data:
            unverified.append(rule)
            continue
        value = customer_data[field]
        if rule.startswith("min_") and value < limit:
            failed.append(f"{field} {value} is below the minimum of {limit}")
        elif rule.startswith("max_") and value > limit:
            failed.append(f"{field} {value} is above the maximum of {limit}")

    result = {
        "eligible": not failed,
        "failed_requirements": failed,
        "unverified_requirements": unverified,
        "documents": requirements.get("documents", []),
    }
    notes = [requirements[key] for key in ("requirement", "preference", "conversion") if key in requirements]
    if notes:
        result["notes"] = notes
    return result

def check_eligibility(product_type: str, customer_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check eligibility for banking products.

    Some products (e.g. loans) have variants such as "salaried" /
    "self_employed". Pass customer_data["variant"] to check one variant;
    otherwise every variant is checked and the customer is eligible if any
    of them passes.

    `eligible` only reflects the requirements customer_data could be checked
    against - see `unverified_requirements` for the rest.

    Args:
        product_type: Product name, e.g. "Gold Credit Card"
        customer_data: Customer profile, e.g. {"age": 28, "credit_score": 760}

    Returns:
        Dict with "eligible" plus details of failed/unverified requirements,
        or {"eligible": False, "reason": "Product not found"}
    """
    path = Path("data/business_data/eligibility_rules.json")
    with open(path, 'r', encoding='utf-8') as f:
        rules = json.load(f)

    requirements: Optional[Dict[str, Any]] = None
    for category in rules.values():
        if product_type in category:
            requirements = category[product_type]
            break
    if requirements is None:
        return {"eligible": False, "reason": "Product not found"}

    has_variants = all(isinstance(value, dict) for value in requirements.values())
    if not has_variants:
        return {"product": product_type, **_check_requirements(requirements, customer_data)}

    variant = customer_data.get("variant")
    if variant is not None:
        if variant not in requirements:
            return {
                "eligible": False,
                "reason": f"Unknown variant '{variant}' for {product_type}",
                "variants": list(requirements),
            }
        return {"product": product_type, "variant": variant,
                **_check_requirements(requirements[variant], customer_data)}

    variants = {name: _check_requirements(reqs, customer_data) for name, reqs in requirements.items()}
    return {
        "product": product_type,
        "eligible": any(result["eligible"] for result in variants.values()),
        "variants": variants,
    }
