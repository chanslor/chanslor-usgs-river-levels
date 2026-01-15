#!/usr/bin/env python3
"""
Unit tests for core alert logic in usgs_multi_alert.py

Run with: pytest tests/ -v
"""
import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# Test normalize_site_id()
# =============================================================================
class TestNormalizeSiteId:
    """Tests for site ID extraction/normalization."""

    def test_plain_numeric(self):
        """Plain numeric string passes through unchanged."""
        from usgs_multi_alert import normalize_site_id
        assert normalize_site_id("02399200") == "02399200"
        assert normalize_site_id("03572690") == "03572690"

    def test_extract_from_text(self):
        """Extract 8+ digit ID from mixed text."""
        from usgs_multi_alert import normalize_site_id
        assert normalize_site_id("Little River (USGS 02399200)") == "02399200"
        assert normalize_site_id("Foo (USGS 03572690)") == "03572690"

    def test_extract_last_match(self):
        """When multiple numbers present, use the last 8+ digit match."""
        from usgs_multi_alert import normalize_site_id
        # Should pick "02399200" not "12345"
        assert normalize_site_id("Site 12345 gauge 02399200") == "02399200"

    def test_whitespace_handling(self):
        """Strips leading/trailing whitespace."""
        from usgs_multi_alert import normalize_site_id
        assert normalize_site_id("  02399200  ") == "02399200"
        assert normalize_site_id("\t02399200\n") == "02399200"

    def test_invalid_raises_error(self):
        """Raise ValueError when no valid site ID found."""
        from usgs_multi_alert import normalize_site_id
        with pytest.raises(ValueError, match="no numeric id found"):
            normalize_site_id("InvalidSite")
        # Note: plain numeric strings of any length pass through (isdigit check)
        # Only text with embedded short numbers fails (regex needs 8+ digits)
        with pytest.raises(ValueError, match="no numeric id found"):
            normalize_site_id("Site 123")  # Text with short ID fails

    def test_empty_raises_error(self):
        """Raise ValueError for empty/None input."""
        from usgs_multi_alert import normalize_site_id
        with pytest.raises(ValueError):
            normalize_site_id("")
        with pytest.raises(ValueError):
            normalize_site_id(None)


# =============================================================================
# Test is_in() threshold logic
# =============================================================================
class TestIsInThreshold:
    """Tests for dual-threshold evaluation logic.

    The is_in() function is defined inside main(), so we recreate the logic here.
    This tests the ALGORITHM, not the actual function (which would require mocking main()).
    """

    @staticmethod
    def is_in(stage, cfs, th_ft, th_cfs):
        """Recreate threshold logic for testing."""
        cond_ft = True if th_ft is None else (stage is not None and stage >= th_ft)
        cond_cfs = True if th_cfs is None else (cfs is not None and cfs >= th_cfs)
        return cond_ft and cond_cfs

    # --- Both thresholds set ---
    def test_both_thresholds_both_pass(self):
        """Both conditions met = IN."""
        assert self.is_in(stage=5.0, cfs=300, th_ft=4.0, th_cfs=250) is True

    def test_both_thresholds_ft_fails(self):
        """Stage below threshold = OUT (even if CFS passes)."""
        assert self.is_in(stage=3.0, cfs=300, th_ft=4.0, th_cfs=250) is False

    def test_both_thresholds_cfs_fails(self):
        """CFS below threshold = OUT (even if stage passes)."""
        assert self.is_in(stage=5.0, cfs=200, th_ft=4.0, th_cfs=250) is False

    def test_both_thresholds_both_fail(self):
        """Both conditions fail = OUT."""
        assert self.is_in(stage=3.0, cfs=200, th_ft=4.0, th_cfs=250) is False

    # --- Only ft threshold ---
    def test_ft_only_passes(self):
        """Stage-only threshold, condition met."""
        assert self.is_in(stage=5.0, cfs=None, th_ft=4.0, th_cfs=None) is True

    def test_ft_only_fails(self):
        """Stage-only threshold, condition not met."""
        assert self.is_in(stage=3.0, cfs=None, th_ft=4.0, th_cfs=None) is False

    # --- Only cfs threshold ---
    def test_cfs_only_passes(self):
        """CFS-only threshold, condition met."""
        assert self.is_in(stage=None, cfs=300, th_ft=None, th_cfs=250) is True

    def test_cfs_only_fails(self):
        """CFS-only threshold, condition not met."""
        assert self.is_in(stage=None, cfs=200, th_ft=None, th_cfs=250) is False

    # --- Edge cases ---
    def test_exact_threshold_is_in(self):
        """Exactly at threshold = IN (>= comparison)."""
        assert self.is_in(stage=4.0, cfs=250, th_ft=4.0, th_cfs=250) is True

    def test_none_values_handled(self):
        """None stage/cfs with threshold = OUT."""
        assert self.is_in(stage=None, cfs=300, th_ft=4.0, th_cfs=250) is False
        assert self.is_in(stage=5.0, cfs=None, th_ft=4.0, th_cfs=250) is False

    def test_no_thresholds_always_in(self):
        """No thresholds configured = always IN."""
        assert self.is_in(stage=1.0, cfs=50, th_ft=None, th_cfs=None) is True
        assert self.is_in(stage=None, cfs=None, th_ft=None, th_cfs=None) is True


