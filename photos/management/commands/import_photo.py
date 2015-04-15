import sys
import logging
from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from django.conf import settings
from photos.tools import toolbox
from photos.importer import ImportMedia


class Command(BaseCommand):
    """
    Import new photos: create JPEG, XMP and thumbnail files, add to database
    """
    option_list = BaseCommand.option_list + (
        make_option('-f', '--force',
                    dest='force_mode',
                    action='store_true',
                    default=False,
                    help='(Re)create JPEG, XMP, thumbnail files regardless whether they exist'),
    )

    def handle(self, *args, **options):
        logging.basicConfig(filename=settings.LOGFILE, level=settings.LOGLEVEL, format=settings.LOG_FORMAT)
        toolbox.mkdir(settings.EXPORT_DIR)

        im = ImportMedia(force=options['force_mode'], lock=True, name='import_photo')

        # if args is empty: read filenames from stdin instead
        if len(args) == 0:
            for importfilename in sys.stdin:
                im.do_import(importfilename.strip())
        else:
            for importfilename in args:
                im.do_import(importfilename)

        im.close()


