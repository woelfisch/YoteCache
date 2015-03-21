#! /bin/sh
export PATH=$PATH:/usr/bin
cd $(readlink -f $(dirname $0))
python manage.py copy_card $@  | python manage.py import_photo
