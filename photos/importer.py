import os
import os.path
import logging

from subprocess import call
from dateutil import tz
from fractions import Fraction
import magic  # python-magic
from gi.repository import GExiv2  # libgexiv2-2, typelib-1_0-GExiv2-0_4, python-gobject2

from django.conf import settings
from photos import tools
from photos.statuswriter import StatusWriter
from photos.models import MimeType, Catalog, MediaDir, MediaFile

if settings.IMAGE_LIB == 'wand':
    from wand.image import Image  # Wand
elif settings.IMAGE_LIB == 'rawpy':
    import rawpy
    from PIL import Image


class ImportMedia(object):
    """
    Import new photos: create JPEG, XMP and thumbnail files, add to database
    """

    PROXY_FULLSIZE = 0
    PROXY_THUMBNAIL = 1
    PROXY_WEBSIZED = 2

    # outrageously slow, exec()s ufraw-batch in newer versions
    def _create_proxy_wand(self, source, dest, mode):
        # load image if not yet done
        if not self.image:
            try:
                self.image = Image(filename=source)
            except Exception as e:
                logging.error('cannot read {}: {}'.format(source, e.args[0]))
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
            logging.error('Error: cannot write {}: {}'.format(dest, e.args[0]))
            raise e

    def _create_proxy_rawpy(self, source, dest, mode):
        # maybe Pillow supports this file type directly?
        if not self.image:
            try:
                self.image = Image.open(source)
            except IOError:
                pass
            except Exception as e:
                logging.error('cannot read {}: {}'.format(source, e.args[0]))
                raise e

        # obviously not, try decoding as Raw
        if not self.image:
            try:
                raw = rawpy.imread(source)
                rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=True)
                self.image = Image.fromarray(rgb)
            except Exception as e:
                logging.error('cannot read {}: {}'.format(source, e.args[0]))
                raise e

        image = self.image.copy()
        if mode == self.PROXY_FULLSIZE:
            pass
        elif mode == self.PROXY_THUMBNAIL:
            image.thumbnail(settings.THUMBNAILSIZE)
        elif mode == self.PROXY_WEBSIZED:
            image.thumbnail(settings.WEBSIZE)

        try:
            image.save(dest)
        except Exception as e:
            logging.error('cannot write {}: {}'.format(dest, e.args[0]))

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
                logging.error('cannot link {} to {}: {}'.format(source, dest, e.args[0]))
                raise e

            return

        if settings.IMAGE_LIB == 'wand':
            self._create_proxy_wand(source, dest, mode)
        elif settings.IMAGE_LIB == 'rawpy':
            self._create_proxy_rawpy(source, dest, mode)
        else:
            logging.error('configuration error: unknown or missing IMAGE_LIB {}'.format(settings.IMAGE_LIB))

    def create_video_proxy(self, source, thumbnail, websized):
        logging.info('called for {}, {}, {}'.format(source, thumbnail, websized))
        if os.path.isfile(thumbnail) and os.path.isfile(websized) and not self.force:
            return

        call([settings.FFMPEG_COMMAND, '-i', source,
              '-i', settings.THUMBNAIL_VIDEO_PLAY_BUTTON,
              '-i', settings.PREVIEW_VIDEO_PLAY_BUTTON,
              '-filter_complex', settings.FFMPEG_FILTER,
              '-y', '-v', 'quiet',
              '-map', '[tn]',
              '-frames:v', '1',
              thumbnail,
              '-map', '[proxy]',
              '-frames:v', '1',
              websized],
             shell=False)


    def write_xmp_sidecar(self, sourcefile):
        destxmppath = os.path.splitext(sourcefile)[0] + '.xmp'
        try:
            # how brain-damaged is this?!
            fd = open(destxmppath, mode='w+')
            fd.write('<?xml version="1.0" encoding="UTF-8"?><x:xmpmeta xmlns:x="adobe:ns:meta/"></x:xmpmeta>')
            fd.close()
            self.exif.save_file(destxmppath)
        except Exception as e:
            logging.error('cannot write {}: {}'.format(destxmppath, e))

        return destxmppath

    def get_timestamp(self, source_file, use_exif=True):
        # first try to get it from EXIF data
        if use_exif:
            timestamp = self.exif.get_tag_string('Exif.Photo.DateTimeOriginal')
            if not timestamp:
                timestamp = self.exif.get_tag_string('Exif.Image.DateTime')
        else:
            timestamp = None

        # try timestamp of file
        if not timestamp:
            st = os.stat(source_file)
            timestruct = tz.time.gmtime(int(st.st_ctime))
            # camera clock not set, eh?
            if timestruct.tm_year < 2000:
                timestruct = tz.time.gmtime()
            return timestruct

        return tz.time.strptime(timestamp, '%Y:%m:%d %H:%M:%S')

    def create_filename(self, source_file, timestruct):
        datestring = tz.time.strftime("%Y%m%d", timestruct)
        mediabasename = os.path.basename(source_file).lower()
        filename = datestring + "-" + mediabasename
        count = 1
        while count < 1000000:
            try:
                MediaFile.objects.get(filename=filename)
            except Exception as e:
                break
            filename = '{}-{:06d}-{}'.format(datestring, count, mediabasename)
            count += 1

        if count == 1000000:
            logging.error('Cannot create unique export filename')
            return None

        return filename

    def update_image_parameters(self, entry):
        try:
            entry.f_number = Fraction(self.exif.get_tag_string('Exif.Photo.FNumber')) * 1.0
        except Exception:
            entry.f_number = 0

        try:
            entry.exposure_time = Fraction(self.exif.get_tag_string('Exif.Photo.ExposureTime')) * 1.0
        except Exception:
            entry.exposure_time = 0

        try:
            entry.gain_value = float(self.exif.get_tag_string('Exif.Photo.ISOSpeedRatings'))
        except Exception:
            try:
                entry.gain_value = float(self.exif.get_tag_string('Exif.Photo.GainControl'))
            except Exception:
                entry.gain_value = 0

        try:
            entry.focal_length = Fraction(self.exif.get_tag_string('Exif.Photo.FocalLength')) * 1.0
        except Exception as e:
            entry.focal_length = 0

    def update_db(self, source_file, sidecar=None, is_supported_media=True):
        entry = None
        media_dir = self.mediadir
        media_file = os.path.basename(source_file)

        try:
            entry = MediaFile.objects.get(media_dir=media_dir, media_file=media_file)
            if not self.force:
                return entry
        except MediaFile.DoesNotExist:
            timestamp = self.get_timestamp(source_file, use_exif=is_supported_media)
            filename = self.create_filename(source_file, timestamp)
            if not filename:
                return None

            catalog, created = Catalog.objects.get_or_create(name=settings.DEFAULT_CATALOG)
            mime_type, created = MimeType.objects.get_or_create(type=self.mimetype)

            try:
                entry = MediaFile(media_dir=media_dir, media_file=media_file)
            except Exception as e:
                logging.error('Cannot get object: {}'.format(e.args[0]))
                raise e

            entry.mime_type = mime_type
            entry.catalog = catalog
            entry.filename = filename
            entry.date = tz.time.strftime('%Y-%m-%dT%H:%M:%SZ', timestamp)

            if is_supported_media:
                rating = self.exif.get_tag_long('Xmp.xmp.Rating')
                if rating:
                    entry.rating = rating
                label = self.exif.get_tag_string('Xmp.xmp.Label')
                if label:
                    entry.label = label

                entry.sidecar_file = sidecar

        if is_supported_media:
            self.update_image_parameters(entry)
        return entry

    def import_image(self, source_file):
        self.image = None
        # prefer XMP "sidecar" files to save us from parsing huge RAW files more than necessary
        source_xmp_file = os.path.splitext(source_file)[0]
        havesourcesidecar = False
        for ext in (".xmp", ".XMP", "Xmp"):
            if os.path.isfile(source_xmp_file + ext):
                source_xmp_file += ext
                try:
                    havesourcesidecar = self.exif.open_path(source_xmp_file)  # returns True on success
                except Exception:
                    pass

                break

        # No sidecar, oh well...
        if not havesourcesidecar:
            self.exif.open_path(source_file)

        (mediareldir, jpegfilename) = os.path.split(os.path.relpath(source_file, settings.SOURCE_DIR))
        jpegfilename = os.path.splitext(jpegfilename)[0] + ".jpg"

        self.status.update(10, 'Writing Proxy')
        try:
            mediadir = settings.WEB_DIR + mediareldir
            jpegfullpath = mediadir + '/' + jpegfilename
            tools.mkdir(mediadir)
            self.create_proxy(source_file, jpegfullpath, self.PROXY_FULLSIZE)
        except Exception as e:
            raise e

        self.status.update(75, 'Writing Thumbnail')
        try:
            tndir = mediadir + "/" + settings.THUMBNAIL_DIR
            tnfullpath = tndir + '/' + jpegfilename
            tools.mkdir(tndir)
            self.create_proxy(source_file, tnfullpath, self.PROXY_THUMBNAIL)
        except Exception as e:
            os.unlink(jpegfullpath)
            raise e

        self.status.update(85, 'Writing Preview')
        try:
            webimgdir = mediadir + "/" + settings.PREVIEW_DIR
            webimgfullpath = webimgdir + '/' + jpegfilename
            tools.mkdir(webimgdir)
            self.create_proxy(source_file, webimgfullpath, self.PROXY_WEBSIZED)
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
            source_xmp_file = self.write_xmp_sidecar(source_file)

        entry = self.update_db(source_file, sidecar=os.path.basename(source_xmp_file))
        self.status.update(95, 'Writing Database')
        entry.save()
        self.status.update(100, 'Done')

    def import_video(self, source_file):
        if not settings.FFMPEG_COMMAND:
            raise NotImplementedError

        source_thm_file = os.path.splitext(source_file)[0]
        havesourcesidecar = False
        for ext in (".thm", ".THM", "Thm"):
            if os.path.isfile(source_thm_file + ext):
                source_thm_file += ext
                try:
                    havesourcesidecar = self.exif.open_path(source_thm_file)  # returns True on success
                except Exception:
                    pass

                break

        (mediareldir, jpegfilename) = os.path.split(os.path.relpath(source_file, settings.SOURCE_DIR))
        mediadir = settings.WEB_DIR + mediareldir
        jpegfilename = os.path.splitext(jpegfilename)[0] + ".jpg"

        self.status.update(50, 'Writing Thumbnail and Proxy')
        try:
            tndir = mediadir + "/" + settings.THUMBNAIL_DIR
            tnfullpath = tndir + '/' + jpegfilename
            tools.mkdir(tndir)
        except Exception as e:
            raise e

        try:
            webimgdir = mediadir + "/" + settings.PREVIEW_DIR
            webimgfullpath = webimgdir + '/' + jpegfilename
            tools.mkdir(webimgdir)
        except Exception as e:
            os.unlink(tnfullpath)
            raise e

        self.create_video_proxy(source_file, tnfullpath, webimgfullpath)

        self.status.update(90, 'Writing Sidecar')
        if not havesourcesidecar:
            source_sidecar = self.write_xmp_sidecar(source_file)
            self.exif.open_path(source_sidecar)
            sidecar = os.path.basename(source_sidecar)
        else:
            sidecar = os.path.basename(source_thm_file)

        entry = self.update_db(source_file, sidecar=sidecar)
        self.status.update(95, 'Writing Database')
        entry.save()
        self.status.update(100, 'Done')

    def import_other(self, source_file):
        entry = self.update_db(source_file, is_supported_media=False)
        if entry.mime_type.copy:
            self.status.update(50, 'Writing Database')
            entry.save()
        self.status.update(100, 'Done')

    def do_import(self, source_file):
        self.status = StatusWriter(statusname=settings.PROCESS_STATUS, filename=source_file, text='Start')
        source_file = os.path.abspath(source_file)

        if not source_file.startswith(settings.SOURCE_DIR):
            logging.critical('{} is not below directory {}'.format(source_file, settings.SOURCE_DIR))
            self.status.error('Broken Configuration')
            return

        if not os.path.isfile(source_file):
            logging.critical('{} does not exist or is not a file'.format(source_file))
            self.status.error('Not a File')
            return

        if self.lock:
            self.mediadir = MediaDir.objects.compare_and_lock(self.mediadir, source_file, prefix=settings.SOURCE_DIR,
                                                              name=self.name)
        else:
            self.mediadir = MediaDir.objects.get_or_create_by_full_path(source_file, prefix=settings.SOURCE_DIR)

        self.status.update(5, 'Examining File Type')
        self.mimetype = magic.from_file(filename=source_file, mime=True)
        extension = os.path.splitext(source_file)[1].lower()

        # image, but skip video thumbnail (handled by do_import_video and exporter)
        if self.mimetype.startswith('image/') and extension != '.thm':
            try:
                self.import_image(source_file)
                return
            except Exception as e:
                logging.warning('Importer: ', exc_info=True)
                self.status.update(0, 'Script Error')
                pass

        # video, yay.
        if self.mimetype.startswith('video/'):
            try:
                self.import_video(source_file)
                return
            except Exception as e:
                logging.warning('Importer: ', exc_info=True)
                self.status.update(0, 'Script Error')
                pass

        # sidecar gets handled explicitly by exporter
        if extension == '.xmp':
            self.status.update(100, 'Done')
            return

        self.import_other(source_file)

    def close(self):
        if self.status:
            self.status.close()
            self.status = None
        if self.mediadir and self.lock:
            self.mediadir.unlock()
            self.mediadir = None

    def __del__(self):
        self.close()

    def __init__(self, force=False, lock=True, name=None):
        self.exif = GExiv2.Metadata()
        self.force = force
        self.lock = lock
        self.name = name
        self.mediadir = None
        self.image = None
        self.status = None