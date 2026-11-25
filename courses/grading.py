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


def letter_tone(letter):
    """CSS tone for a letter: A green, B blue, C yellow, D/F red, anything else (Pass, P/NP) gray.
    Goes by the first character, so A- / B+ take their letter's color."""
    first = (letter or "").strip()[:1].upper()
    return {"A": "tone-a", "B": "tone-b", "C": "tone-c", "D": "tone-f", "F": "tone-f"}.get(first, "tone-x")


def fmt_min(n):
    """90 -> '90', 87.5 -> '87.5' (for forms and the scale table)."""
    return f"{Decimal(str(n)).normalize():f}"


def course_percent(graded, weights=None):
    """Course % from graded work: [(group_id, earned, possible), ...].

    weights=None -> total points (earned / possible).
    weights={group_id: weight} -> each group's % x its weight. Groups with nothing graded
    (or weight 0) are skipped and the rest scaled to fill 100%, like Canvas. Ungrouped work
    doesn't count when weighting is on.
    """
    if weights is None:
        possible = sum((p for _, _, p in graded), Decimal(0))
        earned = sum((e for _, e, _ in graded), Decimal(0))
        return earned / possible * 100 if possible else None
    sums = {}
    for gid, e, p in graded:
        if gid in weights:
            se, sp = sums.get(gid, (Decimal(0), Decimal(0)))
            sums[gid] = (se + e, sp + p)
    used = {g: Decimal(weights[g]) for g, (_, p) in sums.items() if p and weights[g]}
    total = sum(used.values(), Decimal(0))
    if not total:
        return None
    return sum(used[g] * sums[g][0] / sums[g][1] * 100 for g in used) / total


def group_breakdown(groups, graded):
    """Per-group rows for display: [{group, earned, possible, percent}]."""
    rows = []
    for g in groups:
        mine = [(e, p) for gid, e, p in graded if gid == g.pk]
        earned = sum((e for e, _ in mine), Decimal(0))
        possible = sum((p for _, p in mine), Decimal(0))
        rows.append({"group": g, "earned": earned, "possible": possible,
                     "percent": earned / possible * 100 if possible else None})
    return rows
