from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Получить элемент словаря по ключу в шаблоне: {{ dict|get_item:key }}"""
    return dictionary.get(key)

@register.filter
def add_int(value, arg):
    """Сложить два числа: {{ value|add_int:arg }}"""
    try:
        return int(value) + int(arg)
    except (ValueError, TypeError):
        return value

@register.filter
def object_in(value, container):
    """Проверка наличия элемента в контейнере"""
    return value in container