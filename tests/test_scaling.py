"""Tests for palettize.scaling module."""

import math

import pytest

from palettize.scaling import (
    get_linear_scaler,
    get_log_scaler,
    get_power_scaler,
    get_scaler_by_name,
    get_sqrt_scaler,
    get_symlog_scaler,
    linear_scale,
    log_scale,
    power_scale,
    symlog_scale,
)


class TestLinearScale:
    """Tests for linear scaling functions."""

    def test_linear_scale_basic(self):
        """Test basic linear scaling."""
        assert linear_scale(0, 0, 100) == 0.0
        assert linear_scale(50, 0, 100) == 0.5
        assert linear_scale(100, 0, 100) == 1.0

    def test_linear_scale_clamping(self):
        """Test that clamping works for out-of-range values."""
        assert linear_scale(-10, 0, 100, clamp=True) == 0.0
        assert linear_scale(150, 0, 100, clamp=True) == 1.0

    def test_linear_scale_no_clamp(self):
        """Test linear scaling without clamping."""
        assert linear_scale(-50, 0, 100, clamp=False) == -0.5
        assert linear_scale(150, 0, 100, clamp=False) == 1.5

    def test_linear_scale_equal_domain_raises_error(self):
        """Test that equal domain_min and domain_max raises ValueError."""
        with pytest.raises(ValueError, match="cannot be equal"):
            linear_scale(50, 100, 100)

    def test_get_linear_scaler(self):
        """Test get_linear_scaler factory function."""
        scaler = get_linear_scaler(0, 100)
        assert scaler(0) == 0.0
        assert scaler(50) == 0.5
        assert scaler(100) == 1.0

    def test_get_linear_scaler_negative_domain(self):
        """Test linear scaler with negative domain."""
        scaler = get_linear_scaler(-100, 100)
        assert scaler(-100) == 0.0
        assert scaler(0) == 0.5
        assert scaler(100) == 1.0


class TestPowerScale:
    """Tests for power scaling functions."""

    def test_power_scale_exponent_2(self):
        """Test power scaling with exponent 2 (quadratic)."""
        assert power_scale(0, 0, 100, 2) == 0.0
        assert abs(power_scale(50, 0, 100, 2) - 0.25) < 0.001
        assert power_scale(100, 0, 100, 2) == 1.0

    def test_power_scale_exponent_half(self):
        """Test power scaling with exponent 0.5 (sqrt)."""
        result = power_scale(25, 0, 100, 0.5)
        assert abs(result - 0.5) < 0.001

    def test_power_scale_clamping(self):
        """Test power scale clamping."""
        assert power_scale(-10, 0, 100, 2, clamp=True) == 0.0
        assert power_scale(150, 0, 100, 2, clamp=True) == 1.0

    def test_get_power_scaler(self):
        """Test get_power_scaler factory function."""
        scaler = get_power_scaler(0, 100, exponent=2)
        assert scaler(0) == 0.0
        assert abs(scaler(50) - 0.25) < 0.001
        assert scaler(100) == 1.0

    def test_get_sqrt_scaler(self):
        """Test get_sqrt_scaler factory function."""
        scaler = get_sqrt_scaler(0, 100)
        result = scaler(25)
        assert abs(result - 0.5) < 0.001


