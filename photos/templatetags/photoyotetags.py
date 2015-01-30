import os.path
from django.conf import settings
from django import template
from photos.tools import toolbox

register = template.Library()

@register.filter(name='proxyfile')
def proxyfile(media_file):
    mt = media_file.mime_type.type
    if mt.startswith('video'):
        extension=".gif"
    elif mt.startswith('image'):
        extension=".jpg"
    else:
        return None

    return toolbox.get_basename(media_file.mediafile_path)+extension

@register.filter(name='thumbnail')
def thumbnail(media_file):
    proxy=proxyfile(media_file)
    if not proxy:
        return settings.STATIC_URL+settings.THUMBNAIL_UNAVAILABLE

    (dir, name) = os.path.split(proxy)
    basename=dir+'/'+settings.THUMBNAIL_DIR+name
    if not os.path.exists(settings.WEB_DIR+basename):
        return settings.STATIC_URL+settings.THUMBNAIL_UNAVAILABLE

    return settings.STATIC_URL+basename

@register.filter(name='preview')
def preview(media_file):
    proxy=proxyfile(media_file)
    if not proxy:
        return settings.STATIC_URL+settings.PREVIEW_UNAVAILABLE

    (dir, name) = os.path.split(proxy)
    basename=dir+'/'+settings.PREVIEW_DIR+name
    if not os.path.exists(settings.WEB_DIR+basename):
        return settings.STATIC_URL+settings.PREVIEW_UNAVAILABLE

    return settings.STATIC_URL+basename

@register.filter(name='fullsize')
def fullsize(media_file):
    proxy=proxyfile(media_file)
    if not proxy:
        return settings.STATIC_URL+settings.FULLSIZE_UNAVAILABLE

    if not os.path.exists(settings.WEB_DIR+proxy):
        return settings.STATIC_URL+settings.FULLSIZE_UNAVAILABLE

    return settings.STATIC_URL+proxy