from django.urls import path

from . import views

urlpatterns = [
    path("", views.projects_index_page, name="projects-index"),
    path("map/", views.projects_map_page, name="projects-map"),
    path("data/projects/", views.project_list_web_data, name="project-list-web-data"),
    path("data/projects/facets/", views.project_facets_web_data, name="project-facets-web-data"),
    path("data/projects/<slug:code>/", views.project_detail_web_data, name="project-detail-web-data"),
    path(
        "data/projects/<slug:code>/products/",
        views.project_products_web_data,
        name="project-products-web-data",
    ),
    path("<slug:code>/resource/<slug:resource_slug>/", views.project_resource_detail_page, name="project-resource-detail"),
    path("<slug:code>/", views.project_detail_page, name="project-detail"),
]
