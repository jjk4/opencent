from django.template.defaultfilters import register

@register.filter(name='to_int')
def to_int(value):
    return int(value)