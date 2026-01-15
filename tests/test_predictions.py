#!/usr/bin/env python3
"""
Unit tests for predictions.py module

Run with: pytest tests/test_predictions.py -v
"""
import pytest
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from predictions import calculate_predictions, format_local_time


# =============================================================================
# Test calculate_predictions()
# =============================================================================
class TestCalculatePredictions:
    """Tests for likelihood calculation logic."""

    @pytest.fixture
    def river_chars(self):
        """Sample river characteristics for testing."""
        return {
            '02455000': {
                'name': 'Locust Fork',
                'avg_response_hours': 33,
                'response_range': [26, 38],
                'rain_needed_inches': 1.75,
                'responsiveness': 'moderate'
            },
            'short_creek': {
                'name': 'Short Creek',
                'avg_response_hours': 12,
                'response_range': [6, 18],
                'rain_needed_inches': 0.65,
                'responsiveness': 'fast'
            }
        }

    def test_no_rain_zero_likelihood(self, river_chars):
        """Zero QPF = 0% likelihood."""
        sites = [{
            'site': '02455000',
            'name': 'Locust Fork',
            'in_range': False,
            'qpf': {'2025-01-01': 0.0, '2025-01-02': 0.0, '2025-01-03': 0.0}
        }]
        predictions = calculate_predictions(sites, river_chars)
        assert len(predictions) == 1
        assert predictions[0]['likelihood'] == 0
        assert predictions[0]['status'] == 'very_unlikely'

    def test_enough_rain_likely(self, river_chars):
        """QPF >= rain_needed = likely status."""
        sites = [{
            'site': '02455000',
            'name': 'Locust Fork',
            'in_range': False,
            'qpf': {'2025-01-01': 0.5, '2025-01-02': 0.75, '2025-01-03': 0.75}  # 2.0" total
        }]
        predictions = calculate_predictions(sites, river_chars)
        assert predictions[0]['likelihood'] >= 70
        assert predictions[0]['status'] == 'likely'

    def test_abundant_rain_very_likely(self, river_chars):
        """QPF >= 1.5x rain_needed = 95% likelihood (capped)."""
        sites = [{
            'site': '02455000',
            'name': 'Locust Fork',
            'in_range': False,
            'qpf': {'2025-01-01': 1.5, '2025-01-02': 1.5, '2025-01-03': 1.0}  # 4.0" total
        }]
        predictions = calculate_predictions(sites, river_chars)
        assert predictions[0]['likelihood'] == 95  # Capped at 95
        assert predictions[0]['status'] == 'likely'

    def test_partial_rain_possible(self, river_chars):
        """75-100% of needed rain = possible status."""
        sites = [{
            'site': '02455000',
            'name': 'Locust Fork',
            'in_range': False,
            'qpf': {'2025-01-01': 0.5, '2025-01-02': 0.5, '2025-01-03': 0.4}  # 1.4" = 80% of 1.75
        }]
        predictions = calculate_predictions(sites, river_chars)
        assert 40 <= predictions[0]['likelihood'] < 70
        assert predictions[0]['status'] == 'possible'

    def test_already_running_100_percent(self, river_chars):
        """in_range=True overrides to 100% likelihood."""
        sites = [{
            'site': '02455000',
            'name': 'Locust Fork',
            'in_range': True,  # Already running!
            'qpf': {'2025-01-01': 0.0, '2025-01-02': 0.0, '2025-01-03': 0.0}  # No rain
        }]
        predictions = calculate_predictions(sites, river_chars)
        assert predictions[0]['likelihood'] == 100
        assert predictions[0]['status'] == 'running'
        assert predictions[0]['status_text'] == 'Running Now!'

    def test_short_creek_detection(self, river_chars):
        """Short Creek matches by name (not site_id)."""
        sites = [{
            'site': 'streambeam_1',  # Non-standard site ID
            'name': 'Short Creek',   # Name contains "short"
            'in_range': False,
            'qpf': {'2025-01-01': 0.3, '2025-01-02': 0.3, '2025-01-03': 0.2}  # 0.8" > 0.65 needed
        }]
        predictions = calculate_predictions(sites, river_chars)
        assert len(predictions) == 1
        assert predictions[0]['name'] == 'Short Creek'
        assert predictions[0]['likelihood'] >= 70  # Should be likely

    def test_unknown_river_skipped(self, river_chars):
        """Rivers without characteristics are skipped."""
        sites = [{
            'site': '99999999',
            'name': 'Unknown River',
            'in_range': False,
            'qpf': {'2025-01-01': 1.0, '2025-01-02': 1.0, '2025-01-03': 1.0}
        }]
        predictions = calculate_predictions(sites, river_chars)
        assert len(predictions) == 0  # Skipped

    def test_sorted_by_likelihood(self, river_chars):
        """Results sorted by likelihood (highest first)."""
        sites = [
            {
                'site': '02455000',
                'name': 'Locust Fork',
                'in_range': False,
                'qpf': {'2025-01-01': 0.0, '2025-01-02': 0.0, '2025-01-03': 0.1}  # Low likelihood
            },
            {
                'site': 'streambeam_1',
                'name': 'Short Creek',
                'in_range': False,
                'qpf': {'2025-01-01': 0.5, '2025-01-02': 0.5, '2025-01-03': 0.5}  # High likelihood
            }
        ]
        predictions = calculate_predictions(sites, river_chars)
        assert predictions[0]['name'] == 'Short Creek'  # Higher likelihood first
        assert predictions[0]['likelihood'] > predictions[1]['likelihood']

    def test_qpf_breakdown_included(self, river_chars):
        """Prediction includes QPF breakdown by day."""
        sites = [{
            'site': '02455000',
            'name': 'Locust Fork',
            'in_range': False,
            'qpf': {'2025-01-01': 0.25, '2025-01-02': 0.50, '2025-01-03': 0.75}
        }]
        predictions = calculate_predictions(sites, river_chars)
        breakdown = predictions[0]['qpf_breakdown']
        assert breakdown['today'] == 0.25
        assert breakdown['tomorrow'] == 0.50
        assert breakdown['day3'] == 0.75

    def test_rain_surplus_calculated(self, river_chars):
        """rain_surplus shows difference from needed."""
        sites = [{
            'site': '02455000',
            'name': 'Locust Fork',
            'in_range': False,
            'qpf': {'2025-01-01': 1.0, '2025-01-02': 1.0, '2025-01-03': 1.0}  # 3.0" total
        }]
        predictions = calculate_predictions(sites, river_chars)
        # 3.0 - 1.75 = 1.25 surplus
        assert predictions[0]['rain_surplus'] == pytest.approx(1.25, abs=0.01)


