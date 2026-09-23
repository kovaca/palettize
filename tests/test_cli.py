"""Tests for palettize.cli."""

from __future__ import annotations

import json
import re

import pytest
from typer.testing import CliRunner

from palettize.cli import ExitCodes, app

runner = CliRunner()

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def invoke(*args: str):
    """Run the CLI with the given arguments."""
    return runner.invoke(app, list(args))


class TestCLIBasic:
    def test_version(self):
        result = invoke("--version")
        assert result.exit_code == ExitCodes.SUCCESS
        assert "Palettize CLI Version:" in result.output

    def test_help(self):
        result = invoke("--help")
        assert result.exit_code == 0
        assert "palettize" in result.output.lower()

    def test_bare_invocation_shows_help(self):
        assert "Usage" in invoke().output

    def test_info_banner(self):
        result = invoke("info")
        assert result.exit_code == ExitCodes.SUCCESS
        assert "Version:" in result.output

    @pytest.mark.parametrize(
        "command", ["show", "create", "analyze", "formats", "list", "info", "presets"]
    )
    def test_every_command_has_help(self, command):
        result = invoke(command, "--help")
        assert result.exit_code == 0


class TestShowCommand:
    def test_with_colors(self):
        assert invoke("show", "--colors", "red,blue").exit_code == ExitCodes.SUCCESS

    def test_with_preset(self):
        assert invoke("show", "viridis").exit_code == ExitCodes.SUCCESS

    def test_missing_input_is_a_usage_error(self):
        result = invoke("show")
        assert result.exit_code == ExitCodes.USAGE_ERROR
        assert "Error" in result.output

    def test_colors_and_preset_together_is_a_usage_error(self):
        result = invoke("show", "viridis", "--colors", "red,blue")
        assert result.exit_code == ExitCodes.USAGE_ERROR
        assert "mutually exclusive" in result.output

    def test_invalid_color_reports_the_right_code(self):
        result = invoke("show", "--colors", "not_a_color_xyz123")
        assert result.exit_code == ExitCodes.INVALID_COLOR

    def test_unknown_preset_reports_not_found(self):
        result = invoke("show", "no_such_preset_xyz")
        assert result.exit_code == ExitCodes.RESOURCE_NOT_FOUND

    def test_width_and_height(self):
        result = invoke("show", "viridis", "--width", "40", "--height", "3")
        assert result.exit_code == ExitCodes.SUCCESS
        assert len(result.output.strip().split("\n")) == 3

    def test_reverse_is_accepted(self):
        assert invoke("show", "viridis", "--reverse").exit_code == ExitCodes.SUCCESS

    def test_hex_listing(self):
        result = invoke("show", "viridis", "--steps", "4", "--hex", "--width", "20")
        assert result.exit_code == ExitCodes.SUCCESS
        assert len(re.findall(r"#[0-9a-f]{6}", result.output)) == 4

    def test_hex_listing_respects_reverse(self):
        forward = invoke("show", "viridis", "--steps", "3", "--hex").output
        reversed_out = invoke("show", "viridis", "--steps", "3", "--hex", "-r").output
        assert re.findall(r"#[0-9a-f]{6}", forward) == list(
            reversed(re.findall(r"#[0-9a-f]{6}", reversed_out))
        )

    def test_cut_changes_the_endpoints(self):
        full = invoke("show", "viridis", "--steps", "2", "--hex").output
        cut = invoke("show", "viridis", "--steps", "2", "--hex", "--cut", "0.4,0.6").output
        assert re.findall(r"#[0-9a-f]{6}", full) != re.findall(r"#[0-9a-f]{6}", cut)

    def test_malformed_cut_is_a_usage_error(self):
        assert invoke("show", "viridis", "--cut", "nonsense").exit_code != 0

    def test_out_of_range_cut_is_rejected(self):
        result = invoke("show", "viridis", "--cut", "0,2")
        assert result.exit_code == ExitCodes.USAGE_ERROR


