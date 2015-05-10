from django.conf.urls import patterns, url, include
from photos import views

urlpatterns = patterns('',
                       url(r'^$', views.index, name='index'),
                       url(r'^(?P<catalog_id>\d+)/', views.lighttable, name='lighttable'),
                       url(r'^data/(?P<media_id>\d+)', views.metadata),
                       url(r'^data/', views.metadata, name='metadata'),
                       url(r'^bulk/', views.bulk, name='bulk'),
                       url(r'^status/', views.status, name='status'),
                       )