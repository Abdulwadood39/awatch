window.AWatch = window.AWatch || {};

(function (AW) {
  AW.BASE = window.location.pathname.replace(/\/$/, "");
  AW.token = new URLSearchParams(location.search).get("token") || localStorage.getItem("awatch_token") || "";
  if (AW.token) localStorage.setItem("awatch_token", AW.token);

  AW.allowUi = false;
  AW.authRequired = false;
  AW.hours = Number(sessionStorage.getItem("awatch_hours") || 24);
  AW.consumerView = "groups";
  AW.consumerGroupDrill = null;
  AW.envLabel = "…";
  AW.filterablePaths = [];

  AW.titles = {
    traffic: ["Traffic", "Requests, throughput, and endpoint breakdown"],
    errors: ["Errors", "Status codes, fingerprints, and validation"],
    performance: ["Performance", "Apdex and latency percentiles"],
    consumers: ["Consumers", "Groups and individuals — click to drill down"],
    requests: ["Request logs", "Inspect headers, bodies, response, and server logs"],
    uptime: ["Uptime", "Synthetic checks and external heartbeat"],
    alerts: ["Alerts", "Trigger history — configure in code"],
    settings: ["Settings", "SMTP, excludes, uptime, and Apdex"],
  };

  AW.getFilterConsumer = function () {
    return sessionStorage.getItem("awatch_filter_consumer") || "";
  };

  AW.getFilterGroup = function () {
    return sessionStorage.getItem("awatch_filter_group") || "";
  };

  AW.setFilterConsumer = function (v) {
    if (v) sessionStorage.setItem("awatch_filter_consumer", v);
    else sessionStorage.removeItem("awatch_filter_consumer");
    AW.renderFilterChips();
  };

  AW.setFilterGroup = function (v) {
    if (v) sessionStorage.setItem("awatch_filter_group", v);
    else sessionStorage.removeItem("awatch_filter_group");
    AW.renderFilterChips();
  };

  AW.filterQuery = function () {
    let q = "";
    const cid = AW.getFilterConsumer();
    const grp = AW.getFilterGroup();
    if (cid) q += `&consumer_id=${encodeURIComponent(cid)}`;
    if (grp) q += `&consumer_group=${encodeURIComponent(grp)}`;
    return q;
  };

  AW.hoursQuery = function () {
    return `hours=${AW.hours}`;
  };

  AW.escapeHtml = function (s) {
    return String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  };

  AW.formatBytes = function (n) {
    const v = Number(n || 0);
    if (v >= 1e9) return (v / 1e9).toFixed(1) + " GB";
    if (v >= 1e6) return (v / 1e6).toFixed(1) + " MB";
    if (v >= 1e3) return (v / 1e3).toFixed(1) + " KB";
    return v + " B";
  };

  /** Parse stored UTC / offset timestamps into a Date. */
  AW.parseUtc = function (iso) {
    if (iso == null || iso === "") return null;
    let s = String(iso).trim();
    if (!s) return null;
    if (/^\d{10,13}$/.test(s)) {
      const n = Number(s);
      return new Date(s.length >= 13 ? n : n * 1000);
    }
    // Naive ISO from the server is UTC.
    if (!/[zZ]|[+-]\d{2}:?\d{2}$/.test(s)) {
      s += "Z";
    }
    const d = new Date(s);
    return Number.isNaN(d.getTime()) ? null : d;
  };

  function pad2(n) {
    return String(n).padStart(2, "0");
  }

  /**
   * Display timestamps in the browser's local timezone (storage stays UTC).
   * style: "list" (compact) | "full" | "time" | "day"
   */
  AW.formatTime = function (iso, style) {
    const d = AW.parseUtc(iso);
    if (!d) return "—";
    style = style || "list";
    const now = new Date();
    const sameDay = d.toDateString() === now.toDateString();
    const y = d.getFullYear();
    const sameYear = y === now.getFullYear();
    const hm = pad2(d.getHours()) + ":" + pad2(d.getMinutes());
    const hms = hm + ":" + pad2(d.getSeconds());
    const md = pad2(d.getMonth() + 1) + "-" + pad2(d.getDate());

    if (style === "full") {
      return d.toLocaleString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
    }
    if (style === "time") return hms;
    if (style === "day") return sameYear ? md : y + "-" + md;
    // list: today → HH:MM:SS; else MM-DD HH:MM (add year if needed)
    if (sameDay) return hms;
    if (sameYear) return md + " " + hm;
    return y + "-" + md + " " + hm;
  };

  /** Local calendar day key for grouping (YYYY-MM-DD). */
  AW.dateKey = function (iso) {
    const d = AW.parseUtc(iso);
    if (!d) return "";
    return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate());
  };

  /** Date separator label like 30-7-26 (D-M-YY, local). */
  AW.formatDateSep = function (iso) {
    const d = AW.parseUtc(iso);
    if (!d) return "";
    const yy = String(d.getFullYear()).slice(-2);
    return d.getDate() + "-" + (d.getMonth() + 1) + "-" + yy;
  };

  AW.localTzName = function () {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || "local";
    } catch (_) {
      return "local";
    }
  };

  AW.parseEndpoint = function (endpoint) {
    const s = String(endpoint || "").trim();
    const m = s.match(/^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(.+)$/i);
    if (m) return { method: m[1].toUpperCase(), path: m[2] };
    return { method: "", path: s };
  };

  AW.statusClass = function (code) {
    if (code >= 500) return "status-5";
    if (code >= 400) return "status-4";
    return "status-2";
  };

  AW.headers = function () {
    const h = { Accept: "application/json", "Content-Type": "application/json" };
    if (AW.token) h.Authorization = `Bearer ${AW.token}`;
    return h;
  };

  AW.showAuthGate = function (message) {
    AW.authRequired = true;
    const gate = document.getElementById("auth-gate");
    gate.classList.add("visible");
    gate.setAttribute("aria-hidden", "false");
    document.getElementById("auth-error").textContent = message || "";
    document.getElementById("auth-token-input").value = AW.token || "";
    document.getElementById("auth-token-input").focus();
  };

  AW.hideAuthGate = function () {
    AW.authRequired = false;
    const gate = document.getElementById("auth-gate");
    gate.classList.remove("visible");
    gate.setAttribute("aria-hidden", "true");
    document.getElementById("auth-error").textContent = "";
  };

  AW.api = async function (path, opts) {
    opts = opts || {};
    const res = await fetch(`${AW.BASE}${path}`, { headers: AW.headers(), ...opts });
    const data = await res.json().catch(() => ({}));
    if (res.status === 401) {
      AW.showAuthGate("Invalid or missing token. Enter a valid auth_token to continue.");
      const err = new Error("Unauthorized");
      err.status = 401;
      throw err;
    }
    if (!res.ok) throw new Error(data.detail || `${res.status} ${res.statusText}`);
    if (AW.authRequired) AW.hideAuthGate();
    return data;
  };

  AW.renderFilterChips = function () {
    const bar = document.getElementById("filter-chips");
    const chips = [];
    const cid = AW.getFilterConsumer();
    const grp = AW.getFilterGroup();
    if (cid) {
      chips.push(`<span class="chip">consumer: <strong>${AW.escapeHtml(cid)}</strong>
        <button type="button" onclick="AWatch.clearFilterConsumer()" title="Clear">×</button></span>`);
    }
    if (grp) {
      chips.push(`<span class="chip">group: <strong>${AW.escapeHtml(grp)}</strong>
        <button type="button" onclick="AWatch.clearFilterGroup()" title="Clear">×</button></span>`);
    }
    bar.innerHTML = chips.join("") || `<span class="muted" style="font-size:.82rem">No global filters</span>`;
    const fc = document.getElementById("filter-consumer");
    const fg = document.getElementById("filter-consumer-group");
    if (fc && document.activeElement !== fc) fc.value = cid;
    if (fg && document.activeElement !== fg) fg.value = grp;
  };

  AW.clearFilterConsumer = function () {
    AW.setFilterConsumer("");
    window._consumerFilterLabel = "";
    if (AW.updateConsumerBanner) AW.updateConsumerBanner();
    const tab = document.querySelector("#tabs button.active")?.dataset.tab;
    if (tab && AW.refresh) AW.refresh(tab);
  };

  AW.clearFilterGroup = function () {
    AW.setFilterGroup("");
    const tab = document.querySelector("#tabs button.active")?.dataset.tab;
    if (tab && AW.refresh) AW.refresh(tab);
  };

  AW.setUnlocked = function (unlocked) {
    AW.allowUi = unlocked;
    const settingsTab = document.getElementById("tab-settings");
    if (settingsTab) settingsTab.hidden = !unlocked;

    const forms = document.getElementById("settings-forms");
    const lockCard = document.getElementById("settings-lock-card");
    if (forms) forms.hidden = !unlocked;
    if (lockCard) lockCard.hidden = unlocked;

    const banner = document.getElementById("settings-banner");
    if (banner) {
      banner.className = "banner" + (unlocked ? " ok" : "");
      banner.innerHTML = unlocked
        ? `<strong class="lock-inline unlocked">UNLOCKED</strong> Configuration is editable. Changes save to the local awatch DB and reload live engines.`
        : `<strong class="lock-inline">LOCKED</strong> Configuration is read-only.`;
    }
    ["btn-save-smtp", "btn-add-exclude", "btn-save-uptime", "btn-save-performance", "btn-save-retention"].forEach(function (id) {
      const el = document.getElementById(id);
      if (el) el.disabled = !unlocked;
    });
    document.querySelectorAll("#settings input, #settings select, #settings textarea").forEach(function (el) {
      el.disabled = !unlocked;
    });

    // Leave Settings if it becomes locked while open.
    const active = document.querySelector("#tabs button.active")?.dataset.tab;
    if (!unlocked && (active === "settings" || document.getElementById("settings")?.classList.contains("active"))) {
      AW.switchTab("traffic");
    }
  };

  AW.openRequestLogs = function (opts) {
    opts = opts || {};
    const path = opts.path || "";
    const status = opts.status || "";
    const pathInput = document.getElementById("filter-path");
    const pathSelect = document.getElementById("filter-path-select");
    const statusInput = document.getElementById("filter-status");
    if (pathInput) pathInput.value = path;
    if (pathSelect) {
      const match = AW.filterablePaths.find(function (p) { return p.path === path; });
      pathSelect.value = match ? path : "";
    }
    if (statusInput) statusInput.value = status ? String(status) : "";
    AW.switchTab("requests");
    if (AW.loadRequests) AW.loadRequests();
  };

  AW.switchTab = function (tab) {
    if (tab === "settings" && !AW.allowUi) {
      tab = "traffic";
    }
    document.querySelectorAll("#tabs button").forEach(function (b) {
      b.classList.toggle("active", b.dataset.tab === tab);
    });
    document.querySelectorAll(".panel").forEach(function (p) { p.classList.remove("active"); });
    document.getElementById(tab)?.classList.add("active");
    const pair = AW.titles[tab] || [tab, ""];
    document.getElementById("page-title").textContent = pair[0];
    document.getElementById("page-sub").textContent = pair[1];
    try {
      window.scrollTo({ top: 0, left: 0, behavior: "auto" });
      document.documentElement.scrollTop = 0;
      document.body.scrollTop = 0;
    } catch (_) { }
    if (AW.refresh) return AW.refresh(tab);
  };

  document.getElementById("auth-form").addEventListener("submit", async function (e) {
    e.preventDefault();
    const value = document.getElementById("auth-token-input").value.trim();
    if (!value) {
      document.getElementById("auth-error").textContent = "Token is required.";
      return;
    }
    AW.token = value;
    localStorage.setItem("awatch_token", AW.token);
    try {
      const url = new URL(location.href);
      if (url.searchParams.has("token")) {
        url.searchParams.delete("token");
        history.replaceState({}, "", url.pathname + url.search + url.hash);
      }
    } catch (_) { }
    document.getElementById("auth-error").textContent = "Checking…";
    try {
      await AW.api("/api/overview");
      AW.hideAuthGate();
      const active = document.querySelector("#tabs button.active")?.dataset.tab || "traffic";
      if (AW.refresh) await AW.refresh(active);
    } catch (err) {
      if (err.status !== 401) {
        document.getElementById("auth-error").textContent = String(err.message || err);
      }
    }
  });

  document.getElementById("auth-clear").addEventListener("click", function () {
    AW.token = "";
    localStorage.removeItem("awatch_token");
    document.getElementById("auth-token-input").value = "";
    document.getElementById("auth-error").textContent = "Saved token cleared.";
    document.getElementById("auth-token-input").focus();
  });
})(window.AWatch);
