import os
import os.path
import logging
from datetime import datetime
from django.db import models
from django.conf import settings
from django.utils import timezone
from model_utils import FieldTracker
from photos import tools
from gi.repository import GExiv2

if settings.DEBUG_MD_LOCKING:
    import sys

LABELS = [
    ('None', 'None'),
    ('Red', 'Red'),
    ('Yellow', 'Yellow'),
    ('Green', 'Green'),
    ('Blue', 'Blue'),
    ('Purple', 'Purple'),
]

# because Django is too fucking stupid to just ignore the damn static function inside the class, this must be
# either in the Meta subclass or a stinking global function to the module. Object Orientation, my arse.
def get_default_catalog():
    return Catalog.objects.get_or_create(name=settings.DEFAULT_CATALOG)[0]


class CatalogManager(models.Manager):
    def get_by_natural_key(self, catalog):
        return self.get(catalog=catalog)


class Catalog(models.Model):
    name = models.CharField(max_length=256, unique=True, help_text='Name of the catalog')
    publish = models.BooleanField(default=True, help_text='Make catalog available to other services')

    objects = CatalogManager()

    def __str__(self):
        return self.name

    def natural_key(self):
        return self.name

    def save(self, *args, **kwargs):
        super(Catalog, self).save(*args, **kwargs)
        tools.mkdir(self.get_path())

    def delete(self, *args, **kwargs):
        try:
            os.rmdir(self.get_path())
        except Exception as e:
            pass

        super(Catalog, self).delete(*args, **kwargs)

    def get_path(self):
        return settings.EXPORT_DIR + self.name + '/'


class MimeTypeManager(models.Manager):
    def get_by_natural_key(self, mime_type):
        return self.get(mime_type=mime_type)


def get_default_mime_type():
    return MimeType.objects.get_or_create(type=settings.UNKOWN_MIME_TYPE)[0]


class MimeType(models.Model):
    type = models.CharField(max_length=256, unique=True, help_text='MIME type')
    hide = models.BooleanField(default=False, help_text='Hide this type of content in frontend')
    copy = models.BooleanField(default=True, help_text='Export this type of content')

    objects = MimeTypeManager()

    def __str__(self):
        return self.type

    def natural_key(self):
        return self.type


def get_default_media_dir():
    return MediaDir.objects.get_or_create(path='__no_directory')[0]


class MediaDirManager(models.Manager):
    def get_by_natural_key(self, path):
        return self.get(path=path)

    def _split_path(self, path, prefix=None, strip_filename=True):
        if prefix:
            path = os.path.relpath(path, prefix)
        if strip_filename:
            path = os.path.dirname(path)
        return path

    def get_by_full_path(self, path, prefix=None, strip_filename=True):
        try:
            return self.get(path=self._split_path(path, prefix, strip_filename))
        except MediaDir.DoesNotExist:
            return None

    def get_or_create_by_full_path(self, path, prefix=None, strip_filename=True):
        return self.get_or_create(path=self._split_path(path, prefix, strip_filename))[0]

    def get_and_lock(self, path, prefix=None, strip_filename=True, name=None):
        md = self.get_or_create_by_full_path(path, prefix, strip_filename)
        md.lock(name)
        return md

    def compare_and_lock(self, mediadir, path, prefix=None, strip_filename=True, name=None):
        path = self._split_path(path, prefix, strip_filename)

        if not mediadir:
            return self.get_and_lock(path, None, False, name)

        if path != mediadir.path:
            md = self.get_and_lock(path, None, False, name)
            mediadir.unlock()
            return md

        return mediadir


class MediaDir(models.Model):
    path = models.CharField(max_length=settings.PATH_MAX, unique=True, help_text='Path to import directory')
    locked_by_pid = models.IntegerField(default=-1, help_text='Process that locked this directory')
    locked_by_name = models.CharField(max_length=32, null=True,
                                      help_text='Subsystem that locked processing this directory')
    locked_at = models.DateTimeField(default=timezone.now(), help_text='Timestamp when this directory was locked')

    objects = MediaDirManager()

    def __str__(self):
        return self.path

    def natural_key(self):
        return self.path

    def lock(self, name=None):
        if not name:
            name = 'unspecified'
        self.locked_by_pid = os.getpid()
        self.locked_by_name = name
        self.locked_at = timezone.now()
        self.save()
        if settings.DEBUG_MD_LOCKING:
            sys.stderr.write('locking {} for {} pid {}\n'.format(self.path, name, self.locked_by_pid))

    def unlock(self):
        if settings.DEBUG_MD_LOCKING:
            sys.stderr.write('unlocking {} for {} pid {}\n'.format(self.path, self.locked_by_name, self.locked_by_pid))
        self.locked_by_pid = -1
        self.locked_by_name = None
        self.locked_at = timezone.now()
        self.save()

    def is_locked(self):
        if self.locked_by_pid == -1:
            return False

        if tools.process_dead(self.locked_by_pid):
            self.unlock()
            return False

        # we probably should check whether the process behind locked_by_pid is one of ours, but that might be
        # tricky.
        return True