class TestShowImageOutput:
    def test_writes_a_png(self, tmp_path):
        target = tmp_path / "out.png"
        result = invoke("show", "viridis", "--output", str(target))
        assert result.exit_code == ExitCodes.SUCCESS
        assert target.read_bytes().startswith(b"\x89PNG")

    def test_writes_an_svg(self, tmp_path):
        target = tmp_path / "out.svg"
        assert invoke("show", "magma", "-o", str(target)).exit_code == ExitCodes.SUCCESS
        assert target.read_text().startswith("<?xml")

    def test_unsupported_extension_is_an_export_error(self, tmp_path):
        result = invoke("show", "viridis", "-o", str(tmp_path / "out.gif"))
        assert result.exit_code == ExitCodes.EXPORT_ERROR
        assert "Unsupported image format" in result.output

    def test_reverse_changes_the_image(self, tmp_path):
        forward, backward = tmp_path / "f.png", tmp_path / "b.png"
        invoke("show", "viridis", "-o", str(forward), "--width", "32")
        invoke("show", "viridis", "-o", str(backward), "--width", "32", "-r")
        assert forward.read_bytes() != backward.read_bytes()


class TestCreateCommand:
    def test_basic_export(self):
        result = invoke("create", "--colors", "red,blue", "-f", "hex", "-n", "3")
        assert result.exit_code == ExitCodes.SUCCESS
        assert result.output.strip().count("#") == 3

    def test_multiple_formats(self):
        result = invoke("create", "--colors", "red,blue", "-f", "hex", "-f", "rgba", "-n", "3")
        assert result.exit_code == ExitCodes.SUCCESS
        assert "#" in result.output and "rgba(" in result.output

    def test_comma_separated_formats(self):
        result = invoke("create", "viridis", "-f", "hex,rgba", "-n", "3")
        assert result.exit_code == ExitCodes.SUCCESS

    def test_no_format_and_no_save_is_a_usage_error(self):
        result = invoke("create", "--colors", "red,blue")
        assert result.exit_code == ExitCodes.USAGE_ERROR
        assert "Nothing to do" in result.output

    def test_unknown_format(self):
        result = invoke("create", "--colors", "red,blue", "-f", "unknown_format")
        assert result.exit_code == ExitCodes.EXPORT_ERROR
        assert "not found" in result.output.lower()

    def test_writes_to_a_file(self, tmp_path):
        target = tmp_path / "out.txt"
        result = invoke("create", "viridis", "-f", "hex", "-n", "3", "-o", str(target))
        assert result.exit_code == ExitCodes.SUCCESS
        assert target.read_text().count("#") == 3

    def test_output_pattern_expands_placeholders(self, tmp_path):
        pattern = str(tmp_path / "{name}_{format}.{ext}")
        result = invoke("create", "viridis", "-f", "hex,json", "-n", "3", "-o", pattern)
        assert result.exit_code == ExitCodes.SUCCESS
        assert (tmp_path / "viridis_hex.txt").exists()
        assert (tmp_path / "viridis_json.json").exists()

    def test_output_creates_missing_directories(self, tmp_path):
        target = tmp_path / "deep" / "nested" / "out.txt"
        invoke("create", "viridis", "-f", "hex", "-n", "3", "-o", str(target))
        assert target.exists()

    def test_reverse_reverses_the_exported_colors(self):
        forward = invoke("create", "viridis", "-f", "hex", "-n", "5").output.split()
        backward = invoke("create", "viridis", "-f", "hex", "-n", "5", "-r").output.split()
        assert forward == list(reversed(backward))

    @pytest.mark.parametrize(
        "scale_args",
        [
            ["--scale", "linear"],
            ["--scale", "sqrt"],
            ["--scale", "power", "--scale-exponent", "2"],
            ["--scale", "log", "--domain", "1,100"],
            ["--scale", "symlog", "--scale-symlog-linthresh", "1", "--domain", "-10,10"],
        ],
        ids=["linear", "sqrt", "power", "log", "symlog"],
    )
    def test_every_scale_type_works(self, scale_args):
        result = invoke("create", "viridis", "-f", "gdal", "-n", "3", *scale_args)
        assert result.exit_code == ExitCodes.SUCCESS

    def test_power_without_exponent_is_a_usage_error(self):
        result = invoke("create", "viridis", "-f", "hex", "-n", "3", "--scale", "power")
        assert result.exit_code == ExitCodes.USAGE_ERROR
        assert "--scale-exponent is required" in result.output

    def test_symlog_without_linthresh_is_a_usage_error(self):
        result = invoke("create", "viridis", "-f", "hex", "-n", "3", "--scale", "symlog")
        assert result.exit_code == ExitCodes.USAGE_ERROR
        assert "--scale-symlog-linthresh is required" in result.output

    def test_unknown_scale_is_a_usage_error(self):
        result = invoke("create", "viridis", "-f", "hex", "--scale", "bogus")
        assert result.exit_code == ExitCodes.USAGE_ERROR

    def test_invalid_log_domain_is_a_usage_error(self):
        result = invoke("create", "viridis", "-f", "gdal", "--scale", "log", "--domain", "0,10")
        assert result.exit_code == ExitCodes.USAGE_ERROR


