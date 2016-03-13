# Notes for setting up and creating the Appliance

These are my notes taken while setting up the original appliance. They are by no means complete and not meant
to be a tutorial. However, I think they might be useful to outline what it takes to get it up and running,
and maybe avoid some pitfalls in the process — Joerg

## Hardware

* CubieTruck (or any other StrongARM board with a SATA interface, for example based on Allwinner A20)
* Spinpoint M8 HDD (rather loud unfortunately, but very stable so far)

## OS

* ~~[Debian Wheezy](http://www.igorpecovnik.com/2013/12/24/cubietruck-debian-wheezy-sd-card-image/) port by Igor Pečovnik~~ *Wheezy is not stale, it's already rotten…*
* ~~[Lubuntu 14.04](http://dl.cubieboard.org/software/a20-cubietruck/lubuntu/ct-lubuntu-card-v2.0/server/) build 2.0 by Linaro~~ *just smells funny, not completely decomposed yet… Alas, kernel recognizes only one core*
* [Stefanius CB2/CT Image](http://stefanius.de/cubieboard-downloads) *at least it boots newer kernels...*


### Additional Packages

* vim ;) 
* usbmount
* dnsmasq hostapd wireless-tools iw hostapd
* *see below*

### Configuration

#### Hostname

/etc/hostname
```
YoteCache
```

#### Ethernet

/etc/network/interfaces

```
auto eth0
        iface eth0 inet dhcp
        hwaddr ether 02:8f:08:XX:XX:XX
```

**Change the hardware address!**

#### WLAN AP

Configuration based on https://wiki.debianforum.de/WLAN-Access-Point_mit_hostapd_und_USB-Stick

/etc/dnsmasq.conf
```
interface=wlan0
no-dhcp-interface=eth0
dhcp-range=interface:wlan0,192.168.73.2,192.168.73.254,infinite
```


/etc/init.d/hostapd
```
DAEMON_CONF=/etc/hostapd.conf
```

/etc/hostapd.conf
```
ssid=YoteCacheAP
interface=wlan0
hw_mode=g
channel=9
logger_syslog=0
logger_syslog_level=0
wmm_enabled=0
wpa=2
preamble=1
wpa_passphrase=**CHANGE_ME**
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
auth_algs=1
macaddr_acl=0
ieee80211d=1
country_code=DE
```

**Change at least the passphrase and the country code**

/etc/network/interfaces
```
auto wlan0
        iface wlan0 inet static
        hwaddress ether 98:3B:16:XX:XX:XX
        address 192.168.73.1
        netmask 255.255.255.0
        broadcast 192.168.73.255
        up service hostapd restart
        up service dnsmasq restart
```

**Change at least the hardware address** 

/etc/modprobe.d/wlan.conf (according to http://debianforum.de/forum/viewtopic.php?f=30&t=149826)
```
options bcmdhd op_mode=2
```

#### Power Button

Wheezy:
```
apt-get install acpid acpi-support-base
```

Lubuntu: 

/etc/acpi/events/powerbtn-acpi-support
```
event=button[ /]power
action=/etc/acpi/powerbtn-acpi-support.sh
```

/etc/acpi/powerbtn-acpi-support.sh
```
#!/bin/sh
/sbin/shutdown -h -P now "Power button pressed"
```

#### Add external disk

```
echo '/dev/sda1 /data defaults,noatime,nodiratime 0 0' >>/etc/fstab
mkdir /data
mount /data
mkdir /data/tmp
chown 1777 /data/tmp
echo 'test -d /data/tmp && export TMPDIR=/data/tmp' >/etc/profile.d/tmpdir.sh
```

#### Updating to 14.04.2

Less smelly... Add 

```
deb http://ports.ubuntu.com/ubuntu-ports/ trusty-updates main universe
deb-src http://ports.ubuntu.com/ubuntu-ports/ trusty-updates main universe
```

to /etc/apt/sources.list and run "apt update ; apt upgrade".

### Django

  * packages: python-pip python-dev gir1.2-gexiv2-0.10 libexiv2-12 libgexiv2-2 ~~python-gobject python-wand~~ python-numpy postgresql postgresql-contrib postgresql-server-dev-9.3 libav-tools git ~~libgphoto2-2-dev gphoto2~~ *too old, build from source, **see below** *
  * compile libraw (≥ 1.6) from ~~source~~ git:

```
git clone https://github.com/LibRaw/LibRaw.git
cd LibRaw
autoreconf --install
apt get zlib1g-dev
export LIBS="-lz" CFLAGS="-D__LITTLE_ENDIAN__" CXXFLAGS="$CFLAGS"
./configure
make
make install
pip install --upgrade rawpy
ldconfig
```

  * pip install django django-model_utils python-dateutil python-magic psycopg2 pillow ~~gphoto2~~ 
  * compile python-gphoto2 from git (needs swig) **see below**
  * for gphoto2-cffi instead: pip install enum34 python-cffi gphoto2-cffi

gphoto2-cffi works, but is rather poorly maintained and disconnects the camera between access, thus slow with some devices. Let's try python-gphoto2 again:

  * remove **_*ALL*_** traces of libgphoto2 from stalebuntu if it ever had been installed!
  * compile swig from source (≥ 3.0.5), needs libpcre3-dev python-cffi
  * compile libgphoto2 from source (≥ 2.5.7), needs pkg-config libexif-dev libxml2-dev libgd-dev libjpeg-dev libltdl-dev libusb-1.0-0-dev libusb-dev
  * ''cd packaging/generic ; ./print-camera-list hwdb >/lib/udev/hwdb.d/20-gphoto.hwdb ; ./print-camera-list udev-rules version 201 >/lib/udev/rules.d/40-libgphoto2.rules''
  * build python-gphoto2 from git, **don't forget to run *python setup.py build_swig* if libgphoto2 has been updated**

python-gobject 3.12 isn't thread safe and will block in a futex() when loaded from mod_wsgi after updating to fUckbuntu 14.04.2. To build from source:

```
  apt remove --purge python-gobject
  apt install libgirepository1.0-dev gobject-introspection libffi-dev libglib2.0-dev gnome-common lcov libcairo-dev python-cairo-dev
  git clone git://git.gnome.org/pygobject
  cd pyobject
  ./autogen.sh
  ./configure --with-python=python2
  # install any other -dev packages it may miss
  make install
  cd /usr/local/lib/python2.7
  # wonder about the expletive above? Yes, those clowns are using "dist-packages" instead of "site-packages"
  mv site-packages/* dist-packages/
```

Seriously, what is a distribution good for if you have to rebuild half of it for a stupid webapp?!

Note: something else isn't thread safe anymore after a dist-upgrade. Add WSGIApplicationGroup %{GLOBAL} to /etc/apache2/mods-enabled/wsgi.conf

Newer versions of ImageMagick are using ufraw-batch instead of dcraw. ufraw is applying all kinds of filters and transformations (like lensfun), which we don't need but increase processing of every raw file to 3 minutes. libraw / rawpy can do it in one minute (still slow) and is good enough for our purpose.

GExiv2 segfaults on some QT videos. Fix:

```
diff -Nur gexiv2.orig/gexiv2/gexiv2-metadata.cpp gexiv2/gexiv2/gexiv2-metadata.cpp
--- gexiv2.orig/gexiv2/gexiv2-metadata.cpp      2015-06-29 20:43:32.630474835 +0000
+++ gexiv2/gexiv2/gexiv2-metadata.cpp   2015-06-21 13:06:09.890014330 +0000
@@ -249,7 +249,7 @@
 
 static gboolean gexiv2_metadata_save_internal (GExiv2Metadata *self, Exiv2::Image::AutoPtr image,
     GError **error) {
-    if (image.get () == NULL || ! image->good ()) {
+    if (image.get () == NULL || ! image->good () || ! self->priv->image.get ()) {
         g_set_error_literal (error, g_quark_from_string ("GExiv2"),
             501, "format seems not to be supported");
```

Get the source with `git clone git://git.gnome.org/gexiv2`

#### JavaScript

  * jQuery 2.1.3
  * jQuery Mobile 1.4.5
  * Bootstrap 3.3.2
  * Moment 2.9.0 http://momentjs.com/
  * Bootstrap Datetimepicker http://eonasdan.github.io/bootstrap-datetimepicker/
  * jQuery Mouse Wheel https://github.com/jquery/jquery-mousewheel/
  * jquery.panzoom https://github.com/timmywil/jquery.panzoom

### Device Support

/etc/udev/rules.d/70-camera.rules
```
ACTION=="add", ENV{DEVTYPE}=="usb_device",  ENV{ID_GPHOTO2}=="1", RUN+="/path/to/django/run_import.sh -p"
```

/etc/usbmount/mount.d/10_photoyote_import
```
#!/bin/sh

# logger "USB media plugged in, $UM_DEVICE mounted on $UM_MOUNTPOINT"

# cannot be a symlink due to the script evaluating $0 for base directory
/srv/django/photoyote/run_import.sh
```

### Apache Configuration

/etc/apache2/sites-enabled/yotecache.conf
```
<VirtualHost *:80>
DocumentRoot /var/www/html/
WSGIScriptAlias /photoyote /srv/django/photoyote/photoyote/wsgi.py
Alias /static/images /data/camera/web
Alias /static /data/www/photoyote/
<Directory /data/www/photoyote>
        AllowOverride FileInfo AuthConfig Limit
        Options +MultiViews +SymLinksIfOwnerMatch +IncludesNoExec
        <Limit GET POST>
                Require all granted
        </Limit>
        <LimitExcept GET POST>
                Require all denied
        </LimitExcept>
</Directory>

<Directory /data/camera/web>
        AllowOverride FileInfo AuthConfig Limit
        Options +MultiViews +SymLinksIfOwnerMatch +IncludesNoExec

        <Limit GET POST>
                Require all granted
        </Limit>

        <LimitExcept GET POST>
                Require all denied
        </LimitExcept>
</Directory>

<Directory /srv/django/photoyote/photoyote/>
        AllowOverride All
        Require all denied
        <Files wsgi.py>
                Require all granted
        </Files>
</Directory>
</VirtualHost>
```

/etc/apache2/mods-enabled/wsgi.conf
```
<IfModule mod_wsgi.c>
    WSGIApplicationGroup %{GLOBAL}
    WSGIDaemonProcess yotecache python-path=/srv/django/photoyote:/srv/django/photoyote/photoyote:/usr/lib/python2.7
    WSGIProcessGroup yotecache
</IfModule>
```

## Further Photo Editing

### Editing in Lightroom

  * Sidecar gets ignored on import, copy XMP-Files to the stored location of the images and re-read metadata
  * Color labels are localized in LR (for example, German). For English:
    * Metadaten → Farbmarkierungssatz → Bearbeiten → Vorgabe → Lightroom-Standard → …als neue Vorgabe speichern… → LR English → Red, Yellow, Green, Blue, Purple