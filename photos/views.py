import re
import json
from datetime import datetime, timedelta
from django.views.decorators.csrf import requires_csrf_token, csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils import timezone
from photos.models import Catalog, MediaFile, ProgressStatus
from django.core import serializers

# Create your views here.
def index(request):
    all_media_list = []
    catalog_list = Catalog.objects.order_by('id')
    for catalog in catalog_list:
        # filename contains a timestamp, otherwise: order_by('date', 'filename')
        media_files = MediaFile.objects.filter(catalog=catalog).exclude(rejected=True).exclude(
            mime_type__hide=True).order_by('filename')
        # the template engine cannot dereference dicts based on variables
        all_media_list.append([catalog, media_files])
    return render(request, 'photos/index.html', {'catalog_list': catalog_list, 'all_media_list': all_media_list})


def lighttable(request, catalog_id):
    catalog = get_object_or_404(Catalog, id=catalog_id)
    filmstrip = MediaFile.objects.filter(catalog__id=catalog_id).exclude(mime_type__hide=True).order_by('filename')

    try:
        media_first = filmstrip[0]
        media_last = filmstrip[len(filmstrip) - 1]
    except:
        media_first = None
        media_last = None

    return render(request, 'photos/lighttable.html', {
        'catalog': catalog,
        'catalog_list': Catalog.objects.order_by('id'),
        'filmstrip': filmstrip,
        'first': media_first,
        'last': media_last})


@requires_csrf_token
def metadata(request, media_id=None):
    media = get_object_or_404(MediaFile, id=media_id)
    for item in request.POST:
        if item == 'rating':
            try:
                rating = int(request.POST[item])
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
            catalog_name = re.sub('[\\\\/]\s?', '', request.POST[item])
            (catalog, created) = Catalog.objects.get_or_create(name=catalog_name)
            media.catalog = catalog

    media.save()

    meta_json = serializers.serialize('json', [media], use_natural_foreign_keys=True)
    return HttpResponse(content=meta_json, content_type='application/json')


@requires_csrf_token
def bulk(request):
    if 'json' not in request.POST:
        return HttpResponseBadRequest('<p>Missing parameter in POST</p>')

    try:
        action = json.loads(request.POST['json'])
    except:
        return HttpResponseBadRequest('<p>Broken JSON</p>')
    if not ('ids' in action and 'select' in action and 'set' in action):
        return HttpResponseBadRequest('<p>Incomplete JSON</p>')

    try:
        item = action['select']['item']
    except:
        return HttpResponseBadRequest('<p>Select item missing</p>')

    value = ''
    op = ''

    if item in ['rating', 'label', 'catalog', 'date']:
        try:
            value = action['select']['value']
        except:
            return HttpResponseBadRequest('<p>Select value missing</p>')

        if item in ['rating', 'label', 'catalog', 'date']:
            try:
                op = action['select']['operator']
            except:
                return HttpResponseBadRequest('<p>Select operator missing</p>')

    media_list = MediaFile.objects.filter(id__in=action['ids'])

    if item == 'all':
        pass
    elif item == 'reject':
        media_list = media_list.filter(rejected=True)
    elif item == 'publish':
        media_list = media_list.filter(rejected=False)
    elif item == 'rating':
        try:
            value = int(value)
        except:
            return HttpResponseBadRequest('<p>Select rating value not a number</p>')

        if op == 'eq':
            media_list = media_list.filter(rating=value)
        elif op == 'ne':
            media_list = media_list.exclude(rating=value)
        elif op == 'le':
            media_list = media_list.filter(rating__lt=value + 1)
        elif op == 'ge':
            media_list = media_list.filter(rating__gt=value - 1)
        else:
            return HttpResponseBadRequest('<p>Wrong operator</p>')
    elif item == 'label':
        if op == 'eq':
            media_list = media_list.filter(label=value)
        else:
            media_list = media_list.exclude(label=value)
    elif item == 'catalog':
        if op == 'eq':
            media_list = media_list.filter(catalog__name=value)
        else:
            media_list = media_list.exclude(catalog__name=value)
    elif item == 'date':
        try:
            dt_start = timezone.make_aware(datetime.strptime(value['start'] + ':00', '%Y-%m-%d %H:%M:%S'), timezone.utc)
            dt_end = timezone.make_aware(datetime.strptime(value['end'] + ':59', '%Y-%m-%d %H:%M:%S'), timezone.utc)
            if dt_start < dt_end:
                dt_range = (dt_start, dt_end)
            else:
                dt_range = (dt_end, dt_start)

            if op == 'eq':
                media_list = media_list.filter(date__range=dt_range)
            else:
                media_list = media_list.exclude(date__range=dt_range)
        except:
            return HttpResponseBadRequest('<p>Wrong or missing date strings</p>')
    else:
        return HttpResponseBadRequest('<p>Select action unsupported</p>')

    try:
        item = action['set']['item']
    except:
        HttpResponseBadRequest('<p>Item to set missing</p>')

    if item in ['rating', 'label', 'catalog']:
        try:
            value = action['set']['value']
            # keep this out of the loop
            if item == 'catalog':
                catalog_name = re.sub('[\\\\/]\s?', '', value)
                (catalog, created) = Catalog.objects.get_or_create(name=catalog_name)
                value = catalog
        except:
            return HttpResponseBadRequest('<p>Item to set missing or wrong</p>')

    # media_list.update() won't call the model save functions, hence iterate over the list
    for media in media_list:
        if item == 'reject':
            media.rejected = True
        elif item == 'publish':
            media.rejected = False
        elif item == 'rating':
            try:
                rating = int(value)
                media.rating = rating
            except:
                return HttpResponseBadRequest('<p>Rating value to set is not a number</p>')
        elif item == 'label':
            media.label = value
        elif item == 'catalog':
            media.catalog = value
        else:
            return HttpResponseBadRequest('<p>Set action unsupported</p>')

        media.save()

    response = serializers.serialize('json', media_list, use_natural_foreign_keys=True)
    return HttpResponse(content=response, content_type='application/json')


@csrf_exempt
def status(request):
    for s in ProgressStatus.objects.filter(running=True):
        if s.timestamp + timedelta(seconds=450) < timezone.now():
            s.timestamp = timezone.now()
            s.running = False
            s.save()
    status_json = serializers.serialize('json', ProgressStatus.objects.all())
    return HttpResponse(content=status_json, content_type='application/json')