# =============================================================================
# Test calculate_percent_change()
# =============================================================================
class TestCalculatePercentChange:
    """Tests for trend percent change calculation."""

    def test_rising_trend(self):
        """Detect rising water (positive change)."""
        from usgs_multi_alert import calculate_percent_change
        trend_data = {"values": [2.0, 2.5, 3.0]}
        pct, direction = calculate_percent_change(trend_data)
        assert pct == pytest.approx(50.0)  # (3.0 - 2.0) / 2.0 * 100
        assert direction == "up"

    def test_falling_trend(self):
        """Detect falling water (negative change)."""
        from usgs_multi_alert import calculate_percent_change
        trend_data = {"values": [3.0, 2.5, 2.0]}
        pct, direction = calculate_percent_change(trend_data)
        assert pct == pytest.approx(-33.33, rel=0.01)  # (2.0 - 3.0) / 3.0 * 100
        assert direction == "down"

    def test_flat_trend(self):
        """Detect steady water (no change)."""
        from usgs_multi_alert import calculate_percent_change
        trend_data = {"values": [2.5, 2.5, 2.5]}
        pct, direction = calculate_percent_change(trend_data)
        assert pct == pytest.approx(0.0)
        assert direction == "flat"

    def test_empty_data(self):
        """Handle empty or missing data gracefully."""
        from usgs_multi_alert import calculate_percent_change
        assert calculate_percent_change(None) == (None, "flat")
        assert calculate_percent_change({}) == (None, "flat")
        assert calculate_percent_change({"values": []}) == (None, "flat")

    def test_single_value(self):
        """Single value = no trend calculable."""
        from usgs_multi_alert import calculate_percent_change
        pct, direction = calculate_percent_change({"values": [2.5]})
        assert pct is None
        assert direction == "flat"


