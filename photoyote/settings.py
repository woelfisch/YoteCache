"""
Django settings for photoyote project.

For more information on this file, see
https://docs.djangoproject.com/en/1.7/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.7/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
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

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'photos',
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

WWWUSER = toolbox.www_user()
WWWGROUP = toolbox.www_group()

PHOTODIR = '/data/camera/'
SOURCEDIR = PHOTODIR+'import/'  # contains dirs with imported images
JPEGDIR = PHOTODIR+'jpeg/'      # just hardlink if import file is JPEG, add XMP sidecar data w/ rating
EXPORTDIR = PHOTODIR+'export/'  # hardlink image from import if not marked as rejected, hardlink xmp sidecar from jpeg
THUMBNAILDIR = 'tn/'    # JPEGDIR + subdir + THUMBNAILDIR + filename
WEBIMAGEDIR = "web/"

THUMBNAILSIZE = '128x128>'
WEBSIZE = '720x720>'

DEFAULT_CATALOG='uncataloged'
UNKNOWN_MIME_TYPE='application/octet-stream'

MAX_PATH = os.pathconf('.', 'PC_PATH_MAX') # how brain damaged is this?!

"""
 <rdf:Description rdf:about='' xmlns:xmp='http://ns.adobe.com/xap/1.0/'>
  <xmp:CreateDate>2014-02-26T16:39:52</xmp:CreateDate>
  <xmp:CreatorTool>Adobe Photoshop Lightroom 4.4 (Windows)</xmp:CreatorTool>
  <xmp:Label>Rot</xmp:Label>
  <xmp:MetadataDate>2014-06-02T22:57:08Z</xmp:MetadataDate>
  <xmp:ModifyDate>2014-06-02T22:57:08</xmp:ModifyDate>
  <xmp:Rating>3</xmp:Rating>
 </rdf:Description>
"""
