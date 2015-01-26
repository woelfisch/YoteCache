# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('photos', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mediafile',
            name='sidecar_path',
            field=models.CharField(help_text=b'Path to sidecar file', max_length=4096, null=True, blank=True),
            preserve_default=True,
        ),
    ]
