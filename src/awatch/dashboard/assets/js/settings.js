window.AWatch = window.AWatch || {};

(function (AW) {
  AW.uiExcludes = [];

  AW.filterPathSelectHtml = function () {
    const parts = [`<option value="">All paths</option>`];
    for (const p of AW.filterablePaths) {
      parts.push(`<option value="${AW.escapeHtml(p.path)}">${AW.escapeHtml(p.endpoint)}</option>`);
    }
    return parts.join("");
  };

  AW.excludePathSelectHtml = function () {
    const parts = [`<option value="">Custom…</option>`];
    for (const p of AW.filterablePaths) {
      const exact = p.path;
      parts.push(`<option value="${AW.escapeHtml(exact)}">${AW.escapeHtml(p.endpoint)}</option>`);
      if (p.glob_path && p.glob_path !== exact) {
        parts.push(`<option value="${AW.escapeHtml(p.glob_path)}">${AW.escapeHtml(p.method)} ${AW.escapeHtml(p.glob_path)} (glob)</option>`);
      }
    }
    return parts.join("");
  };

  AW.populatePathSelects = function () {
    const filterSelect = document.getElementById("filter-path-select");
    const excludeSelect = document.getElementById("exclude-api");
    if (filterSelect) {
      const current = document.getElementById("filter-path")?.value || "";
      filterSelect.innerHTML = AW.filterPathSelectHtml();
      if (current) {
        const match = AW.filterablePaths.find(function (p) { return p.path === current; });
        filterSelect.value = match ? current : "";
      }
    }
    if (excludeSelect) {
      excludeSelect.innerHTML = AW.excludePathSelectHtml();
    }
  };

  AW.loadOpenapi = async function () {
    const d = await AW.api("/api/openapi");
    AW.filterablePaths = d.filterable_paths || [];
    AW.populatePathSelects();
    return d;
  };

  AW.renderExcludes = function (codeExcludes) {
    document.getElementById("exclude-code").textContent =
      `From code/defaults: ${(codeExcludes || []).join(", ") || "none"}`;
    document.getElementById("exclude-list").innerHTML = AW.uiExcludes.map(function (e, i) {
      return `
      <div class="list-item">
        <header>
          <div><strong>${AW.escapeHtml(e.path)}</strong>
            ${e.note ? `<span class="tag">${AW.escapeHtml(e.note)}</span>` : ""}
            <span class="tag">${e.enabled === false ? "disabled" : "active"}</span>
          </div>
          <button class="btn secondary" ${AW.allowUi ? "" : "disabled"} onclick="removeExclude(${i})">Remove</button>
        </header>
      </div>`;
    }).join("") || `<div class="muted">No extra UI excludes — all matching APIs are tracked</div>`;
  };

  AW.loadSettings = async function () {
    const cfg = await AW.api("/api/config");
    AW.setUnlocked(!!cfg.allow_ui_config);
    AW.envLabel = cfg.env || AW.envLabel;
    document.getElementById("env-badge").textContent = `env=${AW.envLabel}`;
    AW.uiExcludes = cfg.exclude_paths || [];
    const smtp = cfg.smtp || {};
    document.getElementById("smtp-url").value = smtp.smtp_url || "";
    document.getElementById("smtp-from").value = smtp.from_addr || "";
    document.getElementById("smtp-to").value = (smtp.default_to || []).join(", ");
    const uptime = cfg.uptime || {};
    document.getElementById("uptime-enabled").value = String(uptime.enabled !== false);
    document.getElementById("uptime-path").value = uptime.path || "/health";
    document.getElementById("uptime-interval").value = uptime.interval_seconds ?? 60;
    document.getElementById("uptime-expected-status").value = uptime.expected_status ?? 200;
    const perf = cfg.performance || {};
    document.getElementById("apdex-t-ms").value = perf.apdex_t_ms ?? 500;
    AW.renderExcludes(cfg.code_exclude_paths || []);
    await AW.loadOpenapi();
  };

  AW.saveUptime = async function () {
    if (!AW.allowUi) return;
    const body = {
      enabled: document.getElementById("uptime-enabled").value === "true",
      path: document.getElementById("uptime-path").value || "/health",
      interval_seconds: Number(document.getElementById("uptime-interval").value || 60),
      expected_status: Number(document.getElementById("uptime-expected-status").value || 200),
    };
    await AW.api("/api/config/uptime", { method: "PUT", body: JSON.stringify(body) });
    await AW.loadSettings();
    alert("Uptime settings saved");
  };

  AW.savePerformance = async function () {
    if (!AW.allowUi) return;
    const body = { apdex_t_ms: Number(document.getElementById("apdex-t-ms").value || 500) };
    await AW.api("/api/config/performance", { method: "PUT", body: JSON.stringify(body) });
    await AW.loadSettings();
    alert("Performance settings saved");
  };

  AW.saveSmtp = async function () {
    if (!AW.allowUi) return;
    const body = {
      smtp_url: document.getElementById("smtp-url").value || null,
      from_addr: document.getElementById("smtp-from").value || null,
      default_to: document.getElementById("smtp-to").value.split(",").map(function (s) { return s.trim(); }).filter(Boolean),
    };
    await AW.api("/api/config/smtp", { method: "PUT", body: JSON.stringify(body) });
    await AW.loadSettings();
    alert("SMTP saved");
  };

  AW.persistExcludes = async function () {
    await AW.api("/api/config/exclude-paths", { method: "PUT", body: JSON.stringify(AW.uiExcludes) });
    const cfg = await AW.api("/api/config");
    AW.renderExcludes(cfg.code_exclude_paths || []);
  };

  AW.addExclude = async function () {
    if (!AW.allowUi) return;
    const custom = document.getElementById("exclude-path").value.trim();
    const apiVal = document.getElementById("exclude-api").value;
    const path = custom || apiVal;
    if (!path) return alert("Path is required");
    AW.uiExcludes.push({
      path: path,
      note: document.getElementById("exclude-note").value.trim() || null,
      enabled: true,
    });
    document.getElementById("exclude-path").value = "";
    document.getElementById("exclude-note").value = "";
    await AW.persistExcludes();
    await AW.loadOpenapi();
  };

  AW.removeExclude = async function (i) {
    if (!AW.allowUi) return;
    AW.uiExcludes.splice(i, 1);
    await AW.persistExcludes();
    await AW.loadOpenapi();
  };
})(window.AWatch);

function saveSmtp() { return AWatch.saveSmtp(); }
function saveUptime() { return AWatch.saveUptime(); }
function savePerformance() { return AWatch.savePerformance(); }
function addExclude() { return AWatch.addExclude(); }
function removeExclude(i) { return AWatch.removeExclude(i); }
