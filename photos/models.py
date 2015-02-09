import os
import os.path
import logging
from django.db import models
from django.conf import settings
from model_utils import FieldTracker
from tools import toolbox
from gi.repository import GExiv2

LABELS = [
    ('None', 'None'),
    ('Red', 'Red'),
    ('Yellow', 'Yellow'),
    ('Green', 'Green'),
    ('Blue', 'Blue'),
    ('Purple', 'Purple'),
]

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
        toolbox.mkdir(self.get_path())

    def delete(self, *args, **kwargs):
        uncataloged, created=Catalog.objects.get_or_create(name=settings.DEFAULT_CATALOG)
        for mediafile in MediaFile.objects.filter(catalog=self):
            mediafile.catalog=uncataloged
            mediafile.save()
        try:
            os.rmdir(self.get_path())
        except Exception as e:
            pass

        super(Catalog, self).delete(*args, **kwargs)

    def get_path(self):
        return settings.EXPORT_DIR+self.name+'/'

class MimeTypeManager(models.Manager):
    def get_by_natural_key(self, mime_type):
        return self.get(mime_type=mime_type)

class MimeType(models.Model):
    type = models.CharField(max_length=256, unique=True, help_text='MIME type')
    hide = models.BooleanField(default=False, help_text='Hide this type of content in frontend')
    copy = models.BooleanField(default=True, help_text='Export this type of content')

    objects = MimeTypeManager()

    def __str__(self):
        return self.type

    def natural_key(self):
        return self.type

    def delete(self, *args, **kwargs):
        unknowntype, created = MimeType.objects.get_or_create(type=settings.UNKOWN_MIME_TYPE)
        for mediafile in MediaFile.objects.filter(mime_type = self.type):
            mediafile.mime_type=unknowntype
        super(MimeType, self).delete(*args, **kwargs)

class MediaFile(models.Model):
    mediafile_path = models.CharField(max_length=settings.MAX_PATH, unique=True, help_text='Path to original file')
    sidecar_path = models.CharField(max_length=settings.MAX_PATH, null=True, blank=True, help_text='Path to sidecar file')
    filename = models.CharField(max_length=settings.MAX_PATH, unique=True, help_text='Filename for export')
    mime_type = models.ForeignKey(MimeType, help_text='MIME type of the file')

    date = models.DateTimeField(help_text='Creation date of the file')
    exposure_time = models.FloatField(blank=True, null=True, help_text='Exposure Time as a fraction')
    f_number = models.FloatField(blank=True, null=True, help_text='F-stop')
    gain_value = models.FloatField(blank=True, null=True, help_text='ISO speed or gain')
    focal_length = models.FloatField(blank=True, null=True, help_text='Focal length')

    catalog = models.ForeignKey(Catalog, help_text='Catalog for this file')
    rating = models.PositiveSmallIntegerField(default=0, blank=True, help_text='Star rating 0-5')
    label = models.CharField(default='None', blank=True, max_length=16, choices=LABELS, help_text='Color label')
    rejected = models.BooleanField(default=False, help_text='Do not export this file')

    tracker = FieldTracker(fields=['catalog', 'rejected', 'rating', 'label'])

    def __str__(self):
        return self.filename

    def __init__(self, *args, **kwargs):
        # logging.basicConfig(filename=settings.LOGFILE, level=settings.LOGLEVEL, format=settings.LOG_FORMAT)
        super(MediaFile, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        destdir=self.catalog.get_path()
        recreate_xmp = False

        if self.tracker.has_changed('catalog'):
            prev=self.tracker.previous('catalog')
            if prev:
                oldcatalog=Catalog.objects.get(id=prev)
                self.unlink_exports(oldcatalog)
            recreate_xmp=True
        elif self.tracker.has_changed('rejected'):
            if self.rejected:
                self.unlink_exports(self.catalog)
            else:
                recreate_xmp=True

        if self.tracker.has_changed('rating') or self.tracker.has_changed('label'):
            recreate_xmp=True

        if not self.rejected:
            if not os.path.isfile(destdir+self.filename):
                recreate_xmp=True
                self.link_exports()

            if recreate_xmp:
                self.create_xmp()

        super(MediaFile, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # note: this will NOT delete proxy files
        self.unlink_exports(self.catalog)
        super(MediaFile, self).delete(*args, **kwargs)

    def link_exports(self):
        destdir=self.catalog.get_path()
        logging.info('destdir is {}'.format(destdir))
        toolbox.mkdir(destdir)
        toolbox.link(settings.SOURCE_DIR+self.mediafile_path, destdir+self.filename)
        sidecar=toolbox.get_sidecar_name(self.filename, self.sidecar_path)
        if sidecar:
            toolbox.link(settings.SOURCE_DIR+self.sidecar_path, destdir+sidecar)

    def unlink_exports(self, catalog):
        try:
            dir=catalog.get_path()
            for filename in (self.filename,
                             toolbox.get_sidecar_name(self.filename, self.sidecar_path),
                             toolbox.get_xmp_name(self.filename)):
                if filename and os.path.isfile(dir+filename):
                    os.unlink(dir+filename)
        except OSError:
            pass

    # granted, this is business logic and doesn't really belong here, but...
    def create_xmp(self):
        if not self.sidecar_path:
            return

        if not self.mime_type.type.split('/')[0] in ('image', 'video'):
            return

        exif=GExiv2.Metadata()
        exif.open_path(settings.SOURCE_DIR+self.sidecar_path)
        sidecar_label=exif.get_tag_interpreted_string('Xmp.xmp.Label')
        sidecar_rating=exif.get_tag_long('Xmp.xmp.Label')

        sidecar_is_xmp=toolbox.sidecar_is_xmp(self.sidecar_path)
        xmpfile=self.catalog.get_path()+toolbox.get_xmp_name(self.filename)
        if sidecar_is_xmp:
            try:
                os.unlink(xmpfile)
            except:
                pass

            if (not self.rating or self.rating == sidecar_rating) and (not self.label or self.label == sidecar_label):
                os.link(settings.SOURCE_DIR+self.sidecar_path, xmpfile)
                return

        try:
            fd=open(xmpfile, 'w')
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
    text = models.CharField(max_length=settings.MAX_PATH, null=True, blank=True, help_text="Text associated with the status")
    progress = models.IntegerField(default=0, help_text="Progress in percent")
    total_items = models.BigIntegerField(default=0, help_text="Total number of items")
    current_item = models.BigIntegerField(default=0, help_text="Current item number")
    filename = models.CharField(max_length=settings.MAX_PATH, null=True, blank=True, help_text="Filename operating on")
    directory = models.CharField(max_length=settings.MAX_PATH, null=True, blank=True, help_text="Directory operating on")

    def __init__(self, *args, **kwargs):
        super(ProgressStatus, self).__init__(*args, **kwargs)

    def __str__(self):
        if self.running:
            return "{} running at {}%".format(self.name, self.progress)
        else:
            return "{} not running"

    def natural_key(self):
        return self.name