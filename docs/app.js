/* What Are the Odds? — front end for the Stock Probability Model.
   Reads data.json (made by step5_export_site_data.py) and draws everything. */

(() => {
  "use strict";

  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  const pct = (x, d = 1) => (x == null ? "–" : `${(x * 100).toFixed(d)}%`);
  const signed = (x, d = 1) => (x == null ? "–" : `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x * 100).toFixed(d)}%`);
  const money = (x) => `$${x.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const dollars = (x) => `$${Math.round(x).toLocaleString("en-US")}`;
  const niceDate = (s, opts = { month: "short", day: "numeric", year: "numeric" }) =>
    new Date(`${s}T12:00:00`).toLocaleDateString("en-US", opts);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  let DATA = null;
  let current = null;
  const charts = {};

  /* ---------- Plain-English clue sentences ---------- */
  function clueSentence(key, v) {
    const up = v >= 0;
    const a = Math.abs(v * 100).toFixed(1);
    switch (key) {
      case "ret_1d": return `${up ? "Up" : "Down"} ${a}% on the last trading day`;
      case "ret_5d": return `${up ? "Up" : "Down"} ${a}% over the past week`;
      case "ret_20d": return `${up ? "Up" : "Down"} ${a}% over the past month`;
      case "ret_60d": return `${up ? "Up" : "Down"} ${a}% over the past 3 months`;
      case "dist_ma20": return `${a}% ${up ? "above" : "below"} its 20-day average price`;
      case "dist_ma50": return `${a}% ${up ? "above" : "below"} its 50-day average price`;
      case "dist_ma200": return `${a}% ${up ? "above" : "below"} its 200-day average price`;
      case "rsi_14": return `RSI is ${v.toFixed(0)}${v > 70 ? ", it rose fast" : v < 30 ? ", it fell fast" : ""}`;
      case "vol_20d": return `Moves about ${(v * 100).toFixed(1)}% on a typical day`;
      case "range_pct": return `Daily high-to-low swing of about ${(v * 100).toFixed(1)}%`;
      case "volume_ratio": return `Trading volume is ${v.toFixed(1)}× normal`;
      case "mkt_ret_5d": return `Whole market ${up ? "up" : "down"} ${a}% this week`;
      case "mkt_ret_20d": return `Whole market ${up ? "up" : "down"} ${a}% this month`;
      case "vix_level": return `Market fear index (VIX) at ${v.toFixed(0)}`;
      case "vix_change_5d": return `Market fear ${up ? "up" : "down"} ${a}% this week`;
      default: return key;
    }
  }

  /* ---------- Hero strip: every stock on the coin-flip line ---------- */
  function domain() {
    const dev = Math.max(...DATA.stocks.map((s) => Math.abs(s.p - 0.5))) + 0.015;
    const span = Math.max(0.1, Math.ceil(dev / 0.05) * 0.05);
    return [0.5 - span, 0.5 + span];
  }

  function drawStrip() {
    const plot = $("#strip");
    const axis = $("#strip-axis");
    const W = plot.clientWidth;
    const [lo, hi] = domain();
    const x = (p) => ((Math.min(hi, Math.max(lo, p)) - lo) / (hi - lo)) * W;
    const D = W < 600 ? 11 : 15; // bead spacing in px (smaller dots on phones)
    plot.style.setProperty("--bead", `${D - 1}px`);

    // Dot plot: stack beads upward so none overlap
    const rows = [];
    const placed = [...DATA.stocks].sort((a, b) => a.p - b.p).map((s) => {
      const px = x(s.p);
      let r = 0;
      while ((rows[r] ?? -Infinity) > px - D) r++;
      rows[r] = px;
      return { s, px, r };
    });
    const H = rows.length * (D - 1) + 14;
    plot.style.height = `${H}px`;
    plot.style.setProperty("--x50", `${x(0.5)}px`);

    plot.innerHTML = "";
    for (const { s, px, r } of placed) {
      const b = document.createElement("button");
      b.className = `bead${s.p < 0.5 ? " below" : ""}`;
      b.style.left = `${px}px`;
      b.style.top = `${H - 8 - r * (D - 1)}px`;
      b.setAttribute("role", "listitem");
      b.setAttribute("aria-label", `${s.t}, ${s.name}: ${pct(s.p)} chance up`);
      b.dataset.t = s.t;
      if (current && current.t === s.t) b.setAttribute("aria-current", "true");
      b.addEventListener("click", () => select(s.t, true));
      const tip = () => showTip(b, `<b>${esc(s.t)}</b> ${pct(s.p)}`);
      b.addEventListener("mouseenter", tip);
      b.addEventListener("focus", tip);
      b.addEventListener("mouseleave", hideTip);
      b.addEventListener("blur", hideTip);
      plot.appendChild(b);
    }

    const step = (hi - lo) / 4;
    axis.innerHTML = [0, 1, 2, 3, 4].map((i) => {
      const p = lo + step * i;
      const isCoin = Math.abs(p - 0.5) < 1e-9;
      return `<span class="${isCoin ? "coin" : ""}" style="left:${x(p)}px">${isCoin ? "50% coin flip" : pct(p, 0)}</span>`;
    }).join("");

    const n = DATA.stocks.length;
    const ups = DATA.stocks.filter((s) => s.p >= 0.5).length;
    const maxDev = Math.max(...DATA.stocks.map((s) => Math.abs(s.p - 0.5))) * 100;
    const lean = ups === n ? `All ${n} lean up today` : ups === 0 ? `All ${n} lean down today` : `${ups} of ${n} lean up today`;
    $("#strip-note").textContent = `${lean}, none by more than ${Math.ceil(maxDev)} points. Click a dot.`;
  }

  /* ---------- Tooltip ---------- */
  function showTip(el, html) {
    const t = $("#tip");
    const r = el.getBoundingClientRect();
    t.innerHTML = html;
    t.hidden = false;
    t.style.left = `${r.left + r.width / 2}px`;
    t.style.top = `${r.top}px`;
  }
  function hideTip() { $("#tip").hidden = true; }

  /* ---------- Detail card ---------- */
  function select(ticker, scroll = false) {
    const s = DATA.stocks.find((x) => x.t === ticker);
    if (!s) return false;
    current = s;
    renderDetail(s);
    $$(".bead").forEach((b) => {
      if (b.dataset.t === s.t) b.setAttribute("aria-current", "true");
      else b.removeAttribute("aria-current");
    });
    $$("#table tbody tr").forEach((tr) => tr.setAttribute("aria-selected", tr.dataset.t === s.t ? "true" : "false"));
    if (location.hash.slice(1) !== s.t) history.replaceState(null, "", `#${s.t}`);
    if (scroll) {
      $("#detail").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
      $("#detail").focus({ preventScroll: true });
    }
    return true;
  }

  function renderDetail(s) {
    const up = css("--up"), down = css("--down");
    const diff = (s.p - 0.5) * 100;
    const vsCoin = Math.abs(diff) < 0.05
      ? "That's right at a coin flip."
      : `That's <b>${Math.abs(diff).toFixed(1)} points ${diff > 0 ? "above" : "below"}</b> a coin flip.`;

    // meter: show a window around 50% so small differences are visible
    const [lo, hi] = domain();
    const pos = (p) => ((Math.min(hi, Math.max(lo, p)) - lo) / (hi - lo)) * 100;
    const left = Math.min(pos(0.5), pos(s.p)), width = Math.abs(pos(s.p) - pos(0.5));

    let record = "";
    if (s.record) {
      const gap = s.record.actual - s.record.said;
      const judge = Math.abs(gap) < 0.02 ? "Pretty honest."
        : gap < 0 ? "So treat this one as a little optimistic."
        : "So it's been a little too cautious at this level.";
      record = `<p class="record">When the model said about <b>${pct(s.record.said, 0)}</b> in the test period, stocks actually went up <b>${pct(s.record.actual, 0)}</b> of the time (${s.record.count.toLocaleString()} predictions). ${judge}</p>`;
    }

    const c = s.clues;
    const clue = (label, v, f = signed) =>
      `<div>${label}<b class="${v > 0 ? "pos" : v < 0 ? "neg" : ""}">${f(v)}</b></div>`;
    const histChg = s.hist[s.hist.length - 1] / s.hist[0] - 1;

    $("#detail").innerHTML = `
      <div class="d-head">
        <h2 class="d-ticker">${esc(s.t)}<span class="d-name">${esc(s.name)}</span></h2>
        <span class="d-price">Closed at <b>${money(s.close)}</b> on ${niceDate(DATA.as_of, { month: "short", day: "numeric" })}
          <span class="${s.chg1d >= 0 ? "pos" : "neg"}">(${signed(s.chg1d)})</span></span>
      </div>
      <div class="d-main">
        <p class="odds">${(s.p * 100).toFixed(1)}<small>%</small></p>
        <p class="odds-sub">chance it closes above ${money(s.close)} five trading days later. ${vsCoin}</p>
        <div class="meter" aria-hidden="true">
          <div class="meter-track"><div class="meter-fill" style="left:${left}%;width:${width}%;background:${s.p >= 0.5 ? up : down}"></div></div>
          <div class="meter-scale"><span>${pct(lo, 0)}</span><span>50%</span><span>${pct(hi, 0)}</span></div>
        </div>
        ${record}
        <div class="clues">
          ${clue("Past week", c.ret_5d)}
          ${clue("Past month", c.ret_20d)}
          ${clue("Past 3 months", c.ret_60d)}
          ${clue("vs. 50-day avg", c.dist_ma50)}
          ${clue("vs. 200-day avg", c.dist_ma200)}
          <div>RSI<b>${c.rsi_14 == null ? "–" : c.rsi_14.toFixed(0)}</b></div>
        </div>
      </div>
      <div class="d-side">
        <h3>Why the model thinks this</h3>
        <ul class="reasons">
          ${s.why.map((w) => `
            <li><span class="sign ${w.dir > 0 ? "plus" : "minus"}" aria-hidden="true">${w.dir > 0 ? "+" : "−"}</span>
              <span>${esc(clueSentence(w.key, w.value))}<span class="eff">${w.dir > 0 ? "Raised" : "Lowered"} the chance</span></span></li>`).join("")}
        </ul>
        <div class="spark">
          <h3>Last 6 months <span class="${histChg >= 0 ? "pos" : "neg"}">${signed(histChg)}</span></h3>
          <div class="spark-box"><canvas id="spark" aria-label="${esc(s.t)} price over the last 6 months" role="img"></canvas></div>
        </div>
      </div>`;
    drawSpark(s);
  }

  function drawSpark(s) {
    if (charts.spark) charts.spark.destroy();
    const color = s.hist[s.hist.length - 1] >= s.hist[0] ? css("--up") : css("--down");
    charts.spark = new Chart($("#spark"), {
      type: "line",
      data: { labels: s.hist.map((_, i) => i), datasets: [{ data: s.hist, borderColor: color, borderWidth: 2, pointRadius: 0, pointHoverRadius: 4, tension: 0.2, fill: false }] },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { display: false }, tooltip: { displayColors: false, callbacks: { title: () => "", label: (ctx) => money(ctx.parsed.y) } } },
        scales: {
          x: { display: false },
          y: { grid: { color: css("--line-soft") }, border: { display: false }, ticks: { color: css("--muted"), maxTicksLimit: 4, callback: (v) => `$${v}` } },
        },
      },
    });
  }

  /* ---------- Table ---------- */
  let sortKey = "p", sortDir = -1, showAll = false;
  const PREVIEW_ROWS = 15;
  function renderTable() {
    const q = $("#filter").value.trim().toLowerCase();
    const [lo, hi] = domain();
    const pos = (p) => ((Math.min(hi, Math.max(lo, p)) - lo) / (hi - lo)) * 100;
    const ranked = [...DATA.stocks].sort((a, b) => b.p - a.p).map((s, i) => ({ ...s, rank: i + 1 }));
    const rows = ranked
      .filter((s) => !q || s.t.toLowerCase().includes(q) || s.name.toLowerCase().includes(q))
      .sort((a, b) => {
        const A = a[sortKey], B = b[sortKey];
        return (typeof A === "string" ? A.localeCompare(B) : A - B) * sortDir;
      });
    const tb = $("#table tbody");
    const more = $("#more");
    const limited = !q && !showAll && rows.length > PREVIEW_ROWS;
    more.hidden = !limited && !(showAll && !q);
    more.textContent = limited ? `Show all ${rows.length} stocks` : `Show top ${PREVIEW_ROWS} only`;
    $("#all .table-scroll").classList.toggle("has-more", !more.hidden);
    if (!rows.length) {
      tb.innerHTML = `<tr class="empty"><td colspan="6">No stock matches "${esc(q)}". Try a ticker like AAPL or a name like Apple.</td></tr>`;
      return;
    }
    tb.innerHTML = (limited ? rows.slice(0, PREVIEW_ROWS) : rows).map((s) => {
      const left = Math.min(pos(0.5), pos(s.p)), width = Math.abs(pos(s.p) - pos(0.5));
      const w = s.why[0];
      return `<tr data-t="${esc(s.t)}" tabindex="0" aria-selected="${current && current.t === s.t}">
        <td class="num muted">${s.rank}</td>
        <td><span class="tk">${esc(s.t)}</span><span class="nm">${esc(s.name)}</span></td>
        <td><div class="cbar"><b>${pct(s.p)}</b><div class="cbar-track"><div class="cbar-fill" style="left:${left}%;width:${width}%;background:${s.p >= 0.5 ? "var(--up)" : "var(--down)"}"></div></div></div></td>
        <td class="num hide-sm">${money(s.close)}</td>
        <td class="num hide-sm ${s.chg1d >= 0 ? "pos" : "neg"}">${signed(s.chg1d)}</td>
        <td class="hide-md reason-cell">${w.dir > 0 ? "+" : "−"} ${esc(clueSentence(w.key, w.value))}</td>
      </tr>`;
    }).join("");
  }

  function initTable() {
    renderTable();
    $("#filter").addEventListener("input", renderTable);
    $("#more").addEventListener("click", () => {
      showAll = !showAll;
      renderTable();
      if (!showAll) $("#all").scrollIntoView({ block: "start" });
    });
    $("#table tbody").addEventListener("click", (e) => {
      const tr = e.target.closest("tr[data-t]");
      if (tr) select(tr.dataset.t, true);
    });
    $("#table tbody").addEventListener("keydown", (e) => {
      const tr = e.target.closest("tr[data-t]");
      if (tr && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); select(tr.dataset.t, true); }
    });
    $$("#table th button").forEach((btn) => btn.addEventListener("click", () => {
      const k = btn.dataset.sort;
      if (k === sortKey) sortDir *= -1;
      else { sortKey = k; sortDir = k === "t" || k === "rank" ? 1 : -1; }
      $$("#table th button").forEach((b) => b.removeAttribute("aria-sort"));
      btn.setAttribute("aria-sort", sortDir === 1 ? "ascending" : "descending");
      renderTable();
    }));
  }

  /* ---------- Search ---------- */
  function initSearch() {
    $("#tickers").innerHTML = DATA.stocks.map((s) => `<option value="${esc(s.t)}">${esc(s.name)}</option>`).join("");
    $("#lookup").addEventListener("submit", (e) => {
      e.preventDefault();
      const q = $("#q").value.trim();
      const msg = $("#search-msg");
      if (!q) { msg.textContent = "Type a ticker like NVDA or a company like Apple."; return; }
      const ql = q.toLowerCase();
      const hit = DATA.stocks.find((s) => s.t.toLowerCase() === ql)
        || DATA.stocks.find((s) => s.name.toLowerCase() === ql)
        || DATA.stocks.find((s) => s.name.toLowerCase().startsWith(ql))
        || DATA.stocks.find((s) => s.name.toLowerCase().includes(ql));
      if (hit) { msg.textContent = ""; select(hit.t, true); }
      else msg.textContent = `"${q}" isn't one of the ${DATA.stocks.length} stocks this model covers. It only tracks the biggest US companies.`;
    });
  }

  /* ---------- Trust section ---------- */
  function renderTrust() {
    const m = DATA.metrics, rb = DATA.robustness;
    $("#trust-intro").textContent =
      "Two different questions: are the percentages honest, and could you make money following them? The answers are different, and the second one took some digging.";

    $("#cal-text").innerHTML =
      `Tested on <b>${m.n_test.toLocaleString()} predictions</b> from ${niceDate(m.test_start)} to ${niceDate(m.test_end)}, none of which the model trained on. ` +
      `When it says about 55%, stocks go up about 55% of the time. But it rarely strays far from 50%, and its skill at ranking winners above losers is barely better than a coin flip.`;

    $("#stats").innerHTML = `
      <div class="stat"><b>${m.auc_lr.toFixed(3)}</b>ranking skill (AUC). A coin flip scores 0.500</div>
      <div class="stat"><b>${m.auc_gb.toFixed(3)}</b>the fancier gradient boosting model</div>
      <div class="stat"><b>${pct(m.up_rate)}</b>of the time, stocks went up anyway</div>`;

    $("#bt-text").innerHTML =
      `Buying the model's top ${DATA.top_n} picks every week turned $1,000 into <b>${dollars(1000 * (1 + rb.model))}</b>, versus ${dollars(1000 * (1 + rb.all))} for buying all of them. ` +
      `That looked like a win until I checked where it came from. This list is <i>today's</i> biggest companies, so it quietly includes stocks like Nvidia and Palantir that we already know took off. ` +
      `Take out the ${rb.winners_removed.length} biggest winners and the edge disappears.`;

    const rows = [
      ["Model's top 10 vs. buying everything", `${signed(rb.model)} vs. ${signed(rb.all)}`, "Looks like a win at first", false],
      ["Dumb rule: buy the 10 jumpiest stocks", signed(rb.jumpy), "A no-brainer rule did about twice as well, so beating this list isn't hard", false],
      [`Remove the ${rb.winners_removed.length} biggest winners (${rb.winners_removed.slice(0, 4).join(", ")}…)`, `${signed(rb.model_nw)} vs. ${signed(rb.all_nw)}`, "The edge vanishes. It was survivorship bias", true],
      ["Add trading costs (0.1% per trade)", signed(rb.model_cost), `It swaps ${pct(rb.turnover, 0)} of its picks every week, and costs eat most of the edge`, false],
      ["Luck test (t-stat, 2+ means probably real)", `${rb.t.toFixed(2)} → ${rb.t_nw.toFixed(2)}`, "Easily explained by luck", false],
    ];
    $("#checks tbody").innerHTML = rows.map(([a, b, c, key]) =>
      `<tr class="${key ? "key" : ""}"><td>${esc(a)}</td><td class="num">${esc(b)}</td><td>${esc(c)}</td></tr>`).join("");

    drawCalibration();
    drawBacktest("full");
    $$(".toggle button").forEach((b) => b.addEventListener("click", () => {
      $$(".toggle button").forEach((x) => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
      drawBacktest(b.dataset.set);
    }));
  }

  function baseOptions() {
    const grid = css("--line-soft"), tick = css("--muted");
    return {
      responsive: true, maintainAspectRatio: false, animation: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: grid }, border: { color: css("--line") }, ticks: { color: tick } },
        y: { grid: { color: grid }, border: { display: false }, ticks: { color: tick } },
      },
    };
  }

  function drawCalibration() {
    if (charts.cal) charts.cal.destroy();
    const pts = DATA.calibration.map((c) => ({ x: c.said, y: c.actual, n: c.count }));
    const lo = Math.floor((Math.min(...pts.map((p) => Math.min(p.x, p.y))) - 0.01) * 20) / 20;
    const hi = Math.ceil((Math.max(...pts.map((p) => Math.max(p.x, p.y))) + 0.01) * 20) / 20;
    const o = baseOptions();
    o.scales.x = { ...o.scales.x, type: "linear", min: lo, max: hi, title: { display: true, text: "Model said", color: css("--ink-2") }, ticks: { ...o.scales.x.ticks, callback: (v) => pct(v, 0), stepSize: 0.05 } };
    o.scales.y = { ...o.scales.y, min: lo, max: hi, title: { display: true, text: "Actually went up", color: css("--ink-2") }, ticks: { ...o.scales.y.ticks, callback: (v) => pct(v, 0), stepSize: 0.05 } };
    o.plugins.tooltip = {
      filter: (item) => item.datasetIndex === 1,
      displayColors: false,
      callbacks: {
        title: () => "",
        label: (ctx) => [`Said ${pct(ctx.raw.x)}`, `Went up ${pct(ctx.raw.y)}`, `${ctx.raw.n.toLocaleString()} predictions`],
      },
    };
    const maxN = Math.max(...pts.map((p) => p.n));
    charts.cal = new Chart($("#cal-chart"), {
      type: "scatter",
      data: {
        datasets: [
          { data: [{ x: lo, y: lo }, { x: hi, y: hi }], showLine: true, borderColor: css("--coin"), borderWidth: 1.5, borderDash: [5, 5], pointRadius: 0, pointHoverRadius: 0 },
          { data: pts, showLine: true, borderColor: css("--accent"), backgroundColor: css("--accent"), borderWidth: 2,
            pointRadius: pts.map((p) => 4 + 8 * Math.sqrt(p.n / maxN)), pointHoverRadius: pts.map((p) => 6 + 8 * Math.sqrt(p.n / maxN)),
            pointBorderColor: css("--surface"), pointBorderWidth: 2 },
        ],
      },
      options: o,
    });
  }

  function drawBacktest(set) {
    if (charts.bt) charts.bt.destroy();
    const b = DATA.backtest;
    const accent = css("--accent"), grey = css("--ink-2"), amber = "#c98500";
    const series = set === "full"
      ? [
          ["Model's top 10", b.model, accent, []],
          ["Model after trading costs", b.model_cost, accent, [6, 5]],
          ["10 jumpiest stocks", b.jumpy, amber, []],
          ["All stocks equally", b.all, grey, []],
        ]
      : [
          ["Model's top 10", b.model_nw, accent, []],
          ["All stocks equally", b.all_nw, grey, []],
        ];
    $("#bt-cap").textContent = set === "full"
      ? "What $1,000 would have grown to, 2023 to today"
      : `Same test without ${DATA.robustness.winners_removed.join(", ")}`;
    $("#bt-legend").innerHTML = series.map(([name, d, color, dash]) =>
      `<span><i class="${dash.length ? "dash" : ""}" style="background:${color};border-color:${color}"></i>${esc(name)} <b>${dollars(d[d.length - 1])}</b></span>`).join("");

    const o = baseOptions();
    o.interaction = { mode: "index", intersect: false };
    o.scales.x.ticks = { ...o.scales.x.ticks, maxTicksLimit: 8, maxRotation: 0, callback: function (v) { return niceDate(this.getLabelForValue(v), { month: "short", year: "numeric" }); } };
    o.scales.y.ticks = { ...o.scales.y.ticks, callback: (v) => dollars(v) };
    o.plugins.tooltip = {
      callbacks: {
        title: (items) => niceDate(items[0].label),
        label: (ctx) => ` ${ctx.dataset.label}: ${dollars(ctx.parsed.y)}`,
      },
    };
    charts.bt = new Chart($("#bt-chart"), {
      type: "line",
      data: {
        labels: b.dates,
        datasets: series.map(([label, data, color, dash]) => ({
          label, data, borderColor: color, backgroundColor: color, borderDash: dash, borderWidth: 2,
          pointRadius: 0, pointHoverRadius: 4, tension: 0.1,
        })),
      },
      options: o,
    });
  }

  /* ---------- Boot ---------- */
  async function boot() {
    try {
      const res = await fetch("data.json", { cache: "no-cache" });
      if (!res.ok) throw new Error(res.status);
      DATA = await res.json();
    } catch (err) {
      $("#detail").innerHTML = `<p>Couldn't load the prediction data (data.json). If you're opening this file directly, run <code>python -m http.server 8000 --directory docs</code> and visit http://localhost:8000 instead.</p>`;
      return;
    }
    $("#foot-date").textContent = `Predictions use closing prices from ${niceDate(DATA.as_of)}.`;
    if (window.Chart) Chart.defaults.font.family = css("--font");

    const fromHash = decodeURIComponent(location.hash.slice(1)).toUpperCase();
    current = DATA.stocks.find((s) => s.t === fromHash) || DATA.stocks[0];
    drawStrip();
    initSearch();
    initTable();
    renderTrust();
    select(current.t, !!DATA.stocks.find((s) => s.t === fromHash));

    let rt;
    addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(drawStrip, 120); });
    addEventListener("scroll", hideTip, { passive: true });
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { renderDetail(current); drawCalibration(); drawBacktest($(".toggle [aria-pressed=true]").dataset.set); });
  }

  boot();
})();
