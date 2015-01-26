# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Catalog',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(help_text=b'Name of the catalog', unique=True, max_length=256)),
                ('publish', models.BooleanField(default=True, help_text=b'Make catalog available to other services')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='MediaFile',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('mediafile_path', models.CharField(help_text=b'Path to original file', unique=True, max_length=4096)),
                ('sidecar_path', models.CharField(help_text=b'Path to sidecar file', max_length=4096, blank=True)),
                ('filename', models.CharField(help_text=b'Filename for export', unique=True, max_length=4096)),
                ('date', models.DateTimeField(help_text=b'Creation date of the file')),
                ('exposure_time', models.FloatField(help_text=b'Exposure Time as a fraction', null=True, blank=True)),
                ('f_number', models.FloatField(help_text=b'F-stop', null=True, blank=True)),
                ('gain_value', models.FloatField(help_text=b'ISO speed or gain', null=True, blank=True)),
                ('focal_length', models.FloatField(help_text=b'Focal length', null=True, blank=True)),
                ('rating', models.PositiveSmallIntegerField(default=0, help_text=b'Star rating 0-5', blank=True)),
                ('label', models.CharField(default=b'None', help_text=b'Color label', max_length=16, blank=True, choices=[(b'None', b'None'), (b'Red', b'Red'), (b'Yellow', b'Yellow'), (b'Green', b'Green'), (b'Blue', b'Blue'), (b'Purple', b'Purple')])),
                ('rejected', models.BooleanField(default=False, help_text=b'Do not export this file')),
                ('catalog', models.ForeignKey(help_text=b'Catalog for this file', to='photos.Catalog')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='MimeType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('type', models.CharField(help_text=b'MIME type', unique=True, max_length=256)),
                ('hide', models.BooleanField(default=False, help_text=b'Hide this type of content in frontend')),
                ('copy', models.BooleanField(default=True, help_text=b'Export this type of content')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='mediafile',
            name='mime_type',
            field=models.ForeignKey(help_text=b'MIME type of the file', to='photos.MimeType'),
            preserve_default=True,
        ),
    ]
