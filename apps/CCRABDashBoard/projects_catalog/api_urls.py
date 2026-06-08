from django.urls import path

from . import views

urlpatterns = [
    path("projects/", views.project_list_api, name="project-list-api"),
    path("projects/facets/", views.project_facets_api, name="project-facets-api"),
    path("projects/<slug:code>/", views.project_detail_api, name="project-detail-api"),
    path(
        "projects/<slug:code>/products/",
        views.project_products_api,
        name="project-products-api",
    ),
]
