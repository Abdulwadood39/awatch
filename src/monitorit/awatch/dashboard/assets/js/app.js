window.AWatch = window.AWatch || {};

(function (AW) {
  AW.refresh = async function (tab) {
    try {
      if (tab === "traffic") await AW.loadTraffic();
      if (tab === "errors") await AW.loadErrors();
      if (tab === "performance") await AW.loadPerformance();
      if (tab === "consumers") await AW.loadConsumers();
      if (tab === "requests") await AW.loadRequests();
      if (tab === "uptime") await AW.loadUptime();
      if (tab === "alerts") await AW.loadAlerts();
      if (tab === "settings") await AW.loadSettings();
    } catch (e) {
      console.error(e);
      if (e.status === 401) return;
      document.getElementById("header-meta").textContent = String(e.message || e);
    }
  };

  document.querySelectorAll("#tabs button").forEach(function (btn) {
    btn.addEventListener("click", function () {
      AW.switchTab(btn.dataset.tab);
      const sidebar = document.getElementById("sidebar");
      const toggle = document.getElementById("nav-toggle");
      if (sidebar) sidebar.classList.remove("open");
      if (toggle) {
        toggle.setAttribute("aria-expanded", "false");
        toggle.textContent = "☰";
      }
    });
  });

  const navToggle = document.getElementById("nav-toggle");
  if (navToggle) {
    navToggle.addEventListener("click", function () {
      const sidebar = document.getElementById("sidebar");
      if (!sidebar) return;
      const open = sidebar.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
      navToggle.textContent = open ? "✕" : "☰";
    });
  }

  document.getElementById("hours-select").value = String(AW.hours);
  document.getElementById("hours-select").addEventListener("change", function (e) {
    AW.hours = Number(e.target.value);
    sessionStorage.setItem("awatch_hours", String(AW.hours));
    if (AW.resetRequestsPage) AW.resetRequestsPage();
    const tab = document.querySelector("#tabs button.active")?.dataset.tab || "traffic";
    AW.refresh(tab);
  });

  AW.renderFilterChips();

  document.querySelectorAll("#consumer-view-toggle button").forEach(function (btn) {
    btn.addEventListener("click", function () {
      AW.consumerView = btn.dataset.view;
      document.querySelectorAll("#consumer-view-toggle button").forEach(function (b) {
        b.classList.toggle("active", b.dataset.view === AW.consumerView);
      });
      if (AW.consumerView === "groups") AW.consumerGroupDrill = null;
      AW.loadConsumers();
    });
  });

  const filterPathSelect = document.getElementById("filter-path-select");
  if (filterPathSelect) {
    filterPathSelect.addEventListener("change", function () {
      const pathInput = document.getElementById("filter-path");
      if (pathInput) pathInput.value = filterPathSelect.value || "";
      if (AW.updateResetFiltersBtn) AW.updateResetFiltersBtn();
    });
  }

  ["filter-path", "filter-consumer", "filter-consumer-group", "filter-status"].forEach(function (id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("input", function () {
      if (AW.updateResetFiltersBtn) AW.updateResetFiltersBtn();
    });
    el.addEventListener("change", function () {
      if (AW.updateResetFiltersBtn) AW.updateResetFiltersBtn();
    });
  });

  AW.refresh("traffic");

  // Live refresh — pause when the tab is hidden so a parked dashboard
  // does not spam the app's uvicorn access log.
  const POLL_MS = 30000;
  setInterval(function () {
    if (AW.authRequired) return;
    if (document.visibilityState === "hidden") return;
    const active = document.querySelector("#tabs button.active")?.dataset.tab;
    if (active && active !== "settings") AW.refresh(active);
  }, POLL_MS);

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState !== "visible" || AW.authRequired) return;
    const active = document.querySelector("#tabs button.active")?.dataset.tab;
    if (active && active !== "settings") AW.refresh(active);
  });

  AW.loadOpenapi().catch(function (e) {
    if (e.status !== 401) console.error(e);
  });
})(window.AWatch);
