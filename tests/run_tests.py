#!/usr/bin/env python3
"""
Standalone test runner for USGS River Alert System.

Runs core logic tests without requiring pytest.
Usage: python3 tests/run_tests.py
"""
import sys
import os
import traceback

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'
BOLD = '\033[1m'


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []


def run_test(name, test_func, result):
    """Run a single test and record result."""
    try:
        test_func()
        result.passed += 1
        print(f"  {GREEN}✓{RESET} {name}")
    except AssertionError as e:
        result.failed += 1
        result.errors.append((name, str(e), traceback.format_exc()))
        print(f"  {RED}✗{RESET} {name}")
    except Exception as e:
        result.failed += 1
        result.errors.append((name, str(e), traceback.format_exc()))
        print(f"  {RED}✗{RESET} {name} (ERROR: {e})")


# =============================================================================
# Test normalize_site_id()
# =============================================================================
def test_normalize_site_id():
    from usgs_multi_alert import normalize_site_id

    # Plain numeric (any length passes through)
    assert normalize_site_id("02399200") == "02399200"
    assert normalize_site_id("12345") == "12345"  # Short IDs accepted

    # Extract from text (requires 8+ digits)
    assert normalize_site_id("Little River (USGS 02399200)") == "02399200"
    assert normalize_site_id("Site 12345 gauge 02399200") == "02399200"  # Takes last 8+

    # Whitespace
    assert normalize_site_id("  02399200  ") == "02399200"

    # Invalid raises error (no digits at all)
    try:
        normalize_site_id("InvalidSite")
        raise AssertionError("Should have raised ValueError")
    except ValueError:
        pass

    # Text with only short numbers raises (regex needs 8+)
    try:
        normalize_site_id("Site 123")
        raise AssertionError("Should have raised ValueError for text with short ID")
    except ValueError:
        pass


# =============================================================================
# Test is_in() threshold logic
# =============================================================================
def is_in(stage, cfs, th_ft, th_cfs):
    """Recreate threshold logic for testing."""
    cond_ft = True if th_ft is None else (stage is not None and stage >= th_ft)
    cond_cfs = True if th_cfs is None else (cfs is not None and cfs >= th_cfs)
    return cond_ft and cond_cfs


def test_is_in_both_thresholds():
    # Both pass
    assert is_in(5.0, 300, 4.0, 250) is True
    # ft fails
    assert is_in(3.0, 300, 4.0, 250) is False
    # cfs fails
    assert is_in(5.0, 200, 4.0, 250) is False
    # Both fail
    assert is_in(3.0, 200, 4.0, 250) is False


def test_is_in_single_threshold():
    # ft-only passes
    assert is_in(5.0, None, 4.0, None) is True
    # ft-only fails
    assert is_in(3.0, None, 4.0, None) is False
    # cfs-only passes
    assert is_in(None, 300, None, 250) is True
    # cfs-only fails
    assert is_in(None, 200, None, 250) is False


def test_is_in_edge_cases():
    # Exactly at threshold = IN
    assert is_in(4.0, 250, 4.0, 250) is True
    # None stage with ft threshold = OUT
    assert is_in(None, 300, 4.0, 250) is False
    # No thresholds = always IN
    assert is_in(1.0, 50, None, None) is True


# =============================================================================
# Test calculate_percent_change()
# =============================================================================
def test_percent_change_rising():
    from usgs_multi_alert import calculate_percent_change
    trend_data = {"values": [2.0, 2.5, 3.0]}
    pct, direction = calculate_percent_change(trend_data)
    assert abs(pct - 50.0) < 0.01  # 50% change
    assert direction == "up"


def test_percent_change_falling():
    from usgs_multi_alert import calculate_percent_change
    trend_data = {"values": [3.0, 2.5, 2.0]}
    pct, direction = calculate_percent_change(trend_data)
    assert abs(pct - (-33.33)) < 0.5
    assert direction == "down"


def test_percent_change_flat():
    from usgs_multi_alert import calculate_percent_change
    trend_data = {"values": [2.5, 2.5, 2.5]}
    pct, direction = calculate_percent_change(trend_data)
    assert pct == 0.0
    assert direction == "flat"


def test_percent_change_empty():
    from usgs_multi_alert import calculate_percent_change
    assert calculate_percent_change(None) == (None, "flat")
    assert calculate_percent_change({}) == (None, "flat")
    assert calculate_percent_change({"values": []}) == (None, "flat")


# =============================================================================
# Test predictions module
# =============================================================================
def test_predictions_no_rain():
    from predictions import calculate_predictions
    river_chars = {
        '02455000': {
            'name': 'Locust Fork',
            'avg_response_hours': 33,
            'response_range': [26, 38],
            'rain_needed_inches': 1.75,
            'responsiveness': 'moderate'
        }
    }
    sites = [{
        'site': '02455000',
        'name': 'Locust Fork',
        'in_range': False,
        'qpf': {'2025-01-01': 0.0, '2025-01-02': 0.0, '2025-01-03': 0.0}
    }]
    predictions = calculate_predictions(sites, river_chars)
    assert predictions[0]['likelihood'] == 0


def test_predictions_enough_rain():
    from predictions import calculate_predictions
    river_chars = {
        '02455000': {
            'name': 'Locust Fork',
            'avg_response_hours': 33,
            'response_range': [26, 38],
            'rain_needed_inches': 1.75,
            'responsiveness': 'moderate'
        }
    }
    sites = [{
        'site': '02455000',
        'name': 'Locust Fork',
        'in_range': False,
        'qpf': {'2025-01-01': 0.5, '2025-01-02': 0.75, '2025-01-03': 0.75}  # 2.0"
    }]
    predictions = calculate_predictions(sites, river_chars)
    assert predictions[0]['likelihood'] >= 70


