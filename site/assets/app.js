/* Site script. It has no dependencies.
   Parts: colour theme, language memory, song page (player and script switch), library (filters and search). */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var base = ($('meta[name="site-base"]') || {}).content || "/";
  var lang = document.documentElement.dataset.lang || "te";

  function store(k, v) {
    try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; }
  }

  /* ------------------------------------------------------------ theme and language */

  var themeBtn = $(".theme-btn");
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var cur = document.documentElement.dataset.theme;
      if (!cur) cur = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
      var next = cur === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      store("theme", next);
    });
  }
  store("lang", lang);
  $$("[data-set-lang]").forEach(function (a) {
    a.addEventListener("click", function () {
      store("lang", a.dataset.setLang);
      // Keep the library filters when the language changes.
      if (location.search || location.hash) a.href = a.href.split(/[?#]/)[0] + location.search + location.hash;
    });
  });

  /* ------------------------------------------------------------ song page */

  $$(".yt").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var f = document.createElement("iframe");
      f.src = "https://www.youtube-nocookie.com/embed/" + btn.dataset.id + "?autoplay=1&rel=0&modestbranding=1";
      f.title = btn.getAttribute("aria-label") || "YouTube";
      f.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";
      f.allowFullscreen = true;
      btn.replaceWith(f);
    });
  });

  var verse = $("#verse");
  if (verse) {
    var article = verse.closest("[data-default-script]");
    var mode = store("script:" + lang) || (article && article.dataset.defaultScript) || "te";
    var setMode = function (m) {
      verse.dataset.script = m;
      $$(".script button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.script === m)); });
    };
    setMode(mode);
    $$(".script button").forEach(function (b) {
      b.addEventListener("click", function () { setMode(b.dataset.script); store("script:" + lang, b.dataset.script); });
    });
  }

  /* ------------------------------------------------------------ library */

  var catEl = $("#catalog");
  if (!catEl) return;
  var cat = JSON.parse(catEl.textContent);
  var tx = JSON.parse($("#i18n").textContent);
  var L = cat.labels;
  var items = cat.items;
  var list = $(".lib-list");
  var rows = {};
  $$(".entry", list).forEach(function (li) { rows[li.dataset.id] = li; });
  var TELUGU = /[ఀ-౿]/;

  var FOLD = [["aa", "a"], ["ee", "i"], ["oo", "u"], ["th", "t"], ["dh", "d"], ["sh", "s"], ["bh", "b"], ["kh", "k"],
    ["gh", "g"], ["ph", "p"], ["jh", "j"], ["chh", "ch"], ["w", "v"], ["z", "j"], ["q", "k"], ["x", "ks"], ["f", "p"],
    ["ou", "au"], ["y", "i"]];
  // The same rules as fold() in scripts/translit.py. Keep the two in step.
  function fold(t) {
    t = t.toLowerCase().normalize("NFKD").replace(/[^a-z0-9 ]+/g, " ");
    FOLD.forEach(function (p) { t = t.split(p[0]).join(p[1]); });
    return t.replace(/(.)\1+/g, "$1").replace(/\s+/g, " ").trim();
  }
  function cleanTe(t) { return t.normalize("NFC").replace(/[​-‍\s]+/g, " ").trim(); }

  var decLabel = function (d) { return lang === "te" ? d + "లు" : d + "s"; };
  var byLabel = function (labels) { return function (v) { return labels[v] || v; }; };
  var FACETS = [
    { key: "type", title: tx.f_type, chips: true, get: function (it) { return [it.ty]; }, label: byLabel(L.ty), order: "fixed", open: true },
    { key: "decade", title: tx.f_decade, chips: true, get: function (it) { return it.y ? [String(Math.floor(it.y / 10) * 10)] : []; }, label: decLabel, order: "num", open: true },
    { key: "year", title: tx.f_year, get: function (it) { return it.y ? [String(it.y)] : []; }, label: String, order: "num" },
    { key: "work", title: tx.f_work, get: function (it) { return it.w ? [it.w] : []; }, label: byLabel(L.w), order: "alpha", find: true },
    { key: "singer", title: tx.f_singer, get: function (it) { return it.s; }, label: byLabel(L.p), order: "count", find: true },
    { key: "lyricist", title: tx.f_lyricist, get: function (it) { return it.l; }, label: byLabel(L.p), order: "count", find: true },
    { key: "music", title: tx.f_music, get: function (it) { return it.m; }, label: byLabel(L.p), order: "count", find: true },
    { key: "source", title: tx.f_source, get: function (it) { return it.src ? [it.src] : []; }, label: byLabel(L.src), order: "count" },
    { key: "theme", title: tx.f_theme, chips: true, get: function (it) { return it.th; }, label: byLabel(L.th), order: "count" },
    { key: "format", title: tx.f_format, chips: true, get: function (it) { return [it.sh ? "1" : "0"]; }, label: byLabel(L.sh), order: "fixed" }
  ];

  var state = { q: "", sort: "new", sel: {} };
  FACETS.forEach(function (f) { state.sel[f.key] = new Set(); });
  var searchIdx = null, searchLoading = false;

  // Read the state from the URL.
  var params = new URLSearchParams(location.search);
  state.q = params.get("q") || "";
  state.sort = params.get("sort") || "new";
  FACETS.forEach(function (f) {
    var v = params.get(f.key);
    if (v) v.split(",").forEach(function (x) { if (x) state.sel[f.key].add(x); });
  });

  function writeUrl() {
    var p = new URLSearchParams();
    if (state.q) p.set("q", state.q);
    if (state.sort !== "new") p.set("sort", state.sort);
    FACETS.forEach(function (f) { if (state.sel[f.key].size) p.set(f.key, Array.from(state.sel[f.key]).join(",")); });
    var s = p.toString();
    history.replaceState(null, "", location.pathname + (s ? "?" + s : "") + location.hash);
  }

  function loadSearch() {
    if (searchIdx || searchLoading) return;
    searchLoading = true;
    fetch(base + "data/search.json").then(function (r) { return r.json(); }).then(function (d) {
      searchIdx = d; render();
    }).catch(function () { searchLoading = false; });
  }

  function queryMatch(it) {
    var q = state.q.trim();
    if (!q) return true;
    var extra = searchIdx && searchIdx[it.id];
    if (TELUGU.test(q)) {
      var qt = cleanTe(q);
      return it.kt.indexOf(qt) >= 0 || (extra && extra[0].indexOf(qt) >= 0);
    }
    var toks = fold(q).split(" ").filter(Boolean);
    if (!toks.length) return true;
    return toks.every(function (t) { return it.kr.indexOf(t) >= 0 || (extra && extra[1].indexOf(t) >= 0); });
  }

  function facetMatch(it, except) {
    for (var i = 0; i < FACETS.length; i++) {
      var f = FACETS[i];
      if (f.key === except) continue;
      var sel = state.sel[f.key];
      if (!sel.size) continue;
      var vals = f.get(it), ok = false;
      for (var j = 0; j < vals.length; j++) if (sel.has(vals[j])) { ok = true; break; }
      if (!ok) return false;
    }
    return true;
  }

  // Build the facet groups once. The counts change in render().
  var totals = {};
  FACETS.forEach(function (f) {
    var c = {};
    items.forEach(function (it) { f.get(it).forEach(function (v) { c[v] = (c[v] || 0) + 1; }); });
    totals[f.key] = c;
    var vals = Object.keys(c);
    if (f.order === "num") vals.sort(function (a, b) { return a - b; });
    else if (f.order === "alpha") vals.sort(function (a, b) { return f.label(a).localeCompare(f.label(b), lang); });
    else if (f.order === "count") vals.sort(function (a, b) { return c[b] - c[a] || f.label(a).localeCompare(f.label(b), lang); });
    else if (f.key === "type") vals = Object.keys(L.ty).filter(function (k) { return c[k]; });
    else vals.sort();
    f.values = vals;
  });

  var groups = $("#facet-groups");
  FACETS.forEach(function (f) {
    if (f.values.length < 2 && !state.sel[f.key].size) return;
    var d = document.createElement("details");
    d.className = "fg";
    d.open = !!(f.open || state.sel[f.key].size);
    var sum = document.createElement("summary");
    sum.innerHTML = '<span></span><span class="fsel"></span>';
    sum.firstChild.textContent = f.title;
    d.appendChild(sum);
    f.el = d;
    f.selEl = sum.lastChild;
    f.items = {};
    if (f.chips) {
      var box = document.createElement("div");
      box.className = "fg-chips";
      f.values.forEach(function (v) {
        var b = document.createElement("button");
        b.type = "button";
        b.innerHTML = '<span></span><span class="n"></span>';
        b.firstChild.textContent = f.label(v);
        b.addEventListener("click", function () { toggle(f.key, v); });
        box.appendChild(b);
        f.items[v] = b;
      });
      d.appendChild(box);
    } else {
      if (f.find && f.values.length > 8) {
        var inp = document.createElement("input");
        inp.type = "search"; inp.className = "fg-find"; inp.placeholder = tx.filter_more;
        inp.setAttribute("aria-label", f.title + " — " + tx.filter_more);
        inp.addEventListener("input", function () {
          var q = inp.value.trim(), qf = fold(q), te = TELUGU.test(q);
          f.values.forEach(function (v) {
            var lab = f.label(v);
            var hit = !q || (te ? lab.indexOf(q) >= 0 : fold(lab).indexOf(qf) >= 0);
            f.items[v].parentNode.hidden = !hit;
          });
        });
        d.appendChild(inp);
      }
      var ul = document.createElement("ul");
      f.values.forEach(function (v) {
        var li = document.createElement("li");
        li.innerHTML = '<label><input type="checkbox"><span class="lab"></span><span class="n"></span></label>';
        li.querySelector(".lab").textContent = f.label(v);
        var cb = li.querySelector("input");
        cb.value = v;
        cb.addEventListener("change", function () { toggle(f.key, v); });
        ul.appendChild(li);
        f.items[v] = li.firstChild;
      });
      d.appendChild(ul);
    }
    groups.appendChild(d);
  });

  function toggle(key, v) {
    var s = state.sel[key];
    if (s.has(v)) s.delete(v); else s.add(v);
    render();
  }

  var SORTS = {
    "new": function (a, b) { return (b.p || "").localeCompare(a.p || ""); },
    "old_film": function (a, b) { return (a.y || 9999) - (b.y || 9999) || (b.p || "").localeCompare(a.p || ""); },
    "new_film": function (a, b) { return (b.y || 0) - (a.y || 0) || (b.p || "").localeCompare(a.p || ""); },
    "views": function (a, b) { return b.v - a.v; },
    "title": function (a, b) { return a.t.localeCompare(b.t, lang); }
  };

  var countEl = $("#count"), chipsEl = $("#chips"), emptyEl = $("#empty"), fcount = $("#fcount"), doneBtn = $("#filters-done");
  var lastOrder = "";

  function plural(n) { return n === 1 ? tx.result_one : tx.results.replace("{n}", n); }

  function render() {
    var visible = items.filter(function (it) { return queryMatch(it) && facetMatch(it, null); });
    var vis = new Set(visible.map(function (it) { return it.id; }));
    items.forEach(function (it) { rows[it.id].hidden = !vis.has(it.id); });

    var order = items.slice().sort(SORTS[state.sort] || SORTS["new"]).map(function (it) { return it.id; }).join(",");
    if (order !== lastOrder) {
      var frag = document.createDocumentFragment();
      order.split(",").forEach(function (id) { frag.appendChild(rows[id]); });
      list.appendChild(frag);
      lastOrder = order;
    }

    // Facet counts: the items that match the query and all the other facets.
    FACETS.forEach(function (f) {
      if (!f.el) return;
      var c = {};
      items.forEach(function (it) {
        if (!queryMatch(it) || !facetMatch(it, f.key)) return;
        f.get(it).forEach(function (v) { c[v] = (c[v] || 0) + 1; });
      });
      var sel = state.sel[f.key];
      f.values.forEach(function (v) {
        var el = f.items[v], n = c[v] || 0, on = sel.has(v);
        el.querySelector(".n").textContent = n;
        if (f.chips) { el.setAttribute("aria-pressed", String(on)); el.disabled = !n && !on; }
        else { el.querySelector("input").checked = on; el.parentNode.classList.toggle("zero", !n && !on); }
      });
      f.selEl.textContent = sel.size ? sel.size : "";
    });

    // Active filter chips.
    chipsEl.innerHTML = "";
    var active = 0;
    FACETS.forEach(function (f) {
      state.sel[f.key].forEach(function (v) {
        active++;
        var b = document.createElement("button");
        b.type = "button"; b.className = "chip";
        b.innerHTML = '<b></b><span></span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7l10 10M17 7 7 17" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
        b.firstChild.textContent = f.title;
        b.children[1].textContent = f.label(v);
        b.addEventListener("click", function () { toggle(f.key, v); });
        chipsEl.appendChild(b);
      });
    });
    if (active > 1 || (active && state.q)) {
      var c = document.createElement("button");
      c.type = "button"; c.className = "chip chip-clear"; c.textContent = tx.clear;
      c.addEventListener("click", clearAll);
      chipsEl.appendChild(c);
    }
    fcount.textContent = active || "";
    countEl.textContent = plural(visible.length);
    doneBtn.textContent = tx.show.replace("{n}", visible.length);
    emptyEl.hidden = visible.length > 0;

    $$(".tl-y.on").forEach(function (a) { a.classList.toggle("sel", state.sel.year.has(a.dataset.year)); });
    writeUrl();
  }

  function clearAll() {
    FACETS.forEach(function (f) { state.sel[f.key].clear(); });
    state.q = ""; q.value = "";
    render();
  }

  var q = $("#q"), sortSel = $("#sort");
  q.value = state.q;
  sortSel.value = state.sort;
  var qTimer;
  q.addEventListener("input", function () {
    loadSearch();
    clearTimeout(qTimer);
    qTimer = setTimeout(function () { state.q = q.value; render(); }, 120);
  });
  q.addEventListener("focus", loadSearch, { once: true });
  sortSel.addEventListener("change", function () { state.sort = sortSel.value; render(); });
  $("#clear-all").addEventListener("click", clearAll);

  // Timeline: a year column toggles the year filter.
  $$(".tl-y.on").forEach(function (a) {
    a.addEventListener("click", function (e) {
      e.preventDefault();
      toggle("year", a.dataset.year);
      var lib = $("#library");
      if (lib.getBoundingClientRect().top > innerHeight * 0.6) lib.scrollIntoView({ behavior: "smooth" });
    });
  });

  // Filter sheet on small screens.
  var facets = $("#facets");
  function sheet(open) {
    facets.classList.toggle("open", open);
    document.body.classList.toggle("sheet-open", open);
  }
  $("#filters-open").addEventListener("click", function () { sheet(true); });
  $("#filters-close").addEventListener("click", function () { sheet(false); });
  doneBtn.addEventListener("click", function () { sheet(false); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") sheet(false); });
  document.body.addEventListener("click", function (e) {
    if (document.body.classList.contains("sheet-open") && !facets.contains(e.target) && !e.target.closest("#filters-open")) sheet(false);
  });

  if (state.q) loadSearch();
  render();
})();
