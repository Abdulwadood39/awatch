window.AWatch = window.AWatch || {};

(function (AW) {
  function bucketLabel(bucket) {
    const s = String(bucket || "");
    if (s.includes("T")) return s.split("T")[1].slice(0, 5);
    return s.slice(-5);
  }

  AW.renderTimelineChart = function (elId, timeline, opts) {
    opts = opts || {};
    const el = document.getElementById(elId);
    if (!el) return;
    const valueKey = opts.valueKey || "count";
    const errKey = opts.errKey || "errors";
    const yLabel = opts.yLabel || "count";
    const points = (timeline || []).slice(-48);
    if (!points.length) {
      el.innerHTML = `<div class="muted" style="padding:1rem 0">No data in this window</div>`;
      return;
    }
    const values = points.map(function (t) {
      return Number(t[valueKey] ?? t.count ?? t.total ?? 0);
    });
    const max = Math.max(1, ...values);
    const mid = Math.round(max / 2);
    const first = bucketLabel(points[0].bucket);
    const last = bucketLabel(points[points.length - 1].bucket);
    const bars = points.map(function (t, i) {
      const count = values[i];
      const errs = Number(t[errKey] ?? t.errors ?? 0);
      const h = Math.max(3, Math.round((count / max) * 140));
      const hasErr = errs > 0 || (t.total && t.ok_count != null && (t.total - t.ok_count) > 0);
      const tip = `${t.bucket || ""} · ${yLabel}=${count}`
        + (errs ? ` · errors=${errs}` : "")
        + (t.avg_ms != null ? ` · avg=${Number(t.avg_ms).toFixed(1)}ms` : "");
      return `<div class="bar ${hasErr ? "err" : ""}" style="height:${h}px" title="${AW.escapeHtml(tip)}"></div>`;
    }).join("");
    el.innerHTML = `
      <div class="chart-wrap">
        <div class="chart-y"><span>${max}</span><span>${mid}</span><span>0</span></div>
        <div class="chart">${bars}</div>
        <div class="chart-x"><span>${AW.escapeHtml(first)}</span><span>time →</span><span>${AW.escapeHtml(last)}</span></div>
      </div>
      <div class="chart-legend">
        <span><i class="c-req"></i> ${AW.escapeHtml(yLabel)} </span>
        <span><i class="c-err"></i>Red bars include errors</span>
      </div>`;
  };
})(window.AWatch);