def test_predictions_already_running():
    from predictions import calculate_predictions
    river_chars = {
        '02455000': {
            'name': 'Locust Fork',
            'avg_response_hours': 33,
            'response_range': [26, 38],
            'rain_needed_inches': 1.75,
            'responsiveness': 'moderate'
        }
    }
    sites = [{
        'site': '02455000',
        'name': 'Locust Fork',
        'in_range': True,  # Already running
        'qpf': {'2025-01-01': 0.0, '2025-01-02': 0.0, '2025-01-03': 0.0}
    }]
    predictions = calculate_predictions(sites, river_chars)
    assert predictions[0]['likelihood'] == 100
    assert predictions[0]['status'] == 'running'


# =============================================================================
# Test visual gauge conversion
# =============================================================================
def test_visual_gauge_conversion():
    """North Chickamauga: Visual = 0.69 × USGS - 1.89"""
    def usgs_to_visual(usgs_stage):
        return 0.69 * usgs_stage - 1.89

    # Calibration point: 6.22 ft USGS ≈ 2.42 ft visual
    assert abs(usgs_to_visual(6.22) - 2.42) < 0.1

    # Runnable threshold: 5.2 ft USGS = 1.7 ft visual
    assert abs(usgs_to_visual(5.2) - 1.70) < 0.1


# =============================================================================
# Test LRC flow classification
# =============================================================================
def test_lrc_flow_classification():
    def classify(cfs):
        if cfs < 250:
            return "not_runnable"
        elif cfs < 400:
            return "good_low"
        elif cfs < 800:
            return "shitty_medium"
        elif cfs < 1500:
            return "good_medium"
        elif cfs < 2500:
            return "best"
        else:
            return "too_high"

    assert classify(100) == "not_runnable"
    assert classify(300) == "good_low"
    assert classify(600) == "shitty_medium"
    assert classify(1000) == "good_medium"
    assert classify(2000) == "best"
    assert classify(3000) == "too_high"

    # Boundary tests
    assert classify(249) == "not_runnable"
    assert classify(250) == "good_low"


# =============================================================================
# Test alert state transitions
# =============================================================================
def test_alert_state_rising_mode():
    def should_alert_rising(was_in, in_range, time_since, cooldown):
        return (not was_in) and in_range and (time_since >= cooldown)

    # OUT→IN triggers alert
    assert should_alert_rising(False, True, 7200, 3600) is True
    # Already IN, no alert
    assert should_alert_rising(True, True, 7200, 3600) is False
    # Cooldown blocks
    assert should_alert_rising(False, True, 1800, 3600) is False


def test_alert_state_out_alert():
    def should_alert_out(was_in, in_range, send_out, time_since, cooldown):
        return send_out and was_in and (not in_range) and (time_since >= cooldown)

    # IN→OUT with send_out enabled
    assert should_alert_out(True, False, True, 7200, 3600) is True
    # send_out disabled
    assert should_alert_out(True, False, False, 7200, 3600) is False
    # Wasn't previously IN
    assert should_alert_out(False, False, True, 7200, 3600) is False


# =============================================================================
# Main runner
# =============================================================================
def main():
    print(f"\n{BOLD}USGS River Alert System - Core Logic Tests{RESET}")
    print("=" * 50)

    result = TestResult()

    # Group 1: Site ID Normalization
    print(f"\n{YELLOW}normalize_site_id(){RESET}")
    run_test("handles plain numeric IDs", test_normalize_site_id, result)

    # Group 2: Threshold Logic
    print(f"\n{YELLOW}is_in() threshold logic{RESET}")
    run_test("both thresholds configured", test_is_in_both_thresholds, result)
    run_test("single threshold configured", test_is_in_single_threshold, result)
    run_test("edge cases (exact threshold, None values)", test_is_in_edge_cases, result)

    # Group 3: Percent Change
    print(f"\n{YELLOW}calculate_percent_change(){RESET}")
    run_test("rising trend detection", test_percent_change_rising, result)
    run_test("falling trend detection", test_percent_change_falling, result)
    run_test("flat/steady trend detection", test_percent_change_flat, result)
    run_test("empty/missing data handling", test_percent_change_empty, result)

    # Group 4: Predictions
    print(f"\n{YELLOW}predictions module{RESET}")
    run_test("zero QPF = 0% likelihood", test_predictions_no_rain, result)
    run_test("sufficient QPF = likely status", test_predictions_enough_rain, result)
    run_test("in_range=True = 100% running", test_predictions_already_running, result)

    # Group 5: Visual Gauge
    print(f"\n{YELLOW}visual gauge conversion{RESET}")
    run_test("North Chickamauga formula", test_visual_gauge_conversion, result)

    # Group 6: LRC Flow Classification
    print(f"\n{YELLOW}Little River Canyon flow levels{RESET}")
    run_test("6-level classification", test_lrc_flow_classification, result)

    # Group 7: Alert State Machine
    print(f"\n{YELLOW}alert state transitions{RESET}")
    run_test("rising mode (OUT→IN triggers)", test_alert_state_rising_mode, result)
    run_test("OUT alerts (IN→OUT with send_out)", test_alert_state_out_alert, result)

    # Summary
    print("\n" + "=" * 50)
    total = result.passed + result.failed
    if result.failed == 0:
        print(f"{GREEN}{BOLD}All {total} tests passed!{RESET}")
    else:
        print(f"{RED}{BOLD}{result.failed}/{total} tests failed{RESET}")
        print(f"\n{RED}Failed tests:{RESET}")
        for name, error, tb in result.errors:
            print(f"\n  {name}:")
            print(f"    {error}")

    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
