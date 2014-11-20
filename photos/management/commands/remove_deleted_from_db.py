from optparse import make_option
import re
import os
import os.path

from dateutil import tz
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

class Command(BaseCommand):
    """
    Remove entries of deleted photos from the database
    """
    def handle(self, *args, **options):
        return