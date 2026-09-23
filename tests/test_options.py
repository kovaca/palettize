"""Tests for the declarative exporter option schema."""

from __future__ import annotations

import pytest

from palettize.exceptions import ExporterOptionError
from palettize.exporters import get_exporter, list_available_exporters
from palettize.exporters._options import AMBIENT_OPTIONS, Opt, OptionSpec


class TestBoolCoercion:
    @pytest.mark.parametrize("value", [True, "true", "True", "1", "yes", "y", "on"])
    def test_truthy_spellings(self, value):
        assert Opt("flag", bool, False).coerce(value) is True

    @pytest.mark.parametrize("value", [False, "false", "False", "0", "no", "n", "off"])
    def test_falsy_spellings(self, value):
        assert Opt("flag", bool, True).coerce(value) is False

    def test_the_string_false_is_not_treated_as_truthy(self):
        # Plain `bool("false")` is True; this is the bug the schema exists to prevent.
        assert Opt("flag", bool, True).coerce("false") is False

    @pytest.mark.parametrize("value", ["maybe", "2", ""])
    def test_unrecognized_spellings_are_rejected(self, value):
        with pytest.raises(ExporterOptionError, match="expects a boolean"):
            Opt("flag", bool, False).coerce(value)


class TestIntCoercion:
    @pytest.mark.parametrize("value,expected", [(5, 5), ("5", 5), (5.0, 5), ("5.0", 5)])
    def test_whole_numbers_are_accepted(self, value, expected):
        assert Opt("n", int, 1).coerce(value) == expected

    @pytest.mark.parametrize("value", ["5.5", 5.5])
    def test_fractional_values_are_rejected(self, value):
        with pytest.raises(ExporterOptionError, match="whole number"):
            Opt("n", int, 1).coerce(value)

    def test_non_numeric_strings_are_rejected(self):
        with pytest.raises(ExporterOptionError, match="expects an integer"):
            Opt("n", int, 1).coerce("abc")

    def test_booleans_are_not_silently_ints(self):
        with pytest.raises(ExporterOptionError, match="Got a boolean"):
            Opt("n", int, 1).coerce(True)

    def test_minimum_is_enforced(self):
        with pytest.raises(ExporterOptionError, match=r"'n' must be >= 2"):
            Opt("n", int, 5, minimum=2).coerce(1)

    def test_maximum_is_enforced(self):
        with pytest.raises(ExporterOptionError, match=r"'n' must be <= 10"):
            Opt("n", int, 5, maximum=10).coerce(11)


class TestOtherTypes:
    def test_floats_parse_from_strings(self):
        assert Opt("x", float, 0.0).coerce("0.25") == 0.25

    def test_float_range_is_enforced(self):
        with pytest.raises(ExporterOptionError, match="must be <= 1.0"):
            Opt("x", float, 0.0, minimum=0.0, maximum=1.0).coerce(2.0)

    def test_lists_split_on_commas(self):
        assert Opt("tags", list, None).coerce("a, b ,c") == ["a", "b", "c"]

    def test_lists_pass_through_sequences(self):
        assert Opt("tags", list, None).coerce(["a", "b"]) == ["a", "b"]

    def test_choices_are_enforced(self):
        with pytest.raises(ExporterOptionError, match="must be one of: a, b"):
            Opt("mode", str, "a", choices=("a", "b")).coerce("c")

    def test_valid_choice_passes(self):
        assert Opt("mode", str, "a", choices=("a", "b")).coerce("b") == "b"

    def test_none_stays_none(self):
        assert Opt("x", int, 5).coerce(None) is None

    def test_custom_parser_is_used(self):
        opt = Opt("pair", str, None, parser=lambda v: tuple(int(p) for p in v.split(",")))
        assert opt.coerce("1,2") == (1, 2)

    def test_custom_parser_errors_are_wrapped(self):
        opt = Opt("pair", str, None, parser=lambda v: int(v))
        with pytest.raises(ExporterOptionError, match="Option 'pair'"):
            opt.coerce("nope")


