from optparse import make_option
import sys
import os
import os.path
import logging

from subprocess import check_output, check_call
from dateutil import tz
from uuid import uuid4
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from photos.tools import toolbox
from photos.statuswriter import StatusWriter

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
                    help='Use PTP mode'),
    )

    # source stuff

    def mk_dos_uuid(self):
        uuid = uuid4().fields
        # 32 bit of random data should be enough to avoid collisions
        return '{:04X}-{:04X}'.format(uuid[1], uuid[2])

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
        try:
            timestruct = tz.time.gmtime(int(os.path.getctime(self.dcim_directory)))
            # anything older means that the clock of the camera hasn't been set.
            if timestruct.tm_year < 2000:
                raise
        except:
            # in that case (or the stat() above fails...) use the current time
            timestruct = tz.time.gmtime()

        return tz.time.strftime("%Y-%m-%d", timestruct)

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

    # copy stuff

    def check_if_same_file(self, source, destination):
        try:
            ctime_dest = os.path.getctime(destination)
            tm_dest = tz.time.gmtime(int(ctime_dest))
            if tm_dest.tm_year < 2000:
                # camera time not set?
                return False
        except:
            return False

        ctime_src = os.path.getctime(source)
        tm_src = tz.time.gmtime(int(ctime_src))
        if tm_src.tm_year < 2000:
            # camera time not set?
            return False

        # DOS timestamps have a resolution of 2 seconds.
        return abs(ctime_src - ctime_src) < 4

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

        status.total_items = filenumber
        logging.debug('get_file_list(): found {} files to copy'.format(filenumber))
        return filelist

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

        try:
            check_call(['/bin/cp', '-p', name, destpath])
        except:
            logging.error('copy_file: ', exc_info=True)
            pass

        print destpath

    def copy(self):
        '''
        Copies metadata before actual content for import_photo to have it available
        :return:None
        '''

        self.status=StatusWriter(statusfilename=settings.IMPORT_STATUS,
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


    def handle(self, *args, **options):
        logging.basicConfig(filename=settings.LOGFILE, level=settings.LOGLEVEL, format=settings.LOG_FORMAT)
        self.card_directory = options['card_directory']
        self.card_device = options['card_device']

        if not self.card_directory:
            raise CommandError('Missing mount point parameter')
        if not self.card_device:
            raise CommandError('Missing device node parameter')

        self.dcim_directory=self.card_directory+'/DCIM'
        self.status=StatusWriter(settings.IMPORT_STATUS, )

        try:
            self.importbase=settings.SOURCE_DIR+self.get_card_info()
        except:
            logging.error('Copy_Card: ', exc_info=True)
            return

        self.copy()

