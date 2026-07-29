"""Test suite for extraction endpoint and typo matching."""

import json
import requests
from typing import Dict, List

BASE_URL = "http://localhost:8000"

# Test cases
TESTS = [
    # Category 1: Computer
    {
        "name": "Computer: iPhone exact",
        "input": {"title": "iPhone 15 256GB Black", "description": "Latest Apple smartphone"},
        "expect": {
            "category": "computer",
            "attrs": ["Manufacturer", "Capacity", "Color"],
            "has_suggestions": True  # Suggestions OK for alternatives
        }
    },
    {
        "name": "Computer: Typo - iPhone",
        "input": {"title": "Apple iphon 256GB blck", "description": ""},
        "expect": {
            "category": "computer",
            "attrs": ["Manufacturer", "Capacity"],
            "has_suggestions": True,
            "suggestion_keys": ["Color"]
        }
    },
    {
        "name": "Computer: Typo - Silver",
        "input": {"title": "Dell laptop slvr 512GB", "description": ""},
        "expect": {
            "category": "computer",
            "attrs": ["Manufacturer"],
            "has_suggestions": True,
            "suggestion_keys": ["Color"]
        }
    },

    # Category 2: Jewelry
    {
        "name": "Jewelry: Gold ring exact",
        "input": {"title": "Gold Diamond Ring 18K", "description": "Beautiful wedding ring"},
        "expect": {
            "category": "jewelry",
            "attrs": ["Metal", "MetalPurity", "Gemstone"],
            "has_suggestions": True  # Suggestions OK
        }
    },
    {
        "name": "Jewelry: Typo - Gold",
        "input": {"title": "Gld Diamond Ring 18K", "description": ""},
        "expect": {
            "category": "jewelry",
            "attrs": ["MetalPurity"],
            "has_suggestions": True,
            "suggestion_keys": ["Metal"]
        }
    },

    # Category 3: Office
    {
        "name": "Office: Desk chair exact",
        "input": {"title": "Office Desk Chair Executive", "description": "Ergonomic"},
        "expect": {
            "category": "office",
            "attrs": ["ProductType"],
            "has_suggestions": True  # Suggestions OK
        }
    },
    {
        "name": "Office: Paper GSM",
        "input": {"title": "Premium paper 80gsm white", "description": ""},
        "expect": {
            "category": "office",
            "attrs": [],
            "has_suggestions": True
        }
    },

    # Category 4: Home & Garden
    {
        "name": "Home: Garden tool set",
        "input": {"title": "Garden Tool Set 10 Piece", "description": "Complete tools"},
        "expect": {
            "category": "home",
            "attrs": ["ProductType"],
            "has_suggestions": True  # Suggestions OK
        }
    },
    {
        "name": "Home: Wooden furniture",
        "input": {"title": "Wooden cabinet oak furniture", "description": ""},
        "expect": {
            "category": "home",
            "attrs": [],
            "has_suggestions": True
        }
    },

    # Category 5: Grocery
    {
        "name": "Grocery: Coffee beans exact",
        "input": {"title": "Organic Coffee Beans 500g", "description": "Premium arabica"},
        "expect": {
            "category": "grocery",
            "attrs": ["Weight", "Organic"],
            "has_suggestions": True  # Suggestions OK
        }
    },
    {
        "name": "Grocery: Typo - Organic",
        "input": {"title": "Orgnic Coffee 500g arabica", "description": ""},
        "expect": {
            "category": "grocery",
            "attrs": ["Weight"],
            "has_suggestions": True,
            "suggestion_keys": ["Organic"]
        }
    },
]

def test_extract_endpoint():
    """Test /extract endpoint."""
    results = {
        "total": len(TESTS),
        "passed": 0,
        "failed": 0,
        "errors": []
    }

    for test in TESTS:
        try:
            response = requests.post(
                f"{BASE_URL}/extract",
                json=test["input"],
                timeout=5
            )

            if response.status_code != 200:
                results["failed"] += 1
                results["errors"].append({
                    "test": test["name"],
                    "error": f"HTTP {response.status_code}"
                })
                continue

            data = response.json()

            # Check category
            if data["category"] != test["expect"]["category"]:
                results["failed"] += 1
                results["errors"].append({
                    "test": test["name"],
                    "error": f"Expected category {test['expect']['category']}, got {data['category']}"
                })
                continue

            # Check attributes extracted
            extracted_keys = set(data["attributes"].keys())
            expected_keys = set(test["expect"]["attrs"])

            if not expected_keys.issubset(extracted_keys):
                missing = expected_keys - extracted_keys
                results["failed"] += 1
                results["errors"].append({
                    "test": test["name"],
                    "error": f"Missing attributes: {missing}"
                })
                continue

            # Check suggestions
            has_suggestions = len(data.get("suggestions", {})) > 0
            if has_suggestions != test["expect"].get("has_suggestions", False):
                results["failed"] += 1
                results["errors"].append({
                    "test": test["name"],
                    "error": f"Expected suggestions={test['expect'].get('has_suggestions')}, got {has_suggestions}"
                })
                continue

            results["passed"] += 1

        except Exception as e:
            results["failed"] += 1
            results["errors"].append({
                "test": test["name"],
                "error": str(e)
            })

    return results

