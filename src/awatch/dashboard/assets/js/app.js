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
    btn.addEventListener("click", function () { AW.switchTab(btn.dataset.tab); });
  });

  document.getElementById("hours-select").value = String(AW.hours);
  document.getElementById("hours-select").addEventListener("change", function (e) {
    AW.hours = Number(e.target.value);
    sessionStorage.setItem("awatch_hours", String(AW.hours));
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
    });
  }

  AW.refresh("traffic");

  setInterval(function () {
    if (AW.authRequired) return;
    const active = document.querySelector("#tabs button.active")?.dataset.tab;
    if (active && active !== "settings") AW.refresh(active);
  }, 8000);

  AW.loadOpenapi().catch(function (e) {
    if (e.status !== 401) console.error(e);
  });
})(window.AWatch);
