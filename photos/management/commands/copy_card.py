from optparse import make_option
import re
import sys
import os
import os.path
import time
import logging
import gphoto2 as gp    # that's gphoto2-cffi, not the SWIG based one!

from subprocess import check_output, check_call
from dateutil import tz
from datetime import datetime
from uuid import uuid4
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from photos.tools import toolbox
from photos.statuswriter import StatusWriter

class GenericCopyFramework(object):
    _framework = 'generic'

    def sanitze_filename(self, name):
        # not sure if gphoto2 guarantees safe filenames, better safe than sorry.
        return re.sub('[\s/\\\\:]', '_', name)

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

    def check_if_same_file(self, source, dest):
        return False

    def mk_unique_name(self, source, path):
        dir = os.path.dirname(path)
        fn = os.path.basename(path)
        count = 1

        while os.path.isfile(path):
            if self.check_if_same_file(source, path):
                return None

            path = dir + '/{:04d}-{}'.format(count, fn)
            count += 1
            # goddammit robin!
            # DCIM allows a maximum of 9999 files per folder
            # the outer loops allows 10000 name collissions
            # if the inner loop keeps colliding, too, something is terribly wrong.
            while count > 9999 and os.path.isfile(path):
                path = dir + '/{}-{}'.format(base64.urlsafe_b64encode(uuid4().bytes)[:10], fn)
                if self.check_if_same_file(source, path):
                    return None

        return path

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

        self.status.update(text=' ')
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

        self.status.update(text='Done')
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
        (timestruct, valid) = self.get_mtime(self.dcim_folder)
        return tz.time.strftime("%Y-%m-%d", timestruct)

    # copy stuff

    def check_if_same_file(self, source, destination):
        (mtime_dest, valid) = self.get_mtime(destination)
        if not valid:
            return False

        (mtime_src, valid) = self.get_mtime(source)
        if not valid:
            return False

        dt = datetime(*mtime_dest[:6]) - datetime(*mtime_src[:6])
        return abs(dt.total_seconds()) < 2

    def get_file_list(self):
        filelist = {}
        filenumber = 0

        for root, dirs, files in os.walk(self.dcim_folder):
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
        self.status.update_filecopy(name)

        # needs to print path of imported file to console to pipe into import_photo
        destpath=self.mk_unique_name(name, self.importbase+'/'+os.path.relpath(name, self.dcim_folder))
        if not destpath:
            logging.debug('File {} already exists'.format(name))
            return

        destdir=os.path.dirname(destpath)
        toolbox.mkdir(destdir)

        logging.info('Copying file {}'.format(name))

        try:
            check_call(['/bin/cp', '-p', name, destpath])
        except:
            logging.error('copy_file: ', exc_info=True)
            pass

        print(destpath)
        sys.stdout.flush()

    def __init__(self, card_folder, card_device):
        if not card_folder:
            raise CommandError('Missing mount point parameter')
        if not card_device:
            raise CommandError('Missing device node parameter')

        self.card_device=card_device
        self.dcim_folder=card_folder+'/DCIM'
        self.status=StatusWriter(settings.IMPORT_STATUS)
        self.importbase=settings.SOURCE_DIR+self.get_card_info()

CopyPTP = None
def ptpimplementation(obj):
    '''
    :param obj: PTP copy class
    :return: obj for chaining
    Unfortunately, both the SWIG and the FFI based python bindings for libgphoto2 have the same name ("gphoto2"),
    the SWIG one is actively maintained but has some strict dependencies to other parts of the framework, the
    FFI based implementation seems to be stable but disconnects from the camera after each operation (slow)
    and isn't exactly well maintained...
    '''
    global CopyPTP

    logging.basicConfig(filename=settings.LOGFILE, level=settings.LOGLEVEL, format=settings.LOG_FORMAT)
    if obj._framework == 'swig' and hasattr(gp, 'Context'):
        logging.debug('using SWIG bindings for gphoto2')
        CopyPTP = obj
    if obj._framework == 'ffi' and hasattr(gp, 'backend') and hasattr(gp.backend, 'ffi'):
        logging.debug('using FFI bindings for gphoto2')
        CopyPTP = obj

    return obj

