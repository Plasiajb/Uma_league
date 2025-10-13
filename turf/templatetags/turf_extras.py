# turf/templatetags/turf_extras.py

from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """ Allows accessing dictionary keys with a variable in Django templates """
    return dictionary.get(key)