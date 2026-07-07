import calendar
import io
import logging
import math
import re
from dataclasses import dataclass
from datetime import date as dt_date
from datetime import timedelta

import pytesseract
from PIL import Image, ImageEnhance

logger = logging.getLogger(__name__)

MONTH_NAMES_PT = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
    "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}

DAY_NAMES_PT = ["dom", "seg", "ter", "qua", "qui", "sex", "sab"]


@dataclass
class ParsedSchedule:
    month: str
    days_off: list[int]
    work_days: list[int]


def _enhance(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    max_dim = 1500
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    return img


def _ocr(img: Image.Image) -> list[dict]:
    data = pytesseract.image_to_data(img, lang="por", config="--psm 6", output_type=pytesseract.Output.DICT)
    results = []
    for i, text in enumerate(data["text"]):
        text = text.strip()
        if text:
            results.append({
                "text": text,
                "x": data["left"][i],
                "y": data["top"][i],
                "w": data["width"][i],
                "h": data["height"][i],
            })

    if not results:
        data = pytesseract.image_to_data(img, lang="por", config="--psm 3", output_type=pytesseract.Output.DICT)
        for i, text in enumerate(data["text"]):
            text = text.strip()
            if text:
                results.append({
                    "text": text,
                    "x": data["left"][i],
                    "y": data["top"][i],
                    "w": data["width"][i],
                    "h": data["height"][i],
                })

    return results


def _make_grid(year: int, month: int) -> list[list[int]]:
    cal = calendar.Calendar(calendar.SUNDAY)
    return cal.monthdayscalendar(year, month)


def _find_all_month_items(ocr_items: list[dict]) -> list[dict]:
    months = []
    for item in ocr_items:
        text_lower = item["text"].lower()
        for name, num in MONTH_NAMES_PT.items():
            if name in text_lower:
                year_item = None
                for other in ocr_items:
                    if re.match(r"^\d{4}$", other["text"]) and abs(other["y"] - item["y"]) < 30:
                        year_item = other
                        break
                if year_item:
                    months.append({
                        "month": f"{year_item['text']}-{num:02d}",
                        "y": item["y"],
                    })
    return months


def _find_all_header_rows(ocr_items: list[dict]) -> list[list[dict]]:
    day_items = []
    for item in ocr_items:
        text = item["text"].lower().strip().rstrip(".")
        if text in DAY_NAMES_PT:
            day_items.append(item)

    day_items.sort(key=lambda h: h["y"])

    rows = []
    current_row = []
    current_y = None

    for item in day_items:
        if current_y is None or abs(item["y"] - current_y) < 25:
            current_row.append(item)
            current_y = item["y"] if current_y is None else current_y
        else:
            if len(current_row) >= 5:
                current_row.sort(key=lambda h: h["x"])
                rows.append(current_row)
            current_row = [item]
            current_y = item["y"]

    if len(current_row) >= 5:
        current_row.sort(key=lambda h: h["x"])
        rows.append(current_row)

    return rows


def _find_best_month_and_headers(ocr_items: list[dict]) -> tuple[str, list[dict]]:
    months = _find_all_month_items(ocr_items)
    header_rows = _find_all_header_rows(ocr_items)

    if not header_rows:
        fallback_month = None
        for m in months:
            fallback_month = m["month"]
            break
        if not fallback_month:
            today = dt_date.today()
            if today.day >= 20:
                today += timedelta(days=12)
            fallback_month = today.strftime("%Y-%m")
        return fallback_month, []

    if not months:
        today = dt_date.today()
        if today.day >= 20:
            today += timedelta(days=12)
        month = today.strftime("%Y-%m")
        best_row = header_rows[0]
        return month, best_row

    months.sort(key=lambda m: m["y"])

    for m in months:
        best_headers = None
        best_dist = 99999
        for header_row in header_rows:
            header_y = header_row[0]["y"]
            dist = header_y - m["y"]
            if dist < 10 or dist > 150:
                continue
            if dist < best_dist:
                best_dist = dist
                best_headers = header_row
        if best_headers:
            return m["month"], best_headers

    best_month = months[0]["month"]
    best_headers = header_rows[0]
    return best_month, best_headers


def _sample_circle_color(img: Image.Image, cx: int, cy: int, radius: int = 22) -> tuple[int, int, int] | None:
    samples = []

    for angle_deg in range(0, 360, 15):
        angle = math.radians(angle_deg)
        x = int(cx + radius * math.cos(angle))
        y = int(cy + radius * math.sin(angle))
        if 0 <= x < img.width and 0 <= y < img.height:
            samples.append(img.getpixel((x, y)))

    for angle_deg in range(7, 360, 15):
        angle = math.radians(angle_deg)
        x = int(cx + radius * 0.5 * math.cos(angle))
        y = int(cy + radius * 0.5 * math.sin(angle))
        if 0 <= x < img.width and 0 <= y < img.height:
            samples.append(img.getpixel((x, y)))

    colored = []
    for r, g, b in samples:
        max_c = max(r, g, b)
        min_c = min(r, g, b)
        if max_c < 100:
            continue
        if max_c > 230 and (max_c - min_c) < 25:
            continue
        colored.append((r, g, b))

    if not colored:
        return None

    avg_r = sum(r for r, g, b in colored) // len(colored)
    avg_g = sum(g for r, g, b in colored) // len(colored)
    avg_b = sum(b for r, g, b in colored) // len(colored)

    return (avg_r, avg_g, avg_b)


def _classify_color(avg: tuple[int, int, int] | None) -> str:
    if avg is None:
        return "work"
    r, g, b = avg

    spread = max(r, g, b) - min(r, g, b)
    if spread < 30 and r > 180:
        return "work"

    if b > 200 and b > r + 15:
        return "off"
    if g > 200 and g > r + 15 and b > 180:
        return "off"

    return "work"


def parse_schedule_image(image_bytes: bytes) -> ParsedSchedule:
    original = Image.open(io.BytesIO(image_bytes))
    img = _enhance(original)

    ocr_items = _ocr(img)

    month, headers = _find_best_month_and_headers(ocr_items)

    year, mon = int(month[:4]), int(month[5:7])
    grid = _make_grid(year, mon)

    if headers:
        header_y = headers[0]["y"]

        DAY_TO_COL = {"dom": 0, "seg": 1, "ter": 2, "qua": 3, "qui": 4, "sex": 5, "sab": 6}
        col_xs = [0] * 7
        detected = {}
        for h in headers:
            text = h["text"].lower().strip().rstrip(".")
            if text in DAY_TO_COL:
                detected[DAY_TO_COL[text]] = h["x"] + h["w"] // 2

        if len(detected) == 7:
            col_xs = [detected[i] for i in range(7)]
        else:
            indices = sorted(detected.keys())
            positions = [detected[i] for i in indices]
            avg_gap = (positions[-1] - positions[0]) / (indices[-1] - indices[0]) if len(indices) >= 2 else img.width // 7
            for i in range(7):
                if i in detected:
                    col_xs[i] = detected[i]
                elif i < indices[0]:
                    col_xs[i] = int(positions[0] - avg_gap * (indices[0] - i))
                elif i > indices[-1]:
                    col_xs[i] = int(positions[-1] + avg_gap * (i - indices[-1]))
                else:
                    for j in range(len(indices) - 1):
                        if indices[j] < i < indices[j + 1]:
                            t = (i - indices[j]) / (indices[j + 1] - indices[j])
                            col_xs[i] = int(positions[j] + t * (positions[j + 1] - positions[j]))
                            break

        calendar_top = header_y + 59
        row_spacing = 70
    else:
        month_item = None
        for item in ocr_items:
            text_lower = item["text"].lower()
            for name in MONTH_NAMES_PT:
                if name in text_lower:
                    month_item = item
                    break
            if month_item:
                break

        if month_item:
            calendar_top = month_item["y"] + 100
        else:
            calendar_top = img.height // 3

        col_width = img.width // 7
        col_xs = [col_width * i + col_width // 2 for i in range(7)]
        row_spacing = 70

    days_off = []
    work_days = []

    for row_idx, row in enumerate(grid):
        for col_idx, day in enumerate(row):
            if day == 0:
                continue

            cx = col_xs[col_idx]
            cy = calendar_top + row_idx * row_spacing

            color_sample = _sample_circle_color(img, cx, cy)
            classification = _classify_color(color_sample)

            logger.debug("Day %d: pos=(%d,%d) color=%s class=%s", day, cx, cy, color_sample, classification)

            if classification == "off":
                days_off.append(day)
            else:
                work_days.append(day)

    return ParsedSchedule(
        month=month,
        days_off=sorted(set(days_off)),
        work_days=sorted(set(work_days)),
    )