@ptpimplementation
class _CopyPTP(GenericCopyFramework):
    '''
        gphoto2-cffi operates on object representations instead of (virtual) path names, so we have to
        replicate all the crap from above again without being able to reuse much of it. OOP my arse.
    '''

    _framework = 'ffi'

    def get_camera_info(self):
        self.stores = []
        try:
            manufacturer = self.sanitze_filename(self.camera.status.manufacturer)
        except:
            manufacturer = 'OEM'

        try:
            model = self.sanitze_filename(self.camera.status.cameramodel)
        except:
            model = 'Camera'

        try:
            serial_number = self.sanitze_filename(self.camera.status.serialnumber)
        except:
            serial_number = '00000042'

        for volume in self.camera.storage_info:
            self.stores.append((volume.directory, '-'.join((model, serial_number, volume.directory.path[7:]))))


    def check_if_same_file(self, source, destination):
        (mtime_dest, valid) = self.get_mtime(destination)
        if not valid:
            return False


        mtime_src = source.last_modified
        if mtime_src.year < 2000:
            return False

        dt = datetime(*mtime_dest[:6]) - mtime_src
        if abs(dt.total_seconds()) > 1:
            return False

        try:
            s1 = os.path.getsize(destination)
            s2 = source.size
            return s2 == s1
        except:
            return False

    def get_file_list(self, base_folder):
        filelist = {}
        filenumber = 0

        for folder in base_folder.directories:
            folder_name = os.path.basename(folder.path)
            if folder_name[:3].isdigit() or folder_name.lower() == 'camera':
                filenumber+=len(tuple(folder.files))
                for f in folder.files:
                    name, ext = os.path.splitext(f.name)
                    if name not in filelist:
                        filelist[name] = [f]
                    else:
                        filelist[name].append(f)

        self.status.total_items = filenumber
        logging.debug('get_file_list(): found {} files to copy'.format(filenumber))
        return filelist

    def copy_file(self, import_base, file_obj):
        name = file_obj.name
        path = file_obj.directory.path
        self.status.update_filecopy(name)

        destpath = self.mk_unique_name(file_obj, '/'.join((import_base, file_obj.directory.path.split('/')[-1], self.sanitze_filename(name))))
        if not destpath:
            logging.debug('File {} already exists'.format(name))
            return

        destdir=os.path.dirname(destpath)
        toolbox.mkdir(destdir)

        logging.info('Copying file {}'.format(name))
        try:
            file_obj.save(destpath)
            mtime = time.mktime(file_obj.last_modified.timetuple())
            os.utime(destpath, (mtime, mtime))
        except Exception as e:
            logging.warning("Cannot copy {} to {}: {}".format(name, destpath, e.message))

        print(destpath)
        sys.stdout.flush()


    def copy_volume(self, import_base, folder):
        self.status=StatusWriter(statusname=settings.IMPORT_STATUS,
                                 dirname=os.path.relpath(import_base, settings.SOURCE_DIR),
                                 text='Start')

        filelist = self.get_file_list(folder)
        basenames = filelist.keys()
        basenames.sort()

        self.status.update(text=' ')
        for name in basenames:
            file_obj = filelist[name]
            remaining = []
            for f in file_obj:
                if os.path.splitext(f.name)[1].lower() in settings.METADATA_EXTENSIONS:
                    self.copy_file(import_base, f)
                    continue
                remaining.append(f)
            for f in remaining:
                self.copy_file(import_base, f)

        self.status.update(text='Done')
        self.status.close()

    def copy(self):
        for folder, import_base in self.stores:
            for dcim_candidate in folder.directories:
                if dcim_candidate.path.endswith('/DCIM'):
                    self.copy_volume(settings.SOURCE_DIR+import_base, dcim_candidate)


    def __init__(self):
        self.status=StatusWriter(settings.IMPORT_STATUS)
        self.camera = gp.Camera()
        self.get_camera_info()

