import re;
from django.views.decorators.csrf import requires_csrf_token
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from photos.models import Catalog, MediaFile
from django.core import serializers

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


def lighttable(request, catalog_id):
    return render(request, 'photos/lighttable.html', {
        'catalog': Catalog.objects.get(id=catalog_id),
        'catalog_list': Catalog.objects.order_by('id'),
        'filmstrip': MediaFile.objects.filter(catalog__id=catalog_id).exclude(mime_type__hide=True).order_by('filename')})

@requires_csrf_token
def metadata(request, media_id):
    media = get_object_or_404(MediaFile, id=media_id)
    for item in request.POST:
        if item == 'rating':
            try:
                rating=int(request.POST[item])
                if (rating < 0) or (rating > 5):
                    continue
                media.rating = rating
            except:
                pass
        elif item == 'label':
            try:
                media.label = request.POST[item]
            except:
                pass
        elif item == 'rejected':
            rejected = request.POST[item]
            media.rejected = rejected.lower() == 'true'
        elif item == 'catalog':
            catalog_name=re.sub('[\\\\/]\s?', '', request.POST[item])
            (catalog, created) = Catalog.objects.get_or_create(name=catalog_name)
            media.catalog = catalog

    media.save()

    json = serializers.serialize('json', [media], use_natural_foreign_keys=True)
    return HttpResponse(content=json, content_type='application/json')
