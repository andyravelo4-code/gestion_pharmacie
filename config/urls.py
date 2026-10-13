"""Routage principal de PharmaGest."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "PharmaGest — Administration"
admin.site.site_title = "PharmaGest"
admin.site.index_title = "Gestion de la pharmacie"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("utilisateurs.urls")),
    path("medicaments/", include("medicaments.urls")),
    path("fournisseurs/", include("fournisseurs.urls")),
    path("clients/", include("clients.urls")),
    path("stock/", include("stock.urls")),
    path("achats/", include("achats.urls")),
    path("ventes/", include("ventes.urls")),
    path("", include("rapports.urls")),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")

handler403 = "core.views.erreur_403"
handler404 = "core.views.erreur_404"
handler500 = "core.views.erreur_500"
