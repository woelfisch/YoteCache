from optparse import make_option
import re
import os
import os.path
import libxmp # python-xmp-toolkit

from dateutil import tz
from wand.image import Image # Wand
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

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

    force = False
    image = None

    PROXY_FULLSIZE=0
    PROXY_THUMBNAIL=1
    PROXY_WEBSIZED=2

    def mkdir(self, path):
        try:
            os.makedirs(path)
        except OSError as e:
            if os.path.isdir(path):
                pass
            else:
                self.stderr.write('Error: cannot create directory {}: {}'.format(path, e.message))
                raise

    def create_proxy(self, source, dest, mode):
        if os.path.isfile(dest) and not self.force:
            return

        if not self.image:
            try:
                self.image=Image(filename=source)
            except Exception as e:
                self.stderr.write('Error: cannot read {}: {}'.format(source, e.message))
                raise

        image = self.image.convert('jpeg')

        if mode == self.PROXY_FULLSIZE:
            pass
        elif mode == self.PROXY_THUMBNAIL:
            image.transform(resize=settings.THUMBNAILSIZE)
        elif mode == self.PROXY_WEBSIZED:
            image.transform(resize=settings.WEBSIZE)

        try:
            image.save(filename=dest)
        except IOError as e:
            self.stderr.write('Error: cannot write {}: {}'.format(dest, e.message))
            raise

        return


    def do_import(self, sourcefullpath):
        sourcefullpath=os.path.abspath(sourcefullpath)
        if not sourcefullpath.startswith(settings.SOURCEDIR):
            self.stderr.write('Error: {} is not below directory {}'.format(sourcefullpath, settings.SOURCEDIR))
            return

        if not os.path.isfile(sourcefullpath):
            self.stderr.write('Error: {} is does not exist or is not a file'.format(sourcefullpath))
            return

        sourcerelpath=os.path.relpath(sourcefullpath, settings.SOURCEDIR)
        (jpegreldir, jpegname)=os.path.split(sourcerelpath)
        jpegname=os.path.splitext(jpegname)[0]+".jpg"

        try:
            jpegdir=settings.JPEGDIR+jpegreldir
            self.mkdir(jpegdir)
            self.create_proxy(sourcefullpath, jpegdir+"/"+jpegname, self.PROXY_FULLSIZE)
        except:
            return

        try:
            tndir=jpegdir+"/"+settings.THUMBNAILDIR
            self.mkdir(tndir)
            self.create_proxy(sourcefullpath, tndir+"/"+jpegname, self.PROXY_THUMBNAIL)
        except:
            return

        try:
            webimgdir=jpegdir+"/"+settings.WEBIMAGEDIR
            self.mkdir(webimgdir)
            self.create_proxy(sourcefullpath, webimgdir+"/"+jpegname, self.PROXY_WEBSIZED)
        except:
            return

        sourcexmppath=os.path.splitext(sourcefullpath)[0]
        havesourcesidecar=False
        for ext in [".xmp", ".XMP", "Xmp"]:
            if os.path.isfile(sourcexmppath+ext):
                sourcexmppath+=ext
                havesourcesidecar=True
                break
        # if sidecar jpegdir+"/"+splitext(jpegname)[0]+".xmp" does not exist, or force mode:
        #    if havesourcesidecar: read XMP data from source with libxmp
        #    else: read it from image with libxmp
        #    create sidecar in jpegdir
        # else: read xmp data from sidecar in jpegdir
        # keep xmp data for database
        #
        # database: if entry exists (key: jpegreldir) and force mode: update w/ XMP data
        # else: create new entry

    def handle(self, *args, **options):
        self.force=options['force_mode']
        # if args is empty: read filenames from stdin instead
        for importfilename in args:
            self.do_import(importfilename)
