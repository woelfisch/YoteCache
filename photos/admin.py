from django.contrib import admin
from photos.models import MediaFile, Catalog, MimeType

class MediaFileAdmin(admin.ModelAdmin):
    list_display = ('date', 'mediafile_path', 'filename', 'catalog', 'mime_type', 'rejected')

class CatalogAdmin(admin.ModelAdmin):
    list_display = ('name', 'publish')

class MimeTypeAdmin(admin.ModelAdmin):
    list_display = ('type', 'hide', 'copy')

# Register your models here.
admin.site.register(MediaFile, MediaFileAdmin)
admin.site.register(Catalog, CatalogAdmin)
admin.site.register(MimeType, MimeTypeAdmin)