"""Declarative option schemas for exporters.

Exporter options arrive from two very different places: Python callers pass
native values, while the CLI's ``-O key=value`` flag can only produce strings.
Rather than have every exporter hand-roll ``isinstance`` checks and string
coercion, each exporter declares its options once as a tuple of :class:`Opt`.
That single declaration drives coercion, validation, and the option tables
shown by ``palettize formats <id>``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from palettize.exceptions import ExporterOptionError

_TRUE_STRINGS = frozenset({"true", "1", "yes", "y", "on"})
_FALSE_STRINGS = frozenset({"false", "0", "no", "n", "off"})

#: Options the CLI injects into every exporter. They are always accepted, so a
#: user typo in ``-O`` can still be reported without false positives.
AMBIENT_OPTIONS = frozenset({"num_colors", "precision", "name", "scale_type", "verbose"})


@dataclass(frozen=True)
class Opt:
    """One declared exporter option.

    Args:
        name: The option key, as used in ``-O name=value``.
        type: ``bool``, ``int``, ``float``, ``str``, or ``list`` (comma-separated).
        default: Value used when the option is absent. ``None`` means "unset".
        help: One-line description shown in ``palettize formats <id>``.
        choices: When non-empty, the value must be one of these.
        minimum: Inclusive lower bound for numeric options.
        maximum: Inclusive upper bound for numeric options.
        parser: Escape hatch for option shapes the standard types can't express.
    """

    name: str
    type: type = str
    default: Any = None
    help: str = ""
    choices: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    parser: Callable[[Any], Any] | None = field(default=None, repr=False, compare=False)

    @property
    def type_label(self) -> str:
        """Human-readable type, e.g. ``"int"`` or ``"one of: a, b"``."""
        if self.choices:
            return "one of: " + ", ".join(self.choices)
        if self.parser is not None:
            return "custom"
        return {bool: "bool", int: "int", float: "float", list: "list"}.get(self.type, "str")

    @property
    def default_label(self) -> str:
        """Human-readable default, e.g. ``"256"`` or ``"(unset)"``."""
        if self.default is None:
            return "(unset)"
        if isinstance(self.default, bool):
            return "true" if self.default else "false"
        if isinstance(self.default, (list, tuple)):
            return ", ".join(str(v) for v in self.default)
        return str(self.default)

    def coerce(self, value: Any) -> Any:
        """Convert ``value`` to this option's type and validate it.

        Raises:
            ExporterOptionError: If the value cannot be converted or is out of range.
        """
        if value is None:
            return None
        if self.parser is not None:
            try:
                return self.parser(value)
            except ExporterOptionError:
                raise
            except (TypeError, ValueError) as e:
                raise ExporterOptionError(f"Option '{self.name}': {e}") from e

        coerced = self._convert(value)
        self._validate(coerced)
        return coerced

    def _convert(self, value: Any) -> Any:
        if self.type is bool:
            if isinstance(value, bool):
                return value
            text = str(value).strip().lower()
            if text in _TRUE_STRINGS:
                return True
            if text in _FALSE_STRINGS:
                return False
            raise ExporterOptionError(
                f"Option '{self.name}' expects a boolean (true/false, yes/no, 1/0). Got: {value!r}"
            )

        if self.type is int:
            if isinstance(value, bool):
                raise ExporterOptionError(
                    f"Option '{self.name}' expects an integer. Got a boolean."
                )
            try:
                # Accept "5" and 5.0, but reject "5.5" and 5.5 as lossy.
                number = float(value)
            except (TypeError, ValueError):
                raise ExporterOptionError(
                    f"Option '{self.name}' expects an integer. Got: {value!r}"
                ) from None
            if number != int(number):
                raise ExporterOptionError(
                    f"Option '{self.name}' expects a whole number. Got: {value!r}"
                )
            return int(number)

        if self.type is float:
            try:
                return float(value)
            except (TypeError, ValueError):
                raise ExporterOptionError(
                    f"Option '{self.name}' expects a number. Got: {value!r}"
                ) from None

        if self.type is list:
            if isinstance(value, (list, tuple)):
                return [str(v) for v in value]
            return [part.strip() for part in str(value).split(",") if part.strip()]

        return str(value)

    def _validate(self, value: Any) -> None:
        if self.choices and value not in self.choices:
            raise ExporterOptionError(
                f"Option '{self.name}' must be one of: {', '.join(self.choices)}. Got: {value!r}"
            )
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if self.minimum is not None and value < self.minimum:
                raise ExporterOptionError(
                    f"Option '{self.name}' must be >= {self.minimum}. Got: {value}"
                )
            if self.maximum is not None and value > self.maximum:
                raise ExporterOptionError(
                    f"Option '{self.name}' must be <= {self.maximum}. Got: {value}"
                )


class OptionSpec:
    """An ordered, validated collection of :class:`Opt` declarations."""

    def __init__(self, *opts: Opt) -> None:
        self._opts: tuple[Opt, ...] = opts
        self._by_name: dict[str, Opt] = {opt.name: opt for opt in opts}

    def __iter__(self) -> Iterator[Opt]:
        return iter(self._opts)

    def __len__(self) -> int:
        return len(self._opts)

    def __contains__(self, name: object) -> bool:
        return name in self._by_name

    def resolve(self, options: Mapping[str, Any] | None) -> dict[str, Any]:
        """Return every declared option, coerced, with defaults filled in.

        Undeclared keys are ignored so that CLI-injected ambient options don't
        break exporters that have no use for them. Use :meth:`unknown` to report
        keys the caller explicitly supplied that nothing will read.
        """
        supplied = options or {}
        resolved: dict[str, Any] = {}
        for opt in self._opts:
            if opt.name in supplied and supplied[opt.name] is not None:
                resolved[opt.name] = opt.coerce(supplied[opt.name])
            else:
                resolved[opt.name] = opt.default
        return resolved

    def unknown(self, names: Iterable[str] | None) -> list[str]:
        """Return the given option names that are neither declared nor ambient."""
        if not names:
            return []
        return sorted(
            name for name in names if name not in self._by_name and name not in AMBIENT_OPTIONS
        )