@ptpimplementation
class _CopyPTP(GenericCopyFramework):
    _framework = 'swig'

    def get_camera_info(self):
        self.stores = []
        manufacturer = 'OEM'
        model = 'Camera'
        serial_number = '0000000000000042'
        summary = self.camera.get_summary(self.context).text
        for t in summary.splitlines():
            if t.startswith('Manufacturer:'):
                manufacturer = self.sanitze_filename(t[14:])
            if t.startswith('Model:'):
                model = self.sanitze_filename(t[7:])
            if t.startswith('  Serial Number:'):
                serial_number = self.sanitze_filename(t[17:])
            if t.startswith('store_') and t[-1] == ':':
                # store_%08x is generated by gphoto2, thus safe.
                self.stores.append(('/'+t[:-1], '-'.join((model, serial_number, t[6:-1]))))

    def check_if_same_file(self, source, destination):
        (mtime_dest, valid) = self.get_mtime(destination)
        if not valid:
            return False

        folder, filename = os.path.split(source)
        try:
            file_info = self.camera.file_get_info(folder, filename, self.context)
        except gp.GPhoto2Error as e:
            return False

        mtime_src = tz.time.gmtime(int(file_info.file.mtime))
        if mtime_src.tm_year < 2000:
            return False

        dt = datetime(*mtime_dest[:6]) - datetime(*mtime_src[:6])
        if abs(dt.total_seconds()) > 1:
            return False

        try:
            s1 = os.path.getsize(destination)
            s2 = file_info.file.size
            return s2 == s1
        except:
            return False


    def get_file_list(self):
        filelist = {}
        filenumber = 0

        # print self.importbase, self.dcim_folder
        for folder, value in self.camera.folder_list_folders(self.dcim_folder, self.context):
            if folder[:3].isdigit() or folder.lower() == 'camera':
                files = self.camera.folder_list_files(self.dcim_folder+'/'+folder, self.context)
                filenumber+=len(files)
                for f, v in files:
                    name, ext = os.path.splitext(self.dcim_folder + '/' + folder + '/' + f)
                    if name not in filelist:
                        filelist[name] = [ext]
                    else:
                        filelist[name].append(ext)

        self.status.total_items = filenumber
        logging.debug('get_file_list(): found {} files to copy'.format(filenumber))
        return filelist

    def copy_file(self, name):
        self.status.update_filecopy(name)

        # needs to print path of imported file to console to pipe into import_photo
        destpath=self.mk_unique_name(name, self.importbase+'/'+os.path.relpath(name, self.dcim_folder))
        if not destpath:
            logging.debug('File {} already exists'.format(name))
            return

        destdir=os.path.dirname(destpath)
        toolbox.mkdir(destdir)

        logging.info('Copying file {}'.format(name))

        # hurrdurrderp
        folder, filename = os.path.split(name)
        try:
            the_file = self.camera.file_get(folder, filename, gp.GP_FILE_TYPE_NORMAL, self.context)
            the_file.save(destpath)
        except gp.GPhoto2Error as e:
            logging.warning("Cannot copy {} to {}: {}".format(filename, destpath, e.string))

        print(destpath)
        sys.stdout.flush()
        return destpath

    def copy(self):
        for folder, import_base in self.stores:
            self.importbase = settings.SOURCE_DIR+import_base
            self.dcim_folder = folder+'/DCIM'
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
                    dest='card_folder',
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
                obj=CopyFlash(options['card_folder'], options['card_device'])

            obj.copy()
        except:
            logging.error('Copy_Card: ', exc_info=True)
            return