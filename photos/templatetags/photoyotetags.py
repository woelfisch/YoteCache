import os.path
from django.conf import settings
from django import template
from photos import tools

register = template.Library()


@register.filter(name='proxyfile')
def proxyfile(media_file):
    if not media_file or not media_file.mime_type:
        return None

    mt = media_file.mime_type.type
    if mt.startswith('video'):
        # used to be animated gifs until I found out how crappy Safari is...
        extension = ".jpg"
    elif mt.startswith('image'):
        extension = ".jpg"
    else:
        return None

    return tools.get_basename(media_file.media_dir.path + '/' + media_file.media_file) + extension


@register.filter(name='thumbnail')
def thumbnail(media_file):
    proxy = proxyfile(media_file)
    if not proxy:
        return settings.STATIC_URL + settings.THUMBNAIL_UNAVAILABLE

    (directory, name) = os.path.split(proxy)
    thumbnail_path = directory + '/' + settings.THUMBNAIL_DIR + name
    if not os.path.exists(settings.WEB_DIR + thumbnail_path):
        return settings.STATIC_URL + settings.THUMBNAIL_UNAVAILABLE

    return settings.IMAGE_URL + thumbnail_path


@register.filter(name='preview')
def preview(media_file):
    proxy = proxyfile(media_file)
    if not proxy:
        return settings.STATIC_URL + settings.PREVIEW_UNAVAILABLE

    (directory, name) = os.path.split(proxy)
    preview_path = directory + '/' + settings.PREVIEW_DIR + name
    if not os.path.exists(settings.WEB_DIR + preview_path):
        return settings.STATIC_URL + settings.PREVIEW_UNAVAILABLE

    return settings.IMAGE_URL + preview_path


@register.filter(name='fullsize')
def fullsize(media_file):
    proxy = proxyfile(media_file)
    if not proxy:
        return settings.STATIC_URL + settings.FULLSIZE_UNAVAILABLE

    if not os.path.exists(settings.WEB_DIR + proxy):
        return settings.STATIC_URL + settings.FULLSIZE_UNAVAILABLE

    return settings.IMAGE_URL + proxy


@register.filter(name='basename')
def basename(media_file):
    return os.path.split(media_file)[1]

@register.filter(name='halfmax')
def halfmax(counter, thumbnail_items):
    if thumbnail_items > settings.INDEX_THUMBNAILS_MAX and counter == settings.INDEX_THUMBNAILS_MAX/2:
        return True

@register.simple_tag(name='static-image')
def static_image(what):
    prefix = settings.STATIC_URL

    if what == 'thumbnail':
        return prefix + settings.THUMBNAIL_TRANSPARENT_OVERLAY
    if what == 'preview':
        return prefix + settings.PREVIEW_TRANSPARENT_OVERLAY
    if what == 'unavailable':
        return prefix + settings.PREVIEW_UNAVAILABLE

    return prefix + "MISSING-IMAGE-FIX-ME.png"


@register.simple_tag(name='star-rating')
def star_rating(rating, **kwargs):
    """
    :param rating: rating of the image
    :param kwargs:
        fillup:
            0: just # of rating stars,
            1: fillup with empty stars,
            2: one star if rating = 0,
            3: fillup with empty <span>
        spacing:
            add space between stars
    :return:
    """
    spacing = 'spacing' in kwargs

    if 'fillup' in kwargs:
        fillup = kwargs['fillup']
    else:
        fillup = 0

    if 'style' in kwargs:
        style = kwargs['style']
    else:
        style = None

    def span_with_style(icon):
        span = '<span class="glyphicon ' + icon + '"'
        if style:
            span += 'style="' + style + '"'
        return span + "></span>"

    if not rating:
        if not fillup: return span_with_style('')
        if fillup == 2:
            return span_with_style('glyphicon-star-empty')

    rv = ''
    for r in range(5):
        if r + 1 <= rating:
            rv += span_with_style('glyphicon-star')
        else:
            if fillup == 1:
                rv += span_with_style('glyphicon-star-empty')
            else:
                rv += span_with_style('')

        if spacing:
            rv += ' '

    return rv


@register.inclusion_tag("photos/dropdown-catalog.html", takes_context=True)
def dropdown_catalog(context, **kwargs):
    return {
        "catalog": context["catalog"],
        "catalog_list": context["catalog_list"],
        "name": kwargs["name"],
        "has_input_field": "has_input_field" in kwargs,
        "has_icon": "has_icon" in kwargs
    }


@register.inclusion_tag("photos/dropdown-label.html", takes_context=False)
def dropdown_label(**kwargs):
    return {
        "name": kwargs["name"],
        "has_icon": "has_icon" in kwargs
    }


@register.inclusion_tag("photos/dropdown-rating.html", takes_context=False)
def dropdown_rating(**kwargs):
    return {
        "name": kwargs["name"],
    }