from django.conf import settings
import os
from pwd import getpwnam
from grp import getgrnam
from sys import stderr

class toolbox:
    @staticmethod
    def www_user():
        for username in ('wwwrun', 'www-data', 'www', 'apache', 'httpd'):
            try:
                pw=getpwnam(username)
                return pw.pw_uid
            except:
                pass
        return getpwnam('nobody').pw_uid

    @staticmethod
    def www_group():
        for groupname in ('www', 'www-data', 'apache', 'httpd'):
            try:
                gr=getgrnam(groupname)
                return gr.gr_gid
            except:
                pass
        return getgrnam('nogroup').gr_gid

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
            os.chown(path, settings.WWWUSER, settings.WWWGROUP)
            os.chmod(path, 0755)
        except (KeyError, OSError) as e:
            stderr.write('Warning: cannot change owner / group of {}: {}'.format(path, e.message))

    @staticmethod
    def link(source, dest):
        try:
            os.unlink(dest)
        except OSError:
            pass

        try:
            os.link(source, dest)
            return
        except OSError:
            pass

        try:
            os.symlink(source, dest)
            return
        except OSError:
            # probably should try copying
            pass

    @staticmethod
    def get_extension(path):
        try:
            return os.path.splitext(path.__str__())[1].lower()
        except:
            return None

    @staticmethod
    def get_basename(path):
        return os.path.splitext(path.__str__())[0]

    @staticmethod
    def sidecar_is_xmp(path):
        return  toolbox.get_extension(path) == '.xmp'

    @staticmethod
    def get_sidecar_name(mediafilename, path):
        if not path:
            return None

        ext=toolbox.get_extension(path)
        if ext == '.xmp':
            return None

        filename=toolbox.get_basename(mediafilename)+ext
        return filename

    @staticmethod
    def get_xmp_name(mediafilename):
        filename=toolbox.get_basename(mediafilename)+'.xmp'
        return filename