class TestCreateOptions:
    def test_namespaced_option_is_applied(self):
        result = invoke("create", "viridis", "-f", "hex", "-n", "3", "-O", "hex:output_format=csv")
        assert result.exit_code == ExitCodes.SUCCESS
        assert ", " in result.output

    def test_global_option_reaches_the_exporter(self):
        result = invoke("create", "viridis", "-f", "hex", "-O", "num_colors=4")
        assert result.exit_code == ExitCodes.SUCCESS
        assert result.output.strip().count("#") == 4

    def test_string_options_are_coerced_for_boolean_flags(self):
        """`-O gdal:nodata=false` must be falsy; a naive bool() would make it true."""
        result = invoke("create", "viridis", "-f", "gdal", "-n", "3", "-O", "gdal:nodata=false")
        assert result.exit_code == ExitCodes.SUCCESS
        assert "nv " not in result.output

    def test_malformed_option_is_a_usage_error(self):
        result = invoke("create", "viridis", "-f", "hex", "-O", "no_equals_sign")
        assert result.exit_code == ExitCodes.USAGE_ERROR
        assert "key=value" in result.output

    def test_invalid_option_value_is_an_export_error(self):
        result = invoke("create", "viridis", "-f", "hex", "-O", "hex:output_format=bogus")
        assert result.exit_code == ExitCodes.EXPORT_ERROR
        assert "must be one of" in result.output

    def test_unknown_option_warns_but_still_exports(self):
        result = invoke("create", "viridis", "-f", "hex", "-n", "3", "-O", "hex:bogus=1")
        assert result.exit_code == ExitCodes.SUCCESS
        assert "does not accept" in result.output
        assert "#" in result.output

    def test_unknown_global_option_warns(self):
        result = invoke("create", "viridis", "-f", "hex", "-n", "3", "-O", "bogus=1")
        assert result.exit_code == ExitCodes.SUCCESS
        assert "bogus" in result.output
        assert "does not accept" in result.output


class TestSaveAndReload:
    def test_save_writes_a_colormap_file(self, tmp_path):
        target = tmp_path / "map.json"
        result = invoke("create", "viridis", "--save", str(target))
        assert result.exit_code == ExitCodes.SUCCESS
        assert json.loads(target.read_text())["palettize"] == 1

    def test_saved_file_can_be_used_as_a_colormap_source(self, tmp_path):
        target = tmp_path / "map.json"
        invoke("create", "viridis", "--save", str(target), "--reverse")
        from_file = invoke("create", str(target), "-f", "hex", "-n", "5").output
        direct = invoke("create", "viridis", "-r", "-f", "hex", "-n", "5").output
        assert from_file == direct

    def test_saved_transforms_survive_the_round_trip(self, tmp_path):
        target = tmp_path / "map.json"
        invoke("create", "viridis", "--save", str(target), "--cut", "0.2,0.8", "-r")
        from_file = invoke("create", str(target), "-f", "hex", "-n", "5").output
        direct = invoke(
            "create", "viridis", "--cut", "0.2,0.8", "-r", "-f", "hex", "-n", "5"
        ).output
        assert from_file == direct

    def test_save_and_export_in_one_call(self, tmp_path):
        target = tmp_path / "map.json"
        result = invoke("create", "viridis", "--save", str(target), "-f", "hex", "-n", "3")
        assert result.exit_code == ExitCodes.SUCCESS
        assert target.exists() and "#" in result.output

    def test_show_accepts_a_saved_file(self, tmp_path):
        target = tmp_path / "map.json"
        invoke("create", "viridis", "--save", str(target))
        assert invoke("show", str(target), "--width", "20").exit_code == ExitCodes.SUCCESS

    def test_corrupt_file_reports_not_found(self, tmp_path):
        target = tmp_path / "bad.json"
        target.write_text("{not json")
        result = invoke("show", str(target))
        assert result.exit_code == ExitCodes.RESOURCE_NOT_FOUND

    def test_missing_file_reports_not_found(self, tmp_path):
        result = invoke("show", str(tmp_path / "nope.json"))
        assert result.exit_code == ExitCodes.RESOURCE_NOT_FOUND


