from optparse import make_option
import sys
import os
import os.path
import logging

from subprocess import call
from dateutil import tz
from fractions import Fraction
import magic    # python-magic
from wand.image import Image  # Wand
from gi.repository import GExiv2  # libgexiv2-2, typelib-1_0-GExiv2-0_4, python-gobject2
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from photos.tools import toolbox
from photos.statuswriter import StatusWriter
from photos.models import MimeType, Catalog, MediaFile

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
    status = None

    PROXY_FULLSIZE = 0
    PROXY_THUMBNAIL = 1
    PROXY_WEBSIZED = 2


    def create_proxy(self, source, dest, mode):
        logging.info('called for {}, {}, {}'.format(source, dest, mode))
        if os.path.isfile(dest) and not self.force:
            return

        # just link fullsize image if JPEG and orientation is normal
        is_jpeg = os.path.splitext(source)[1].lower() in ('.jpg', '.jpeg')
        orientation = self.exif.get_orientation()
        logging.debug('EXIF Orientation: {}'.format(orientation.value_nick))

        if mode == self.PROXY_FULLSIZE and is_jpeg and orientation == orientation.NORMAL:
            try:
                os.unlink(dest)
            except Exception as e:
                pass

            try:
                os.link(source, dest)
            except Exception as e:
                logging.error('cannot link {} to {}: {}'.format(source, dest, e.message))
                raise e

            return

        # load image if not yet done
        if not self.image:
            try:
                self.image = Image(filename=source)
            except Exception as e:
                logging.error('cannot read {}: {}'.format(source, e.message))
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

        try:
            # Wand does auto-rotate, but doesn't fix EXIF data... m(
            image.strip()
            image.save(filename=dest)
        except (Exception, IOError) as e:
            logging.error('Error: cannot write {}: {}'.format(dest, e.message))
            raise e

        return

    def create_video_proxy(self, source, dest, mode):
        logging.info('called for {}, {}, {}'.format(source, dest, mode))
        if os.path.isfile(dest) and not self.force:
            return

        if mode == self.PROXY_THUMBNAIL:
            resize_to=settings.VIDEO_THUMBNAILSIZE
        elif mode == self.PROXY_WEBSIZED:
            resize_to=settings.VIDEO_WEBSIZE
        else:
            return

        # ffmpeg -i ../../import/test/MVI_7541.MOV -vsync 0 -vf select="eq(pict_type\,PICT_TYPE_I)",scale=768:-1 -r 10 -t 30 -y /tmp/test.gif'''
        # avconv -i /data/camera/import/test/MVI_7541.MOV -vsync 0 -vf select="eq(pict_type\,I)",scale=768:-1,format=rgb8 -r 10 -t 30 -pix_fmt rgb24 -y test.gif'''

        call([settings.FFMPEG_COMMAND, '-i', source, '-vsync', '0',
              '-vf', settings.FFMPEG_FILTER.format(resize_to),
              '-r', '10', '-t', '{:d}'.format(settings.VIDEO_PREVIEWTIME),
              '-y', '-v', 'quiet'] +
             settings.FFMPEG_EXTRA+[dest], shell=False)

    def write_xmp_sidecar(self, sourcefile):
        destxmppath=os.path.splitext(sourcefile)[0]+'.xmp'
        try:
            # how brain-damaged is this?!
            fd=open(destxmppath, mode='w+')
            fd.write('<?xml version="1.0" encoding="UTF-8"?><x:xmpmeta xmlns:x="adobe:ns:meta/"></x:xmpmeta>')
            fd.close()
            self.exif.save_file(destxmppath)
        except Exception as e:
            logging.error('cannot write {}: {}'.format(destxmppath, e))

        return destxmppath

    def get_timestamp(self, sourcefullpath, use_exif=True):
        # first try to get it from EXIF data
        if use_exif:
            timestamp=self.exif.get_tag_string('Exif.Photo.DateTimeOriginal')
            if not timestamp:
                timestamp=self.exif.get_tag_string('Exif.Image.DateTime')
        else:
            timestamp=None

        # try timestamp of file
        if not timestamp:
            st=os.stat(sourcefullpath)
            timestruct=tz.time.gmtime(int(st.st_ctime))
            # camera clock not set, eh?
            if timestruct.tm_year < 2000:
                timestruct=tz.time.gmtime()
            return timestruct

        return tz.time.strptime(timestamp, '%Y:%m:%d %H:%M:%S')

    def create_filename(self, sourcefullpath, timestruct):
        datestring=tz.time.strftime("%Y%m%d", timestruct)
        mediabasename=os.path.basename(sourcefullpath).lower()
        filename=datestring+"-"+mediabasename
        count=1
        while count < 1000000:
            try:
                MediaFile.objects.get(filename=filename)
            except Exception as e:
                break
            filename='{}-{:06d}-{}'.format(datestring, count, mediabasename)
            count+=1

        if count == 1000000:
            logging.error('Cannot create unique export filename')
            return None

        return filename

    def update_image_parameters(self, entry):
        try:
            entry.f_number=Fraction(self.exif.get_tag_string('Exif.Photo.FNumber'))*1.0
        except Exception:
            entry.f_number=0

        try:
            entry.exposure_time=Fraction(self.exif.get_tag_string('Exif.Photo.ExposureTime'))*1.0
        except Exception:
            entry.exposure_time=0

        try:
            entry.gain_value=float(self.exif.get_tag_string('Exif.Photo.ISOSpeedRatings'))
        except Exception:
            try:
                entry.gain_value=float(self.exif.get_tag_string('Exif.Photo.GainControl'))
            except Exception:
                entry.gain_value=0

        try:
            entry.focal_length=Fraction(self.exif.get_tag_string('Exif.Photo.FocalLength'))*1.0
        except Exception as e:
            entry.focal_length=0

    def update_db(self, sourcefullpath, sourcerelpath, sidecar=None, is_supported_media=True):
        entry=None
        try:
            entry=MediaFile.objects.get(mediafile_path=sourcerelpath)
            if not self.force:
                return entry
        except MediaFile.DoesNotExist:
            timestamp=self.get_timestamp(sourcefullpath, use_exif=is_supported_media)
            filename=self.create_filename(sourcefullpath, timestamp)
            if not filename:
                return

            catalog, created=Catalog.objects.get_or_create(name=settings.DEFAULT_CATALOG)
            mime_type, created=MimeType.objects.get_or_create(type=self.mimetype)

            try:
                entry=MediaFile(mediafile_path=sourcerelpath)
            except Exception as e:
                logging.error('Cannot get object: {}'.format(e.message))
                raise e

            entry.mime_type=mime_type
            entry.catalog=catalog
            entry.filename=filename
            entry.date=tz.time.strftime('%Y-%m-%dT%H:%M:%SZ', timestamp)

            if is_supported_media:
                rating=self.exif.get_tag_long('Xmp.xmp.Rating')
                if rating:
                    entry.rating=rating
                label=self.exif.get_tag_string('Xmp.xmp.Label')
                if label:
                    entry.label=label

                entry.sidecar_path=sidecar

        if is_supported_media:
            self.update_image_parameters(entry)
        return entry

    def import_image(self, sourcefullpath, sourcerelpath):
        self.image = None
        # prefer XMP "sidecar" files to save us from parsing huge RAW files more than necessary
        sourcexmppath = os.path.splitext(sourcefullpath)[0]
        havesourcesidecar = False
        for ext in (".xmp", ".XMP", "Xmp"):
            if os.path.isfile(sourcexmppath + ext):
                sourcexmppath += ext
                try:
                    havesourcesidecar = self.exif.open_path(sourcexmppath)  # returns True on success
                except Exception:
                    pass

                break

        # No sidecar, oh well...
        if not havesourcesidecar:
            self.exif.open_path(sourcefullpath)

        (mediareldir, jpegfilename) = os.path.split(sourcerelpath)
        jpegfilename = os.path.splitext(jpegfilename)[0] + ".jpg"

        self.status.update(10, 'Writing Proxy')
        try:
            mediadir = settings.WEB_DIR + mediareldir
            jpegfullpath = mediadir+'/'+jpegfilename
            toolbox.mkdir(mediadir)
            self.create_proxy(sourcefullpath, jpegfullpath, self.PROXY_FULLSIZE)
        except Exception as e:
            raise e

        self.status.update(75, 'Writing Thumbnail')
        try:
            tndir = mediadir + "/" + settings.THUMBNAIL_DIR
            tnfullpath = tndir+'/'+jpegfilename
            toolbox.mkdir(tndir)
            self.create_proxy(sourcefullpath, tnfullpath, self.PROXY_THUMBNAIL)
        except Exception as e:
            os.unlink(jpegfullpath)
            raise e

        self.status.update(85, 'Writing Preview')
        try:
            webimgdir = mediadir + "/" + settings.PREVIEW_DIR
            webimgfullpath = webimgdir+'/'+jpegfilename
            toolbox.mkdir(webimgdir)
            self.create_proxy(sourcefullpath, webimgfullpath, self.PROXY_WEBSIZED)
        except Exception as e:
            os.unlink(jpegfullpath)
            os.unlink(tnfullpath)
            raise e

        # we need to write the XMP sidecar file here as we definitely do not want to parse
        # RAW files from the web app and exiv2 isn't capable to construct it's content without
        # a source file. A sidecar file is required for import of the rating and label tags
        # with lightroom, though.
        #
        # ATTN: We'll write it to SOURCE_DIR. The web app should never touch the proxy dirs
        # by itself

        if not havesourcesidecar:
            sourcexmppath=self.write_xmp_sidecar(sourcefullpath)

        xmprelpath = os.path.relpath(sourcexmppath, settings.SOURCE_DIR)
        entry=self.update_db(sourcefullpath, sourcerelpath, xmprelpath)
        self.status.update(95, 'Writing Database')
        entry.save()
        self.status.update(100, 'Done')

    def import_video(self, sourcefullpath, sourcerelpath):
        if not settings.FFMPEG_COMMAND:
            raise NotImplementedError

        sourcethmpath = os.path.splitext(sourcefullpath)[0]
        havesourcesidecar = False
        for ext in (".thm", ".THM", "Thm"):
            if os.path.isfile(sourcethmpath + ext):
                sourcethmpath += ext
                try:
                    havesourcesidecar = self.exif.open_path(sourcethmpath)  # returns True on success
                except Exception:
                    pass

                break

        (mediareldir, giffilename) = os.path.split(sourcerelpath)
        mediadir = settings.WEB_DIR + mediareldir
        giffilename = os.path.splitext(giffilename)[0] + ".gif"

        self.status.update(10, 'Writing Thumbnail')
        try:
            tndir = mediadir + "/" + settings.THUMBNAIL_DIR
            tnfullpath = tndir+'/'+giffilename
            toolbox.mkdir(tndir)
            self.create_video_proxy(sourcefullpath, tnfullpath, self.PROXY_THUMBNAIL)
        except Exception as e:
            raise e

        self.status.update(50, 'Writing Proxy')
        try:
            webimgdir = mediadir + "/" + settings.PREVIEW_DIR
            webimgfullpath = webimgdir+'/'+giffilename
            toolbox.mkdir(webimgdir)
            self.create_video_proxy(sourcefullpath, webimgfullpath, self.PROXY_WEBSIZED)
        except Exception as e:
            os.unlink(tnfullpath)
            raise e

        self.status.update(90, 'Writing Sidecar')
        if not havesourcesidecar:
            sourcesidecarpath=self.write_xmp_sidecar(sourcefullpath)
            self.exif.open_path(sourcesidecarpath)
            sidecarrelpath = os.path.relpath(sourcesidecarpath, settings.SOURCE_DIR)
        else:
            sidecarrelpath = os.path.relpath(sourcethmpath, settings.SOURCE_DIR)

        entry = self.update_db(sourcefullpath, sourcerelpath, sidecarrelpath)
        self.status.update(95, 'Writing Database')
        entry.save()
        self.status.update(100, 'Done')

    def import_other(self, sourcefullpath, sourcerelpath):
        entry = self.update_db(sourcefullpath, sourcerelpath, is_supported_media=False)
        if entry.mime_type.copy:
            self.status.update(50, 'Writing Database')
            entry.save()
        self.status.update(100, 'Done')

    def do_import(self, sourcefullpath):
        self.status=StatusWriter(statusfilename=settings.IMPORT_STATUS, filename=sourcefullpath, text='Start')
        sourcefullpath = os.path.abspath(sourcefullpath)
        if not sourcefullpath.startswith(settings.SOURCE_DIR):
            logging.critical('{} is not below directory {}'.format(sourcefullpath, settings.SOURCE_DIR))
            self.status.error('Broken Configuration')
            return

        if not os.path.isfile(sourcefullpath):
            logging.critical('{} does not exist or is not a file'.format(sourcefullpath))
            self.status.error('Not a File')
            return

        sourcerelpath = os.path.relpath(sourcefullpath, settings.SOURCE_DIR)

        self.status.update(5, 'Examining File Type')
        self.mimetype=magic.from_file(filename=sourcefullpath, mime=True)
        extension=os.path.splitext(sourcefullpath)[1].lower()

        # image, but skip video thumbnail (handled by do_import_video and exporter)
        if self.mimetype.startswith('image/') and extension != '.thm':
            try:
                self.import_image(sourcefullpath, sourcerelpath)
                return
            except Exception as e:
                logging.warning('Importer: ',exc_info=True)
                self.status.update(0, 'Script Error')
                pass

        # video, yay.
        if self.mimetype.startswith('video/'):
            try:
                self.import_video(sourcefullpath, sourcerelpath)
                return
            except Exception as e:
                logging.warning('Importer: ',exc_info=True)
                self.status.update(0, 'Script Error')
                pass

        # sidecar gets handled explicitly by exporter
        if extension == '.xmp':
            return

        self.import_other(sourcefullpath, sourcerelpath)
        self.status.close()


    def handle(self, *args, **options):
        logging.basicConfig(filename=settings.LOGFILE, level=settings.LOGLEVEL, format=settings.LOG_FORMAT)
        self.force = options['force_mode']

        toolbox.mkdir(settings.EXPORT_DIR)

        # if args is empty: read filenames from stdin instead
        if len(args) == 0:
            for importfilename in sys.stdin:
                self.do_import(importfilename.strip())
        else:
            for importfilename in args:
                self.do_import(importfilename)

        if self.status:
                self.status.close()
