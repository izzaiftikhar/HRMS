from datetime import date, datetime

from flask import jsonify


def error(message, status=400):
    return jsonify({"error": message}), status


def parse_date(value, field_name="date"):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"Invalid {field_name}. Use YYYY-MM-DD."
            )


def parse_time(value, field_name="time"):
    if not value:
        return None

    try:
        return datetime.strptime(value, "%H:%M:%S").time()
    except (TypeError, ValueError):
        try:
            return datetime.strptime(value, "%H:%M").time()
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid {field_name}. Use HH:MM or HH:MM:SS."
            ) from exc
            