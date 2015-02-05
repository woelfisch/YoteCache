import os.path
from django.conf import settings
from django import template
from photos.tools import toolbox

register = template.Library()

@register.filter(name='proxyfile')
def proxyfile(media_file):
    if not media_file or not media_file.mime_type:
        return None

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

@register.filter(name='basename')
def basename(media_file):
    return os.path.split(media_file)[1]

@register.tag(name='static-image')
def static_image(parser, token):
    tag_name, what = token.split_contents()
    print tag_name, what
    prefix=settings.STATIC_URL

    if what == 'thumbnail':
        return Url(prefix+settings.THUMBNAIL_TRANSPARENT_OVERLAY)
    if what == 'preview':
        return Url(prefix+settings.PREVIEW_TRANSPARENT_OVERLAY)
    if what == 'unavailable':
        return Url(prefix+settings.PREVIEW_UNAVAILABLE)

    return Url(prefix+"MISSING-IMAGE-FIX-ME.png")

class Url(template.Node):
    def __init__(self, value):
        self.value = value
    def render(self, context):
        return self.value