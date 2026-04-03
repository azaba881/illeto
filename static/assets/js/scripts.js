/**
 * Illeto — interactivité statique (menus, formulaires, atlas)
 */
(function () {
  "use strict";

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }
  function qsa(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

  function initSiteHeader() {
    var header = qs("#site-header");
    if (!header) return;
    var btn = qs("#mobile-menu-btn", header);
    var panel = qs("#mobile-menu-panel", header);
    var menuIcon = qs("#mobile-menu-icon-open", header);
    var closeIcon = qs("#mobile-menu-icon-close", header);
    function onScroll() {
      if (window.scrollY > 20) {
        header.classList.add("glass-panel", "border-b", "border-border/30");
        header.classList.remove("bg-transparent");
      } else {
        header.classList.remove("glass-panel", "border-b", "border-border/30");
        header.classList.add("bg-transparent");
      }
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    if (btn && panel) {
      btn.addEventListener("click", function () {
        var isOpen = !panel.classList.contains("hidden");
        if (isOpen) {
          panel.classList.add("hidden");
          btn.setAttribute("aria-expanded", "false");
          if (menuIcon) menuIcon.classList.remove("hidden");
          if (closeIcon) closeIcon.classList.add("hidden");
        } else {
          panel.classList.remove("hidden");
          btn.setAttribute("aria-expanded", "true");
          if (menuIcon) menuIcon.classList.add("hidden");
          if (closeIcon) closeIcon.classList.remove("hidden");
        }
      });
    }
  }

  function initHero() {
    var input = qs("#hero-search-input");
    if (!input) return;
    var wrap = qs("#hero-search-wrap");
    var full =
      "Rechercher un quartier (ex: Agla), une commune, une zone inondable...";
    var i = 0;
    var tick = setInterval(function () {
      if (i < full.length) {
        i++;
        input.setAttribute("placeholder", full.slice(0, i));
      } else {
        clearInterval(tick);
      }
    }, 40);
    input.addEventListener("focus", function () {
      if (wrap) {
        wrap.classList.add("ring-1", "ring-primary/50", "shadow-lg", "shadow-primary/10");
      }
    });
    input.addEventListener("blur", function () {
      if (wrap) {
        wrap.classList.remove("ring-1", "ring-primary/50", "shadow-lg", "shadow-primary/10");
      }
    });
    qsa("[data-hero-suggest]").forEach(function (b) {
      b.addEventListener("click", function () {
        input.value = b.getAttribute("data-hero-suggest") || "";
      });
    });
  }

  /** Subtle mouse-follow on hero SVG skeleton (~3px), respects reduced motion */
  function initHeroParallax() {
    var section = qs("#hero-section");
    var layer = qs("#hero-skeleton-layer");
    if (!section || !layer) return;
    var mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    var maxPx = 3;
    function reduced() {
      return mq.matches;
    }
    function onMove(e) {
      if (reduced()) return;
      var r = section.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) return;
      var cx = r.left + r.width * 0.5;
      var cy = r.top + r.height * 0.5;
      var nx = (e.clientX - cx) / (r.width * 0.5);
      var ny = (e.clientY - cy) / (r.height * 0.5);
      if (nx < -1) nx = -1;
      else if (nx > 1) nx = 1;
      if (ny < -1) ny = -1;
      else if (ny > 1) ny = 1;
      layer.style.transform =
        "translate(" + nx * maxPx + "px, " + ny * maxPx + "px)";
    }
    function reset() {
      layer.style.transform = "translate(0px, 0px)";
    }
    section.addEventListener("mousemove", onMove, { passive: true });
    section.addEventListener("mouseleave", reset);
    if (mq.addEventListener) {
      mq.addEventListener("change", function () {
        if (reduced()) reset();
      });
    } else if (mq.addListener) {
      mq.addListener(function () {
        if (reduced()) reset();
      });
    }
  }

  function initDataShowcaseCards() {
    qsa("[data-showcase-card]").forEach(function (card) {
      var inner = qs("[data-showcase-inner]", card);
      var glow = card.getAttribute("data-glow") || "";
      card.addEventListener("mouseenter", function () {
        if (inner)
          inner.style.boxShadow =
            "0 25px 80px oklch(0 0 0 / 0.6), 0 0 60px " + glow;
      });
      card.addEventListener("mouseleave", function () {
        if (inner) inner.style.boxShadow = "";
      });
    });
  }

  function initCartesLayers() {
    qsa("[data-carte-layer]").forEach(function (el) {
      var color = el.getAttribute("data-layer-color") || "#00875A";
      el.addEventListener("mouseenter", function () {
        el.style.boxShadow =
          "0 25px 80px oklch(0 0 0 / 0.6), 0 0 40px " + color + "30";
      });
      el.addEventListener("mouseleave", function () {
        el.style.boxShadow = "";
      });
    });
  }

  function initContactForm() {
    var form = qs("#contact-form");
    if (!form) return;
    var success = qs("#contact-success");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var btn = qs("#contact-submit", form) || qs("[type='submit']", form);
      if (btn) {
        btn.disabled = true;
        btn.innerHTML =
          '<div class="w-5 h-5 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin"></div><span> Envoi en cours...</span>';
      }
      setTimeout(function () {
        form.classList.add("hidden");
        if (success) success.classList.remove("hidden");
        setTimeout(function () {
          form.reset();
          form.classList.remove("hidden");
          if (success) success.classList.add("hidden");
          if (btn) {
            btn.disabled = false;
            btn.innerHTML =
              '<i data-lucide="send" class="w-5 h-5"></i> Envoyer le message';
            btn.classList.add("flex", "items-center", "justify-center", "gap-2");
            if (window.lucide) window.lucide.createIcons();
          }
        }, 3000);
      }, 1500);
    });
  }

  function initPartnerForm() {
    var form = qs("#partner-form");
    if (!form) return;
    var success = qs("#partner-success");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var btn = qs("#partner-submit", form) || qs("[type='submit']", form);
      if (btn) {
        btn.disabled = true;
        btn.innerHTML =
          '<div class="w-5 h-5 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin"></div><span> Envoi...</span>';
      }
      setTimeout(function () {
        form.classList.add("hidden");
        if (success) success.classList.remove("hidden");
        setTimeout(function () {
          form.reset();
          form.classList.remove("hidden");
          if (success) success.classList.add("hidden");
          if (btn) {
            btn.disabled = false;
            btn.innerHTML =
              '<i data-lucide="send" class="w-5 h-5"></i> Envoyer la candidature';
            btn.classList.add("flex", "items-center", "justify-center", "gap-2");
            if (window.lucide) window.lucide.createIcons();
          }
        }, 2800);
      }, 1400);
    });
  }

  /* ——— Atlas ——— */
  var LAND_USE_LABELS = {
    residential: "Résidentiel",
    commercial: "Commercial",
    green: "Espace vert",
  };

  var atlasState = {
    departmentId: null,
    departmentName: "",
    communeId: null,
    communeName: "",
    neighborhood: null,
    neighborhoodName: "",
    neighborhoodKind: null,
    systemUtilisateur: "Existant",
    landUse: ["residential", "commercial"],
    exportSelection: null,
    exportFormat: "image_png",
    poiToggles: {
      market: false,
      health: false,
      transport: false,
    },
  };

  function escapeChipText(s) {
    var d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function hashStr(s) {
    var h = 2166136261 >>> 0;
    var str = String(s || "");
    for (var i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  function simulatedDeptMetrics() {
    var key = atlasState.departmentId || atlasState.departmentName || "x";
    var h = hashStr(key);
    var pop = 85000 + (h % 220000);
    var dens = 45 + (h % 120);
    var km2 = 1200 + (h % 3500);
    return {
      population: pop.toLocaleString("fr-FR"),
      density: dens + " hab./km²",
      superficie: km2.toLocaleString("fr-FR") + " km²",
    };
  }

  function updateRightExportPanel() {
    var previewTitle = qs("#export-dept-title");
    var statsTitle = qs("#export-stats-title");
    var chips = qs("#export-landuse-chips");
    var sysVal = qs("#export-system-value");
    var simEl = qs("#export-dept-stats");
    var communeLine = qs("#export-commune-line");

    var dname = atlasState.departmentName;
    if (previewTitle) {
      previewTitle.textContent = dname || "Sélectionnez un territoire";
    }
    if (statsTitle) {
      statsTitle.textContent = dname
        ? "Statistiques : " + dname
        : "Statistiques : —";
    }

    if (chips) {
      var parts = [];
      if (dname) {
        parts.push(
          '<span class="px-2 py-1 text-[10px] rounded-md bg-primary/15 text-primary border border-primary/35 shadow-[0_0_14px_oklch(0.55_0.15_160_/_0.2)]">' +
          "Département : " +
          escapeChipText(dname) +
          "</span>"
        );
      }
      if (atlasState.communeName) {
        parts.push(
          '<span class="px-2 py-1 text-[10px] rounded-md bg-secondary/40 text-foreground border border-glass-border">' +
          "Commune : " +
          escapeChipText(atlasState.communeName) +
          "</span>"
        );
      }
      if (atlasState.neighborhoodName) {
        parts.push(
          '<span class="px-2 py-1 text-[10px] rounded-md border border-[#00875A]/40 bg-[#00875A]/15 text-[#2dd4a0]">' +
          (atlasState.neighborhoodKind === "zone"
            ? "Arrondissement : "
            : "Quartier : ") +
          escapeChipText(atlasState.neighborhoodName) +
          "</span>"
        );
      }
      atlasState.landUse.forEach(function (lid) {
        var lab = LAND_USE_LABELS[lid] || lid;
        parts.push(
          '<span class="px-2 py-1 text-[10px] rounded-md bg-primary/20 text-primary border border-primary/30">' +
          escapeChipText(lab) +
          "</span>"
        );
      });
      chips.innerHTML =
        parts.length > 0
          ? parts.join("")
          : '<span class="text-[10px] text-muted-foreground">Sélectionnez un territoire</span>';
    }

    if (sysVal) {
      sysVal.textContent = atlasState.systemUtilisateur || "—";
    }

    if (simEl) {
      if (dname) {
        var m = simulatedDeptMetrics();
        simEl.innerHTML =
          '<span class="text-foreground font-medium">Estimation (démo)</span> — population ≈ ' +
          m.population +
          ", densité ≈ " +
          m.density +
          ", superficie (simulée) ≈ " +
          m.superficie +
          ".";
      } else {
        simEl.textContent =
          "Sélectionnez un département pour afficher des indicateurs simulés.";
      }
    }

    if (communeLine) {
      var cl =
        atlasState.communeName
          ? "Commune : " + atlasState.communeName
          : "Commune : —";
      if (atlasState.neighborhoodName) {
        cl +=
          " · " +
          (atlasState.neighborhoodKind === "zone"
            ? "Arrondissement"
            : "Quartier") +
          " : " +
          atlasState.neighborhoodName;
      }
      communeLine.textContent = cl;
    }

    if (window.lucide) window.lucide.createIcons();
  }

  function closeAllCascade() {
    qsa("[data-cascade-dropdown]").forEach(function (d) {
      d.classList.add(
        "opacity-0",
        "scale-95",
        "-translate-y-2",
        "pointer-events-none"
      );
      d.classList.remove("opacity-100", "scale-100", "translate-y-0");
    });
    qsa("[data-cascade-btn]").forEach(function (b) {
      b.classList.remove("ring-1", "ring-primary/50");
      var ch = qs(".cascade-chevron", b);
      if (ch) ch.classList.remove("rotate-180");
    });
  }

  function setCascadeOpen(btn, dropdown, open) {
    if (open) {
      closeAllCascade();
      dropdown.classList.remove(
        "opacity-0",
        "scale-95",
        "-translate-y-2",
        "pointer-events-none"
      );
      dropdown.classList.add("opacity-100", "scale-100", "translate-y-0");
      btn.classList.add("ring-1", "ring-primary/50");
      var ch = qs(".cascade-chevron", btn);
      if (ch) ch.classList.add("rotate-180");
    } else {
      dropdown.classList.add(
        "opacity-0",
        "scale-95",
        "-translate-y-2",
        "pointer-events-none"
      );
      dropdown.classList.remove("opacity-100", "scale-100", "translate-y-0");
      btn.classList.remove("ring-1", "ring-primary/50");
      var ch2 = qs(".cascade-chevron", btn);
      if (ch2) ch2.classList.remove("rotate-180");
    }
  }

  function updateAtlasDataPanel() {
    var panel = qs("#atlas-data-panel");
    if (panel) {
      panel.innerHTML = "";
      panel.classList.add("hidden");
    }
    updateRightExportPanel();
  }

  function refillCommuneOptions() {
    var sel = qs('[data-cascade="commune"]');
    if (!sel) return;
    var dd = qs("[data-cascade-dropdown]", sel);
    if (!dd) return;
    var deptId = atlasState.departmentId;
    if (!deptId) {
      dd.innerHTML = "";
      return;
    }
    dd.innerHTML =
      '<p class="px-4 py-2.5 text-xs text-muted-foreground">Chargement des communes…</p>';
    fetch(
      "/geo/api/communes/?departement_id=" + encodeURIComponent(deptId),
      { credentials: "same-origin" }
    )
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (rows) {
        if (!Array.isArray(rows)) {
          if (rows && rows.detail) throw new Error(String(rows.detail));
          rows = [];
        }
        var cls =
          "w-full px-4 py-2.5 text-left text-sm transition-all duration-200 hover:bg-primary/10 hover:text-primary";
        dd.innerHTML = rows.length
          ? rows
              .map(function (o) {
                return (
                  '<button type="button" data-opt-id="' +
                  o.id +
                  '" class="' +
                  cls +
                  '">' +
                  o.name +
                  "</button>"
                );
              })
              .join("")
          : '<p class="px-4 py-2 text-xs text-muted-foreground">Aucune commune en base pour ce département.</p>';
      })
      .catch(function () {
        dd.innerHTML =
          '<p class="px-4 py-2 text-xs text-destructive">Impossible de charger les communes.</p>';
      });
  }

  function refillNeighborhoodOptions() {
    var sel = qs('[data-cascade="quartier"]');
    if (!sel) return;
    var dd = qs("[data-cascade-dropdown]", sel);
    if (!dd) return;
    var cid = atlasState.communeId;
    if (!cid) {
      dd.innerHTML =
        '<p class="px-4 py-2 text-xs text-muted-foreground">Sélectionnez un territoire.</p>';
      return;
    }
    dd.innerHTML =
      '<p class="px-4 py-2.5 text-xs text-muted-foreground">Chargement des zones / quartiers…</p>';
    fetch(
      "/geo/api/zones/geojson/?commune_id=" + encodeURIComponent(cid),
      { credentials: "same-origin" }
    )
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        var feats = data && data.features ? data.features : [];
        window.__atlasSubGeometries = window.__atlasSubGeometries || {};
        Object.keys(window.__atlasSubGeometries).forEach(function (k) {
          delete window.__atlasSubGeometries[k];
        });
        for (var fi = 0; fi < feats.length; fi++) {
          var f = feats[fi];
          var fid =
            f.id != null && f.id !== ""
              ? String(f.id)
              : f.properties && f.properties.pk != null
                ? String(f.properties.pk)
                : "";
          if (fid && f.geometry) window.__atlasSubGeometries[fid] = f.geometry;
        }
        try {
          window.dispatchEvent(
            new CustomEvent("illeto-atlas-zones-geojson", {
              detail: { geojson: data, count: feats.length },
            })
          );
        } catch (e) {
          /* CustomEvent */
        }
        if (!feats.length) {
          dd.innerHTML =
            '<div class="px-3 py-3 rounded-lg border border-glass-border/60 bg-secondary/20 space-y-2">' +
            '<p class="text-xs text-muted-foreground leading-relaxed">Aucune zone ni quartier n’est encore vectorisé pour cette commune dans la base IlèTô.</p>' +
            '<p class="text-[10px] text-muted-foreground/80">Proposez une contribution ou suivez l’enrichissement des données territoriales.</p>' +
            (function () {
              var cn =
                typeof atlasState !== "undefined" &&
                atlasState.communeName &&
                String(atlasState.communeName).trim();
              var href = cn
                ? "/contact/?commune=" +
                  encodeURIComponent(String(atlasState.communeName).trim()) +
                  "&sujet=crowd"
                : "/contact/?sujet=crowd";
              return (
                '<a href="' +
                href +
                '" class="inline-flex items-center justify-center w-full px-3 py-2 rounded-lg text-xs font-medium bg-[#00875A]/15 text-[#2dd4a0] border border-[#00875A]/35 hover:bg-[#00875A]/25 transition-colors">Contribuer via Crowdsourcing</a>'
              );
            })() +
            "</div>";
          return;
        }
        var cls =
          "w-full px-4 py-2.5 text-left text-sm transition-all duration-200 hover:bg-primary/10 hover:text-primary";
        dd.innerHTML = feats
          .map(function (f) {
            var p = f.properties || {};
            var id =
              f.id != null && f.id !== ""
                ? String(f.id)
                : p.pk != null
                  ? String(p.pk)
                  : "";
            var label =
              p.name != null && String(p.name).trim() !== ""
                ? String(p.name).trim()
                : "—";
            var kind =
              p.kind === "zone" ? "zone" : "quartier";
            return (
              '<button type="button" data-opt-id="' +
              id +
              '" data-kind="' +
              kind +
              '" class="' +
              cls +
              '">' +
              escapeChipText(label) +
              "</button>"
            );
          })
          .join("");
      })
      .catch(function () {
        dd.innerHTML =
          '<p class="px-4 py-2 text-xs text-destructive">Impossible de charger les zones / quartiers.</p>';
      });
  }

  function featureDepartmentPk(f) {
    if (f.id != null && f.id !== "") return String(f.id);
    var p = f.properties || {};
    if (p.pk != null) return String(p.pk);
    if (p.id != null) return String(p.id);
    return "";
  }

  function highlightDepartementOption(selectedId) {
    var container = qs('[data-cascade="departement"]');
    if (!container) return;
    qsa("[data-opt-id]", container).forEach(function (el) {
      var on = el.getAttribute("data-opt-id") === selectedId;
      el.classList.toggle("bg-primary/15", on);
      el.classList.toggle("text-primary", on);
    });
  }

  function highlightCommuneOption(selectedId) {
    var container = qs('[data-cascade="commune"]');
    if (!container) return;
    qsa("[data-opt-id]", container).forEach(function (el) {
      var on = el.getAttribute("data-opt-id") === selectedId;
      el.classList.toggle("bg-primary/15", on);
      el.classList.toggle("text-primary", on);
    });
  }

  function syncCommuneDropdownUI(communeId, label) {
    var cCont = qs('[data-cascade="commune"]');
    if (!cCont) return;
    var cBtn = qs("[data-cascade-btn]", cCont);
    var cSpan = cBtn ? qs("[data-cascade-label]", cBtn) : null;
    if (cSpan) {
      cSpan.textContent = label && String(label).trim() ? String(label).trim() : "Sélectionner...";
      cSpan.classList.toggle("text-muted-foreground", !label || !String(label).trim());
    }
    highlightCommuneOption(communeId || "");
  }

  function notifyPoiTogglesChanged() {
    try {
      window.dispatchEvent(new CustomEvent("illeto-atlas-poi-toggles"));
    } catch (e) {
      /* */
    }
  }

  function selectTerritory(type, id, data) {
    data = data || {};
    var idStr = id != null && id !== "" ? String(id) : "";

    if (type === "departement") {
      applyDepartmentSelection(idStr, data.name || "");
      return;
    }

    if (type === "commune") {
      atlasState.communeId = idStr || null;
      atlasState.communeName = (data.name && String(data.name).trim()) || "";
      atlasState.neighborhood = null;
      atlasState.neighborhoodName = "";
      atlasState.neighborhoodKind = null;
      syncCommuneDropdownUI(idStr, atlasState.communeName);
      var qCont = qs('[data-cascade="quartier"]');
      var qBtn = qCont ? qs("[data-cascade-btn]", qCont) : null;
      var qSpan = qBtn ? qs("[data-cascade-label]", qBtn) : null;
      if (qSpan) {
        qSpan.textContent = "Sélectionner...";
        qSpan.classList.add("text-muted-foreground");
      }
      if (qBtn) {
        qBtn.disabled = !idStr;
        qBtn.classList.toggle("opacity-40", !idStr);
        qBtn.classList.toggle("cursor-not-allowed", !idStr);
      }
      refillNeighborhoodOptions();
      try {
        window.dispatchEvent(
          new CustomEvent("illeto-atlas-commune", {
            detail: {
              communeId: idStr,
              communeName: atlasState.communeName,
              source: data.source || "filter",
            },
          })
        );
      } catch (e) {
        /* */
      }
      updateAtlasDataPanel();
      return;
    }

    if (type === "quartier" || type === "zone") {
      var kind = data.kind || (type === "zone" ? "zone" : "quartier");
      atlasState.neighborhood = idStr || null;
      atlasState.neighborhoodName = (data.name && String(data.name).trim()) || "";
      atlasState.neighborhoodKind = kind;
      var qCont2 = qs('[data-cascade="quartier"]');
      var qBtn2 = qCont2 ? qs("[data-cascade-btn]", qCont2) : null;
      var qSpan2 = qBtn2 ? qs("[data-cascade-label]", qBtn2) : null;
      if (qSpan2) {
        qSpan2.textContent = atlasState.neighborhoodName || "Sélectionner...";
        qSpan2.classList.toggle("text-muted-foreground", !atlasState.neighborhoodName);
      }
      highlightCommuneOption(atlasState.communeId || "");
      var subGeom =
        window.__atlasSubGeometries &&
        window.__atlasSubGeometries[String(idStr)]
          ? window.__atlasSubGeometries[String(idStr)]
          : null;
      try {
        window.dispatchEvent(
          new CustomEvent("illeto-atlas-neighborhood", {
            detail: {
              id: idStr,
              name: atlasState.neighborhoodName,
              kind: kind,
              geometry: subGeom,
            },
          })
        );
      } catch (e) {
        /* */
      }
      updateAtlasDataPanel();
      return;
    }
  }

  function applyDepartmentSelection(deptPk, label) {
    var sid = deptPk != null ? String(deptPk) : "";
    atlasState.departmentId = sid || null;
    atlasState.departmentName = label || "";
    atlasState.communeId = null;
    atlasState.communeName = "";
    atlasState.neighborhood = null;
    atlasState.neighborhoodName = "";
    atlasState.neighborhoodKind = null;
    var container = qs('[data-cascade="departement"]');
    var btn = container ? qs("[data-cascade-btn]", container) : null;
    var span = btn ? qs("[data-cascade-label]", btn) : null;
    if (span) {
      span.textContent = label || "Sélectionner…";
      span.classList.toggle("text-muted-foreground", !label);
    }
    highlightDepartementOption(sid);
    refillCommuneOptions();
    var cCont = qs('[data-cascade="commune"]');
    var cBtn = cCont ? qs("[data-cascade-btn]", cCont) : null;
    var cSpan = cBtn ? qs("[data-cascade-label]", cBtn) : null;
    if (cSpan) {
      cSpan.textContent = "Sélectionner...";
      cSpan.classList.add("text-muted-foreground");
    }
    var qCont = qs('[data-cascade="quartier"]');
    var qBtn = qCont ? qs("[data-cascade-btn]", qCont) : null;
    var qSpan = qBtn ? qs("[data-cascade-label]", qBtn) : null;
    if (qSpan) {
      qSpan.textContent = "Sélectionner...";
      qSpan.classList.add("text-muted-foreground");
    }
    if (qBtn) {
      qBtn.disabled = true;
      qBtn.classList.add("opacity-40", "cursor-not-allowed");
    }
    refillNeighborhoodOptions();
    updateAtlasDataPanel();
    try {
      window.dispatchEvent(
        new CustomEvent("illeto-atlas-department", {
          detail: {
            departmentId: sid,
            departmentName: atlasState.departmentName,
          },
        })
      );
      window.dispatchEvent(
        new CustomEvent("illeto-atlas-commune", {
          detail: { communeId: null, communeName: "" },
        })
      );
    } catch (e) {
      /* CustomEvent ou contexte restreint */
    }
  }

  function populateDepartementFromGeoJSON(features) {
    var container = qs('[data-cascade="departement"]');
    if (!container) return;
    var dd = qs("[data-cascade-dropdown]", container);
    if (!dd || !features || !features.length) return;
    var rows = [];
    for (var j = 0; j < features.length; j++) {
      var f = features[j];
      var pk = featureDepartmentPk(f);
      var raw =
        f.properties && f.properties.name != null
          ? String(f.properties.name).trim()
          : "";
      if (!pk || !raw) continue;
      rows.push({ id: pk, name: raw });
    }
    rows.sort(function (a, b) {
      return a.name.localeCompare(b.name, "fr");
    });
    var cls =
      "w-full px-4 py-2.5 text-left text-sm transition-all duration-200 hover:bg-primary/10 hover:text-primary";
    dd.innerHTML = rows
      .map(function (o) {
        return (
          '<button type="button" data-opt-id="' +
          o.id +
          '" class="' +
          cls +
          '">' +
          o.name +
          "</button>"
        );
      })
      .join("");
    if (rows.length && !atlasState.departmentId) {
      applyDepartmentSelection(rows[0].id, rows[0].name);
    } else {
      highlightDepartementOption(atlasState.departmentId || "");
      refillCommuneOptions();
    }
  }

  window.IlletoAtlas = {
    syncDepartmentFromMap: function (deptPk, label) {
      if (deptPk == null || deptPk === "") return;
      selectTerritory("departement", deptPk, { name: label || String(deptPk) });
    },
    selectTerritory: selectTerritory,
    populateDepartementFromGeoJSON: populateDepartementFromGeoJSON,
    getPoiToggles: function () {
      return {
        market: !!atlasState.poiToggles.market,
        health: !!atlasState.poiToggles.health,
        transport: !!atlasState.poiToggles.transport,
      };
    },
    showPoi: function (key) {
      if (!atlasState.poiToggles.hasOwnProperty(key)) return;
      atlasState.poiToggles[key] = true;
      notifyPoiTogglesChanged();
      qsa("[data-poi-toggle]").forEach(function (inp) {
        if (inp.getAttribute("data-poi-toggle") === key) inp.checked = true;
      });
    },
    hidePoi: function (key) {
      if (!atlasState.poiToggles.hasOwnProperty(key)) return;
      atlasState.poiToggles[key] = false;
      notifyPoiTogglesChanged();
      qsa("[data-poi-toggle]").forEach(function (inp) {
        if (inp.getAttribute("data-poi-toggle") === key) inp.checked = false;
      });
    },
    getState: function () {
      return {
        departmentId: atlasState.departmentId,
        departmentName: atlasState.departmentName,
        communeId: atlasState.communeId,
        communeName: atlasState.communeName,
        neighborhood: atlasState.neighborhood,
        neighborhoodName: atlasState.neighborhoodName,
        neighborhoodKind: atlasState.neighborhoodKind,
        exportFormat: atlasState.exportFormat,
        landUse: atlasState.landUse.slice(),
        systemUtilisateur: atlasState.systemUtilisateur,
        poiToggles: {
          market: !!atlasState.poiToggles.market,
          health: !!atlasState.poiToggles.health,
          transport: !!atlasState.poiToggles.transport,
        },
        userType:
          typeof window.__atlasUserType !== "undefined"
            ? window.__atlasUserType
            : "PUBLIC",
      };
    },
  };

  function initAtlasExplorer() {
    var root = qs("#atlas-explorer-root");
    if (!root) return;

    qsa("[data-cascade]", root).forEach(function (container) {
      var btn = qs("[data-cascade-btn]", container);
      var dd = qs("[data-cascade-dropdown]", container);
      if (!btn || !dd) return;
      btn.addEventListener("click", function () {
        if (btn.disabled) return;
        var isOpen = dd.classList.contains("opacity-100");
        if (isOpen) setCascadeOpen(btn, dd, false);
        else setCascadeOpen(btn, dd, true);
      });
    });

    document.addEventListener("click", function (e) {
      if (!e.target.closest("[data-cascade]")) closeAllCascade();
    });

    root.addEventListener("click", function (e) {
      var opt = e.target.closest("[data-opt-id]");
      if (!opt || !root.contains(opt)) return;
      var container = opt.closest("[data-cascade]");
      if (!container) return;
      var kind = container.getAttribute("data-cascade");
      var id = opt.getAttribute("data-opt-id");
      var label = opt.textContent.trim();
      var btn = qs("[data-cascade-btn]", container);
      var dd = qs("[data-cascade-dropdown]", container);
      var span = qs("[data-cascade-label]", btn);
      if (span) {
        span.textContent = label;
        span.classList.remove("text-muted-foreground");
      }
      setCascadeOpen(btn, dd, false);

      if (kind === "departement") {
        applyDepartmentSelection(id, label);
      } else if (kind === "commune") {
        selectTerritory("commune", id, { name: label, source: "filter" });
      } else if (kind === "quartier") {
        selectTerritory("quartier", id, {
          name: label,
          kind: opt.getAttribute("data-kind") || "quartier",
          source: "filter",
        });
        return;
      }
      if (kind !== "departement") updateAtlasDataPanel();
    });

    refillCommuneOptions();
    refillNeighborhoodOptions();

    qsa("[data-poi-toggle]").forEach(function (inp) {
      function syncFromState() {
        var k = inp.getAttribute("data-poi-toggle");
        if (!k || !atlasState.poiToggles.hasOwnProperty(k)) return;
        inp.checked = !!atlasState.poiToggles[k];
      }
      syncFromState();
      inp.addEventListener("change", function () {
        var k = inp.getAttribute("data-poi-toggle");
        if (!k || !atlasState.poiToggles.hasOwnProperty(k)) return;
        atlasState.poiToggles[k] = !!inp.checked;
        notifyPoiTogglesChanged();
      });
    });

    qsa("[data-landuse-toggle]").forEach(function (b) {
      b.addEventListener("click", function () {
        var id = b.getAttribute("data-landuse-toggle");
        var idx = atlasState.landUse.indexOf(id);
        if (idx >= 0) atlasState.landUse.splice(idx, 1);
        else atlasState.landUse.push(id);
        var on = atlasState.landUse.indexOf(id) >= 0;
        b.classList.toggle("bg-primary/15", on);
        b.classList.toggle("text-primary", on);
        b.classList.toggle("border-primary/30", on);
        b.classList.toggle("bg-secondary/30", !on);
        b.classList.toggle("text-muted-foreground", !on);
        b.classList.toggle("border-glass-border", !on);
        var dot = qs("[data-landuse-dot]", b);
        if (dot) dot.classList.toggle("hidden", !on);
        updateRightExportPanel();
      });
    });

    updateAtlasDataPanel();
  }

  function setAtlasPerspectiveUI(root, mode) {
    qsa("[data-layer-toggle]", root).forEach(function (btn) {
      var m = btn.getAttribute("data-layer-toggle");
      var on = m === mode;
      var ring = qs("[data-active-glow]", btn);
      btn.classList.toggle("text-primary", on);
      btn.classList.toggle("text-muted-foreground", !on);
      btn.classList.toggle("atlas-perspective-active", on);
      btn.style.boxShadow = on
        ? "0 0 20px oklch(0.62 0.16 160 / 0.45)"
        : "";
      if (ring) ring.classList.toggle("hidden", !on);
    });
  }

  function initPerspectiveSwitcher() {
    var root = qs("#perspective-switcher");
    if (!root) return;
    var defaultMode = "administrative";
    setAtlasPerspectiveUI(root, defaultMode);
    qsa("[data-layer-toggle]", root).forEach(function (btn) {
      btn.addEventListener("click", function () {
        var mode = btn.getAttribute("data-layer-toggle");
        if (!mode) return;
        setAtlasPerspectiveUI(root, mode);
        if (
          window.IlletoAtlasMap &&
          typeof window.IlletoAtlasMap.setPerspective === "function"
        ) {
          window.IlletoAtlasMap.setPerspective(mode);
        }
      });
    });
    if (
      window.IlletoAtlasMap &&
      typeof window.IlletoAtlasMap.setPerspective === "function"
    ) {
      window.IlletoAtlasMap.setPerspective(defaultMode);
    }
  }

  function initCoordinatesDisplay() {
    if (qs("#map")) return;
    var latEl = qs("#coord-lat");
    var lngEl = qs("#coord-lng");
    if (!latEl || !lngEl) return;
    var lat = 6.3654;
    var lng = 2.4183;
    setInterval(function () {
      lat += (Math.random() - 0.5) * 0.0001;
      lng += (Math.random() - 0.5) * 0.0001;
      latEl.textContent = lat.toFixed(4) + "°";
      lngEl.textContent = lng.toFixed(4) + "°";
    }, 2000);
  }

  function initFloatingDock() {
    if (qs("#floating-dock")) return;
    var dock = document.createElement("div");
    dock.id = "floating-dock";
    dock.className = "floating-dock";
    dock.setAttribute("aria-label", "Actions rapides");
    dock.innerHTML =
      '<div id="floating-dock-flyout" class="floating-dock__flyout" role="menu" aria-hidden="true">' +
      '<a href="https://wa.me/22900000000" target="_blank" rel="noopener noreferrer" role="menuitem" class="text-left">' +
      '<i data-lucide="message-circle" class="w-4 h-4 text-primary shrink-0"></i><span>WhatsApp</span></a>' +
      '<a href="https://www.linkedin.com/company/illeto" target="_blank" rel="noopener noreferrer" role="menuitem" class="text-left">' +
      '<i data-lucide="linkedin" class="w-4 h-4 text-primary shrink-0"></i><span>LinkedIn</span></a>' +
      "</div>" +
      '<button type="button" id="floating-dock-chat" class="floating-dock__btn" aria-label="Contacter" aria-expanded="false" aria-controls="floating-dock-flyout">' +
      '<i data-lucide="messages-square" class="w-[1.15rem] h-[1.15rem]"></i>' +
      "</button>" +
      '<button type="button" id="floating-dock-top" class="floating-dock__btn" aria-label="Retour en haut de page">' +
      '<i data-lucide="chevron-up" class="w-[1.15rem] h-[1.15rem]"></i>' +
      "</button>";
    document.body.appendChild(dock);
    var flyout = qs("#floating-dock-flyout", dock);
    var chatBtn = qs("#floating-dock-chat", dock);
    var topBtn = qs("#floating-dock-top", dock);
    function closeFlyout() {
      if (!flyout || !chatBtn) return;
      flyout.classList.remove("is-open");
      chatBtn.setAttribute("aria-expanded", "false");
      flyout.setAttribute("aria-hidden", "true");
    }
    function toggleFlyout() {
      if (!flyout || !chatBtn) return;
      var open = !flyout.classList.contains("is-open");
      if (open) {
        flyout.classList.add("is-open");
        chatBtn.setAttribute("aria-expanded", "true");
        flyout.setAttribute("aria-hidden", "false");
      } else closeFlyout();
    }
    if (chatBtn) {
      chatBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        toggleFlyout();
      });
    }
    if (topBtn) {
      topBtn.addEventListener("click", function () {
        closeFlyout();
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    }
    document.addEventListener("click", function () {
      closeFlyout();
    });
    dock.addEventListener("click", function (e) {
      e.stopPropagation();
    });
    if (window.lucide) window.lucide.createIcons();
  }

  function initExportSidebar() {
    var btn = qs("#export-download-btn");
    if (!btn) return;
    var isAtlasPage = !!qs("#map");
    if (isAtlasPage && qs("#atlas-export-modal")) {
      return;
    }
    function applyFormatSelection(selected) {
      qsa("[data-export-format]").forEach(function (x) {
        var on = x.getAttribute("data-export-format") === selected;
        x.classList.toggle("bg-primary/10", on);
        x.classList.toggle("border-primary/50", on);
        x.classList.toggle("text-primary", on);
        x.classList.toggle("atlas-export-format-active", on);
        x.classList.toggle("bg-secondary/30", !on);
        x.classList.toggle("border-glass-border", !on);
        x.classList.toggle("text-muted-foreground", !on);
        x.classList.toggle("hover:border-primary/30", !on);
        x.classList.toggle("hover:text-foreground", !on);
        var dot = qs("[data-format-dot]", x);
        if (dot) dot.classList.toggle("hidden", !on);
        var glow = qs("[data-format-glow]", x);
        if (glow) glow.classList.toggle("hidden", !on);
      });
      atlasState.exportFormat = selected;
    }
    qsa("[data-export-format]").forEach(function (b) {
      b.addEventListener("click", function () {
        var fid = b.getAttribute("data-export-format");
        if (fid) applyFormatSelection(fid);
      });
    });
    applyFormatSelection(atlasState.exportFormat || "image");
    if (isAtlasPage) {
      return;
    }
    btn.addEventListener("click", function () {
      if (btn.disabled) return;
      btn.disabled = true;
      btn.innerHTML =
        '<div class="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin inline-block align-middle mr-2"></div><span>Préparation...</span>';
      btn.classList.add("opacity-70", "cursor-not-allowed");
      setTimeout(function () {
        btn.disabled = false;
        btn.classList.remove("opacity-70", "cursor-not-allowed");
        btn.className =
          "w-full flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl font-medium text-sm transition-all duration-300 bg-primary text-primary-foreground";
        btn.style.boxShadow = "0 0 30px oklch(0.65 0.18 155 / 0.4)";
        btn.innerHTML =
          '<i data-lucide="check" class="w-4 h-4"></i><span>Export réussi</span>';
        if (window.lucide) window.lucide.createIcons();
        setTimeout(function () {
          btn.className =
            "w-full flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl font-medium text-sm transition-all duration-300 bg-secondary text-foreground hover:bg-secondary/80";
          btn.style.boxShadow = "";
          btn.innerHTML =
            '<i data-lucide="download" class="w-4 h-4"></i><span>Télécharger</span>';
          if (window.lucide) window.lucide.createIcons();
        }, 2000);
      }, 1500);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (window.lucide) window.lucide.createIcons();
    initSiteHeader();
    initFloatingDock();
    initHero();
    initHeroParallax();
    initDataShowcaseCards();
    initCartesLayers();
    initContactForm();
    initPartnerForm();
    initAtlasExplorer();
    initPerspectiveSwitcher();
    initCoordinatesDisplay();
    initExportSidebar();
  });
})();
