"""Tests for palettize.cli module."""

import pytest
from typer.testing import CliRunner

from palettize.cli import app, ExitCodes


runner = CliRunner()


class TestCLIBasic:
    """Basic CLI tests."""

    def test_version(self):
        """Test --version flag shows version."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == ExitCodes.SUCCESS
        assert "Palettize CLI Version:" in result.output

    def test_help(self):
        """Test --help flag shows help."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "palettize" in result.output.lower()


class TestShowCommand:
    """Tests for the 'show' command."""

    def test_show_with_colors(self):
        """Test show command with custom colors."""
        result = runner.invoke(app, ["show", "--colors", "red,blue"])
        assert result.exit_code == ExitCodes.SUCCESS

    def test_show_missing_input(self):
        """Test show command without colors or preset."""
        result = runner.invoke(app, ["show"])
        assert result.exit_code == ExitCodes.USAGE_ERROR
        assert "Error" in result.output

    def test_show_invalid_color(self):
        """Test show command with invalid color."""
        result = runner.invoke(app, ["show", "--colors", "not_a_color_xyz123"])
        # Should fail with an error exit code
        assert result.exit_code != ExitCodes.SUCCESS
        assert "Error" in result.output or "error" in result.output.lower()

    def test_show_with_width(self):
        """Test show command with width option."""
        result = runner.invoke(app, ["show", "--colors", "red,blue", "--width", "40"])
        assert result.exit_code == ExitCodes.SUCCESS


class TestCreateCommand:
    """Tests for the 'create' command."""

    def test_create_basic(self):
        """Test basic create command with hex exporter."""
        result = runner.invoke(
            app, ["create", "--colors", "red,blue", "--format", "hex", "--steps", "3"]
        )
        assert result.exit_code == ExitCodes.SUCCESS
        # Should output hex colors
        assert "#" in result.output

    def test_create_rgba_format(self):
        """Test create command with rgba format."""
        result = runner.invoke(
            app, ["create", "--colors", "red,blue", "--format", "rgba", "--steps", "3"]
        )
        assert result.exit_code == ExitCodes.SUCCESS
        # Output contains rgba format colors
        assert "rgba" in result.output.lower()

    def test_create_multiple_formats(self):
        """Test create command with multiple formats."""
        result = runner.invoke(
            app,
            ["create", "--colors", "red,blue", "-f", "hex", "-f", "rgba", "-n", "3"],
        )
        assert result.exit_code == ExitCodes.SUCCESS
        # Should have output from both formats
        assert len(result.output) > 0

    def test_create_missing_format(self):
        """Test create command without format raises error."""
        result = runner.invoke(app, ["create", "--colors", "red,blue"])
        assert result.exit_code != ExitCodes.SUCCESS

    def test_create_unknown_format(self):
        """Test create command with unknown format."""
        result = runner.invoke(
            app, ["create", "--colors", "red,blue", "-f", "unknown_format"]
        )
        assert result.exit_code == ExitCodes.EXPORT_ERROR
        assert "not found" in result.output.lower()

    def test_create_with_domain(self):
        """Test create command with custom domain."""
        result = runner.invoke(
            app,
            [
                "create",
                "--colors",
                "red,blue",
                "-f",
                "hex",
                "-n",
                "3",
                "--domain",
                "0,255",
            ],
        )
        assert result.exit_code == ExitCodes.SUCCESS

    def test_create_with_scale(self):
        """Test create command with different scale types."""
        # Linear scale
        result = runner.invoke(
            app,
            [
                "create",
                "--colors",
                "red,blue",
                "-f",
                "hex",
                "-n",
                "3",
                "--scale",
                "linear",
            ],
        )
        assert result.exit_code == ExitCodes.SUCCESS

        # Power scale requires exponent
        result = runner.invoke(
            app,
            [
                "create",
                "--colors",
                "red,blue",
                "-f",
                "hex",
                "-n",
                "3",
                "--scale",
                "power",
                "--scale-exponent",
                "2",
            ],
        )
        assert result.exit_code == ExitCodes.SUCCESS

    def test_create_power_without_exponent(self):
        """Test create command with power scale without exponent."""
        result = runner.invoke(
            app,
            [
                "create",
                "--colors",
                "red,blue",
                "-f",
                "hex",
                "-n",
                "3",
                "--scale",
                "power",
            ],
        )
        assert result.exit_code == ExitCodes.USAGE_ERROR


class TestListCommand:
    """Tests for the 'list' subcommands."""

    def test_list_exporters(self):
        """Test list exporters command."""
        result = runner.invoke(app, ["list", "exporters"])
        assert result.exit_code == ExitCodes.SUCCESS
        assert "gdal" in result.output.lower()
        assert "qgis" in result.output.lower()

    def test_list_presets(self):
        """Test list presets command."""
        result = runner.invoke(app, ["list", "presets"])
        assert result.exit_code == ExitCodes.SUCCESS


class TestVerboseFlag:
    """Tests for verbose flag behavior."""

    def test_verbose_shows_more_output(self):
        """Test that verbose flag shows additional output."""
        # Without verbose - should only show results
        quiet_result = runner.invoke(
            app, ["create", "--colors", "red,blue", "-f", "hex", "-n", "3"]
        )

        # With verbose - should show more messages
        verbose_result = runner.invoke(
            app, ["create", "-v", "--colors", "red,blue", "-f", "hex", "-n", "3"]
        )

        # Verbose output should be longer due to status messages
        assert len(verbose_result.output) >= len(quiet_result.output)

    def test_default_is_quiet(self):
        """Test that default behavior is quiet (only results)."""
        result = runner.invoke(
            app, ["create", "--colors", "red,blue", "-f", "hex", "-n", "3"]
        )
        assert result.exit_code == ExitCodes.SUCCESS
        # Should NOT contain status messages like "Exporting to"
        assert "Exporting to" not in result.output
        assert "Export process completed" not in result.output