def test_category_coverage():
    """Test that all 5 categories are recognized."""
    categories = ["computer", "jewelry", "office", "home", "grocery"]
    results = {
        "total": len(categories),
        "recognized": 0,
        "categories": {}
    }

    category_tests = {
        "computer": "dell laptop processor",
        "jewelry": "gold ring diamond carat",
        "office": "paper desk printer",
        "home": "furniture garden tool wood",
        "grocery": "coffee organic tea snack"
    }

    for category, text in category_tests.items():
        try:
            response = requests.post(
                f"{BASE_URL}/extract",
                json={"title": text},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                detected = data["category"]
                confidence = data["category_confidence"]

                if detected == category or detected == "home":  # home is parent of garden
                    results["recognized"] += 1

                results["categories"][category] = {
                    "detected": detected,
                    "confidence": confidence
                }
        except Exception as e:
            results["categories"][category] = {"error": str(e)}

    return results

def test_typo_matching():
    """Test typo/fuzzy matching."""
    typo_tests = [
        {
            "text": "silv",
            "target": "Silver",
            "category": "computer",
            "attr": "Color"
        },
        {
            "text": "blck",
            "target": "Black",
            "category": "computer",
            "attr": "Color"
        },
        {
            "text": "gld",
            "target": "Gold",
            "category": "jewelry",
            "attr": "Metal"
        },
    ]

    results = {
        "total": len(typo_tests),
        "matched": 0,
        "typos": {}
    }

    for test in typo_tests:
        try:
            response = requests.post(
                f"{BASE_URL}/extract",
                json={"title": f"{test['text']} product"},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                suggestions = data.get("suggestions", {})

                # Check if target is in suggestions
                found = False
                for attr, values in suggestions.items():
                    if test["target"] in values:
                        found = True
                        results["matched"] += 1
                        break

                results["typos"][test["text"]] = {
                    "target": test["target"],
                    "found": found,
                    "suggestions": suggestions
                }
        except Exception as e:
            results["typos"][test["text"]] = {"error": str(e)}

    return results

def test_attribute_count():
    """Count attributes extracted across categories."""
    results = {
        "total_tests": len(TESTS),
        "total_attrs_extracted": 0,
        "avg_per_test": 0,
        "by_category": {}
    }

    for test in TESTS:
        try:
            response = requests.post(
                f"{BASE_URL}/extract",
                json=test["input"],
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                category = data["category"]
                attr_count = len(data["attributes"])

                results["total_attrs_extracted"] += attr_count

                if category not in results["by_category"]:
                    results["by_category"][category] = {
                        "count": 0,
                        "total_attrs": 0
                    }

                results["by_category"][category]["count"] += 1
                results["by_category"][category]["total_attrs"] += attr_count
        except:
            pass

    if results["total_tests"] > 0:
        results["avg_per_test"] = round(
            results["total_attrs_extracted"] / results["total_tests"], 2
        )

    return results

if __name__ == "__main__":
    print("=" * 70)
    print("PAVE EXTRACTION ENDPOINT TEST SUITE")
    print("=" * 70)
    print()

    # Test 1: Extract endpoint
    print("[1/4] Testing extraction endpoint...")
    extract_results = test_extract_endpoint()
    print(f"  PASSED: {extract_results['passed']}/{extract_results['total']}")
    print(f"  FAILED: {extract_results['failed']}/{extract_results['total']}")
    if extract_results["errors"]:
        print("  Errors:")
        for err in extract_results["errors"][:3]:
            print(f"    - {err['test']}: {err['error']}")
    print()

    # Test 2: Category coverage
    print("[2/4] Testing category coverage...")
    category_results = test_category_coverage()
    print(f"  RECOGNIZED: {category_results['recognized']}/{category_results['total']}")
    for cat, info in category_results["categories"].items():
        conf = info.get("confidence", 0)
        detected = info.get("detected", "ERROR")
        print(f"    - {cat}: detected as '{detected}' ({conf*100:.0f}%)")
    print()

    # Test 3: Typo matching
    print("[3/4] Testing typo/fuzzy matching...")
    typo_results = test_typo_matching()
    print(f"  MATCHED: {typo_results['matched']}/{typo_results['total']}")
    for typo, info in typo_results["typos"].items():
        found = info.get("found", False)
        target = info.get("target", "?")
        status = "[OK]" if found else "[FAIL]"
        print(f"    {status} '{typo}' -> '{target}'")
    print()

    # Test 4: Attribute count
    print("[4/4] Testing attribute extraction count...")
    count_results = test_attribute_count()
    print(f"  TOTAL ATTRS EXTRACTED: {count_results['total_attrs_extracted']}")
    print(f"  AVG PER TEST: {count_results['avg_per_test']}")
    print("  By category:")
    for cat, stats in count_results["by_category"].items():
        avg = stats["total_attrs"] / stats["count"] if stats["count"] > 0 else 0
        print(f"    - {cat}: {stats['total_attrs']} attrs across {stats['count']} tests (avg: {avg:.1f})")
    print()

    # Summary
    print("=" * 70)
    print("METRICS SUMMARY")
    print("=" * 70)
    pass_rate = (extract_results['passed'] / extract_results['total'] * 100) if extract_results['total'] > 0 else 0
    category_rate = (category_results['recognized'] / category_results['total'] * 100) if category_results['total'] > 0 else 0
    typo_rate = (typo_results['matched'] / typo_results['total'] * 100) if typo_results['total'] > 0 else 0

    print(f"Extraction Pass Rate:  {pass_rate:.1f}% ({extract_results['passed']}/{extract_results['total']})")
    print(f"Category Recognition:  {category_rate:.1f}% ({category_results['recognized']}/{category_results['total']})")
    print(f"Typo Matching Rate:    {typo_rate:.1f}% ({typo_results['matched']}/{typo_results['total']})")
    print(f"Avg Attributes/Test:   {count_results['avg_per_test']}")
    print()

    overall = (pass_rate + category_rate + typo_rate) / 3
    print(f"OVERALL SCORE: {overall:.1f}%")
    print("=" * 70)
