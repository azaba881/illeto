"""Tests minimaux pages site (Atlas)."""

from django.test import Client, SimpleTestCase
from django.urls import reverse


class AtlasPageTests(SimpleTestCase):
    databases = []
    def test_atlas_get_returns_200(self):
        r = Client().get(reverse("website:atlas"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "atlas-map-wrap", html=True)

    def test_atlas_contains_export_helpers_in_markup(self):
        r = Client().get(reverse("website:atlas"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "downloadCanvasAsPngFile")
        self.assertContains(r, "bringAtlasExtraOverlaysToFront")
        self.assertContains(r, "admin-1-boundary")
        self.assertContains(r, "atlas-territory-search")
        self.assertContains(r, "atlasForcePngDataUrlDownload")
        self.assertContains(r, "atlasTerritories")
        self.assertContains(r, "atlasLabels")
        self.assertContains(r, "html2CanvasScale")
