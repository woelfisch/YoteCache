import re
import json
from datetime import datetime, timedelta
from django.contrib.auth.views import redirect_to_login
from django.views.decorators.csrf import requires_csrf_token, csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.utils import timezone
from photos.models import Catalog, MediaFile, ProgressStatus
from django.core import serializers
from django.core.exceptions import PermissionDenied
from django.conf import settings
import tools

_PERM_VIEW='photos.view_mediafile'
_PERM_CHANGE='photos.change_mediafile'
_PERM_MOVE='photos.move_mediafile'

# the @login_required decorator doesn't work here as it does not realize that the login service
# might be behind a prefix. Using an own decorator either means copy-pasting most of
# django.contrib.auth.decorators.login_required with a one-line change, or getting lost in three
# levels of indirection...
def login_redirector(request):
    prefix=request.path.rstrip(request.path_info)
    return redirect_to_login(request.get_full_path(), prefix+settings.LOGIN_URL)

def index(request):
    if not request.user.is_authenticated():
        return login_redirector(request)

    if not request.user.has_perm(_PERM_VIEW):
        raise PermissionDenied

    all_media_list = []
    catalog_list = Catalog.objects.order_by('id')
    for catalog in catalog_list:
        # filename contains a timestamp, otherwise: order_by('date', 'filename')
        media_files = MediaFile.objects.filter(catalog=catalog).exclude(rejected=True).exclude(
            mime_type__hide=True).order_by('date', 'filename')
        count = media_files.count()

        if count <= 18:
            ml = list(media_files[:18])
        elif count <= 24:
            ml = list(media_files[:6])+list(media_files[count-12:count])
        else:
            midrow = count/6*2
            ml = list(media_files[:6])+list(media_files[midrow:midrow+6])+list(media_files[count-6:count])

        print(catalog, ml)
        # the template engine cannot dereference dicts based on variables
        all_media_list.append([catalog, ml, count])
    return render(request, 'photos/index.html', {'catalog_list': catalog_list, 'all_media_list': all_media_list})

def lighttable(request, catalog_id):
    if not request.user.is_authenticated():
        return login_redirector(request)

    if not request.user.has_perm(_PERM_VIEW):
        raise PermissionDenied

    catalog = get_object_or_404(Catalog, id=catalog_id)
    filmstrip = MediaFile.objects.filter(catalog__id=catalog_id).exclude(mime_type__hide=True).order_by('date', 'filename').values('id')

    try:
        media_first = MediaFile.objects.get(id=filmstrip[0]['id'])
        media_last = MediaFile.objects.get(id=filmstrip[len(filmstrip) - 1]['id'])
    except Exception as e:
        media_first = None
        media_last = None

    return render(request, 'photos/lighttable.html', {
        'catalog': catalog,
        'catalog_list': Catalog.objects.order_by('id'),
        'filmstrip': filmstrip,
        'first': media_first,
        'last': media_last,
    })

@requires_csrf_token
def filmstrip(request):
    if not request.user.has_perm(_PERM_VIEW):
        return HttpResponseForbidden()

    if 'json' not in request.POST:
        return HttpResponseBadRequest('<p>Missing parameter in POST</p>')

    try:
        action = json.loads(request.POST['json'])
    except:
        return HttpResponseBadRequest('<p>Broken JSON</p>')
    if not ('ids' in action):
        return HttpResponseBadRequest('<p>Incomplete JSON</p>')

    media = MediaFile.objects.filter(id__in=action['ids']) # order_by('date', 'filename')

    if 'set' in action:
        may_modify = request.user.has_perm(_PERM_CHANGE)
        may_move = request.user.has_perm(_PERM_MOVE)

        values = action['set']

        for m in media:
            for item in values:
                value = values[item]
                if item == 'rating' and may_modify:
                    try:
                        rating = int(value)
                        if (rating < 0) or (rating > 5):
                            continue
                        m.rating = rating
                    except:
                        pass
                elif item == 'label' and may_modify:
                    try:
                        m.label = value
                    except:
                        pass
                elif item == 'rejected' and may_modify:
                    m.rejected = value
                elif item == 'catalog' and may_move:
                    catalog_name = re.sub('[\\\\/]\s?', '', value)
                    (catalog, created) = Catalog.objects.get_or_create(name=catalog_name)
                    m.catalog = catalog
            m.save()

    meta_json=tools.create_json(media)
    # meta_json = serializers.serialize('json', media, use_natural_foreign_keys=True)
    return HttpResponse(content=meta_json, content_type='application/json')

@requires_csrf_token
def bulk(request):
    if not request.user.has_perm(_PERM_VIEW):
        return HttpResponseForbidden()

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

    may_modify = request.user.has_perm(_PERM_CHANGE)
    may_move = request.user.has_perm(_PERM_MOVE)


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

    if item in ['reject', 'publish', 'rating', 'label'] and not may_modify:
        raise PermissionDenied

    if item == 'catalog' and not may_move:
        raise PermissionDenied

    changed_ids = []
    # media_list.update() won't call the model save functions, hence iterate over the list
    for media in media_list:
        changed = False
        if item == 'reject':
            changed |= not media.rejected
            media.rejected = True
        elif item == 'publish':
            changed |= media.rejected
            media.rejected = False
        elif item == 'rating':
            try:
                rating = int(value)
                changed |= (media.rating != rating)
                media.rating = rating
            except:
                return HttpResponseBadRequest('<p>Rating value to set is not a number</p>')
        elif item == 'label':
            changed |= (media.label != value)
            media.label = value
        elif item == 'catalog':
            changed |= (media.catalog != value)
            media.catalog = value
        else:
            return HttpResponseBadRequest('<p>Set action unsupported</p>')

        # Model.save() keeps track of changes by itself but won't tell us about it
        if changed:
            media.save()
            changed_ids.append(media.id)

    # response = serializers.serialize('json', media_list, use_natural_foreign_keys=True)
    response = json.dumps(changed_ids)
    return HttpResponse(content=response, content_type='application/json')

@requires_csrf_token
def catalogid(request):
    if not request.user.has_perm(_PERM_VIEW):
        return HttpResponseForbidden()
    if 'json' not in request.POST:
        return HttpResponseBadRequest('<p>Missing parameter in POST</p>')
    try:
        action = json.loads(request.POST['json'])
    except:
        return HttpResponseBadRequest('<p>Broken JSON</p>')
    try:
        catalog = Catalog.objects.get(name=action)
        id = catalog.id
    except:
        id = -1
    return HttpResponse(content=json.dumps(id), content_type='application/json')


@csrf_exempt
def status(request):
    for s in ProgressStatus.objects.filter(running=True):
        if s.timestamp + timedelta(seconds=450) < timezone.now():
            s.timestamp = timezone.now()
            s.running = False
            s.save()
    status_json = serializers.serialize('json', ProgressStatus.objects.all())
    return HttpResponse(content=status_json, content_type='application/json')