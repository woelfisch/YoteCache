"""
Django settings for photoyote project.

For more information on this file, see
https://docs.djangoproject.com/en/1.7/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.7/ref/settings/
"""

import os
import logging
from photos import tools

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.7/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '=)c1zoh^5-zc!kpj&rj7$=km#r*tcswi3g^13ank3*q@u1+p%u'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

TEMPLATE_DEBUG = True

ALLOWED_HOSTS = []

# Application definition

# our app  must be first, otherwise admin interface templates will be used for accounts
# see https://code.djangoproject.com/ticket/20186
INSTALLED_APPS = (
    'photos',
    'django.contrib.auth',
    'django.contrib.admin',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'photoyote.urls'

WSGI_APPLICATION = 'photoyote.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.7/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# Internationalization
# https://docs.djangoproject.com/en/1.7/topics/i18n/

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.7/howto/static-files/

STATIC_URL = '/static/'
IMAGE_URL = STATIC_URL + 'images/'

try:
    from local_settings import *
except ImportError:
    try:
        from photoyote.local_settings import *
    except:
        pass

WWWUSER = tools.www_user()
WWWGROUP = tools.www_group()

MEDIA_DIR = '/data/camera/'
SOURCE_DIR = MEDIA_DIR + 'import/'  # contains dirs with imported images
WEB_DIR = MEDIA_DIR + 'web/'        # just hardlink if import file is JPEG, add XMP sidecar data w/ rating
EXPORT_DIR = MEDIA_DIR + 'export/'  # hardlink image from import if not marked as rejected, hardlink xmp sidecar
THUMBNAIL_DIR = 'tn/'               # WEB_DIR + subdir + THUMBNAIL_DIR + filename
PREVIEW_DIR = 'preview/'
os.environ['TMPDIR'] = '/data/tmp/'

STATUS_USE_FILE = False
if STATUS_USE_FILE:
    STATUS_DIR = WEB_DIR + 'status/'
    IMPORT_STATUS = 'import.json'
    PROCESS_STATUS = 'process.json'
else:
    IMPORT_STATUS = 'import'
    PROCESS_STATUS = 'process'

THUMBNAIL_UNAVAILABLE = 'photos/images/photoyote-thumbnail-unavailable.png'
PREVIEW_UNAVAILABLE = 'photos/images/photoyote-preview-unavailable.png'
FULLSIZE_UNAVAILABLE = 'photos/images/photoyote-fullsize-unavailable.png'

THUMBNAIL_TRANSPARENT_OVERLAY = 'photos/images/photoyote-thumbnail-transparent.png'
PREVIEW_TRANSPARENT_OVERLAY = 'photos/images/photoyote-preview-transparent.png'

if DEBUG:
    STATICFILES_DIRS = (
        WEB_DIR,
    )
    IMAGE_URL = STATIC_URL

LOGFILE = MEDIA_DIR + 'log.txt'
LOG_FORMAT = '%(asctime)s %(levelname)s %(module)s:%(funcName)s:%(lineno)d %(message)s'
LOGGER_HANDLE = 'photoyote'
if DEBUG:
    LOGLEVEL = logging.DEBUG
    DEBUG_MD_LOCKING = True
else:
    LOGLEVEL = logging.WARNING
    DEBUG_MD_LOCKING = False

# You can use either wand (ImageMagick) or rawpy (libraw, numpy, pillow) as IMAGE_LIB
# ImageMagick is outrageously slow and exec()s ufraw-batch, which uses lensfun to correct lens distortions, among
# other things we really do not need for a quick overview. Each RAW file of a Canon 7D takes 3 minutes to process
# with wand on the CubieTruck. Use rawpy.
IMAGE_LIB = 'rawpy'

if IMAGE_LIB == 'wand':
    THUMBNAILSIZE = '128x128>'
    WEBSIZE = '720x720>'
else:
    THUMBNAILSIZE = (128, 128)
    WEBSIZE = (720, 720)

DEFAULT_CATALOG = 'uncataloged'
UNKNOWN_MIME_TYPE = 'application/octet-stream'
METADATA_EXTENSIONS = ('.thn', '.xmp')
INDEX_THUMBNAILS_MAX = 200

PATH_MAX = os.pathconf(BASE_DIR, 'PC_PATH_MAX')  # how brain damaged is this?!
NAME_MAX = os.pathconf(BASE_DIR, 'PC_NAME_MAX')

VIDEO_WEBSIZE = 768
VIDEO_THUMBNAILSIZE = 128

THUMBNAIL_VIDEO_PLAY_BUTTON = os.path.join(BASE_DIR, 'photos/static', 'photos/images/playbutton-thumbnail.png')
PREVIEW_VIDEO_PLAY_BUTTON = os.path.join(BASE_DIR, 'photos/static', 'photos/images/playbutton-preview.png')

if tools.is_in_path('avconv'):
    FFMPEG_COMMAND = 'avconv'
elif tools.is_in_path('ffmpeg'):
    FFMPEG_COMMAND = 'ffmpeg'
else:
    FFMPEG_COMMAND = None
