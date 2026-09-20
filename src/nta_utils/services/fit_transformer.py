import datetime
import re
from pathlib import Path
from typing import Any

from fit_tool.fit_file import FitFile

FIT_EPOCH = datetime.datetime(1989, 12, 31, 0, 0, 0, tzinfo=datetime.timezone.utc)


def extract_date_from_filename(filename: str) -> str | None:
    """Extract 8-digit date string like '20260917' from filename (e.g. Zepp20260917061123.fit or 2026-09-17.fit)."""
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", filename)
    if match:
        return f"{match.group(1)}{match.group(2)}{match.group(3)}"
    match = re.search(r"(\d{8})", filename)
    if match:
        return match.group(1)
    return None


def extract_date_from_fit(fit: FitFile) -> str | None:
    """Extract 'YYYYMMDD' date from the first available timestamp in FIT file."""
    for r in fit.records:
        msg = getattr(r, "message", None)
        if msg and type(msg).__name__ == "ActivityMessage" and getattr(msg, "local_timestamp", None) is not None:
            dt = FIT_EPOCH + datetime.timedelta(seconds=msg.local_timestamp)
            return dt.strftime("%Y%m%d")

    for r in fit.records:
        msg = getattr(r, "message", None)
        if msg and type(msg).__name__ == "SessionMessage" and getattr(msg, "start_time", None) is not None:
            dt = datetime.datetime.fromtimestamp(msg.start_time / 1000, tz=datetime.timezone.utc)
            return dt.strftime("%Y%m%d")

    for r in fit.records:
        msg = getattr(r, "message", None)
        if msg and type(msg).__name__ == "RecordMessage" and getattr(msg, "timestamp", None) is not None:
            dt = datetime.datetime.fromtimestamp(msg.timestamp / 1000, tz=datetime.timezone.utc)
            return dt.strftime("%Y%m%d")

    return None


def generate_new_filename(filename: str, old_date_compact: str, new_date_compact: str) -> str:
    """Generate new filename by replacing date, or appending new date."""
    if old_date_compact in filename:
        return filename.replace(old_date_compact, new_date_compact)
    old_dashed = f"{old_date_compact[:4]}-{old_date_compact[4:6]}-{old_date_compact[6:8]}"
    new_dashed = f"{new_date_compact[:4]}-{new_date_compact[4:6]}-{new_date_compact[6:8]}"
    if old_dashed in filename:
        return filename.replace(old_dashed, new_dashed)
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    return f"{stem}_{new_date_compact}{suffix}"


def change_fit_date(
    input_path: str | Path,
    output_path: str | Path,
    new_date_str: str,
    filename: str | None = None,
) -> dict[str, Any]:
    """
    Replace the date in a FIT file with new_date_str (YYYY-MM-DD or YYYYMMDD).
    Returns dict with old_date (YYYY-MM-DD), new_date (YYYY-MM-DD), and new_filename.
    """
    new_clean = new_date_str.replace("-", "").strip()
    if len(new_clean) < 8 or not new_clean[:8].isdigit():
        raise ValueError(f"Invalid date format: {new_date_str}")

    new_date_compact = new_clean[:8]
    new_date = datetime.date(
        int(new_date_compact[:4]),
        int(new_date_compact[4:6]),
        int(new_date_compact[6:8]),
    )

    fit = FitFile.from_file(str(input_path))

    orig_filename = filename or Path(input_path).name
    old_date_compact = extract_date_from_filename(orig_filename)
    if not old_date_compact:
        old_date_compact = extract_date_from_fit(fit)

    if not old_date_compact:
        raise ValueError("Could not determine existing date from FIT file or filename.")

    old_date = datetime.date(
        int(old_date_compact[:4]),
        int(old_date_compact[4:6]),
        int(old_date_compact[6:8]),
    )

    delta_days = (new_date - old_date).days
    delta_seconds = delta_days * 86400
    delta_ms = delta_seconds * 1000

    for record in fit.records:
        msg = getattr(record, "message", None)
        if not msg or not hasattr(msg, "fields"):
            continue
        for field in msg.fields:
            if field.type_name == "date_time":
                val = field.get_value()
                if val is not None:
                    if isinstance(val, list):
                        field.set_values([v + delta_ms for v in val if v is not None])
                    else:
                        field.set_value(0, val + delta_ms)
            elif field.type_name == "local_date_time":
                val = field.get_value()
                if val is not None:
                    if isinstance(val, list):
                        field.set_values([v + delta_seconds for v in val if v is not None])
                    else:
                        field.set_value(0, val + delta_seconds)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fit.to_file(str(output_path))

    new_filename = generate_new_filename(orig_filename, old_date_compact, new_date_compact)

    return {
        "old_date": f"{old_date_compact[:4]}-{old_date_compact[4:6]}-{old_date_compact[6:8]}",
        "new_date": f"{new_date_compact[:4]}-{new_date_compact[4:6]}-{new_date_compact[6:8]}",
        "new_filename": new_filename,
    }
