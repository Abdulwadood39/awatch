window.AWatch = window.AWatch || {};

(function (AW) {
  AW.loadHeaderMeta = async function () {
    const o = await AW.api("/api/overview");
    AW.setUnlocked(!!o.allow_ui_config);
    AW.envLabel = o.env || "unknown";
    document.getElementById("env-badge").textContent = `env=${AW.envLabel}`;
    document.getElementById("header-meta").textContent =
      `release=${o.release || "n/a"} · queue=${o.queue_depth} · ${AW.hours}h window`;
    return o;
  };

  AW.loadTraffic = async function () {
    await AW.loadHeaderMeta();
    const d = await AW.api(`/api/traffic?${AW.hoursQuery()}${AW.filterQuery()}`);
    document.getElementById("traffic-cards").innerHTML = [
      ["Requests", d.requests, `${d.rpm} rpm`],
      ["Error rate", `${((d.error_rate || 0) * 100).toFixed(2)}%`, `${d.errors_4xx || 0} 4xx · ${d.errors_5xx || 0} 5xx`],
      ["Bytes in", AW.formatBytes(d.bytes_in), "request payload"],
      ["Bytes out", AW.formatBytes(d.bytes_out), "response payload"],
      ["Avg latency", `${Number(d.avg_ms || 0).toFixed(1)}ms`, `${AW.hours}h window`],
    ].map(function (row) {
      return `<div class="card"><div class="label">${row[0]}</div><div class="value">${row[1]}</div><div class="delta">${row[2]}</div></div>`;
    }).join("");

    AW.renderTimelineChart("traffic-chart", d.timeline || [], { yLabel: "requests / min" });
    const meta = document.getElementById("traffic-chart-meta");
    if (meta) {
      const n = (d.timeline || []).length;
      meta.textContent = n
        ? `Requests per minute · ${n} buckets in last ${AW.hours}h · hover a bar for exact values`
        : `No traffic in the last ${AW.hours}h`;
    }
    const eps = d.endpoints || [];
    document.getElementById("traffic-endpoints").innerHTML = eps.slice(0, 8).map(function (e) {
      const parsed = AW.parseEndpoint(e.endpoint);
      return `<div class="clickable" data-path="${AW.escapeHtml(parsed.path)}" style="display:flex;justify-content:space-between;gap:1rem;padding:.35rem 0;border-bottom:1px solid var(--border);cursor:pointer">
        <span>${AW.escapeHtml(e.endpoint)}</span>
        <span class="muted">${e.count} · p95 ${e.p95_ms}ms</span>
      </div>`;
    }).join("") || "No data";
    document.querySelectorAll("#traffic-endpoints [data-path]").forEach(function (row) {
      row.addEventListener("click", function () { AW.openRequestLogs({ path: row.dataset.path }); });
    });
    document.getElementById("traffic-endpoints-body").innerHTML = eps.map(function (e) {
      const parsed = AW.parseEndpoint(e.endpoint);
      return `<tr class="clickable" data-path="${AW.escapeHtml(parsed.path)}">
        <td>${AW.escapeHtml(e.endpoint)}</td><td>${e.count}</td><td>${(e.error_rate * 100).toFixed(1)}%</td>
        <td>${e.p50_ms}</td><td>${e.p95_ms}</td><td>${e.avg_ms}</td><td>${e.apdex}</td></tr>`;
    }).join("") || `<tr><td colspan="7" class="muted">No data</td></tr>`;
    document.querySelectorAll("#traffic-endpoints-body tr[data-path]").forEach(function (tr) {
      tr.addEventListener("click", function () { AW.openRequestLogs({ path: tr.dataset.path }); });
    });
  };

  AW.loadErrors = async function () {
    const d = await AW.api(`/api/errors?${AW.hoursQuery()}${AW.filterQuery()}`);
    const totalErr = (d.status_codes || []).reduce(function (s, r) { return s + (r.count || 0); }, 0);
    const fpCount = (d.fingerprints || []).length;
    const valCount = (d.validation || []).reduce(function (s, r) { return s + (r.count || 0); }, 0);
    document.getElementById("errors-cards").innerHTML = [
      ["HTTP errors", totalErr, "4xx and 5xx"],
      ["Fingerprints", fpCount, "unique exception groups"],
      ["422 validation", valCount, "field failures"],
    ].map(function (row) {
      return `<div class="card"><div class="label">${row[0]}</div><div class="value">${row[1]}</div><div class="delta">${row[2]}</div></div>`;
    }).join("");

    const errTimeline = (d.timeline || []).map(function (t) {
      return {
        ...t,
        count: (t.errors || 0) + (t.errors_4xx || 0),
        errors: (t.errors || 0) + (t.errors_4xx || 0),
      };
    });
    AW.renderTimelineChart("errors-chart", errTimeline, { yLabel: "errors / min", valueKey: "count", errKey: "errors" });
    const emeta = document.getElementById("errors-chart-meta");
    if (emeta) {
      emeta.textContent = errTimeline.length
        ? `4xx + 5xx per minute · ${errTimeline.length} buckets · hover for details`
        : `No errors in the last ${AW.hours}h`;
    }
    document.getElementById("status-codes-body").innerHTML = (d.status_codes || []).map(function (r) {
      return `<tr class="clickable" data-status="${r.status_code}">
        <td class="${AW.statusClass(r.status_code)}">${r.status_code}</td><td>${r.count}</td>
        <td>${r.affected_consumers || 0}</td>
        <td class="muted">${(r.last_seen || "").replace("T", " ").slice(0, 19)}</td></tr>`;
    }).join("") || `<tr><td colspan="4" class="muted">No HTTP errors</td></tr>`;
    document.querySelectorAll("#status-codes-body tr[data-status]").forEach(function (tr) {
      tr.addEventListener("click", function () { AW.openRequestLogs({ status: tr.dataset.status }); });
    });
    document.getElementById("fingerprints-body").innerHTML = (d.fingerprints || []).map(function (r) {
      const parsed = AW.parseEndpoint(r.endpoint || "");
      return `<tr class="clickable" data-path="${AW.escapeHtml(parsed.path)}">
        <td>${AW.escapeHtml(r.exception_type || "")}</td><td>${AW.escapeHtml(r.endpoint || "")}</td><td>${r.count}</td>
        <td class="muted">${(r.last_seen || "").replace("T", " ").slice(0, 19)}</td>
        <td><code>${AW.escapeHtml((r.sample || "").slice(0, 80))}</code></td></tr>`;
    }).join("") || `<tr><td colspan="5" class="muted">No grouped errors</td></tr>`;
    document.querySelectorAll("#fingerprints-body tr[data-path]").forEach(function (tr) {
      tr.addEventListener("click", function () { AW.openRequestLogs({ path: tr.dataset.path, status: "500" }); });
    });
    document.getElementById("validation-body").innerHTML = (d.validation || []).map(function (r) {
      const parsed = AW.parseEndpoint(r.endpoint || "");
      return `<tr class="clickable" data-path="${AW.escapeHtml(parsed.path)}">
        <td>${AW.escapeHtml(r.endpoint)}</td><td>${AW.escapeHtml(r.field)}</td>
        <td>${AW.escapeHtml(r.message)}</td><td>${r.count}</td></tr>`;
    }).join("") || `<tr><td colspan="4" class="muted">No 422s yet</td></tr>`;
    document.querySelectorAll("#validation-body tr[data-path]").forEach(function (tr) {
      tr.addEventListener("click", function () { AW.openRequestLogs({ path: tr.dataset.path, status: "422" }); });
    });
  };

  AW.loadPerformance = async function () {
    const d = await AW.api(`/api/performance?${AW.hoursQuery()}${AW.filterQuery()}`);
    document.getElementById("perf-cards").innerHTML = [
      ["Apdex", d.apdex, `T=${d.apdex_t_ms}ms`],
      ["p50", `${d.p50_ms}ms`, `${d.request_count} requests`],
      ["p75", `${d.p75_ms}ms`, "75th percentile"],
      ["p95", `${d.p95_ms}ms`, "95th percentile"],
      ["Avg", `${d.avg_ms}ms`, "mean latency"],
    ].map(function (row) {
      return `<div class="card"><div class="label">${row[0]}</div><div class="value">${row[1]}</div><div class="delta">${row[2]}</div></div>`;
    }).join("");

    document.getElementById("perf-endpoints-body").innerHTML = (d.endpoints || []).map(function (e) {
      const parsed = AW.parseEndpoint(e.endpoint);
      return `<tr class="clickable" data-path="${AW.escapeHtml(parsed.path)}">
        <td>${AW.escapeHtml(e.endpoint)}</td><td>${e.count}</td><td>${e.p50_ms}</td><td>${e.p75_ms}</td>
        <td>${e.p95_ms}</td><td>${e.avg_ms}</td><td>${e.apdex}</td></tr>`;
    }).join("") || `<tr><td colspan="7" class="muted">No data</td></tr>`;
    document.querySelectorAll("#perf-endpoints-body tr[data-path]").forEach(function (tr) {
      tr.addEventListener("click", function () { AW.openRequestLogs({ path: tr.dataset.path }); });
    });
  };

  AW.loadUptime = async function () {
    const d = await AW.api(`/api/uptime?${AW.hoursQuery()}`);
    const avail = d.availability != null ? `${(d.availability * 100).toFixed(2)}%` : "—";
    const hb = d.heartbeat_age_s != null ? `${Number(d.heartbeat_age_s).toFixed(0)}s ago` : "—";
    const last = d.last_result || {};
    const lastTxt = last.ok != null
      ? `${last.ok ? "up" : "down"}${last.latency_ms != null ? " · " + last.latency_ms + "ms" : ""}`
      : "—";
    document.getElementById("uptime-cards").innerHTML = [
      ["Availability", avail, `${AW.hours}h window`],
      ["Heartbeat", hb, "last external ping"],
      ["Last synthetic", lastTxt, last.message || last.path || ""],
    ].map(function (row) {
      return `<div class="card"><div class="label">${row[0]}</div><div class="value" style="font-size:1.35rem">${AW.escapeHtml(String(row[1]))}</div><div class="delta">${AW.escapeHtml(String(row[2]))}</div></div>`;
    }).join("");

    const timeline = (d.timeline || []).map(function (t) {
      return {
        bucket: t.bucket,
        count: t.total,
        total: t.total,
        ok_count: t.ok_count,
        errors: t.total - (t.ok_count || 0),
      };
    });
    AW.renderTimelineChart("uptime-chart", timeline, { yLabel: "checks / min" });
    document.getElementById("uptime-ping-url").textContent = `${AW.BASE}/api/uptime/ping`;
    const cfg = d.config || {};
    document.getElementById("uptime-config-meta").textContent =
      `Synthetic: ${cfg.enabled ? "on" : "off"} · path ${cfg.path} · every ${cfg.interval_seconds}s · expect ${cfg.expected_status}`;
    document.getElementById("uptime-recent-body").innerHTML = (d.recent || []).map(function (r) {
      return `<tr><td class="muted">${(r.timestamp || "").replace("T", " ").slice(0, 19)}</td>
      <td>${AW.escapeHtml(r.kind)}</td>
      <td class="${r.ok ? "status-2" : "status-5"}">${r.ok}</td>
      <td>${r.latency_ms != null ? Number(r.latency_ms).toFixed(1) : "—"}</td>
      <td>${r.status_code ?? "—"}</td>
      <td>${AW.escapeHtml(r.path || "—")}</td>
      <td>${AW.escapeHtml(r.message || "")}</td></tr>`;
    }).join("") || `<tr><td colspan="7" class="muted">No uptime checks yet</td></tr>`;
  };

  AW.updateConsumerBanner = function () {
    const id = AW.getFilterConsumer() || document.getElementById("filter-consumer")?.value.trim();
    const banner = document.getElementById("consumer-filter-banner");
    const clearBtn = document.getElementById("btn-clear-consumer");
    if (!banner) return;
    if (!id) {
      banner.style.display = "none";
      if (clearBtn) clearBtn.style.display = "none";
      return;
    }
    const label = window._consumerFilterLabel || id;
    banner.style.display = "block";
    banner.innerHTML = `Showing requests for consumer <strong>${AW.escapeHtml(label)}</strong> (<code>${AW.escapeHtml(id)}</code>). Click a request to inspect and debug.`;
    if (clearBtn) clearBtn.style.display = "inline-block";
  };

  AW.requestsOffset = 0;
  AW.requestsLimit = Number(sessionStorage.getItem("awatch_req_limit") || 50);
  AW.requestsTotal = 0;
  AW._parentDetailId = null;

  AW.loadRequests = async function () {
    AW.updateConsumerBanner();
    const path = document.getElementById("filter-path").value;
    const status = document.getElementById("filter-status").value;
    const consumer = document.getElementById("filter-consumer").value.trim() || AW.getFilterConsumer();
    const consumerGroup = document.getElementById("filter-consumer-group").value.trim() || AW.getFilterGroup();
    if (consumer && consumer !== AW.getFilterConsumer()) AW.setFilterConsumer(consumer);
    if (consumerGroup && consumerGroup !== AW.getFilterGroup()) AW.setFilterGroup(consumerGroup);
    const limitSelect = document.getElementById("requests-page-size");
    if (limitSelect) {
      AW.requestsLimit = Number(limitSelect.value || 50);
      sessionStorage.setItem("awatch_req_limit", String(AW.requestsLimit));
    }
    let q = `/api/requests?limit=${AW.requestsLimit}&offset=${AW.requestsOffset}&${AW.hoursQuery()}`;
    if (path) q += `&path_contains=${encodeURIComponent(path)}`;
    if (status) q += `&status_code=${status}`;
    if (consumer) q += `&consumer_id=${encodeURIComponent(consumer)}`;
    if (consumerGroup) q += `&consumer_group=${encodeURIComponent(consumerGroup)}`;
    const page = await AW.api(q);
    const rows = page.items || [];
    AW.requestsTotal = page.total || 0;
    const body = document.getElementById("requests-body");
    body.innerHTML = rows.map(function (r) {
      return `
      <tr data-id="${r.request_id}" class="clickable">
        <td class="muted">${(r.timestamp || "").replace("T", " ").slice(0, 19)}</td>
        <td>${r.method}</td><td class="path-cell">${AW.escapeHtml(r.path)}</td>
        <td class="${AW.statusClass(r.status_code)}">${r.status_code}</td>
        <td>${Number(r.duration_ms).toFixed(1)}</td>
      </tr>`;
    }).join("") || `<tr><td colspan="5" class="muted">No requests${consumer ? " for this consumer" : ""}</td></tr>`;
    body.querySelectorAll("tr[data-id]").forEach(function (tr) {
      tr.addEventListener("click", async function () {
        body.querySelectorAll("tr").forEach(function (x) { x.classList.remove("selected"); });
        tr.classList.add("selected");
        const detail = await AW.api(`/api/requests/${tr.dataset.id}`);
        AW._parentDetailId = detail.request_id;
        AW.renderRequestDetail(detail);
      });
    });
    const meta = document.getElementById("requests-page-meta");
    if (meta) {
      const start = AW.requestsTotal ? AW.requestsOffset + 1 : 0;
      const end = Math.min(AW.requestsOffset + AW.requestsLimit, AW.requestsTotal);
      meta.textContent = `${start}–${end} of ${AW.requestsTotal}`;
    }
    const prev = document.getElementById("requests-prev");
    const next = document.getElementById("requests-next");
    if (prev) prev.disabled = AW.requestsOffset <= 0;
    if (next) next.disabled = AW.requestsOffset + AW.requestsLimit >= AW.requestsTotal;
    AW.updateResetFiltersBtn();
  };

  AW.requestsFiltersActive = function () {
    const path = (document.getElementById("filter-path")?.value || "").trim();
    const pathSelect = document.getElementById("filter-path-select")?.value || "";
    const status = document.getElementById("filter-status")?.value || "";
    const consumer = (document.getElementById("filter-consumer")?.value || "").trim() || AW.getFilterConsumer();
    const group = (document.getElementById("filter-consumer-group")?.value || "").trim() || AW.getFilterGroup();
    return !!(path || pathSelect || status || consumer || group);
  };

  AW.updateResetFiltersBtn = function () {
    const btn = document.getElementById("btn-reset-filters");
    if (btn) btn.style.display = AW.requestsFiltersActive() ? "inline-block" : "none";
  };

  AW.resetRequestFilters = async function () {
    const pathInput = document.getElementById("filter-path");
    const pathSelect = document.getElementById("filter-path-select");
    const status = document.getElementById("filter-status");
    const consumer = document.getElementById("filter-consumer");
    const group = document.getElementById("filter-consumer-group");
    if (pathInput) pathInput.value = "";
    if (pathSelect) pathSelect.value = "";
    if (status) status.value = "";
    if (consumer) consumer.value = "";
    if (group) group.value = "";
    AW.setFilterConsumer("");
    AW.setFilterGroup("");
    window._consumerFilterLabel = "";
    AW.resetRequestsPage();
    AW.updateConsumerBanner();
    const detail = document.getElementById("request-detail");
    if (detail) {
      detail.innerHTML =
        `<div class="inspector-empty">Select a request to inspect headers, body, response, and server logs</div>`;
    }
    await AW.loadRequests();
  };

  AW.requestsPrevPage = function () {
    AW.requestsOffset = Math.max(0, AW.requestsOffset - AW.requestsLimit);
    AW.loadRequests();
  };

  AW.requestsNextPage = function () {
    if (AW.requestsOffset + AW.requestsLimit < AW.requestsTotal) {
      AW.requestsOffset += AW.requestsLimit;
      AW.loadRequests();
    }
  };

  AW.resetRequestsPage = function () {
    AW.requestsOffset = 0;
  };

  function prettyBody(raw) {
    if (raw == null || raw === "") return null;
    if (typeof raw === "object") return JSON.stringify(raw, null, 2);
    try { return JSON.stringify(JSON.parse(raw), null, 2); }
    catch { return String(raw); }
  }

  function kvTable(obj) {
    if (!obj || !Object.keys(obj).length) {
      return `<div class="empty-hint">None captured</div>`;
    }
    return `<table class="kv">${Object.entries(obj).map(function (entry) {
      const k = entry[0];
      const v = entry[1];
      return `<tr><td>${AW.escapeHtml(k)}</td><td>${AW.escapeHtml(typeof v === "object" ? JSON.stringify(v) : v)}</td></tr>`;
    }).join("")}</table>`;
  }

  function codeBlock(text, label) {
    const id = "cb-" + Math.random().toString(36).slice(2, 10);
    return `
      <div class="code-wrap">
        <div class="code-toolbar">
          <span class="code-label">${AW.escapeHtml(label || "Code")}</span>
          <button type="button" class="btn secondary btn-copy" data-copy-target="${id}">Copy</button>
        </div>
        <pre class="code-block" id="${id}">${AW.escapeHtml(text)}</pre>
      </div>`;
  }

  function codeOrHint(raw, hint, label) {
    const pretty = prettyBody(raw);
    if (!pretty) return `<div class="empty-hint">${hint}</div>`;
    return codeBlock(pretty, label || "Body");
  }

  function wireCopyButtons(root) {
    (root || document).querySelectorAll(".btn-copy").forEach(function (btn) {
      if (btn.dataset.bound === "1") return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", async function () {
        const el = document.getElementById(btn.dataset.copyTarget);
        if (!el) return;
        const text = el.textContent || "";
        try {
          await navigator.clipboard.writeText(text);
        } catch (_) {
          const range = document.createRange();
          range.selectNodeContents(el);
          const sel = window.getSelection();
          sel.removeAllRanges();
          sel.addRange(range);
          document.execCommand("copy");
          sel.removeAllRanges();
        }
        const prev = btn.textContent;
        btn.textContent = "Copied";
        setTimeout(function () { btn.textContent = prev || "Copy"; }, 1200);
      });
    });
  }

  function renderLogs(logs) {
    if (!logs || !logs.length) {
      return `<div class="empty-hint">No correlated server logs for this request. Logs are always kept for 5xx/exceptions; enable <code>capture_logs=True</code> to keep them on all traffic.</div>`;
    }
    return logs.map(function (l) {
      return `
      <div class="log-row">
        <div class="log-level ${AW.escapeHtml(l.level || "INFO")}">${AW.escapeHtml(l.level || "INFO")}</div>
        <div>
          <div class="log-meta">${AW.escapeHtml((l.timestamp || "").replace("T", " ").slice(0, 19))} · ${AW.escapeHtml(l.logger || "app")}</div>
          <div class="log-msg">${AW.escapeHtml(l.message || "")}</div>
        </div>
      </div>`;
    }).join("");
  }

  function renderSpans(spans) {
    const sqlOnly = (spans || []).filter(function (s) { return (s.kind || "") !== "http"; });
    if (!sqlOnly.length) {
      return `<div class="empty-hint">No SQL/dependency spans for this request. Outbound HTTP calls appear in the dropdown above when instrument_outbound_http=True.</div>`;
    }
    return sqlOnly.map(function (s) {
      return `
      <div class="span-row">
        <div><span class="tag">${AW.escapeHtml(s.kind || "span")}</span> ${AW.escapeHtml(s.name || "")}</div>
        <div class="muted">${Number(s.duration_ms || 0).toFixed(2)} ms</div>
      </div>`;
    }).join("");
  }

  AW.renderRequestDetail = function (r, opts) {
    opts = opts || {};
    if (!r || r.error) {
      document.getElementById("request-detail").innerHTML =
        `<div class="inspector-empty">Request not found</div>`;
      return;
    }
    const cats = (r.categories || []).map(function (c) {
      return `<span class="tag">${AW.escapeHtml(c)}</span>`;
    }).join("") || `<span class="muted">none</span>`;
    const consumer = r.consumer_id
      ? `${AW.escapeHtml(r.consumer_id)}${r.consumer_name ? " · " + AW.escapeHtml(r.consumer_name) : ""}${r.consumer_group ? " · " + AW.escapeHtml(r.consumer_group) : ""}`
      : "—";
    const outbound = r.outbound || [];
    const isOutbound = (r.direction || "inbound") === "outbound";
    const outboundSelect = isOutbound
      ? `<button class="btn secondary" type="button" id="btn-back-parent">← Back to parent</button>`
      : `<label class="outbound-select">Outbound calls
          <select id="outbound-select">
            <option value="">Parent request (${outbound.length} calls)</option>
            ${outbound.map(function (o) {
              return `<option value="${AW.escapeHtml(o.request_id)}">${AW.escapeHtml(o.method)} ${AW.escapeHtml(o.path)} · ${o.status_code} · ${Number(o.duration_ms || 0).toFixed(0)}ms</option>`;
            }).join("")}
          </select>
        </label>
        ${!outbound.length ? `<div class="empty-hint" style="margin-top:.35rem">No outbound HTTP calls recorded. Enable <code>instrument_outbound_http=True</code>.</div>` : ""}`;

    document.getElementById("request-detail").innerHTML = `
      <div class="insp-hero">
        <span class="insp-method">${AW.escapeHtml(r.method)}</span>
        <span class="insp-path">${AW.escapeHtml(r.path)}</span>
        <span class="insp-status ${AW.statusClass(r.status_code)}">${r.status_code}</span>
        ${isOutbound ? `<span class="tag">outbound</span>` : ""}
        <div class="insp-meta">
          <span><strong>${Number(r.duration_ms).toFixed(1)}</strong> ms</span>
          <span>route <strong>${AW.escapeHtml(r.route || "—")}</strong></span>
          <span>${AW.escapeHtml((r.timestamp || "").replace("T", " ").slice(0, 19))}</span>
          <span>id <strong>${AW.escapeHtml((r.request_id || "").slice(0, 8))}…</strong></span>
        </div>
      </div>

      <div class="outbound-bar">${outboundSelect}</div>

      <div class="insp-meta">
        <span>IP <strong>${AW.escapeHtml(r.client_ip || "—")}</strong></span>
        <span>Consumer <strong>${consumer}</strong></span>
        <span>Sizes <strong>${r.request_size || 0}B → ${r.response_size || 0}B</strong></span>
        <span>Categories <span class="pill-row" style="display:inline-flex">${cats}</span></span>
      </div>

      <div class="insp-tabs" id="insp-tabs">
        <button class="active" data-sec="req">Request</button>
        <button data-sec="res">Response</button>
        <button data-sec="logs">Server logs ${(r.logs || []).length ? "(" + r.logs.length + ")" : ""}</button>
        <button data-sec="spans">Timing ${(r.spans || []).filter(function (s) { return (s.kind || "") !== "http"; }).length ? "(" + (r.spans || []).filter(function (s) { return (s.kind || "") !== "http"; }).length + ")" : ""}</button>
        <button data-sec="err">Exception</button>
        <button data-sec="curl">cURL</button>
      </div>

      <div class="insp-section active" data-sec="req">
        <div class="label" style="margin-bottom:.45rem">Query params</div>
        ${kvTable(r.query_params)}
        <div class="label" style="margin:1rem 0 .45rem">Request headers</div>
        ${kvTable(r.request_headers)}
        <div class="label" style="margin:1rem 0 .45rem">Request body</div>
        ${codeOrHint(r.request_body, "Body not captured. Enable log_request_body=True on AWatch.", "Request body")}
      </div>

      <div class="insp-section" data-sec="res">
        <div class="label" style="margin-bottom:.45rem">Response headers</div>
        ${kvTable(r.response_headers)}
        <div class="label" style="margin:1rem 0 .45rem">Response body</div>
        ${codeOrHint(r.response_body, "Body not captured. Enable log_response_body=True on AWatch.", "Response body")}
        ${(r.validation_errors || []).length ? `
          <div class="label" style="margin:1rem 0 .45rem">Validation errors</div>
          ${codeBlock(JSON.stringify(r.validation_errors, null, 2), "Validation")}
        ` : ""}
      </div>

      <div class="insp-section" data-sec="logs">${renderLogs(r.logs)}</div>
      <div class="insp-section" data-sec="spans">${renderSpans(r.spans)}</div>
      <div class="insp-section" data-sec="err">
        ${r.exception
          ? `<div class="label" style="margin-bottom:.45rem">${AW.escapeHtml(r.exception_type || "Exception")}</div>
             ${codeBlock(r.exception, "Exception")}`
          : `<div class="empty-hint">No exception for this request.</div>`}
      </div>
      <div class="insp-section" data-sec="curl">
        ${codeBlock(r.curl || "", "cURL")}
      </div>
    `;

    document.querySelectorAll("#insp-tabs button").forEach(function (btn) {
      btn.addEventListener("click", function () {
        document.querySelectorAll("#insp-tabs button").forEach(function (b) { b.classList.remove("active"); });
        document.querySelectorAll("#request-detail .insp-section").forEach(function (s) { s.classList.remove("active"); });
        btn.classList.add("active");
        document.querySelector(`#request-detail .insp-section[data-sec="${btn.dataset.sec}"]`)?.classList.add("active");
      });
    });

    wireCopyButtons(document.getElementById("request-detail"));

    const select = document.getElementById("outbound-select");
    if (select) {
      select.addEventListener("change", async function () {
        const id = select.value;
        if (!id) {
          if (AW._parentDetailId) {
            const parent = await AW.api(`/api/requests/${AW._parentDetailId}`);
            AW.renderRequestDetail(parent);
          }
          return;
        }
        const child = await AW.api(`/api/requests/${id}`);
        AW.renderRequestDetail(child);
      });
    }
    const back = document.getElementById("btn-back-parent");
    if (back) {
      back.addEventListener("click", async function () {
        const parentId = r.parent_request_id || AW._parentDetailId;
        if (!parentId) return;
        const parent = await AW.api(`/api/requests/${parentId}`);
        AW._parentDetailId = parent.request_id;
        AW.renderRequestDetail(parent);
      });
    }
  };

  AW.openConsumer = async function (consumerId, name, group) {
    if (!consumerId) return;
    window._consumerFilterLabel = [name, group].filter(Boolean).join(" · ") || consumerId;
    AW.setFilterConsumer(consumerId);
    if (group) AW.setFilterGroup(group);
    document.getElementById("filter-consumer").value = consumerId;
    if (group) document.getElementById("filter-consumer-group").value = group;
    document.getElementById("request-detail").innerHTML =
      `<div class="inspector-empty">Select a request from this consumer to inspect</div>`;
    AW.updateConsumerBanner();
    await AW.switchTab("requests");
  };

  AW.clearConsumerFilter = async function () {
    AW.setFilterConsumer("");
    window._consumerFilterLabel = "";
    document.getElementById("filter-consumer").value = "";
    AW.updateConsumerBanner();
    document.getElementById("request-detail").innerHTML =
      `<div class="inspector-empty">Select a request to inspect headers, body, response, and server logs</div>`;
    await AW.loadRequests();
  };

  AW.loadConsumers = async function () {
    let q = `/api/consumers?${AW.hoursQuery()}&view=${AW.consumerView}`;
    if (AW.consumerGroupDrill) q += `&group=${encodeURIComponent(AW.consumerGroupDrill)}`;
    const d = await AW.api(q);
    const adoption = d.adoption || {};
    document.getElementById("adoption-line").textContent =
      `${adoption.unique ?? 0} unique · ${adoption.new ?? 0} new · ${adoption.returning ?? 0} returning`;

    const banner = document.getElementById("consumer-group-banner");
    if (AW.consumerView === "individuals" && AW.consumerGroupDrill) {
      banner.style.display = "block";
      banner.innerHTML = `Showing individuals in group <strong>${AW.escapeHtml(AW.consumerGroupDrill)}</strong>.
        <button class="btn secondary" type="button" style="margin-left:.5rem" onclick="AWatch.clearConsumerGroupDrill()">Back to all groups</button>`;
    } else {
      banner.style.display = "none";
    }

    const head = document.getElementById("consumers-head");
    const body = document.getElementById("consumers-body");
    if (AW.consumerView === "groups") {
      head.innerHTML = `<tr><th>Group</th><th>Unique consumers</th><th>Count</th><th>Errors</th><th>avg ms</th></tr>`;
      body.innerHTML = (d.rows || []).map(function (r) {
        return `
        <tr class="clickable" data-group="${AW.escapeHtml(r.group_name)}">
          <td><strong>${AW.escapeHtml(r.group_name)}</strong></td>
          <td>${r.unique_consumers}</td>
          <td>${r.count}</td>
          <td class="${r.errors ? "status-5" : ""}">${r.errors}</td>
          <td>${Number(r.avg_ms || 0).toFixed(1)}</td>
        </tr>`;
      }).join("") || `<tr><td colspan="5" class="muted">No consumer groups yet</td></tr>`;
      body.querySelectorAll("tr[data-group]").forEach(function (tr) {
        tr.addEventListener("click", function () {
          AW.consumerGroupDrill = tr.dataset.group;
          AW.consumerView = "individuals";
          document.querySelectorAll("#consumer-view-toggle button").forEach(function (b) {
            b.classList.toggle("active", b.dataset.view === "individuals");
          });
          AW.loadConsumers();
        });
      });
    } else {
      head.innerHTML = `<tr><th>Consumer</th><th>Name</th><th>Group</th><th>Count</th><th>Errors</th></tr>`;
      body.innerHTML = (d.rows || []).map(function (r) {
        const id = r.consumer_id || "";
        const name = r.consumer_name || "";
        const group = r.consumer_group || "";
        return `
        <tr class="clickable" data-consumer-id="${AW.escapeHtml(id)}" data-consumer-name="${AW.escapeHtml(name)}" data-consumer-group="${AW.escapeHtml(group)}">
          <td><strong>${AW.escapeHtml(id)}</strong></td>
          <td>${AW.escapeHtml(name)}</td>
          <td>${AW.escapeHtml(group)}</td>
          <td>${r.count}</td>
          <td class="${r.errors ? "status-5" : ""}">${r.errors}</td>
        </tr>`;
      }).join("") || `<tr><td colspan="5" class="muted">No consumers — use set_consumer() in code</td></tr>`;
      body.querySelectorAll("tr[data-consumer-id]").forEach(function (tr) {
        tr.addEventListener("click", function () {
          AW.openConsumer(tr.dataset.consumerId, tr.dataset.consumerName, tr.dataset.consumerGroup);
        });
      });
    }
  };

  AW.clearConsumerGroupDrill = function () {
    AW.consumerGroupDrill = null;
    AW.consumerView = "groups";
    document.querySelectorAll("#consumer-view-toggle button").forEach(function (b) {
      b.classList.toggle("active", b.dataset.view === "groups");
    });
    AW.loadConsumers();
  };

  AW.loadAlerts = async function () {
    const d = await AW.api("/api/triggers");
    document.getElementById("triggers-body").innerHTML = (d.history || []).map(function (r) {
      return `
      <tr><td class="muted">${(r.timestamp || "").replace("T", " ").slice(0, 19)}</td>
      <td>${AW.escapeHtml(r.trigger_name)}</td>
      <td class="${r.success ? "status-2" : "status-5"}">${r.success}</td>
      <td>${AW.escapeHtml(r.message || "")}</td></tr>`;
    }).join("") || `<tr><td colspan="4" class="muted">No trigger history</td></tr>`;
  };
})(window.AWatch);

// Global onclick aliases
function loadRequests() { return AWatch.loadRequests(); }
function clearConsumerFilter() { return AWatch.clearConsumerFilter(); }
function clearConsumerGroupDrill() { return AWatch.clearConsumerGroupDrill(); }
function requestsPrevPage() { return AWatch.requestsPrevPage(); }
function requestsNextPage() { return AWatch.requestsNextPage(); }
function resetRequestsPage() { return AWatch.resetRequestsPage(); }
function resetRequestFilters() { return AWatch.resetRequestFilters(); }
