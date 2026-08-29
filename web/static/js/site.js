(() => {
  const shell = document.querySelector("[data-app-shell]");
  if (!shell) return;

  const compact = document.querySelector("[data-nav-compact]");

  compact?.addEventListener("click", () => {
    const isCompact = shell.classList.toggle("is-compact");
    compact.setAttribute("aria-pressed", String(isCompact));
    compact.setAttribute(
      "aria-label",
      isCompact ? "Déployer la navigation" : "Réduire la navigation",
    );
    try { localStorage.setItem("navigation-compact", String(isCompact)); } catch (_) {}
  });

  try {
    if (localStorage.getItem("navigation-compact") === "true") {
      shell.classList.add("is-compact");
      compact?.setAttribute("aria-pressed", "true");
    }
  } catch (_) {}

  const levelSelect = document.querySelector("#id_geographic_level");
  const territorySelect = document.querySelector("#id_geographic_code");
  if (levelSelect && territorySelect) {
    const syncTerritories = () => {
      const level = levelSelect.value;
      const selected = territorySelect.value;
      let selectedStillAvailable = false;

      territorySelect.querySelectorAll("optgroup").forEach((group) => {
        const matches = group.label === level;
        group.hidden = !matches;
        group.querySelectorAll("option").forEach((option) => {
          option.disabled = !matches;
          option.hidden = !matches;
          if (matches && option.value === selected) selectedStillAvailable = true;
        });
      });

      if (!selectedStillAvailable) {
        const matchingGroup = [...territorySelect.querySelectorAll("optgroup")]
          .find((group) => group.label === level);
        const firstAvailable = matchingGroup?.querySelector("option:not(:disabled)");
        territorySelect.value = firstAvailable?.value ?? "";
      }
    };

    levelSelect.addEventListener("change", syncTerritories);
    syncTerritories();
  }

  const dashboard = document.querySelector("[data-territorial-dashboard]");
  if (dashboard) {
    const controls = {
      level: dashboard.querySelector("#map-level"),
      indicator: dashboard.querySelector("#map-indicator"),
      from: dashboard.querySelector("#chart-from"),
      to: dashboard.querySelector("#chart-to"),
    };
    const mapLayer = dashboard.querySelector("[data-map-layer]");
    const chart = dashboard.querySelector("[data-trend-chart]");
    const summary = dashboard.querySelector("[data-territory-summary]");
    const status = dashboard.querySelector(".map-status");
    const trendNote = dashboard.querySelector("[data-trend-note]");
    const trendLegend = dashboard.querySelector("[data-trend-legend]");
    const exportChart = dashboard.querySelector("[data-export-chart]");
    const exportCsv = dashboard.querySelector("[data-export-csv]");
    const state = { catalog: [], rows: [], chartRows: [], geo: {}, selected: null };

    const normalize = (value) => String(value ?? "").normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]/g, "");
    const selectedCatalog = () => state.catalog.find(
      (item) => `${item.source}:${item.code}` === controls.indicator.value
        && item.level === controls.level.value,
    );
    const fillSelect = (select, values, selected) => {
      select.replaceChildren(...values.map((value) => {
        const option = document.createElement("option");
        option.value = value.value ?? value;
        option.textContent = value.label ?? value;
        option.selected = option.value === String(selected ?? "");
        return option;
      }));
    };
    const api = async (params) => {
      const response = await fetch(`${dashboard.dataset.apiUrl}?${new URLSearchParams(params)}`, {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error("Impossible de récupérer les données.");
      return response.json();
    };
    const polygons = (geometry) => geometry.type === "Polygon"
      ? [geometry.coordinates] : geometry.coordinates;
    const everyPoint = (features) => features.flatMap((feature) =>
      polygons(feature.geometry).flatMap((polygon) => polygon.flatMap((ring) => ring)));
    const pathFor = (geometry, project) => polygons(geometry).map((polygon) =>
      polygon.map((ring) => ring.map((point, index) =>
        `${index ? "L" : "M"}${project(point).join(",")}`).join(" ") + " Z").join(" ")).join(" ");
    const featureKey = (feature) => String(feature.properties.code ?? "");
    const featureName = (feature) => feature.properties.nom ?? feature.properties.name ?? "Territoire";
    const rowForFeature = (feature, rows) => rows.find((row) =>
      (row.geographic_code && featureKey(feature) === String(row.geographic_code))
      || normalize(featureName(feature)) === normalize(row.geographic_name));
    const classification = (value, sorted, polarity) => {
      if (!Number.isFinite(value)) return "missing";
      const q1 = sorted[Math.floor((sorted.length - 1) / 3)];
      const q2 = sorted[Math.floor((sorted.length - 1) * 2 / 3)];
      let level = value <= q1 ? "low" : value <= q2 ? "medium" : "high";
      if (polarity === "higher_is_favorable") {
        level = level === "low" ? "high" : level === "high" ? "low" : level;
      }
      return level;
    };

    const renderChart = () => {
      chart.replaceChildren();
      const catalog = selectedCatalog();
      const indicatorLabel = catalog?.label ?? catalog?.code ?? "Indicateur";
      const unit = catalog?.unit ? ` (${catalog.unit})` : "";
      const nationalRows = state.rows.filter((row) =>
        String(row.geographic_code ?? "").toUpperCase() === "FR"
        || String(row.geographic_level ?? "").toLowerCase() === "national"
        || normalize(row.geographic_name) === "france");
      const averageRows = () => {
        const grouped = new Map();
        state.rows.forEach((row) => {
          const value = Number(row.value_numeric);
          if (!Number.isFinite(value)) return;
          const period = String(row.reference_period);
          const values = grouped.get(period) ?? [];
          values.push(value); grouped.set(period, values);
        });
        return [...grouped.entries()].map(([reference_period, values]) => ({
          reference_period,
          value_numeric: values.reduce((sum, value) => sum + value, 0) / values.length,
        }));
      };
      const nationalLabel = nationalRows.length
        ? "France"
        : `Moyenne nationale des ${controls.level.value === "region" ? "régions" : "départements"}`;
      const from = controls.from.value;
      const to = controls.to.value;
      const filterPeriod = (rows) => rows.filter((row) =>
        String(row.reference_period) >= from && String(row.reference_period) <= to)
        .sort((a, b) => String(a.reference_period).localeCompare(String(b.reference_period)));
      const benchmarkRows = filterPeriod(nationalRows.length ? nationalRows : averageRows());
      const territoryRows = state.selected ? filterPeriod(state.rows.filter((row) =>
        (row.geographic_code && String(row.geographic_code) === state.selected.code)
          || normalize(row.geographic_name) === normalize(state.selected.name))) : [];
      const chartSeries = [
        { label: nationalLabel, rows: benchmarkRows, national: true },
        ...(state.selected ? [{ label: state.selected.name, rows: territoryRows, national: false }] : []),
      ];
      trendLegend.replaceChildren();
      chartSeries.forEach((series) => {
        const marker = document.createElement("i");
        marker.setAttribute("aria-hidden", "true");
        marker.style.borderTop = series.national ? "3px dashed #6b7c7a" : "3px solid #087f73";
        marker.style.background = "transparent";
        const label = document.createElement("span");
        if (catalog?.code === "risk_score") {
          label.textContent = series.national
            ? "Moyenne nationale"
            : `Score ${series.label}`;
        } else {
          label.textContent = `${series.label} — ${indicatorLabel}${unit}`;
        }
        trendLegend.append(marker, label);
      });
      trendLegend.hidden = false;
      state.chartRows = chartSeries.flatMap((series) => series.rows.map((row) => ({
        ...row, series_label: series.label,
      })));
      const periods = [...new Set(state.chartRows.map((row) => String(row.reference_period)))].sort();
      exportChart.disabled = periods.length < 2;
      exportCsv.disabled = state.chartRows.length === 0;
      if (periods.length < 2) {
        trendNote.textContent = periods.length
          ? "Une seule période est disponible pour cet indicateur : aucune progression ne peut être calculée."
          : "Aucune donnée disponible sur l’intervalle sélectionné.";
        return;
      }
      trendNote.textContent = `${periods.length} périodes affichées, de ${periods[0]} à ${periods.at(-1)}.`;
      const values = state.chartRows.map((row) => Number(row.value_numeric));
      const min = Math.min(...values); const max = Math.max(...values); const span = max - min || 1;
      const x = (period) => 70 + periods.indexOf(String(period)) * 780 / (periods.length - 1);
      const y = (value) => 245 - (value - min) * 190 / span;
      const ns = "http://www.w3.org/2000/svg";
      const svg = (name, attributes = {}) => {
        const node = document.createElementNS(ns, name);
        Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
        return node;
      };
      const formatValue = (value) => Number(value).toLocaleString("fr-FR", { maximumFractionDigits: 2 });
      for (let i = 0; i < 5; i += 1) {
        const tickValue = max - i * span / 4;
        const tickY = 55 + i * 47.5;
        chart.append(svg("line", { x1: 70, x2: 850, y1: tickY, y2: tickY, class: "chart-gridline" }));
        const label = svg("text", { x: 60, y: tickY + 4, class: "chart-axis-label chart-axis-label--y" });
        label.textContent = formatValue(tickValue);
        chart.append(label);
      }
      chart.append(svg("line", { x1: 70, x2: 70, y1: 55, y2: 245, class: "chart-axis" }));
      chart.append(svg("line", { x1: 70, x2: 850, y1: 245, y2: 245, class: "chart-axis" }));
      const xTickStep = Math.max(1, Math.ceil((periods.length - 1) / 6));
      periods.forEach((period, i) => {
        if (i % xTickStep !== 0 && i !== periods.length - 1) return;
        chart.append(svg("line", { x1: x(period), x2: x(period), y1: 245, y2: 251, class: "chart-axis" }));
        const label = svg("text", { x: x(period), y: 268, class: "chart-axis-label chart-axis-label--x" });
        label.textContent = period;
        chart.append(label);
      });
      const unitLabel = svg("text", { x: 14, y: 150, class: "chart-axis-title", transform: "rotate(-90 14 150)" });
      unitLabel.textContent = catalog?.unit || "Valeur";
      chart.append(unitLabel);
      chartSeries.forEach((series) => {
        if (series.rows.length < 2) return;
        const polyline = svg("polyline", {
          points: series.rows.map((row) => `${x(row.reference_period)},${y(Number(row.value_numeric))}`).join(" "),
          class: "chart-line",
          stroke: series.national ? "#6b7c7a" : "#087f73",
          "stroke-dasharray": series.national ? "10 7" : "none",
        });
        chart.append(polyline);
        if (series.national) return;
        series.rows.forEach((row) => {
          const point = svg("circle", {
            cx: x(row.reference_period), cy: y(Number(row.value_numeric)), r: 5, class: "chart-point",
          });
          const title = svg("title");
          title.textContent = `${row.reference_period} : ${formatValue(row.value_numeric)}`;
          point.append(title); chart.append(point);
        });
      });
    };

    const renderMap = async () => {
      const periodRows = state.rows.filter((row) => String(row.reference_period) === controls.to.value);
      const url = controls.level.value === "department"
        ? dashboard.dataset.departmentsGeojson : dashboard.dataset.regionsGeojson;
      state.geo[url] ??= await fetch(url).then((response) => response.json());
      const isMetropolitan = (feature) => everyPoint([feature]).some(([x, y]) =>
        x >= -6.5 && x <= 10 && y >= 41 && y <= 52);
      const features = state.geo[url].features.filter(isMetropolitan);
      const points = everyPoint(features);
      const xs = points.map((point) => point[0]); const ys = points.map((point) => point[1]);
      const minX = Math.min(...xs); const maxX = Math.max(...xs);
      const minY = Math.min(...ys); const maxY = Math.max(...ys);
      const scale = Math.min(650 / (maxX - minX), 550 / (maxY - minY));
      const project = ([x, y]) => [35 + (x - minX) * scale, 585 - (y - minY) * scale];
      const values = periodRows.map((row) => Number(row.value_numeric)).filter(Number.isFinite).sort((a, b) => a - b);
      const item = selectedCatalog();
      mapLayer.replaceChildren();
      features.forEach((feature) => {
        const row = rowForFeature(feature, periodRows);
        const value = Number(row?.value_numeric);
        const hasValue = Number.isFinite(value);
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", pathFor(feature.geometry, project));
        path.setAttribute("class", `map-territory level-${classification(value, values, item.polarity)}`);
        path.setAttribute("tabindex", "0"); path.setAttribute("role", "button");
        const displayedValue = hasValue
          ? value.toLocaleString("fr-FR", { maximumFractionDigits: 2 })
          : "indisponible";
        path.setAttribute("aria-label", `${featureName(feature)} : ${displayedValue}`);
        const select = (submitDashboard = true) => {
          if (!hasValue) return;
          state.selected = { code: featureKey(feature), name: featureName(feature) };
          mapLayer.querySelectorAll(".is-selected").forEach((node) => node.classList.remove("is-selected"));
          path.classList.add("is-selected");
          summary.innerHTML = `<p class="eyebrow">Territoire sélectionné</p><h3>${featureName(feature)}</h3><strong class="territory-value">${value.toLocaleString("fr-FR", { maximumFractionDigits: 2 })}${item.unit ? ` ${item.unit}` : ""}</strong><p>${item.label} · ${controls.to.value}</p><span class="badge">Position relative : ${classification(value, values, item.polarity)}</span>`;
          renderChart();
          if (submitDashboard) {
            const params = new URLSearchParams(window.location.search);
            params.set("geographic_level", controls.level.value);
            params.set("geographic_code", featureKey(feature));
            params.delete("reference_period");
            params.delete("comparison_period");
            params.delete("comparison_model_version");
            window.location.search = params.toString();
          }
        };
        path.addEventListener("click", () => select());
        path.addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key)) select(); });
        const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
        title.textContent = `${featureName(feature)} — ${displayedValue}`;
        path.append(title); mapLayer.append(path);
        if (dashboard.dataset.selectedTerritory === featureKey(feature)) {
          select(false);
        }
      });
      status.textContent = `${features.length} territoires représentés pour ${controls.to.value}. Les couleurs indiquent une position relative, pas un diagnostic.`;
    };

    const loadIndicator = async () => {
      status.textContent = "Chargement des données…";
      state.selected = null; summary.innerHTML = "<p class='empty-state'>Sélectionnez un territoire sur la carte.</p>";
      const item = selectedCatalog();
      state.rows = await api({ source: item.source, indicator_code: item.code, geographic_level: item.level });
      const periods = [...new Set(state.rows.map((row) => String(row.reference_period)))].sort();
      fillSelect(controls.from, periods, periods[0]);
      fillSelect(controls.to, periods, periods.at(-1));
      await renderMap(); renderChart();
    };
    const syncIndicators = async () => {
      const items = state.catalog.filter((item) => item.level === controls.level.value);
      fillSelect(controls.indicator, items.map((item) => ({ value: `${item.source}:${item.code}`, label: `${item.group} — ${item.label}` })));
      await loadIndicator();
    };
    controls.level.addEventListener("change", () => syncIndicators().catch((error) => { status.textContent = error.message; }));
    controls.indicator.addEventListener("change", () => loadIndicator().catch((error) => { status.textContent = error.message; }));
    controls.from.addEventListener("change", () => {
      if (controls.from.value > controls.to.value) controls.to.value = controls.from.value;
      renderMap().then(renderChart).catch((error) => { status.textContent = error.message; });
    });
    controls.to.addEventListener("change", () => {
      if (controls.to.value < controls.from.value) controls.from.value = controls.to.value;
      renderMap().then(renderChart).catch((error) => { status.textContent = error.message; });
    });
    const download = (blob, filename) => {
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob); link.download = filename; link.click();
      setTimeout(() => URL.revokeObjectURL(link.href), 0);
    };
    exportCsv.addEventListener("click", () => {
      const item = selectedCatalog();
      const header = ["periode", "territoire", "indicateur", "valeur", "unite"];
      const escape = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
      const rows = state.chartRows.map((row) => [
        row.reference_period,
        row.series_label ?? state.selected?.name ?? row.geographic_name ?? "France",
        item?.label ?? item?.code ?? "",
        row.value_numeric,
        item?.unit ?? row.unit ?? "",
      ]);
      const csv = "\ufeff" + [header, ...rows].map((row) => row.map(escape).join(";")).join("\r\n");
      download(new Blob([csv], { type: "text/csv;charset=utf-8" }), "evolution-territoriale.csv");
    });
    exportChart.addEventListener("click", () => {
      const clone = chart.cloneNode(true);
      const style = document.createElementNS("http://www.w3.org/2000/svg", "style");
      style.textContent = ".chart-gridline{stroke:#dce8e6;stroke-width:1}.chart-axis{stroke:#58706c;stroke-width:1.5}.chart-axis-label,.chart-axis-title{fill:#58706c;font:12px sans-serif}.chart-axis-label--x{text-anchor:middle}.chart-axis-label--y{text-anchor:end}.chart-line{fill:none;stroke:#087f73;stroke-width:4}.chart-point{fill:#fff;stroke:#087f73;stroke-width:3}";
      clone.prepend(style);
      clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
      const image = new Image();
      const source = new Blob([new XMLSerializer().serializeToString(clone)], { type: "image/svg+xml" });
      const url = URL.createObjectURL(source);
      image.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = 1800; canvas.height = 600;
        const context = canvas.getContext("2d");
        context.fillStyle = "#ffffff"; context.fillRect(0, 0, canvas.width, canvas.height);
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        URL.revokeObjectURL(url);
        canvas.toBlob((blob) => { if (blob) download(blob, "evolution-territoriale.png"); }, "image/png");
      };
      image.src = url;
    });
    if (levelSelect?.value) controls.level.value = levelSelect.value;
    api({ catalog: "1" }).then((catalog) => { state.catalog = catalog; return syncIndicators(); })
      .catch((error) => { status.textContent = error.message; });
  }
})();
