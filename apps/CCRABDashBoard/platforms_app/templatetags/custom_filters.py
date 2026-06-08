from django import template
from django.utils import timezone
from dateutil.parser import parse as date_parse

register = template.Library()

@register.filter
def format_datetime(value, fmt="%Y-%m-%d %H:%M"):
    """
    Formats a datetime using the given format string.
    """
    if not value:
        return ""
    date_obj = date_parse(value)

    # Optional: ensure timezone-aware formatting
    #if timezone.is_aware(date_obj):
    #    value = timezone.localtime(value)

    return date_obj.strftime(fmt)
