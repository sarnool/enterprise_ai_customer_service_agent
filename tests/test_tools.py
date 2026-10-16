"""Test suite for business tools."""
import pytest
import json
from pathlib import Path
from src.tools.product_tools import get_product_catalog
from src.tools.branch_tools import find_branch_info
from src.tools.eligibility_tools import check_eligibility

def test_product_catalog_exists():
    """Test product catalog file exists and is valid JSON."""
    catalog_path = Path("data/business_data/product_catalog.json")
    assert catalog_path.exists()
    
    with open(catalog_path, 'r') as f:
        data = json.load(f)
        assert "savings_accounts" in data
        assert "credit_cards" in data
        assert "loans" in data

def test_branch_directory_exists():
    """Test branch directory file exists and is valid JSON."""
    branch_path = Path("data/business_data/branch_directory.json")
    assert branch_path.exists()
    
    with open(branch_path, 'r') as f:
        data = json.load(f)
        assert "branches" in data
        assert len(data["branches"]) > 0

def test_product_catalog_returns_all_categories():
    catalog = get_product_catalog()
    assert {"savings_accounts", "credit_cards", "loans"} <= set(catalog)

def test_product_catalog_filters_by_category():
    catalog = get_product_catalog("credit_cards")
    assert list(catalog) == ["credit_cards"]
    assert len(catalog["credit_cards"]) > 0

def test_product_catalog_unknown_category_is_empty():
    assert get_product_catalog("does_not_exist") == {"does_not_exist": []}

def test_find_branch_info_without_filters_returns_all():
    with open("data/business_data/branch_directory.json", encoding="utf-8") as f:
        total = len(json.load(f)["branches"])
    assert len(find_branch_info()) == total

def test_find_branch_info_city_is_case_insensitive():
    branches = find_branch_info(city="mumbai")
    assert branches
    assert all(b["city"] == "Mumbai" for b in branches)

def test_find_branch_info_filters_by_service():
    branches = find_branch_info(service="Foreign Exchange")
    assert branches
    assert all("Foreign Exchange" in b["services"] for b in branches)

def test_find_branch_info_combines_filters():
    branches = find_branch_info(city="Mumbai", service="Locker Facility")
    assert branches
    assert all(b["city"] == "Mumbai" and "Locker Facility" in b["services"] for b in branches)

def test_find_branch_info_no_match():
    assert find_branch_info(city="Atlantis") == []

def test_check_eligibility_unknown_product():
    assert check_eligibility("Mortgage", {"age": 30}) == {"eligible": False, "reason": "Product not found"}

def test_check_eligibility_passes_all_requirements():
    result = check_eligibility("Gold Credit Card", {"age": 30, "income_annual": 800000, "credit_score": 780})
    assert result["eligible"] is True
    assert result["failed_requirements"] == []
    assert result["documents"]

def test_check_eligibility_fails_minimum():
    result = check_eligibility("Gold Credit Card", {"age": 30, "income_annual": 500000, "credit_score": 780})
    assert result["eligible"] is False
    assert any("income_annual" in reason for reason in result["failed_requirements"])

def test_check_eligibility_fails_maximum():
    result = check_eligibility("Student Savings Account", {"age": 30})
    assert result["eligible"] is False
    assert any("maximum" in reason for reason in result["failed_requirements"])

def test_check_eligibility_reports_missing_data_as_unverified():
    result = check_eligibility("Gold Credit Card", {"age": 30})
    assert result["eligible"] is True
    assert set(result["unverified_requirements"]) == {"min_income_annual", "min_credit_score"}

def test_check_eligibility_selected_variant():
    result = check_eligibility("Personal Loan", {"age": 23, "variant": "self_employed"})
    assert result["variant"] == "self_employed"
    assert result["eligible"] is False

def test_check_eligibility_any_variant_passes():
    # Age 23 fails self_employed (min 25) but passes salaried (min 21).
    result = check_eligibility("Personal Loan", {"age": 23})
    assert result["eligible"] is True
    assert result["variants"]["salaried"]["eligible"] is True
    assert result["variants"]["self_employed"]["eligible"] is False

def test_check_eligibility_unknown_variant():
    result = check_eligibility("Personal Loan", {"variant": "retired"})
    assert result["eligible"] is False
    assert set(result["variants"]) == {"salaried", "self_employed"}
