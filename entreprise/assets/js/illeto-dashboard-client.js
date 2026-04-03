/* Client dashboard interactions (static UI demo) */
(function () {
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function formatFCFA(amount) {
    try {
      return new Intl.NumberFormat("fr-FR").format(amount) + " FCFA";
    } catch {
      return String(amount) + " FCFA";
    }
  }

  function createBlobDownload(filename, mime, content) {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function simulatedDownload(type, label) {
    const safeLabel = String(label || "illeto").replace(/[^\w\-]+/g, "_");
    if (type === "geojson") {
      const sample = {
        type: "FeatureCollection",
        name: safeLabel,
        features: [],
      };
      createBlobDownload(`${safeLabel}.geojson`, "application/geo+json", JSON.stringify(sample, null, 2));
      return;
    }
    if (type === "pdf") {
      createBlobDownload(`${safeLabel}.pdf`, "application/pdf", "%PDF-1.3\n% Illeto - document factice\n");
      return;
    }
    if (type === "png") {
      // 1x1 transparent PNG (data-uri)
      const png =
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+Xv7kAAAAASUVORK5CYII=";
      fetch(png)
        .then((r) => r.blob())
        .then((b) => {
          const url = URL.createObjectURL(b);
          const a = document.createElement("a");
          a.href = url;
          a.download = `${safeLabel}.png`;
          document.body.appendChild(a);
          a.click();
          a.remove();
          setTimeout(() => URL.revokeObjectURL(url), 1000);
        });
      return;
    }
    // fallback: text
    createBlobDownload(`${safeLabel}.txt`, "text/plain", "Téléchargement simulé (Illeto).");
  }

  function openModal(modalEl) {
    if (!modalEl) return;
    modalEl.classList.add("is-open");
    modalEl.setAttribute("aria-hidden", "false");
  }

  function closeModal(modalEl) {
    if (!modalEl) return;
    modalEl.classList.remove("is-open");
    modalEl.setAttribute("aria-hidden", "true");
  }

  function toast(message) {
    let el = $("#illetoToast");
    if (!el) {
      el = document.createElement("div");
      el.id = "illetoToast";
      el.style.position = "fixed";
      el.style.left = "50%";
      el.style.top = "18px";
      el.style.transform = "translateX(-50%)";
      el.style.zIndex = "2500";
      el.style.padding = "10px 14px";
      el.style.background = "rgba(3,5,12,0.92)";
      el.style.border = "1px solid rgba(255,255,255,0.10)";
      el.style.borderRadius = "14px";
      el.style.color = "rgba(255,255,255,0.92)";
      el.style.backdropFilter = "blur(10px)";
      el.style.boxShadow = "0 16px 70px rgba(0,0,0,0.45)";
      el.style.display = "none";
      document.body.appendChild(el);
    }

    el.textContent = message;
    el.style.display = "block";
    clearTimeout(window.__illetoToastTimer);
    window.__illetoToastTimer = setTimeout(() => {
      el.style.display = "none";
    }, 2800);
  }

  function wireDownloadButtons() {
    $$("[data-il-download]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        const type = btn.getAttribute("data-il-download");
        const label = btn.getAttribute("data-il-download-label") || btn.getAttribute("data-il-title") || "Illeto";
        toast(`Téléchargement ${type.toUpperCase()}…`);
        simulatedDownload(type, label);
      });
    });
  }

  function initCart() {
    const cart = new Map(); // id -> {id, name, price, qty}
    const cartBar = $("#illetoCartBar");
    const countEl = $("#illetoCartCount");
    const totalEl = $("#illetoCartTotal");

    function updateUI() {
      const items = Array.from(cart.values());
      const count = items.reduce((s, it) => s + it.qty, 0);
      const total = items.reduce((s, it) => s + it.qty * it.price, 0);
      if (countEl) countEl.textContent = String(count);
      if (totalEl) totalEl.textContent = formatFCFA(total);
      if (cartBar) cartBar.style.opacity = count > 0 ? "1" : "0.6";
      if (cartBar) cartBar.style.pointerEvents = count > 0 ? "auto" : "none";
    }

    $$("[data-store-add]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-store-add");
        const name = btn.getAttribute("data-store-name") || "Produit";
        const price = Number(btn.getAttribute("data-store-price") || 0);
        const existing = cart.get(id);
        if (existing) existing.qty += 1;
        else cart.set(id, { id, name, price, qty: 1 });
        updateUI();
        toast("Ajouté au panier");
      });
    });

    // Payment modal wiring (store page)
    const paymentModal = $("#illetoPaymentModal");
    const cartModalList = $("#illetoCartModalList");
    const cartModalTotal = $("#illetoCartModalTotal");
    let chosenMethod = null;

    const payBtn = $("#illetoGoToPayment");
    if (payBtn) {
      payBtn.addEventListener("click", () => {
        if (!paymentModal) return;
        const items = Array.from(cart.values());
        if (!items.length) return;

        if (cartModalList) {
          cartModalList.innerHTML = items
            .map(
              (it) =>
                `<div class="d-flex justify-content-between gap-3 py-2 border-bottom" style="border-color: rgba(255,255,255,0.08) !important;">
                   <div>
                     <div style="font-weight:800; letter-spacing:0.01em;">${it.name}</div>
                     <div class="small" style="color: rgba(148,163,184,0.74);">${it.qty} x ${formatFCFA(it.price)}</div>
                   </div>
                   <div style="font-weight:900;">${formatFCFA(it.qty * it.price)}</div>
                 </div>`
            )
            .join("");
        }
        if (cartModalTotal) cartModalTotal.textContent = formatFCFA(items.reduce((s, it) => s + it.qty * it.price, 0));
        chosenMethod = null;
        $$("[data-payment-method]").forEach((b) => b.classList.remove("active"));
        openModal(paymentModal);
      });
    }

    $$("[data-payment-method]").forEach((btn) => {
      btn.addEventListener("click", () => {
        chosenMethod = btn.getAttribute("data-payment-method");
        $$("[data-payment-method]").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
      });
    });

    const confirmPay = $("#illetoConfirmPayment");
    if (confirmPay) {
      confirmPay.addEventListener("click", () => {
        if (!cart.size) return;
        if (!chosenMethod) {
          toast("Choisissez un moyen de paiement");
          return;
        }
        closeModal(paymentModal);
        toast("Paiement confirmé (simulation)");
        cart.clear();
        updateUI();
      });
    }

    // Close modal
    $$("[data-modal-close]").forEach((x) => {
      x.addEventListener("click", () => closeModal(x.closest(".illeto-modal")));
    });
    if (paymentModal) {
      paymentModal.addEventListener("click", (e) => {
        if (e.target === paymentModal) closeModal(paymentModal);
      });
    }

    updateUI();
  }

  function initPlanUpgrade() {
    const modal = $("#illetoPlanModal");
    const btnOpen = $("#illetoOpenPlanModal");
    const confirm = $("#illetoConfirmPlanUpgrade");
    if (!modal || !btnOpen || !confirm) return;

    btnOpen.addEventListener("click", () => openModal(modal));

    confirm.addEventListener("click", () => {
      closeModal(modal);
      toast("Plan mis à jour (simulation)");
      const planEl = $("#illetoCurrentPlan");
      if (planEl) planEl.textContent = "Expert";
    });

    $$("[data-modal-close]").forEach((x) => {
      x.addEventListener("click", () => closeModal(x.closest(".illeto-modal")));
    });
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeModal(modal);
    });
  }

  function initSettingsForms() {
    const profileForm = $("#illetoProfileForm");
    const profileBtn = $("#illetoProfileSubmit", profileForm || document);
    if (profileForm) {
      profileForm.addEventListener("submit", (e) => {
        e.preventDefault();
        if (profileBtn) {
          profileBtn.disabled = true;
          const original = profileBtn.innerHTML;
          profileBtn.innerHTML =
            '<div style="display:flex;align-items:center;justify-content:center;gap:8px;">' +
            '<span style="width:18px;height:18px;border:2px solid rgba(45,212,191,0.25);border-top-color: rgba(45,212,191,0.95);border-radius:50%;display:inline-block;animation:spin 0.8s linear infinite;"></span>' +
            "Envoi…</div>";
          setTimeout(() => {
            profileBtn.disabled = false;
            profileBtn.innerHTML = original;
            toast("Profil mis à jour (simulation)");
          }, 1200);
        } else {
          toast("Profil mis à jour (simulation)");
        }
      });
    }

    const pwForm = $("#illetoChangePasswordForm");
    const pwBtn = $("#illetoPasswordSubmit", pwForm || document);
    const newPassEl = $("#illetoNewPassword");
    const confirmEl = $("#illetoNewPasswordConfirm");

    if (pwForm) {
      pwForm.addEventListener("submit", (e) => {
        e.preventDefault();
        if (newPassEl && confirmEl && newPassEl.value !== confirmEl.value) {
          toast("Les mots de passe ne correspondent pas");
          return;
        }
        if (pwBtn) {
          pwBtn.disabled = true;
          const original = pwBtn.innerHTML;
          pwBtn.innerHTML =
            '<div style="display:flex;align-items:center;justify-content:center;gap:8px;">' +
            '<span style="width:18px;height:18px;border:2px solid rgba(45,212,191,0.25);border-top-color: rgba(45,212,191,0.95);border-radius:50%;display:inline-block;animation:spin 0.8s linear infinite;"></span>' +
            "Mise à jour…</div>";
          setTimeout(() => {
            pwBtn.disabled = false;
            pwBtn.innerHTML = original;
            toast("Mot de passe mis à jour (simulation)");
            if (pwForm) pwForm.reset();
          }, 1400);
        } else {
          toast("Mot de passe mis à jour (simulation)");
          pwForm.reset();
        }
      });
    }

    // Ensure keyframes exist once (simple inline)
    if (!document.getElementById("illetoSpinKeyframes")) {
      const style = document.createElement("style");
      style.id = "illetoSpinKeyframes";
      style.textContent = "@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}";
      document.head.appendChild(style);
    }
  }

  function initSidebarToggle() {
    const sidebar = $("#sidebar");
    const topbar = $("#topbar");
    const content = $("#content");
    const overlay = $("#overlay");
    const toggleBtn = $("#toggleBtn");
    const mobileBtn = $("#mobileBtn");
    if (!sidebar || !topbar || !content) return;

    const isMobile = () => window.matchMedia("(max-width: 992px)").matches;

    function setDesktopCollapsed(collapsed) {
      sidebar.classList.toggle("collapsed", collapsed);
      topbar.classList.toggle("full", collapsed);
      content.classList.toggle("full", collapsed);
    }

    function setMobileShow(show) {
      sidebar.classList.toggle("mobile-show", show);
      if (overlay) overlay.classList.toggle("show", show);
    }

    function sync() {
      if (isMobile()) {
        // On mobile, on privilégie le slide-in via `mobile-show`
        setDesktopCollapsed(false);
        setMobileShow(sidebar.classList.contains("mobile-show"));
      } else {
        // Sur desktop, on privilégie `collapsed`
        setMobileShow(false);
        setDesktopCollapsed(sidebar.classList.contains("collapsed"));
      }
    }

    if (toggleBtn) {
      toggleBtn.addEventListener("click", () => {
        if (isMobile()) return;
        const willCollapse = !sidebar.classList.contains("collapsed");
        setDesktopCollapsed(willCollapse);
      });
    }

    if (mobileBtn) {
      mobileBtn.addEventListener("click", () => {
        if (!isMobile()) return;
        const show = !sidebar.classList.contains("mobile-show");
        setMobileShow(show);
        if (toggleBtn) toggleBtn.setAttribute("aria-expanded", "false");
        mobileBtn.setAttribute("aria-expanded", show ? "true" : "false");
      });
    }

    if (overlay) {
      overlay.addEventListener("click", () => {
        setMobileShow(false);
      });
    }

    // Close on outside click (mobile)
    document.addEventListener("click", (e) => {
      if (!isMobile()) return;
      if (!sidebar.classList.contains("mobile-show")) return;
      const clickedInsideSidebar = e.target && e.target.closest && e.target.closest("#sidebar");
      const clickedToggle = e.target && e.target.closest && e.target.closest("#mobileBtn");
      if (!clickedInsideSidebar && !clickedToggle) setMobileShow(false);
    });

    window.addEventListener("resize", sync);
    sync();
  }

  document.addEventListener("DOMContentLoaded", () => {
    wireDownloadButtons();
    initCart();
    initPlanUpgrade();
    initSettingsForms();
    initSidebarToggle();
  });
})();