class MediaFile(models.Model):
    media_dir = models.ForeignKey(MediaDir, null=True, help_text='Path to import directory')
    media_file = models.CharField(max_length=settings.NAME_MAX, null=True, help_text='Name of original file')
    sidecar_file = models.CharField(max_length=settings.NAME_MAX, null=True, help_text='Name of sidecar file')

    filename = models.CharField(max_length=settings.PATH_MAX, unique=True, help_text='Filename for export')
    mime_type = models.ForeignKey(MimeType, help_text='MIME type of the file',
                                  on_delete=models.SET(get_default_mime_type))

    date = models.DateTimeField(help_text='Creation date of the file')
    exposure_time = models.FloatField(blank=True, null=True, help_text='Exposure Time as a fraction')
    f_number = models.FloatField(blank=True, null=True, help_text='F-stop')
    gain_value = models.FloatField(blank=True, null=True, help_text='ISO speed or gain')
    focal_length = models.FloatField(blank=True, null=True, help_text='Focal length')

    catalog = models.ForeignKey(Catalog, help_text='Catalog for this file', on_delete=models.SET(get_default_catalog))
    rating = models.PositiveSmallIntegerField(default=0, blank=True, help_text='Star rating 0-5')
    label = models.CharField(default='None', blank=True, max_length=16, choices=LABELS, help_text='Color label')
    rejected = models.BooleanField(default=False, help_text='Do not export this file')

    tracker = FieldTracker(fields=['catalog', 'rejected', 'rating', 'label'])

    class Meta:
        unique_together = ('media_dir', 'media_file')
        permissions = (
            ("view_mediafile", "Can view media file"),
            ("move_mediafile", "Can move media file")
        )

    def __str__(self):
        return self.filename

    def __init__(self, *args, **kwargs):
        # logging.basicConfig(filename=settings.LOGFILE, level=settings.LOGLEVEL, format=settings.LOG_FORMAT)
        super(MediaFile, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        destdir = self.catalog.get_path()
        recreate_xmp = False

        if self.tracker.has_changed('catalog'):
            prev = self.tracker.previous('catalog')
            if prev:
                oldcatalog = Catalog.objects.get(id=prev)
                self.unlink_exports(oldcatalog)
            recreate_xmp = True
        elif self.tracker.has_changed('rejected'):
            if self.rejected:
                self.unlink_exports(self.catalog)
            else:
                recreate_xmp = True

        if self.tracker.has_changed('rating') or self.tracker.has_changed('label'):
            recreate_xmp = True

        if not self.rejected:
            if not os.path.isfile(destdir + self.filename):
                recreate_xmp = True
                self.link_exports()

            if recreate_xmp:
                self.create_xmp()

        super(MediaFile, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # note: this will NOT delete proxy files
        self.unlink_exports(self.catalog)
        super(MediaFile, self).delete(*args, **kwargs)

    def sidecar_source_full_path(self):
        return settings.SOURCE_DIR + self.media_dir.path + '/' + self.sidecar_file

    def media_source_full_path(self):
        return settings.SOURCE_DIR + self.media_dir.path + '/' + self.media_file

    def link_exports(self):
        destdir = self.catalog.get_path()
        logging.info('destdir is {}'.format(destdir))
        tools.mkdir(destdir)
        tools.link(self.media_source_full_path(), destdir + self.filename)
        sidecar = tools.get_sidecar_name(self.filename, self.sidecar_file)
        if sidecar:
            tools.link(self.sidecar_source_full_path(), destdir + sidecar)

    def unlink_exports(self, catalog):
        try:
            directory = catalog.get_path()
            for filename in (self.filename,
                            tools.get_sidecar_name(self.filename, self.sidecar_file),
                            tools.get_xmp_name(self.filename)):
                if filename and os.path.isfile(directory + filename):
                    os.unlink(directory + filename)
        except OSError:
            pass

    # granted, this is business logic and doesn't really belong here, but...
    def create_xmp(self):
        if not self.sidecar_file:
            return

        if not self.mime_type.type.split('/')[0] in ('image', 'video'):
            return

        exif = GExiv2.Metadata()
        exif.open_path(self.sidecar_source_full_path())
        sidecar_label = exif.get_tag_interpreted_string('Xmp.xmp.Label')
        sidecar_rating = exif.get_tag_long('Xmp.xmp.Label')

        sidecar_is_xmp = tools.sidecar_is_xmp(self.sidecar_file)
        xmpfile = self.catalog.get_path() + tools.get_xmp_name(self.filename)
        if sidecar_is_xmp:
            try:
                os.unlink(xmpfile)
            except:
                pass

            if (not self.rating or self.rating == sidecar_rating) and (not self.label or self.label == sidecar_label):
                os.link(self.sidecar_source_full_path(), xmpfile)
                return

        try:
            fd = open(xmpfile, 'w')
            fd.write('<?xml version="1.0" encoding="UTF-8"?><x:xmpmeta xmlns:x="adobe:ns:meta/"></x:xmpmeta>')
            fd.close()
        except IOError as e:
            logging.error('Cannot create {}: {}'.format(xmpfile, e.message))
            return

        exif.register_xmp_namespace('http://ns.adobe.com/xap/1.0/', 'xmp')
        exif.set_tag_string('Xmp.xmp.Label', self.label.__str__())
        exif.set_tag_string('Xmp.xmp.Rating', self.rating.__str__())
        exif.save_file(xmpfile)


class ProgressStatus(models.Model):
    name = models.CharField(max_length=32, unique=True, help_text="Name of this status")
    running = models.BooleanField(default=False, help_text="Operation running")
    text = models.CharField(max_length=settings.PATH_MAX, null=True, blank=True,
                            help_text="Text associated with the status")
    progress = models.IntegerField(default=0, help_text="Progress in percent")
    total_items = models.BigIntegerField(default=0, help_text="Total number of items")
    current_item = models.BigIntegerField(default=0, help_text="Current item number")
    filename = models.CharField(max_length=settings.NAME_MAX, null=True, blank=True, help_text="Filename operating on")
    directory = models.ForeignKey(MediaDir, null=True, help_text="Directory operating on")
    timestamp = models.DateTimeField(default=timezone.now())

    def __init__(self, *args, **kwargs):
        super(ProgressStatus, self).__init__(*args, **kwargs)

    def __str__(self):
        if self.running:
            return "{} running at {}%".format(self.name, self.progress)
        else:
            return "{} not running"

    def natural_key(self):
        return self.name