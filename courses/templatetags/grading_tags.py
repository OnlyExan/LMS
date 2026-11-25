from django import template

from courses.grading import letter_tone as _letter_tone

register = template.Library()


@register.filter
def letter_tone(letter):
    """{{ letter|letter_tone }} -> tone-a / tone-b / tone-c / tone-f / tone-x"""
    return _letter_tone(letter)


@register.filter
def letter_in(percent, course):
    """{{ pct|letter_in:course }} -> that course's letter for a %"""
    return course.letter_for(percent)