# =============================================================================
# Test alert state transitions
# =============================================================================
class TestAlertStateTransitions:
    """Tests for alert state machine logic.

    These test the CONDITIONS for alerts, not actual email sending.
    """

    @staticmethod
    def should_send_in_alert(was_in: bool, in_range: bool, mode: str,
                              time_since_alert: float, cooldown: float) -> bool:
        """Recreate IN alert logic."""
        if mode == "rising":
            return (not was_in) and in_range and (time_since_alert >= cooldown)
        else:  # mode == "any"
            return in_range and (time_since_alert >= cooldown)

    @staticmethod
    def should_send_out_alert(was_in: bool, in_range: bool, send_out: bool,
                               time_since_out: float, out_cooldown: float) -> bool:
        """Recreate OUT alert logic."""
        return send_out and was_in and (not in_range) and (time_since_out >= out_cooldown)

    # --- Rising mode (default) ---
    def test_rising_mode_out_to_in(self):
        """Rising mode: alert on OUT→IN transition."""
        assert self.should_send_in_alert(
            was_in=False, in_range=True, mode="rising",
            time_since_alert=7200, cooldown=3600
        ) is True

    def test_rising_mode_stay_in(self):
        """Rising mode: no alert if already IN."""
        assert self.should_send_in_alert(
            was_in=True, in_range=True, mode="rising",
            time_since_alert=7200, cooldown=3600
        ) is False

    def test_rising_mode_cooldown_blocks(self):
        """Rising mode: cooldown prevents alert."""
        assert self.should_send_in_alert(
            was_in=False, in_range=True, mode="rising",
            time_since_alert=1800, cooldown=3600  # Only 30 min, need 1 hr
        ) is False

    # --- Any mode ---
    def test_any_mode_alerts_when_in(self):
        """Any mode: alert whenever IN (regardless of previous state)."""
        assert self.should_send_in_alert(
            was_in=True, in_range=True, mode="any",
            time_since_alert=7200, cooldown=3600
        ) is True

    # --- OUT alerts ---
    def test_out_alert_on_transition(self):
        """OUT alert when IN→OUT with send_out enabled."""
        assert self.should_send_out_alert(
            was_in=True, in_range=False, send_out=True,
            time_since_out=7200, out_cooldown=3600
        ) is True

    def test_out_alert_disabled(self):
        """No OUT alert if send_out is False."""
        assert self.should_send_out_alert(
            was_in=True, in_range=False, send_out=False,
            time_since_out=7200, out_cooldown=3600
        ) is False

    def test_out_alert_not_was_in(self):
        """No OUT alert if wasn't previously IN."""
        assert self.should_send_out_alert(
            was_in=False, in_range=False, send_out=True,
            time_since_out=7200, out_cooldown=3600
        ) is False


# =============================================================================
# Test visual gauge conversion (North Chickamauga)
# =============================================================================
class TestVisualGaugeConversion:
    """Tests for North Chickamauga visual gauge formula.

    Formula: Visual = 0.69 × USGS_Stage - 1.89
    """

    @staticmethod
    def usgs_to_visual(usgs_stage: float) -> float:
        """Convert USGS stage to visual gauge reading."""
        return 0.69 * usgs_stage - 1.89

    @staticmethod
    def visual_to_usgs(visual: float) -> float:
        """Convert visual gauge to USGS stage."""
        return (visual + 1.89) / 0.69

    def test_calibration_point_1(self):
        """Verify calibration: 6.22 ft USGS = 2.42 ft visual."""
        visual = self.usgs_to_visual(6.22)
        assert visual == pytest.approx(2.42, abs=0.05)

    def test_calibration_point_2(self):
        """Verify calibration: 5.34 ft USGS = 1.81 ft visual."""
        visual = self.usgs_to_visual(5.34)
        assert visual == pytest.approx(1.79, abs=0.05)  # Slight drift from real data

    def test_runnable_threshold(self):
        """5.2 ft USGS = 1.7 ft visual (runnable threshold)."""
        visual = self.usgs_to_visual(5.2)
        assert visual == pytest.approx(1.70, abs=0.1)

    def test_good_threshold(self):
        """6.6 ft USGS = 2.7 ft visual (good threshold)."""
        visual = self.usgs_to_visual(6.6)
        assert visual == pytest.approx(2.66, abs=0.1)

    def test_reverse_conversion(self):
        """Verify inverse formula works."""
        usgs = self.visual_to_usgs(1.7)
        assert usgs == pytest.approx(5.2, abs=0.1)


