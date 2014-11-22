from django.conf import settings
import os
from pwd import getpwnam
from grp import getgrnam
from sys import stderr

class toolbox:
    @staticmethod
    def mkdir(path):
        try:
            os.makedirs(path)
        except OSError as e:
            if os.path.isdir(path):
                pass
            else:
                stderr.write('Error: cannot create directory {}: {}'.format(path, e.message))
                raise e
        try:
            os.chown(path, getpwnam(settings.WWWUSER).pw_uid, getgrnam(settings.WWWGROUP).gr_gid)
            os.chmod(path, 0755)
        except (KeyError, OSError) as e:
            stderr.write('Warning: cannot change owner / group of {}: {}'.format(path, e.message))
