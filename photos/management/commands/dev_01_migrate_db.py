from optparse import make_option
import os
import os.path
from photos.models import MediaDir, MediaFile
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    """
    Remove entries of deleted photos from the database
    """

    def handle(self, *args, **options):
        for m in MediaFile.objects.all():
            m_dir = os.path.dirname(m.mediafile_path)
            m_file = os.path.basename(m.mediafile_path)
            if m.sidecar_path:
                m_sidecar = os.path.basename(m.sidecar_path)
            else:
                m_sidecar = None

            print("{} {} {}".format(m_dir, m_file, m_sidecar))

            media_dir, created = MediaDir.objects.get_or_create(path=m_dir)
            m.media_dir = media_dir
            m.media_file = m_file
            m.sidecar_file = m_sidecar
            m.save()
        return