class TestAnalyzeCommand:
    def test_reports_on_a_preset(self):
        result = invoke("analyze", "viridis")
        assert result.exit_code == ExitCodes.SUCCESS
        assert "lightness" in result.output and "uniformity" in result.output

    def test_shows_cvd_rows(self):
        output = invoke("analyze", "viridis").output
        assert all(key in output for key in ("protan", "deutan", "tritan"))

    def test_clean_colormap_reports_no_problems(self):
        assert "No problems detected" in invoke("analyze", "cividis").output

    def test_problem_colormap_reports_warnings(self):
        assert "warn" in invoke("analyze", "gist_rainbow").output

    def test_json_output_is_machine_readable(self):
        result = invoke("analyze", "viridis", "--json", "--samples", "8")
        assert result.exit_code == ExitCodes.SUCCESS
        payload = json.loads(result.output)
        assert payload["name"] == "viridis"
        assert payload["samples"] == 8
        assert set(payload["cvd"]) == {"protan", "deutan", "tritan"}

    def test_json_output_has_no_ansi_escapes(self):
        result = invoke("analyze", "viridis", "--json")
        assert not ANSI_ESCAPE_RE.search(result.output)

    def test_strict_fails_on_a_problem_colormap(self):
        result = invoke("analyze", "gist_rainbow", "--strict")
        assert result.exit_code == ExitCodes.EXPORT_ERROR

    def test_strict_passes_a_clean_colormap(self):
        assert invoke("analyze", "cividis", "--strict").exit_code == ExitCodes.SUCCESS

    def test_analyzes_custom_colors(self):
        result = invoke("analyze", "--colors", "black,white", "--json")
        assert result.exit_code == ExitCodes.SUCCESS
        assert json.loads(result.output)["lightness"]["shape"] == "sequential"

    def test_reverse_flips_the_reported_direction(self):
        forward = json.loads(invoke("analyze", "viridis", "--json").output)
        backward = json.loads(invoke("analyze", "viridis", "-r", "--json").output)
        assert forward["lightness"]["direction"] == "ascending"
        assert backward["lightness"]["direction"] == "descending"

    def test_too_few_samples_is_rejected(self):
        assert invoke("analyze", "viridis", "--samples", "1").exit_code != 0


class TestFormatsCommand:
    def test_lists_every_format(self):
        result = invoke("formats")
        assert result.exit_code == ExitCodes.SUCCESS
        for identifier in ("gdal", "qgis", "hex", "css", "svg"):
            assert identifier in result.output

    def test_details_a_single_format(self):
        result = invoke("formats", "gdal")
        assert result.exit_code == ExitCodes.SUCCESS
        assert "num_colors" in result.output
        assert "nodata" in result.output

    def test_shows_defaults_and_types(self):
        output = invoke("formats", "hex").output
        assert "lines" in output and "int" in output

    def test_notes_whether_scaling_applies(self):
        assert "--domain" in invoke("formats", "gdal").output
        assert "do not apply" in invoke("formats", "css").output

    def test_unknown_format_reports_not_found(self):
        result = invoke("formats", "no_such_format_xyz")
        assert result.exit_code == ExitCodes.RESOURCE_NOT_FOUND

    def test_list_exporters_is_an_alias(self):
        result = invoke("list", "exporters")
        assert result.exit_code == ExitCodes.SUCCESS
        assert "gdal" in result.output


class TestListPresets:
    def test_lists_presets(self):
        result = invoke("list", "presets")
        assert result.exit_code == ExitCodes.SUCCESS
        assert "Presets" in result.output

    def test_search_filters_by_name(self):
        result = invoke("list", "presets", "--search", "viridis")
        assert result.exit_code == ExitCodes.SUCCESS
        assert "viridis" in result.output

    def test_category_filter(self):
        result = invoke("list", "presets", "--category", "diverging", "--limit", "5")
        assert result.exit_code == ExitCodes.SUCCESS
        assert "diverging" in result.output

    def test_namespace_filter(self):
        result = invoke("list", "presets", "--namespace", "colorbrewer", "--limit", "5")
        assert result.exit_code == ExitCodes.SUCCESS
        assert "colorbrewer" in result.output

    def test_no_matches_says_so(self):
        result = invoke("list", "presets", "--search", "definitely_not_a_preset_xyz")
        assert result.exit_code == ExitCodes.SUCCESS
        assert "No presets matched" in result.output

    def test_unknown_category_suggests_the_valid_ones(self):
        result = invoke("list", "presets", "--category", "bogus")
        assert "Known categories" in result.output

    def test_limit_is_reported(self):
        result = invoke("list", "presets", "--limit", "3")
        assert "Showing 3 of" in result.output

    def test_swatches_render(self):
        result = invoke("list", "presets", "--search", "viridis", "--swatch", "--limit", "3")
        assert result.exit_code == ExitCodes.SUCCESS

    def test_categories_subcommand(self):
        result = invoke("list", "categories")
        assert result.exit_code == ExitCodes.SUCCESS
        assert "sequential" in result.output


