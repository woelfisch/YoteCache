from optparse import make_option
import sys
import os
import os.path
import logging
from django.conf import settings
from photos.models import MediaDir, MediaFile
from photos.templatetags.photoyotetags import proxyfile

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

def my_unlink(filename):
    if settings.DEBUG:
        sys.stderr.write('unlink({})\n'.format(filename))

    if not filename:
        return

    if os.path.isfile(filename):
        if settings.DEBUG:
            sys.stderr.write('removing file {}\n'.format(filename))
        logging.info('cleanup_db: removing file {}'.format(filename))
        os.unlink(filename)

def my_rmdir(path):
    path=settings.SOURCE_DIR+path
    while path and path != settings.SOURCE_DIR[:-1]:
        if settings.DEBUG:
            sys.stderr.write('rmdir({})\n'.format(path))
        try:
            os.rmdir(path)
        except OSError as e:
            if e.args[0] == os.errno.ENOTEMPTY:
                return
        path=os.path.dirname(path)

class Command(BaseCommand):
    """
    Remove entries of deleted photos from the database
    """
    def handle(self, *args, **options):
        logging.basicConfig(filename=settings.LOGFILE, level=settings.LOGLEVEL, format=settings.LOG_FORMAT)
        for m in MediaFile.objects.all():
            source_dir = settings.SOURCE_DIR+m.media_dir.path+'/'
            source_file = source_dir+m.media_file

            if not os.path.isfile(source_file):
                if settings.DEBUG:
                    sys.stderr.write('{} is gone, removing entry for {}\n'.format(source_file, m.filename))
                logging.info('cleanup_db: {} is gone, removing entry for {}'.format(source_file, m.filename))

                if (m.sidecar_file):
                    my_unlink(source_dir+m.sidecar_file)

                proxy = proxyfile(m)
                if proxy:
                    proxy=os.path.basename(proxy)
                    for proxy_sub_dir in ('', settings.THUMBNAIL_DIR, settings.PREVIEW_DIR):
                        my_unlink(settings.WEB_DIR + m.media_dir.path + '/' + proxy_sub_dir + proxy)

                m.delete()

        for md in MediaDir.objects.all():
            m = MediaFile.objects.filter(media_dir=md)
            if len(m) == 0:
                if settings.DEBUG:
                    sys.stderr.write('no media objects left in {}, removing entry\n'.format(md.path))
                logging.info('cleanup_db: no media objects left in {}, removing entry'.format(md.path))
                my_rmdir(md.path)
                md.delete()