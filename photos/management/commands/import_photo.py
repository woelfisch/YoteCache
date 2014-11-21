from optparse import make_option
import re
import sys
import os
import os.path

from dateutil import tz
from wand.image import Image # Wand
from gi.repository import GExiv2 # libgexiv2-2, typelib-1_0-GExiv2-0_4, python-gobject2
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
    exif = GExiv2.Metadata()

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
                raise e

    def create_proxy(self, source, dest, mode):
        if os.path.isfile(dest) and not self.force:
            return

        # just link fullsize image if JPEG and orientation is normal
        is_jpeg=os.path.splitext(source)[1].lower() in ('.jpg', '.jpeg')
        orientation=self.exif.get_orientation()
        if mode == self.PROXY_FULLSIZE and is_jpeg and orientation == orientation.NORMAL:
            try:
                os.unlink(dest)
            except:
                pass

            try:
                os.link(source, dest)
            except Exception as e:
                self.stderr.write('Error: cannot link {} to {}: {}'.format(source, dest, e.message))
                raise e

            return

        # load image if not yet done
        if not self.image:
            try:
                self.image=Image(filename=source)
            except Exception as e:
                self.stderr.write('Error: cannot read {}: {}'.format(source, e.message))
                raise e

        # copy bitmap, we may need it again
        image = self.image.convert('jpeg')

        # resize
        if mode == self.PROXY_FULLSIZE:
            pass
        elif mode == self.PROXY_THUMBNAIL:
            image.transform(resize=settings.THUMBNAILSIZE)
        elif mode == self.PROXY_WEBSIZED:
            image.transform(resize=settings.WEBSIZE)

        # rotate (after resize to save time)
        if orientation == orientation.NORMAL:
            pass
        elif orientation == orientation.ROT_90:
            image.rotate(degree=90.0)
        elif orientation == orientation.ROT_180:
            image.rotate(degree=180.0)
        elif orientation == orientation.ROT_270:
            image.rotate(degree=270.0)

        try:
            image.save(filename=dest)
        except IOError as e:
            self.stderr.write('Error: cannot write {}: {}'.format(dest, e.message))
            raise e

        return


    def do_import(self, sourcefullpath):
        sourcefullpath=os.path.abspath(sourcefullpath)
        if not sourcefullpath.startswith(settings.SOURCEDIR):
            self.stderr.write('Error: {} is not below directory {}'.format(sourcefullpath, settings.SOURCEDIR))
            return

        if not os.path.isfile(sourcefullpath):
            self.stderr.write('Error: {} is does not exist or is not a file'.format(sourcefullpath))
            return

        # prefer XMP "sidecar" files to save us from parsing huge RAW files more than necessary
        sourcexmppath=os.path.splitext(sourcefullpath)[0]
        havesourcesidecar=False
        for ext in (".xmp", ".XMP", "Xmp"):
            if os.path.isfile(sourcexmppath+ext):
                sourcexmppath+=ext
                try:
                    havesourcesidecar=self.exif.open_path(sourcexmppath) # returns True on success
                except:
                    pass

                break

        # No sidecar, oh well...
        if not havesourcesidecar:
            self.exif.open_path(sourcefullpath)

        sourcerelpath=os.path.relpath(sourcefullpath, settings.SOURCEDIR)
        (jpegreldir, jpegname)=os.path.split(sourcerelpath)
        jpegname=os.path.splitext(jpegname)[0]+".jpg"

        try:
            jpegdir=settings.JPEGDIR+jpegreldir
            self.mkdir(jpegdir)
            self.create_proxy(sourcefullpath, jpegdir+'/'+jpegname, self.PROXY_FULLSIZE)
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

        destxmppath=os.path.splitext(jpegfullpath)[0]+'.xmp'
        if havesourcesidecar:
            if self.force:
                try:
                    os.unlink(destxmppath)
                except:
                    pass
            try:
                fd=open(destxmppath,mode='w+')
                fd.write('<?xml version="1.0" encoding="UTF-8"?>')
                fd.close()
                self.exif.save_file(destxmppath)
            except Exception as e:
                self.stderr.write('Error: cannot write {}: {}'.format(destxmppath, e))
            
        # database: if entry exists (key: jpegreldir) and force mode: update w/ XMP data
        # else: create new entry

    def handle(self, *args, **options):
        self.force=options['force_mode']

        # if args is empty: read filenames from stdin instead
        if len(args) == 0:
            for importfilename in sys.stdin:
                self.do_import(importfilename.strip())
            return

        for importfilename in args:
            self.do_import(importfilename)
