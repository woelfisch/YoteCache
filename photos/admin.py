from django.contrib import admin
from photos.models import MediaFile, MediaDir, Catalog, MimeType

class MediaFileAdmin(admin.ModelAdmin):
    list_display = ('date', 'media_dir', 'media_file', 'filename', 'catalog', 'mime_type', 'rejected')

class MediaDirAdmin(admin.ModelAdmin):
    list_display = ('path', 'locked_by_pid', 'locked_by_name', 'locked_at')

class CatalogAdmin(admin.ModelAdmin):
    list_display = ('name', 'publish')

class MimeTypeAdmin(admin.ModelAdmin):
    list_display = ('type', 'hide', 'copy')

# Register your models here.

admin.site.register(MediaDir, MediaDirAdmin)
admin.site.register(MediaFile, MediaFileAdmin)
admin.site.register(Catalog, CatalogAdmin)
admin.site.register(MimeType, MimeTypeAdmin)