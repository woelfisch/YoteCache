from django.shortcuts import render
from django.http import HttpResponse
from photos.models import Catalog, MediaFile

# Create your views here.
def index(request):
    all_media_list=[]
    catalog_list=Catalog.objects.order_by('id')
    for catalog in catalog_list:
        # filename contains a timestamp, otherwise: order_by('date', 'filename')
        media_files = MediaFile.objects.filter(catalog=catalog).exclude(rejected=True).exclude(mime_type__hide=True).order_by('filename')
        # the template engine cannot dereference dicts based on variables
        all_media_list.append([catalog, media_files])
    return render(request, 'photos/index.html', {'catalog_list': catalog_list, 'all_media_list': all_media_list})


def lighttable(request, image_id):
    return render(request, 'photos/lighttable.html', {'image': MediaFile.objects.get(id=image_id)})
