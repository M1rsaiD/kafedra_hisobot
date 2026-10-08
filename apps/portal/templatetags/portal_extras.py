from django import template

register = template.Library()


@register.filter(name="getattr")
def getattr_filter(obj, attr_name):
    """Позволяет выводить в шаблоне {{ obj|getattr:col }}, когда имя поля
    приходит динамически (из cfg.list_columns), а не как литерал."""
    return getattr(obj, attr_name, "")
