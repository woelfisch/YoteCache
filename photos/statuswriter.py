from django.conf import settings
import os
import logging
import json

class StatusWriter:
    filename = None
    statusfilename = None

    def __init__(self, statusfilename, filename, text=None):
        if not os.path.isdir(settings.STATUS_DIR):
            toolbox.mkdir(settings.STATUS_DIR)

        self.statusfilename = statusfilename
        self.filename = os.path.basename(filename)
        self.update(progress=0, text=text)

    def update(self, progress=None, text=None):
        statusdict={'running': True, 'filename': self.filename}
        if progress is not None:
            statusdict['progress'] = progress
        if text:
            statusdict['text'] = text

        self.write_status(statusdict)

    def error(self, text=None):
        if text is None:
            text='Error'
        else:
            text='Error: {}'.format(text)
        self.update(progress=100, text=text)

    def close(self):
        self.filename=None
        self.write_status({'running': False})

    def write_status(self, statusdict):
        try:
            fd=open(settings.STATUS_DIR+self.statusfilename, mode='w')
            json.dump(statusdict, fd)
            fd.close()
        except Exception as e:
            raise e