class TestLogScale:
    """Tests for logarithmic scaling functions."""

    def test_log_scale_basic(self):
        """Test basic logarithmic scaling."""
        # Domain from 1 to 100 with base 10
        assert log_scale(1, 1, 100, base=10) == 0.0
        assert abs(log_scale(10, 1, 100, base=10) - 0.5) < 0.001
        assert log_scale(100, 1, 100, base=10) == 1.0

    def test_log_scale_clamping(self):
        """Test log scale clamping."""
        assert log_scale(0.5, 1, 100, base=10, clamp=True) == 0.0
        assert log_scale(200, 1, 100, base=10, clamp=True) == 1.0

    def test_log_scale_invalid_domain(self):
        """Test that non-positive domain raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            log_scale(10, 0, 100, base=10)

        with pytest.raises(ValueError, match="must be positive"):
            log_scale(10, -10, 100, base=10)

    def test_log_scale_invalid_base(self):
        """Test that invalid base raises ValueError."""
        with pytest.raises(ValueError, match="base must be"):
            log_scale(10, 1, 100, base=0)

        with pytest.raises(ValueError, match="base must be"):
            log_scale(10, 1, 100, base=1)

    def test_get_log_scaler(self):
        """Test get_log_scaler factory function."""
        scaler = get_log_scaler(1, 100, base=10)
        assert scaler(1) == 0.0
        assert abs(scaler(10) - 0.5) < 0.001
        assert scaler(100) == 1.0


class TestSymlogScale:
    """Tests for symmetric logarithmic scaling functions."""

    def test_symlog_scale_positive(self):
        """Test symlog scaling with positive values."""
        # Simple case with symmetric domain
        result = symlog_scale(0, -100, 100, linthresh=10)
        assert abs(result - 0.5) < 0.001  # 0 should be at midpoint

    def test_symlog_scale_boundaries(self):
        """Test symlog scaling at domain boundaries."""
        assert symlog_scale(-100, -100, 100, linthresh=10, clamp=True) == 0.0
        assert symlog_scale(100, -100, 100, linthresh=10, clamp=True) == 1.0

    def test_symlog_scale_linear_region(self):
        """Test that values within linthresh are scaled linearly."""
        # Within the linear threshold, the scaling should be linear
        result1 = symlog_scale(5, -100, 100, linthresh=10)
        result2 = symlog_scale(-5, -100, 100, linthresh=10)
        # The difference from midpoint should be symmetric
        assert abs((result1 - 0.5) + (result2 - 0.5)) < 0.001

    def test_symlog_scale_invalid_linthresh(self):
        """Test that non-positive linthresh raises ValueError."""
        with pytest.raises(ValueError, match="linthresh"):
            symlog_scale(10, -100, 100, linthresh=0)

        with pytest.raises(ValueError, match="linthresh"):
            symlog_scale(10, -100, 100, linthresh=-5)

    def test_get_symlog_scaler(self):
        """Test get_symlog_scaler factory function."""
        scaler = get_symlog_scaler(-100, 100, linthresh=10)
        assert scaler(-100) == 0.0
        assert abs(scaler(0) - 0.5) < 0.001
        assert scaler(100) == 1.0


class TestGetScalerByName:
    """Tests for the get_scaler_by_name factory function."""

    def test_linear_scaler_by_name(self):
        """Test getting linear scaler by name."""
        scaler = get_scaler_by_name("linear", 0, 100)
        assert scaler(50) == 0.5

    def test_power_scaler_by_name(self):
        """Test getting power scaler by name."""
        scaler = get_scaler_by_name("power", 0, 100, exponent=2)
        assert abs(scaler(50) - 0.25) < 0.001

    def test_sqrt_scaler_by_name(self):
        """Test getting sqrt scaler by name."""
        scaler = get_scaler_by_name("sqrt", 0, 100)
        assert abs(scaler(25) - 0.5) < 0.001

    def test_log_scaler_by_name(self):
        """Test getting log scaler by name."""
        scaler = get_scaler_by_name("log", 1, 100, base=10)
        assert abs(scaler(10) - 0.5) < 0.001

    def test_symlog_scaler_by_name(self):
        """Test getting symlog scaler by name."""
        scaler = get_scaler_by_name("symlog", -100, 100, linthresh=10)
        assert abs(scaler(0) - 0.5) < 0.001

    def test_unknown_scaler_raises_error(self):
        """Test that unknown scaler name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown scaler type"):
            get_scaler_by_name("unknown", 0, 100)

    def test_power_without_exponent_raises_error(self):
        """Test that power scaler without exponent raises ValueError."""
        with pytest.raises(ValueError, match="exponent"):
            get_scaler_by_name("power", 0, 100)

    def test_symlog_without_linthresh_raises_error(self):
        """Test that symlog scaler without linthresh raises ValueError."""
        with pytest.raises(ValueError, match="linthresh"):
            get_scaler_by_name("symlog", -100, 100)

    def test_case_insensitive(self):
        """Test that scaler names are case insensitive."""
        scaler1 = get_scaler_by_name("LINEAR", 0, 100)
        scaler2 = get_scaler_by_name("Linear", 0, 100)
        scaler3 = get_scaler_by_name("linear", 0, 100)
        assert scaler1(50) == scaler2(50) == scaler3(50)
