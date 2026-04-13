/**
 * Menu global « Cartes & données » : ouverture, fermeture, fonds (style=) et thématiques.
 * Sur l’Atlas : IlletoAtlasMap.setStyle / setExtraLayer ; vitrine : redirection /atlas/?style=…
 */
(function () {
  "use strict";

  function illetoCartesRedirectToAtlas(query) {
    var path = window.__ILLETO_ATLAS_PATH || "/atlas/";
    var q = (query || "").replace(/^\?/, "");
    window.location.href =
      path + (path.indexOf("?") >= 0 ? "&" : "?") + q;
  }

  function illetoCloseAtlasChromeFlyouts() {
    if (typeof window.__atlasCloseBottomFlyouts === "function") {
      window.__atlasCloseBottomFlyouts();
      return;
    }
    var bf = document.getElementById("atlas-basemap-flyout");
    var ef = document.getElementById("atlas-perspective-extras-flyout");
    var sw = document.getElementById("perspective-switcher");
    if (bf) bf.setAttribute("hidden", "");
    if (ef) ef.setAttribute("hidden", "");
    if (sw) {
      var openB = sw.querySelector("[data-atlas-open-basemap]");
      var openE = sw.querySelector("[data-atlas-open-extras]");
      if (openB) openB.setAttribute("aria-expanded", "false");
      if (openE) openE.setAttribute("aria-expanded", "false");
    }
  }

  /** Menu « Cartes & données » (équivalent attendu : initAtlasCartesSidebar). */
  function initIlletoCartesMenu() {
    var side = document.getElementById("atlas-layers-sidebar");
    var back = document.getElementById("illeto-cartes-backdrop");
    var closeB = document.getElementById("atlas-layers-sidebar-close");
    var opens = document.querySelectorAll(".illeto-cartes-open-btn");
    if (!side) {
      if (typeof console !== "undefined" && console.warn) {
        console.warn(
          "Illeto cartes: #atlas-layers-sidebar introuvable — menu non initialisé."
        );
      }
      return;
    }
    if (side.getAttribute("data-illeto-cartes-menu-bound") === "1") {
      return;
    }
    side.setAttribute("data-illeto-cartes-menu-bound", "1");

    function setOpen(isOpen) {
      if (isOpen) {
        illetoCloseAtlasChromeFlyouts();
      }
      side.classList.toggle("is-open", isOpen);
      document.body.classList.toggle("illeto-cartes-menu-open", isOpen);
      if (back) {
        back.classList.toggle("is-open", isOpen);
        back.setAttribute("aria-hidden", isOpen ? "false" : "true");
      }
      side.setAttribute("aria-hidden", isOpen ? "false" : "true");
      for (var oi = 0; oi < opens.length; oi++) {
        opens[oi].setAttribute("aria-expanded", isOpen ? "true" : "false");
        opens[oi].classList.toggle("is-active", isOpen);
      }
      if (isOpen) {
        if (window.lucide) window.lucide.createIcons();
        if (
          window.IlletoAtlasMap &&
          typeof window.IlletoAtlasMap.syncCartesMenuExtras === "function"
        ) {
          window.IlletoAtlasMap.syncCartesMenuExtras();
        }
      }
    }

    function closeMenu() {
      setOpen(false);
    }

    setOpen(false);

    for (var bi = 0; bi < opens.length; bi++) {
      opens[bi].addEventListener("click", function (e) {
        e.stopPropagation();
        illetoCloseAtlasChromeFlyouts();
        var next = !side.classList.contains("is-open");
        setOpen(next);
      });
    }
    if (closeB) {
      closeB.addEventListener("click", function () {
        closeMenu();
      });
    }
    if (back) {
      back.addEventListener("click", function () {
        closeMenu();
      });
    }

    document.addEventListener(
      "keydown",
      function (e) {
        if (e.key === "Escape" && side.classList.contains("is-open")) {
          e.preventDefault();
          closeMenu();
        }
      },
      true
    );

    side.addEventListener("click", function (e) {
      var accBtn = e.target.closest("[data-illeto-cartes-accordion]");
      if (accBtn && side.contains(accBtn)) {
        e.stopPropagation();
        var accId = accBtn.getAttribute("data-illeto-cartes-accordion");
        var panel = side.querySelector(
          '[data-illeto-cartes-accordion-panel="' + accId + '"]'
        );
        var chev = accBtn.querySelector(".illeto-cartes-accordion-chevron");
        var expanded = accBtn.getAttribute("aria-expanded") === "true";
        var nextOpen = !expanded;
        accBtn.setAttribute("aria-expanded", nextOpen ? "true" : "false");
        if (panel) panel.classList.toggle("hidden", !nextOpen);
        if (chev) chev.style.transform = nextOpen ? "rotate(180deg)" : "";
        if (window.lucide) window.lucide.createIcons();
        return;
      }
      var allF = e.target.closest("[data-atlas-open-bottom-basemap-flyout]");
      if (allF && side.contains(allF)) {
        e.stopPropagation();
        var mapLayersBtn = document.querySelector("[data-atlas-open-basemap]");
        if (mapLayersBtn) mapLayersBtn.click();
        return;
      }
      var bm = e.target.closest("[data-basemap]");
      if (bm && side.contains(bm)) {
        e.stopPropagation();
        var k = bm.getAttribute("data-basemap");
        if (!k) return;
        if (
          window.IlletoAtlasMap &&
          typeof window.IlletoAtlasMap.setStyle === "function"
        ) {
          window.IlletoAtlasMap.setStyle(k);
          closeMenu();
        } else {
          illetoCartesRedirectToAtlas("style=" + encodeURIComponent(k));
        }
        return;
      }
      var ex = e.target.closest("[data-extra-layer]");
      if (ex && side.contains(ex)) {
        e.stopPropagation();
        var name = ex.getAttribute("data-extra-layer");
        if (!name) return;
        if (
          window.IlletoAtlasMap &&
          typeof window.IlletoAtlasMap.setExtraLayer === "function"
        ) {
          var cur = false;
          if (typeof window.IlletoAtlasMap.getExtraLayerState === "function") {
            var st = window.IlletoAtlasMap.getExtraLayerState();
            cur = !!(st && st[name]);
          }
          window.IlletoAtlasMap.setExtraLayer(name, !cur);
        } else {
          illetoCartesRedirectToAtlas("extra=" + encodeURIComponent(name));
        }
        return;
      }
      var th = e.target.closest("[data-atlas-thematic]");
      if (th && side.contains(th)) {
        e.stopPropagation();
        var slug = th.getAttribute("data-atlas-thematic");
        if (!slug) return;
        var geoReady = th.getAttribute("data-geo-ready") === "true";
        if (
          window.IlletoAtlasMap &&
          typeof window.IlletoAtlasMap.applyThematic === "function"
        ) {
          if (geoReady) {
            window.IlletoAtlasMap.applyThematic(slug);
          } else if (
            typeof window.IlletoAtlasMap.notifyThematicPending === "function"
          ) {
            window.IlletoAtlasMap.notifyThematicPending(slug);
          }
        } else {
          illetoCartesRedirectToAtlas("thematic=" + encodeURIComponent(slug));
        }
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initIlletoCartesMenu);
  } else {
    initIlletoCartesMenu();
  }
  window.initAtlasCartesSidebar = initIlletoCartesMenu;
})();
