window.AWatch = window.AWatch || {};

(function (AW) {
  function detectGrain(points) {
    if (points && points[0] && points[0].grain) return points[0].grain;
    const b = String((points && points[0] && points[0].bucket) || "");
    if (b.length <= 10) return "day";
    if (b.length <= 13) return "hour";
    return "minute";
  }

  function unitLabel(grain) {
    if (grain === "day") return "day";
    if (grain === "hour") return "hour";
    return "min";
  }

  function pad2(n) {
    return String(n).padStart(2, "0");
  }

  /** Parse a UTC bucket key from the API into a Date. */
  function parseBucketUtc(bucket, grain) {
    const s = String(bucket || "").trim();
    if (!s) return null;
    let iso = s;
    if (grain === "day" && /^\d{4}-\d{2}-\d{2}$/.test(s)) {
      iso = s + "T00:00:00.000Z";
    } else if (grain === "hour" && /^\d{4}-\d{2}-\d{2}T\d{2}$/.test(s)) {
      iso = s + ":00:00.000Z";
    } else if (grain === "minute" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(s)) {
      iso = s + ":00.000Z";
    } else if (!/[zZ]|[+-]\d{2}:?\d{2}$/.test(s)) {
      iso = s.includes("T") ? s + "Z" : s + "T00:00:00.000Z";
    }
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  /** Axis / short label in the browser's local timezone. */
  function bucketLabel(bucket, grain) {
    const d = parseBucketUtc(bucket, grain);
    if (!d) {
      const s = String(bucket || "");
      if (grain === "day") return s.slice(5);
      if (grain === "hour") {
        if (s.includes("T")) return s.split("T")[1].slice(0, 2) + ":00";
        return s.slice(-2) + ":00";
      }
      if (s.includes("T")) return s.split("T")[1].slice(0, 5);
      return s.slice(-5);
    }
    if (grain === "day") {
      return pad2(d.getMonth() + 1) + "-" + pad2(d.getDate());
    }
    if (grain === "hour") {
      return pad2(d.getHours()) + ":00";
    }
    return pad2(d.getHours()) + ":" + pad2(d.getMinutes());
  }

  /** Full local timestamp for tooltips. */
  function bucketLocalTitle(bucket, grain) {
    const d = parseBucketUtc(bucket, grain);
    if (!d) return String(bucket || "");
    if (grain === "day") {
      return d.toLocaleDateString(undefined, {
        weekday: "short", year: "numeric", month: "short", day: "numeric",
      });
    }
    return d.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: grain === "minute" ? "2-digit" : undefined,
      hour12: false,
    });
  }

  function localTzName() {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || "local time";
    } catch (_) {
      return "local time";
    }
  }

  function failedCount(t) {
    if (t.ok_count != null) {
      return Math.max(0, Number(t.total ?? t.count ?? 0) - Number(t.ok_count || 0));
    }
    const total = Number(t.count ?? t.total ?? 0);
    const e4 = Number(t.errors_4xx || 0);
    const e5 = Number(t.errors || 0);
    // Errors chart remaps count/errors to combined failures already.
    if (t.errors_4xx != null && total === e5 && e5 >= e4) {
      return Math.min(total, e5);
    }
    if (t.errors_4xx != null) {
      return Math.min(total, e4 + e5);
    }
    return Math.min(total, e5);
  }

  AW.timelineUnitLabel = function (timeline) {
    return unitLabel(detectGrain(timeline || []));
  };

  AW.renderTimelineChart = function (elId, timeline, opts) {
    opts = opts || {};
    const el = document.getElementById(elId);
    if (!el) return;
    const valueKey = opts.valueKey || "count";
    const points = timeline || [];
    const grain = detectGrain(points);
    const unit = unitLabel(grain);
    const yLabel = opts.yLabel || ("requests / " + unit);
    const successLabel = opts.successLabel || "success";
    const failLabel = opts.failLabel || "failed";
    const emptyLabel = opts.emptyLabel || "No requests";
    const legendOk = opts.legendOk || "Success";
    const legendFail = opts.legendFail || "Failed (4xx/5xx)";
    if (!points.length) {
      el.innerHTML = `<div class="muted" style="padding:1rem 0">No data in this window</div>`;
      return;
    }
    const values = points.map(function (t) {
      return Number(t[valueKey] ?? t.count ?? t.total ?? 0);
    });
    const max = Math.max(1, ...values);
    const mid = Math.round(max / 2);
    const first = bucketLabel(points[0].bucket, grain);
    const midIdx = Math.floor(points.length / 2);
    const midLabel = bucketLabel(points[midIdx].bucket, grain);
    const last = bucketLabel(points[points.length - 1].bucket, grain);
    const bars = points.map(function (t, i) {
      const total = values[i];
      const failed = Math.min(total, failedCount(t));
      const success = Math.max(0, total - failed);
      const h = total <= 0 ? 2 : Math.max(6, Math.round((total / max) * 140));
      const okPct = total > 0 ? (success / total) * 100 : 0;
      const failPct = total > 0 ? (failed / total) * 100 : 0;
      const localTitle = bucketLocalTitle(t.bucket, grain);
      const tipHtml = total <= 0
        ? `<strong>${AW.escapeHtml(localTitle)}</strong><br>${AW.escapeHtml(emptyLabel)}`
        : `<strong>${AW.escapeHtml(localTitle)}</strong><br>`
          + `${total} total<br>`
          + `<span class="tip-ok">${success} ${AW.escapeHtml(successLabel)}</span><br>`
          + `<span class="tip-fail">${failed} ${AW.escapeHtml(failLabel)}</span>`
          + (t.avg_ms != null ? `<br>avg ${Number(t.avg_ms).toFixed(1)}ms` : "");

      let segs = "";
      if (total <= 0) {
        segs = `<div class="bar-seg empty" style="height:100%"></div>`;
      } else {
        if (failPct > 0) {
          segs += `<div class="bar-seg fail" style="height:${failPct}%"></div>`;
        }
        if (okPct > 0) {
          segs += `<div class="bar-seg ok" style="height:${okPct}%"></div>`;
        }
      }
      return `<div class="bar ${total <= 0 ? "is-empty" : ""}" style="height:${h}px" tabindex="0" aria-label="${total} total, ${success} ${successLabel}, ${failed} ${failLabel}">
        <div class="bar-tip">${tipHtml}</div>
        ${segs}
      </div>`;
    }).join("");
    el.innerHTML = `
      <div class="chart-wrap">
        <div class="chart-y"><span>${max}</span><span>${mid}</span><span>0</span></div>
        <div class="chart">${bars}</div>
        <div class="chart-x"><span>${AW.escapeHtml(first)}</span><span>${AW.escapeHtml(midLabel)}</span><span>${AW.escapeHtml(last)}</span></div>
      </div>
      <div class="chart-legend">
        <span><i class="c-req"></i> ${AW.escapeHtml(legendOk)}</span>
        <span><i class="c-err"></i> ${AW.escapeHtml(legendFail)}</span>
        <span class="muted">${AW.escapeHtml(yLabel)} · ${AW.escapeHtml(localTzName())}</span>
      </div>`;
  };
})(window.AWatch);
