from django.urls import path
from . import views

urlpatterns = [
    path('webex/webhook/', views.webex_webhook, name='webex_webhook'),
    path('', views.home, name='home'),
    path('user_input/', views.user_input, name='user_input'),
    path('visualise/', views.view_toplogy, name='visualise'),
    path('visualiser/', views.yaml_topology, name='yaml_topology'),
    path('view_topology/', views.restart_containerlab_graph, name='view_topology'),
    path('cleanup_sshx/', views.cleanup_sshx, name='cleanup_sshx'),
    path('activate_sshx/', views.activate_sshx, name='activate_sshx'),
    path('get_router_list/', views.get_router_list, name='get_router_list'),
    path('perform_deep_clean/', views.perform_deep_clean, name='perform_deep_clean'),

    # path('about/', views.about, name='about'),
    # path('contact/', views.contact, name='contact'),
]
