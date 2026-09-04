import logging
import re
from dataclasses import dataclass

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from nta_utils.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)


@dataclass
class ParsedSchedule:
    month: str
    days_off: list[int]
    work_days: list[int]


class ParsedScheduleResponse(BaseModel):
    month: str = Field(
        description="Month and year of the schedule in YYYY-MM format (e.g., '2026-08')."
    )
    days_off: list[int] = Field(
        description=(
            "List of day numbers (1-31) that are days off (folgas). "
            "These are typically visually highlighted, such as with a blue or cyan circle, badge, or background."
        )
    )
    work_days: list[int] = Field(
        description=(
            "List of day numbers (1-31) that are work days (dias de trabalho / plantões). "
            "These are the days that are NOT marked as days off."
        )
    )


SCHEDULE_PROMPT = """Analyze this screenshot of a work schedule calendar app (escala de trabalho).

CRITICAL INSTRUCTIONS:

1. TARGET FULL MONTH SELECTION:
   - The screenshot shows a scrolling calendar view. Often, the top of the image shows the trailing days of the PREVIOUS month, and the bottom shows the leading days of the NEXT month.
   - You MUST IGNORE any trailing days of previous months at the very top and any leading days of next months at the bottom.
   - Focus EXCLUSIVELY on the single FULL MONTH that is displayed completely in the middle/main section with its month name header (e.g., 'Julho 2026', 'Agosto 2026', 'Setembro 2026') and all its days from 1 to the end of that month (28, 29, 30, or 31).
   - Return the target month in 'YYYY-MM' format (e.g., '2026-07', '2026-08', '2026-09').

2. CLASSIFICATION OF DAYS FOR THE FULL MONTH:
   Every day from 1 to the last day of the full month must be classified into either days off or work days:

   - DAYS OFF (folgas):
     * Dates enclosed in a GREEN or CYAN circle (teal / light green).
     * Dates enclosed in a BLUE or PURPLE circle (light blue / lavender).
     Both green/cyan and blue/purple circles represent days off (folgas).

   - WORK DAYS (dias de trabalho):
     * Dates enclosed in an ORANGE or PEACH circle.
     * Dates with NO circle (plain numbers with white/empty background).
     Both orange circles and plain numbers represent work days.

3. VALIDATION RULES:
   - Only include day numbers (1-31) that belong to the selected FULL MONTH.
   - Do NOT include any day numbers from the partial months above or below the full month section.
   - Every day in the full month must appear in exactly one list: either 'days_off' or 'work_days'.
   - Return strictly structured JSON matching the schema.
"""


def _get_client(api_key: str | None = None) -> genai.Client:
    key = api_key or GEMINI_API_KEY
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Please set GEMINI_API_KEY in your environment or .env file."
        )
    return genai.Client(api_key=key)


def parse_schedule_image(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    api_key: str | None = None,
    model: str | None = None,
) -> ParsedSchedule:
    client = _get_client(api_key)
    target_model = model or GEMINI_MODEL

    logger.info("Analyzing schedule image with Gemini (%s)...", target_model)

    max_retries = 3
    last_error: Exception | None = None
    response = None

    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=target_model,
                contents=[
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type=mime_type,
                    ),
                    SCHEDULE_PROMPT,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ParsedScheduleResponse,
                    temperature=0.1,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )
            break
        except Exception as e:
            last_error = e
            status_code = getattr(e, "code", getattr(e, "status_code", None))
            if status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                wait_secs = attempt * 3
                logger.warning(
                    "Gemini API returned status %s on attempt %d/%d. Retrying in %ds...",
                    status_code,
                    attempt,
                    max_retries,
                    wait_secs,
                )
                import time
                time.sleep(wait_secs)
            else:
                raise

    if response is None:
        if last_error:
            raise last_error
        raise ValueError("No response received from Gemini API")

    if isinstance(response.parsed, ParsedScheduleResponse):
        parsed = response.parsed
    elif response.text:
        parsed = ParsedScheduleResponse.model_validate_json(response.text)
    else:
        raise ValueError("Empty or invalid response received from Gemini")

    # Normalize month format to YYYY-MM
    month = parsed.month.strip()
    if not re.match(r"^\d{4}-\d{2}$", month):
        logger.warning("Unexpected month format received: '%s'", month)

    days_off = sorted({d for d in parsed.days_off if 1 <= d <= 31})
    work_days = sorted({d for d in parsed.work_days if 1 <= d <= 31 and d not in days_off})

    logger.info(
        "Parsed schedule for %s: %d days off, %d work days",
        month,
        len(days_off),
        len(work_days),
    )

    return ParsedSchedule(
        month=month,
        days_off=days_off,
        work_days=work_days,
    )
