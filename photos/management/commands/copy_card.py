from optparse import make_option
import re
import sys
import os
import os.path
import logging
import gphoto2 as gp

from subprocess import check_output, check_call
from dateutil import tz
from datetime import datetime
from uuid import uuid4
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from photos.tools import toolbox
from photos.statuswriter import StatusWriter

class GenericCopyFramework(object):
    def get_mtime(self, path):
        try:
            timestruct = tz.time.gmtime(int(os.path.getmtime(path)))
            # anything older means that the clock of the camera hasn't been set.
            if timestruct.tm_year < 2000:
                raise
            return (timestruct, True)
        except:
            # in that case (or the stat() above fails...) use the current time
            return (tz.time.gmtime(), False)

    def mk_dos_uuid(self):
        uuid = uuid4().fields
        # 32 bit of random data should be enough to avoid collisions
        return '{:04X}-{:04X}'.format(uuid[1], uuid[2])

    def mk_unique_name(self, path):
        dir = os.path.dirname(path)
        fn = os.path.basename(path)
        count = 1

        while os.path.isfile(path):
            path = dir + '/{:04d}-{}'.format(count, fn)
            count += 1
            # goddammit robin!
            # DCIM allows a maximum of 9999 files per directory
            # the outer loops allows 10000 name collissions
            # if the inner loop keeps colliding, too, something is terribly wrong.
            while count > 9999 and os.path.isfile(path):
                path = dir + '/{}-{}'.format(base64.urlsafe_b64encode(uuid4().bytes)[:10], fn)

        return path

    def copy_file(self, name):
        self.status.update_filecopy(name)

        # needs to print path of imported file to console to pipe into import_photo
        destpath=self.importbase+'/'+os.path.relpath(name, self.dcim_directory)

        if self.check_if_same_file(name, destpath):
            logging.debug('Files {} and {} are the same'.format(name, destpath))
            return

        logging.info('Copying file {}'.format(name))

        destpath=self.mk_unique_name(destpath)
        destdir=os.path.dirname(destpath)
        toolbox.mkdir(destdir)

        return destpath

    def copy(self):
        '''
        Copies metadata before actual content for import_photo to have it available
        :return:None
        '''

        self.status=StatusWriter(statusname=settings.IMPORT_STATUS,
                                 dirname=os.path.relpath(self.importbase, settings.SOURCE_DIR),
                                 text='Start')

        filelist = self.get_file_list()
        basenames = filelist.keys()
        basenames.sort()

        for name in basenames:
            extensions = filelist[name]
            remaining = []
            for e in extensions:
                if e.lower() in settings.METADATA_EXTENSIONS:
                    self.copy_file(name + e)
                    continue
                remaining.append(e)
            for e in remaining:
                self.copy_file(name + e)

        self.status.close()



class CopyFlash(GenericCopyFramework):
    # source stuff
    def get_card_info(self):
        blkid = {}

        for line in check_output(['blkid', '-o', 'export', self.card_device]).splitlines():
            arg, value = line.split('=')
            blkid[arg] = value

        if not 'LABEL' in blkid and not 'UUID' in blkid:
            return self.mk_dirname()

        if not 'UUID' in blkid:
            blkid['UUID'] = self.mk_dos_uuid()

        if 'LABEL' in blkid:
            destdir = blkid['LABEL'] + '-'
        else:
            destdir = ''

        return destdir + blkid['UUID']

    # destination stuff

    def mk_dirname(self):
        (timestruct, valid) = self.get_mtime(self.dcim_directory)
        return tz.time.strftime("%Y-%m-%d", timestruct)

    # copy stuff

    def check_if_same_file(self, source, destination):
        (mtime_dest, valid) = self.get_mtime(destination)
        if not valid:
            return False

        (mtime_src, valid) = self.get_mtime(source)
        if not valid:
            return False

        # FAT timestamps have a resolution of 2 seconds.
        dt = datetime(*mtime_dest[:6]) - datetime(*mtime_src[:6])
        return abs(dt.total_seconds()) < 4

    def get_file_list(self):
        filelist = {}
        filenumber = 0

        for root, dirs, files in os.walk(self.dcim_directory):
            root_basename=os.path.basename(root)
            if root_basename[:3].isdigit():
                filenumber+=len(files)
                for f in files:
                    name, ext = os.path.splitext(root + '/' + f)
                    if name not in filelist:
                        filelist[name] = [ext]
                    else:
                        filelist[name].append(ext)

        self.status.total_items = filenumber
        logging.debug('get_file_list(): found {} files to copy'.format(filenumber))
        return filelist

    def copy_file(self, name):
        destpath = super(CopyFlash, self).copy_file(name)

        try:
            check_call(['/bin/cp', '-p', name, destpath])
        except:
            logging.error('copy_file: ', exc_info=True)
            pass

        print destpath

        return destpath

    def __init__(self, card_directory, card_device):
        if not card_directory:
            raise CommandError('Missing mount point parameter')
        if not card_device:
            raise CommandError('Missing device node parameter')

        self.card_device=card_device
        self.dcim_directory=card_directory+'/DCIM'
        self.status=StatusWriter(settings.IMPORT_STATUS)
        self.importbase=settings.SOURCE_DIR+self.get_card_info()


