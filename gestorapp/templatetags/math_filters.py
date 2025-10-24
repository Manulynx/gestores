from django import template

register = template.Library()

@register.filter(name='multiply')
def multiply(value, arg):
    try:
        return float(value or 0) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter(name='divide')
def divide(value, arg):
    try:
        arg = float(arg)
        if arg == 0:
            return 0
        return float(value or 0) / arg
    except (ValueError, TypeError):
        return 0