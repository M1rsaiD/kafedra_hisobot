from django import template

register = template.Library()


@register.filter(name="getattr")
def getattr_filter(obj, attr_name):
    """Позволяет выводить в шаблоне {{ obj|getattr:col }}, когда имя поля
    приходит динамически (из cfg.list_columns), а не как литерал."""
    return getattr(obj, attr_name, "")


@register.filter(name="field_display")
def field_display(obj, name):
    """Значение поля для таблицы: для полей с choices — подпись на текущем
    языке, а не код (`Q1`, `outbound` и т.п.)."""
    display = getattr(obj, f"get_{name}_display", None)
    value = display() if callable(display) else getattr(obj, name, "")
    return "" if value is None else value
