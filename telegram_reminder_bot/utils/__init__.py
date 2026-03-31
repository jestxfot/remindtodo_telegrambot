"""
Utility functions
"""

# NOTE: Keep this module import-light to avoid circular imports.
# Many core modules import `utils.timezone`, and `date_parser` depends on
# `storage.models`, so importing everything eagerly here can create a cycle.

__all__ = [
    "parse_datetime",
    "parse_recurrence",
    "extract_title_and_datetime",
    "format_reminder",
    "format_todo",
    "format_datetime",
    "format_interval",
]


def __getattr__(name: str):
    if name in {"parse_datetime", "parse_recurrence", "extract_title_and_datetime"}:
        from . import date_parser

        return getattr(date_parser, name)
    if name in {"format_reminder", "format_todo", "format_datetime", "format_interval"}:
        from . import formatters

        return getattr(formatters, name)
    raise AttributeError(name)
