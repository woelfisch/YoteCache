# PhotoYote
Copyright (C) 2015, by Joerg Reuter <jreuter@yaina.de>

This program comes with ABSOLUTELY NO WARRANTY. This is free software, and you are welcome to redistribute it under
the conditions of the [GNU General Public License v3.0](http://www.gnu.org/licenses/gpl-3.0.en.html).

## About

**Photoyote** is an advanced "image tank" appliance with a HTML5 GUI for mobile devices such as tablets and
smartphones. It can import files from flash card readers and cameras (PTP and mass storage). The web frontend has
been tested with various Android and iOS web browsers. It supports multiple catalogs, star rating, color labels and
control of what gets exported. No original images or movies will be overwritten or deleted by the frontend.

## Implementation notes

See [Notes.md](Notes.md) for some hints on how to build your own appliance.

## Known issues

* Does not work with Internet Explorer. That's intentional.
* Video playback capability depends on codec support by the browser 
* Does not rotate images from Canon Powershot G5X

## Third party software dependencies and copyrights

Note that the following components are required for PhotoYote to work but are not part of the git repository.

### The server side
PhotoYote is written in Python. Apart from the Python interpreter itself and dependencies on the Python standard
library, the following direct runtime dependencies to third-party modules exist:

* [Django](https://www.djangoproject.com/) by the Django Software Foundation; published under the BSD license
* [Pillow](http://python-pillow.github.io/) by Fredrik Lundh,  Alex Clark, et al; published under the PIL license
* [Rawpy](https://github.com/neothemachine/rawpy) by Maik Riechert; published under the MIT license
* [Wand](http://docs.wand-py.org/) by Hong Minhee; published under the MIT license
* [GExiv2](https://wiki.gnome.org/gexiv2) by Jim Nelson, Mike Gemuende; published under the GNU GPL v2
* [python-magic](https://github.com/ahupp/python-magic) by Adam Hupp; published under the MIT license

### The frontend

All third-party JavaScript and CSS is published under the MIT license. The [Glyphicons](http://glyphicons.com) packaged
with Bootstrap can be used for free by webapps utilizing Bootstrap. The third-party components are:

* [jQuery, jQuery-UI, jQuery-mobile, jQuery Mouse Wheel](http://jquery.com/) by the jQuery Foundation
* [jquery Panzoom](https://github.com/timmywil/jquery.panzoom) by Timmy Willison
* [Moment.js](http://momentjs.com) by Tim Wood, Iskren Chernev, et al
* [Bootstrap](http://getbootstrap.com) by Mark Otto, @fat, et al; MIT licensed, containing [Glyphicons](http://glyphicons.com) by Jan Kovařík
* [Bootstrap-Datetimepicker](http://eonasdan.github.io/bootstrap-datetimepicker/) by Jonathan Peterson
