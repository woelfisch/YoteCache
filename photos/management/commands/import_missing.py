from optparse import make_option
import sys
import os
import os.path
import logging
from django.conf import settings
from photos.tools import toolbox
from photos.models import MimeType, Catalog, MediaDir, MediaFile
from photos.templatetags.photoyotetags import proxyfile
from photos.importer import ImportMedia

from time import sleep
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    """
    Add missing photos to database and (re)create proxy files
    """

    def import_directory(self, full_path, files):
        mediadir = MediaDir.objects.get_by_full_path(full_path, prefix=settings.SOURCE_DIR, strip_filename=False)
        unconditionally = False

        if not mediadir:
            mediadir = MediaDir.objects.get_or_create_by_full_path(full_path, prefix=settings.SOURCE_DIR,
                                                                   strip_filename=False)
            unconditionally = True
            reason = 'new directory'

        for f in files:
            if toolbox.file_is_sidecar(f):
                continue

            while mediadir.is_locked():
                sleep(10)

            try:
                if unconditionally:
                    raise MediaFile.DoesNotExist

                reason = 'missing in database'
                media = MediaFile.objects.get(media_dir=mediadir, media_file=f)

                pf = proxyfile(media)
                if not pf:
                    # unsupported media type, do not check for proxy files
                    continue

                proxy_sub_dir_list=(settings.THUMBNAIL_DIR, settings.PREVIEW_DIR)
                # for performance reasons, do not convert movie clips to fullsize animated GIFs...
                if not media.mime_type.type.startswith('video/'):
                    proxy_sub_dir_list += ('', )

                proxy_dir, proxy_name = os.path.split(pf)
                has_proxy = True
                for proxy_sub_dir in proxy_sub_dir_list:
                    proxy = settings.WEB_DIR + proxy_dir + '/' + proxy_sub_dir + proxy_name
                    if not os.path.isfile(proxy):
                        has_proxy = False
                if has_proxy:
                    continue

                reason = 'missing proxy files'
            except MediaFile.DoesNotExist as e:
                pass

            name = full_path + '/' + f

            if settings.DEBUG:
                sys.stderr.write('importing {} ({})\n'.format(name, reason))

            logging.info("import_missing: importing {} ({})".format(name, reason))
            self.importer.do_import(name)

    def handle(self, *args, **options):
        logging.basicConfig(filename=settings.LOGFILE, level=settings.LOGLEVEL, format=settings.LOG_FORMAT)
        self.importer = ImportMedia(lock=False, name='import_missing')

        for root, dirs, files in os.walk(settings.SOURCE_DIR):
            if files:
                self.import_directory(root, files)

        self.importer.close()