class CopyPTP(GenericCopyFramework):
    def get_camera_info(self):
        def sd(s):
            return re.sub('[\s/:]', '_', s)

        self.stores = []
        manufacturer = 'OEM'
        model = 'Camera'
        serial_number = '0000000000000042'
        summary = self.camera.get_summary(self.context).text
        for t in summary.splitlines():
            if t.startswith('Manufacturer:'):
                manufacturer = sd(t[14:])
            if t.startswith('Model:'):
                model = sd(t[7:])
            if t.startswith('  Serial Number:'):
                serial_number = sd(t[17:])
            if t.startswith('store_') and t[-1] == ':':
                t=re.sub('/', '', t[:-1])
                self.stores.append(('/'+t, '-'.join((model, serial_number, t[6:]))))

    def check_if_same_file(self, source, destination):
        (mtime_dest, valid) = self.get_mtime(destination)
        if not valid:
            return False

        #(mtime_src, valid) = self.get_mtime(source)
        #if not valid:
        #    return False

        # FAT timestamps have a resolution of 2 seconds.
        # dt = datetime(*mtime_dest[:6]) - datetime(*mtime_src[:6])
        # return abs(dt.total_seconds()) < 4

        return False

    def get_file_list(self):
        filelist = {}
        filenumber = 0

        # print self.importbase, self.dcim_directory
        for directory, value in self.camera.folder_list_folders(self.dcim_directory, self.context):
            if directory[:3].isdigit() or directory.lower() == 'camera':
                files = self.camera.folder_list_files(self.dcim_directory+'/'+directory, self.context)
                filenumber+=len(files)
                for f, v in files:
                    name, ext = os.path.splitext(self.dcim_directory + '/' + directory + '/' + f)
                    if name not in filelist:
                        filelist[name] = [ext]
                    else:
                        filelist[name].append(ext)

        self.status.total_items = filenumber
        logging.debug('get_file_list(): found {} files to copy'.format(filenumber))
        return filelist

    def copy_file(self, name):
        destpath = super(CopyPTP, self).copy_file(name)

        print destpath
        return destpath

    def copy(self):
        for directory, import_base in self.stores:
            self.importbase = settings.SOURCE_DIR+import_base
            self.dcim_directory = directory+'/DCIM'
            super(CopyPTP, self).copy()


    def __init__(self):
        self.status=StatusWriter(settings.IMPORT_STATUS)
        self.context = gp.Context()
        self.camera = gp.Camera()
        self.get_camera_info()



class Command(BaseCommand):
    """
    Copy photos from card to storage
    """
    option_list = BaseCommand.option_list + (
        make_option('-m', '--mountpoint',
                    dest='card_directory',
                    default=os.getenv('UM_MOUNTPOINT'),
                    help='Mount point of media card'),
        make_option('-d', '--device',
                    dest='card_device',
                    default=os.getenv('UM_DEVICE'),
                    help='Device node of media card'),
        make_option('-p', '--ptp',
                    dest='ptp_mode',
                    default=False,
                    action="store_true",
                    help='Use PTP mode'),
    )

    def handle(self, *args, **options):
        logging.basicConfig(filename=settings.LOGFILE, level=settings.LOGLEVEL, format=settings.LOG_FORMAT)

        try:
            if options['ptp_mode']:
                obj=CopyPTP()
            else:
                obj=CopyFlash(options['card_directory'], options['card_device'])

            obj.copy()
        except:
            logging.error('Copy_Card: ', exc_info=True)
            return