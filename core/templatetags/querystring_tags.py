from django import template

register = template.Library()


@register.simple_tag
def querystring_except_page(request, page):
    q = request.GET.copy()
    q["page"] = str(page)
    return q.urlencode()
