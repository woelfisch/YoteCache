from django.conf import settings
import os
import logging
from pwd import getpwnam
from grp import getgrnam


class toolbox:
    @staticmethod
    def www_user():
        for username in ('wwwrun', 'www-data', 'www', 'apache', 'httpd'):
            try:
                pw = getpwnam(username)
                return pw.pw_uid
            except:
                pass
        return getpwnam('nobody').pw_uid

    @staticmethod
    def www_group():
        for groupname in ('www', 'www-data', 'apache', 'httpd'):
            try:
                gr = getgrnam(groupname)
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
                logging.error('Cannot create directory {}: {}'.format(path, e.args[0]))
                raise e
        try:
            os.chown(path, settings.WWWUSER, settings.WWWGROUP)
            os.chmod(path, 0755)
        except (KeyError, OSError) as e:
            logging.warning('Cannot change owner / group of {}: {}'.format(path, e.args[0]))

    @staticmethod
    def is_in_path(filename):
        # this doesn't take the pathological case of path elements containing quoted colons into account...
        for directory in os.environ['PATH'].split(':'):
            if os.path.isfile(directory + '/' + filename):
                return True
        return False

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
        except OSError as e:
            # probably should try copying
            logging.error('cannot link {} to {}: {}'.format(source, dest, e.args[0]))
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
        return toolbox.get_extension(path) == '.xmp'

    @staticmethod
    def file_is_sidecar(path):
        return toolbox.get_extension(path) in ('.xmp', '.thm', '.lrv')

    @staticmethod
    def get_sidecar_name(mediafilename, path):
        if not path:
            return None

        ext = toolbox.get_extension(path)
        if ext == '.xmp':
            return None

        filename = toolbox.get_basename(mediafilename) + ext
        return filename

    @staticmethod
    def get_xmp_name(mediafilename):
        filename = toolbox.get_basename(mediafilename) + '.xmp'
        return filename

    @staticmethod
    def process_dead(pid):
        try:
            os.kill(pid, 0)
        except OSError as e:
            # only two possibilities: EINVAL, ESRCH or EPERM. EPERM means the process exists ;-)
            # EINVAL cannot happen on POSIX compliant systems.
            return e.args[0] == os.errno.ESRCH  # 'No Such Process'

        return False