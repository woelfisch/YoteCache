from django.conf import settings
import os
import logging
import json
import inspect
from pwd import getpwnam
from grp import getgrnam
from datetime import datetime
from django.db.models.fields.related import ManyToManyField
from django.db.models import ForeignKey

def process_dead(pid):
    try:
        os.kill(pid, 0)
    except OSError as e:
        # only two possibilities: EINVAL, ESRCH or EPERM. EPERM means the process exists ;-)
        # EINVAL cannot happen on POSIX compliant systems.
        return e.args[0] == os.errno.ESRCH  # 'No Such Process'

    return False


def get_xmp_name(mediafilename):
    filename = get_basename(mediafilename) + '.xmp'
    return filename


def get_sidecar_name(mediafilename, path):
    if not path:
        return None

    ext = get_extension(path)
    if ext == '.xmp':
        return None

    filename = get_basename(mediafilename) + ext
    return filename


def file_is_sidecar(path):
    return get_extension(path) in ('.xmp', '.thm', '.lrv')


def sidecar_is_xmp(path):
    return get_extension(path) == '.xmp'


def get_basename(path):
    return os.path.splitext(path.__str__())[0]


def get_extension(path):
    try:
        return os.path.splitext(path.__str__())[1].lower()
    except:
        return None


def link(source, dest):
    try:
        os.unlink(dest)
    except OSError:
        pass

    try:
        os.link(source, dest)
        return
    except OSError:
        pass

    try:
        os.symlink(source, dest)
        return
    except OSError as e:
        # probably should try copying
        logging.error('cannot link {} to {}: {}'.format(source, dest, e.args[0]))
        pass


def is_in_path(filename):
    # this doesn't take the pathological case of path elements containing quoted colons into account...
    for directory in os.environ['PATH'].split(':'):
        if os.path.isfile(directory + '/' + filename):
            return True
    return False


def mkdir(path):
    try:
        os.makedirs(path)
    except OSError as e:
        if os.path.isdir(path):
            pass
        else:
            logging.error('Cannot create directory {}: {}'.format(path, e.args[0]))
            raise e
    try:
        os.chown(path, settings.WWWUSER, settings.WWWGROUP)
        os.chmod(path, 0755)
    except (KeyError, OSError) as e:
        logging.warning('Cannot change owner / group of {}: {}'.format(path, e.args[0]))


def www_group():
    for groupname in ('www', 'www-data', 'apache', 'httpd'):
        try:
            gr = getgrnam(groupname)
            return gr.gr_gid
        except:
            pass
    return getgrnam('nogroup').gr_gid


def www_user():
    for username in ('wwwrun', 'www-data', 'www', 'apache', 'httpd'):
        try:
            pw = getpwnam(username)
            return pw.pw_uid
        except:
            pass
    return getpwnam('nobody').pw_uid


def proxyfile(media_file, converted=True):
    if not media_file or not media_file.mime_type:
        return None

    mt = media_file.mime_type.type
    if mt.startswith('video'):
        # used to be animated gifs until I found out how crappy Safari is...
        if converted:
            extension = ".jpg"
        else:
            extension = get_extension(media_file.media_file)
    elif mt.startswith('image'):
        extension = ".jpg"
    else:
        return None

    return get_basename(media_file.media_dir.path + '/' + media_file.media_file) + extension


def thumbnail(media_file):
    proxy = proxyfile(media_file)
    if not proxy:
        return settings.STATIC_URL + settings.THUMBNAIL_UNAVAILABLE

    (directory, name) = os.path.split(proxy)
    thumbnail_path = directory + '/' + settings.THUMBNAIL_DIR + name
    if not os.path.exists(settings.WEB_DIR + thumbnail_path):
        return settings.STATIC_URL + settings.THUMBNAIL_UNAVAILABLE

    return settings.IMAGE_URL + thumbnail_path


def preview(media_file):
    proxy = proxyfile(media_file)
    if not proxy:
        return settings.STATIC_URL + settings.PREVIEW_UNAVAILABLE

    (directory, name) = os.path.split(proxy)
    preview_path = directory + '/' + settings.PREVIEW_DIR + name
    if not os.path.exists(settings.WEB_DIR + preview_path):
        return settings.STATIC_URL + settings.PREVIEW_UNAVAILABLE

    return settings.IMAGE_URL + preview_path


def fullsize(media_file):
    proxy = proxyfile(media_file, converted=False)
    if not proxy:
        return settings.STATIC_URL + settings.FULLSIZE_UNAVAILABLE

    if not os.path.exists(settings.WEB_DIR + proxy):
        return settings.STATIC_URL + settings.FULLSIZE_UNAVAILABLE

    return settings.IMAGE_URL + proxy


# http://stackoverflow.com/questions/21925671/convert-django-model-object-to-dict-with-all-of-the-fields-intact
def _to_dict(instance):
    opts = instance._meta
    data = {}
    for f in opts.concrete_fields + opts.many_to_many:
        if isinstance(f, ManyToManyField):
            if instance.pk is None:
                data[f.name] = []
            else:
                data[f.name] = list(f.value_from_object(instance).values_list('pk', flat=True))
        elif isinstance(f, ForeignKey):
            try:
                # how about yet ANOTHER level of indirection?!
                data[f.name] = f.rel.to.objects.get(pk=f.value_from_object(instance)).natural_key()
            except:
                data[f.name] = ''
        else:
            data[f.name] = f.value_from_object(instance)

    if hasattr(instance, 'properties'):
        for name, prop in inspect.getmembers(instance.properties, lambda x: inspect.isfunction(x)):
            data[name] = prop(instance)

    if instance.pk:
        data['id'] = instance.pk

    # print data
    return data

def _serialize_other(o):
    if isinstance(o, datetime):
        return o.isoformat()
    raise TypeError("Cannot serialize type {}".format(type(o)))

def create_json(media_objs):
    result = []
    for m in media_objs:
        result.append({'pk': m.pk, 'fields': _to_dict(m)})
    return json.dumps(result, default=_serialize_other)