class TestPresetInfoCommand:
    def test_describes_a_preset(self):
        result = invoke("presets", "bids:viridis")
        assert result.exit_code == ExitCodes.SUCCESS
        assert "sequential" in result.output
        assert "bids" in result.output

    def test_unknown_preset_reports_not_found(self):
        result = invoke("presets", "no_such_preset_xyz")
        assert result.exit_code == ExitCodes.RESOURCE_NOT_FOUND
        # The hint may be soft-wrapped by the console, so match a short fragment.
        assert "list presets" in result.output


class TestStdoutRedirection:
    """The exporter payload written to stdout must be byte-for-byte the
    exporter's string: no Rich markup interpretation of brackets, no ANSI
    codes, so `palettize create ... > out.json` yields a valid file."""

    def test_mapgl_stdout_is_valid_json(self):
        result = invoke(
            "create", "viridis", "--format", "mapgl", "--steps", "5", "--domain", "0,948"
        )
        assert result.exit_code == ExitCodes.SUCCESS
        parsed = json.loads(result.output)
        assert parsed[0] == "interpolate"
        assert parsed[1] == ["linear"]

    def test_json_format_stdout_is_valid_json(self):
        result = invoke("create", "--colors", "red,blue", "--format", "json", "--steps", "3")
        assert result.exit_code == ExitCodes.SUCCESS
        json.loads(result.output)

    def test_observable_stdout_is_valid_json(self):
        result = invoke("create", "viridis", "--format", "observable", "--steps", "5")
        assert result.exit_code == ExitCodes.SUCCESS
        json.loads(result.output)

    @pytest.mark.parametrize(
        "fmt", ["hex", "rgba", "hsl", "css", "svg", "json", "mapgl", "gimp", "gdal"]
    )
    def test_no_ansi_escapes_in_exporter_output(self, fmt):
        result = invoke("create", "viridis", "--format", fmt, "--steps", "3")
        assert result.exit_code == ExitCodes.SUCCESS
        assert not ANSI_ESCAPE_RE.search(result.output)

    def test_bracket_payloads_survive_intact(self):
        result = invoke("create", "viridis", "--format", "mapgl", "--steps", "3")
        assert '"interpolate"' in result.output and '"linear"' in result.output

    def test_stdout_matches_the_file_written_with_output(self, tmp_path):
        target = tmp_path / "out.txt"
        piped = invoke("create", "viridis", "-f", "hex", "-n", "5").output
        invoke("create", "viridis", "-f", "hex", "-n", "5", "-o", str(target))
        assert piped.strip() == target.read_text().strip()


class TestVerbosity:
    def test_default_output_is_results_only(self):
        result = invoke("create", "--colors", "red,blue", "-f", "hex", "-n", "3")
        assert result.exit_code == ExitCodes.SUCCESS
        assert "Exporting to" not in result.output
        assert "Export complete" not in result.output

    @pytest.mark.parametrize(
        "args",
        [
            ("create", "-v", "--colors", "red,blue", "-f", "hex", "-n", "3"),
            ("-v", "create", "--colors", "red,blue", "-f", "hex", "-n", "3"),
        ],
        ids=["after-subcommand", "before-subcommand"],
    )
    def test_verbose_works_on_either_side_of_the_subcommand(self, args):
        result = invoke(*args)
        assert result.exit_code == ExitCodes.SUCCESS
        assert "Exporting to" in result.output
        assert "Export complete" in result.output

    def test_verbose_reports_written_files(self, tmp_path):
        target = tmp_path / "out.txt"
        result = invoke("create", "-v", "viridis", "-f", "hex", "-n", "3", "-o", str(target))
        assert "Wrote" in result.output

    def test_show_accepts_verbose_after_the_subcommand(self):
        result = invoke("show", "-v", "viridis", "--width", "20")
        assert result.exit_code == ExitCodes.SUCCESS
        assert "Preview of" in result.output

    def test_double_verbose_adds_a_traceback_on_failure(self):
        result = invoke("create", "-vv", "viridis", "-f", "gdal", "--domain", "5,5")
        assert result.exit_code != ExitCodes.SUCCESS
