from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Gets an item from a dictionary by key"""
    return dictionary.get(key)

@register.filter
def multiply(value, arg):
    """Multiply the value by the argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def get_score_color(score):
    """Return color class based on score range"""
    try:
        score = float(score)
        if score >= 4:
            return 'score-high'
        elif score >= 2.5:
            return 'score-medium'
        else:
            return 'score-low'
    except (ValueError, TypeError):
        return 'score-low'