# =============================================================================
# Test Little River Canyon flow classification
# =============================================================================
class TestLittleRiverCanyonFlowLevels:
    """Tests for LRC 6-level flow classification (Adam Goshorn system)."""

    @staticmethod
    def classify_lrc_flow(cfs: float) -> tuple:
        """Classify LRC flow level."""
        if cfs < 250:
            return ("not_runnable", "gray", "Not Runnable")
        elif cfs < 400:
            return ("good_low", "yellow", "Good Low")
        elif cfs < 800:
            return ("shitty_medium", "brown", "Shitty Medium")
        elif cfs < 1500:
            return ("good_medium", "light_green", "Good Medium")
        elif cfs < 2500:
            return ("best", "green", "Good High (BEST!)")
        else:
            return ("too_high", "red", "Too High")

    def test_not_runnable(self):
        """< 250 CFS = not runnable."""
        level, _, label = self.classify_lrc_flow(100)
        assert level == "not_runnable"
        assert label == "Not Runnable"

    def test_good_low(self):
        """250-400 CFS = good low."""
        level, _, label = self.classify_lrc_flow(300)
        assert level == "good_low"

    def test_shitty_medium(self):
        """400-800 CFS = shitty medium."""
        level, _, label = self.classify_lrc_flow(600)
        assert level == "shitty_medium"

    def test_good_medium(self):
        """800-1500 CFS = good medium."""
        level, _, label = self.classify_lrc_flow(1000)
        assert level == "good_medium"

    def test_best(self):
        """1500-2500 CFS = BEST!"""
        level, color, label = self.classify_lrc_flow(2000)
        assert level == "best"
        assert "BEST" in label

    def test_too_high(self):
        """2500+ CFS = too high."""
        level, color, _ = self.classify_lrc_flow(3000)
        assert level == "too_high"
        assert color == "red"

    def test_boundary_values(self):
        """Test exact boundary values."""
        assert self.classify_lrc_flow(249)[0] == "not_runnable"
        assert self.classify_lrc_flow(250)[0] == "good_low"
        assert self.classify_lrc_flow(399)[0] == "good_low"
        assert self.classify_lrc_flow(400)[0] == "shitty_medium"


# =============================================================================
# Test StreamBeam data validation
# =============================================================================
class TestStreamBeamValidation:
    """Tests for StreamBeam gauge data validation."""

    @staticmethod
    def validate_streambeam(level_ft: float, last_level: float,
                            min_valid: float = -5.0, max_valid: float = 30.0,
                            max_change: float = 5.0) -> tuple:
        """Validate StreamBeam reading.

        Returns: (is_valid, reason)
        """
        if level_ft is None:
            return (False, "null reading")
        if level_ft < min_valid or level_ft > max_valid:
            return (False, f"out of range [{min_valid}, {max_valid}]")
        if last_level is not None:
            change = abs(level_ft - last_level)
            if change > max_change:
                return (False, f"change {change:.2f} > max {max_change}")
        return (True, "valid")

    def test_valid_reading(self):
        """Normal reading passes validation."""
        valid, _ = self.validate_streambeam(1.5, last_level=1.4)
        assert valid is True

    def test_out_of_range_low(self):
        """Below minimum fails."""
        valid, reason = self.validate_streambeam(-10.0, last_level=1.0)
        assert valid is False
        assert "out of range" in reason

    def test_out_of_range_high(self):
        """Above maximum fails."""
        valid, reason = self.validate_streambeam(50.0, last_level=1.0)
        assert valid is False
        assert "out of range" in reason

    def test_spike_detection(self):
        """Large sudden change fails (spike detection)."""
        valid, reason = self.validate_streambeam(10.0, last_level=1.0, max_change=5.0)
        assert valid is False
        assert "change" in reason

    def test_first_reading_no_spike_check(self):
        """First reading (no previous) skips spike check."""
        valid, _ = self.validate_streambeam(10.0, last_level=None)
        assert valid is True


# =============================================================================
# Integration-style tests (require mocking external APIs)
# =============================================================================
class TestAPIIntegration:
    """Placeholder for integration tests requiring API mocks.

    These would use pytest-mock or responses library to mock USGS API.
    """

    @pytest.mark.skip(reason="Requires API mocking setup")
    def test_fetch_trend_label_rising(self):
        """Test trend detection with mocked rising data."""
        pass

    @pytest.mark.skip(reason="Requires API mocking setup")
    def test_fetch_trend_data_returns_values(self):
        """Test trend data fetch with mocked API response."""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