class TestLabels:
    @pytest.mark.parametrize(
        "opt,expected",
        [
            (Opt("a", int, 1), "int"),
            (Opt("a", bool, True), "bool"),
            (Opt("a", float, 1.0), "float"),
            (Opt("a", list, None), "list"),
            (Opt("a", str, ""), "str"),
            (Opt("a", str, "x", choices=("x", "y")), "one of: x, y"),
            (Opt("a", str, None, parser=int), "custom"),
        ],
    )
    def test_type_labels(self, opt, expected):
        assert opt.type_label == expected

    @pytest.mark.parametrize(
        "opt,expected",
        [
            (Opt("a", int, 256), "256"),
            (Opt("a", int, None), "(unset)"),
            (Opt("a", bool, True), "true"),
            (Opt("a", bool, False), "false"),
            (Opt("a", str, (0, 0, 0, 0)), "0, 0, 0, 0"),
        ],
    )
    def test_default_labels(self, opt, expected):
        assert opt.default_label == expected


class TestOptionSpec:
    @pytest.fixture
    def spec(self) -> OptionSpec:
        return OptionSpec(
            Opt("count", int, 10, minimum=1),
            Opt("flag", bool, False),
            Opt("mode", str, "a", choices=("a", "b")),
        )

    def test_defaults_fill_in_absent_options(self, spec):
        assert spec.resolve(None) == {"count": 10, "flag": False, "mode": "a"}

    def test_supplied_values_are_coerced(self, spec):
        assert spec.resolve({"count": "3", "flag": "yes"}) == {
            "count": 3,
            "flag": True,
            "mode": "a",
        }

    def test_explicit_none_falls_back_to_the_default(self, spec):
        assert spec.resolve({"count": None})["count"] == 10

    def test_undeclared_keys_are_ignored_rather_than_failing(self, spec):
        assert "surprise" not in spec.resolve({"surprise": 1})

    def test_unknown_reports_undeclared_keys(self, spec):
        assert spec.unknown({"count", "surprise"}) == ["surprise"]

    def test_unknown_tolerates_cli_injected_ambient_keys(self, spec):
        assert spec.unknown(AMBIENT_OPTIONS) == []

    def test_unknown_of_nothing_is_empty(self, spec):
        assert spec.unknown(None) == [] and spec.unknown(set()) == []

    def test_membership_and_length(self, spec):
        assert len(spec) == 3
        assert "count" in spec and "nope" not in spec

    def test_iterates_in_declaration_order(self, spec):
        assert [o.name for o in spec] == ["count", "flag", "mode"]


class TestExporterSchemas:
    """Every registered exporter must have a coherent, self-describing schema."""

    @pytest.mark.parametrize("identifier", sorted(list_available_exporters()))
    def test_options_are_declared_as_a_spec(self, identifier):
        assert isinstance(get_exporter(identifier).options, OptionSpec)

    @pytest.mark.parametrize("identifier", sorted(list_available_exporters()))
    def test_every_option_is_documented(self, identifier):
        for opt in get_exporter(identifier).options:
            assert opt.help, f"{identifier}.{opt.name} has no help text"

    @pytest.mark.parametrize("identifier", sorted(list_available_exporters()))
    def test_declared_defaults_are_self_consistent(self, identifier):
        """Resolving an empty option dict must not raise, which means every
        declared default satisfies its own choices and range constraints."""
        assert get_exporter(identifier).options.resolve({}) is not None

    @pytest.mark.parametrize("identifier", sorted(list_available_exporters()))
    def test_string_options_survive_the_cli_round_trip(self, identifier):
        """The CLI can only produce strings, so every non-custom default must
        coerce back to itself when handed over as text."""
        for opt in get_exporter(identifier).options:
            if opt.default is None or opt.parser is not None or opt.type is list:
                continue
            as_text = (
                "true"
                if opt.default is True
                else ("false" if opt.default is False else str(opt.default))
            )
            assert opt.coerce(as_text) == opt.default, (
                f"{identifier}.{opt.name} does not round-trip through a string"
            )