# =============================================================================
# Test format_local_time()
# =============================================================================
class TestFormatLocalTime:
    """Tests for human-friendly time formatting."""

    def test_morning(self):
        """6am-12pm = morning."""
        dt = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)  # 14:00 UTC = 8am Central
        result = format_local_time(dt)
        assert "morning" in result

    def test_afternoon(self):
        """12pm-5pm = afternoon."""
        dt = datetime(2025, 1, 15, 20, 0, 0, tzinfo=timezone.utc)  # 20:00 UTC = 2pm Central
        result = format_local_time(dt)
        assert "afternoon" in result

    def test_evening(self):
        """5pm-9pm = evening."""
        dt = datetime(2025, 1, 15, 23, 0, 0, tzinfo=timezone.utc)  # 23:00 UTC = 5pm Central
        result = format_local_time(dt)
        assert "evening" in result

    def test_includes_day_name(self):
        """Result includes abbreviated day name."""
        dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)  # Wednesday
        result = format_local_time(dt)
        assert "Wed" in result


# =============================================================================
# Test status classification boundaries
# =============================================================================
class TestStatusClassification:
    """Tests for likelihood → status mapping boundaries."""

    @pytest.fixture
    def river_chars(self):
        return {
            'test': {
                'name': 'Test River',
                'avg_response_hours': 24,
                'response_range': [18, 30],
                'rain_needed_inches': 1.0,
                'responsiveness': 'fast'
            }
        }

    def _get_status_for_qpf(self, total_qpf, river_chars):
        """Helper to get status for a given QPF total."""
        sites = [{
            'site': 'test',
            'name': 'Test River',
            'in_range': False,
            'qpf': {'2025-01-01': total_qpf, '2025-01-02': 0, '2025-01-03': 0}
        }]
        predictions = calculate_predictions(sites, river_chars)
        return predictions[0]['status'], predictions[0]['likelihood']

    def test_status_likely_boundary(self, river_chars):
        """70%+ likelihood = likely status."""
        status, likelihood = self._get_status_for_qpf(1.0, river_chars)  # Exactly rain_needed
        assert likelihood >= 70
        assert status == 'likely'

    def test_status_very_unlikely_boundary(self, river_chars):
        """<15% likelihood = very_unlikely status."""
        status, likelihood = self._get_status_for_qpf(0.1, river_chars)  # 10% of needed
        assert likelihood < 15
        assert status == 'very_unlikely'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
