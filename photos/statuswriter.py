import os
import logging
import json
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from tools import toolbox
from photos.models import ProgressStatus


class StatusWriter:
    filename = None
    dirname = None
    statusname = None
    total_items = 1
    items = 0
    status = None  # ProgressStatus instances

    def __init__(self, statusname, filename=None, dirname=None, text=None):
        if settings.STATUS_USE_FILE:
            if not os.path.isdir(settings.STATUS_DIR):
                toolbox.mkdir(settings.STATUS_DIR)
        else:
            ProgressStatus.objects.get_or_create(name=statusname)
            self.status = ProgressStatus.objects.filter(name=statusname)

        self.statusname = statusname

        if filename:
            self.filename = os.path.basename(filename)

        if dirname:
            self.dirname = dirname

        self.update(progress=0, text=text)

    def update(self, progress=None, text=None):
        statusdict = {'running': True, 'filename': self.filename}
        if progress is not None:
            statusdict['progress'] = progress
        if text:
            statusdict['text'] = text

        self.write_status(statusdict)

    def update_filecopy(self, filename):
        self.items += 1
        statusdict = {'running': True,
                      'directory': self.dirname,
                      'filename': filename,
                      'current_item': self.items,
                      'total_items': self.total_items,
                      'progress': int((self.items * 100) / self.total_items)}
        self.write_status(statusdict)

    def error(self, text=None):
        if text is None:
            text = 'Error'
        else:
            text = 'Error: {}'.format(text)
        self.update(progress=100, text=text)

    def close(self):
        self.filename = None
        self.write_status({'running': False})

    def write_status(self, statusdict):
        statusdict['timestamp'] = timezone.now()
        if settings.STATUS_USE_FILE:
            try:
                fd = open(settings.STATUS_DIR + self.statusname, mode='w')
                json.dump(statusdict, fd)
                fd.close()
            except Exception as e:
                raise e
        else:
            try:
                self.status.update(**statusdict)
            except Exception as e:
                print("{}".format(e.message))
                raise e

