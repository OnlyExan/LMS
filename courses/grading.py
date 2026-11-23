"""Letter grades: a scale is a list of [letter, min %], highest first, ending at 0."""
from decimal import ROUND_HALF_UP, Decimal

DEFAULT_SCALE = [["A", 90], ["B", 80], ["C", 70], ["D", 60], ["F", 0]]
PLUS_MINUS_SCALE = [["A", 93], ["A-", 90], ["B+", 87], ["B", 83], ["B-", 80], ["C+", 77],
                    ["C", 73], ["C-", 70], ["D+", 67], ["D", 63], ["D-", 60], ["F", 0]]


def letter_for(scale, percent):
    """Letter for a % (None -> None). Uses the % rounded to 1 decimal, same as what's shown."""
    if percent is None:
        return None
    pct = Decimal(str(percent)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    for letter, minimum in scale:
        if pct >= Decimal(str(minimum)):
            return letter
    return scale[-1][0]


def fmt_min(n):
    """90 -> '90', 87.5 -> '87.5' (for forms and the scale table)."""
    return f"{Decimal(str(n)).normalize():f}"
