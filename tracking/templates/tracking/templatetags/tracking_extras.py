from django import template
register = template.Library()

@register.filter
def has_flag(obj, field_name):
    """Return True/False for a boolean status field on the model."""
    return bool(getattr(obj, field_name, False))

@register.filter
def comment_for(obj, field_name):
    """
    Return the matching *_comment value for a given status field.
    Works for *_downloaded, *_uploaded, *_done -> *_comment.
    Fallback tries '<field_name>_comment'.
    """
    for suffix in ("_downloaded", "_uploaded", "_done"):
        if field_name.endswith(suffix):
            comment_field = field_name.replace(suffix, "_comment")
            return getattr(obj, comment_field, "")
    return getattr(obj, f"{field_name}_comment", "")
