// Draws each <canvas data-chart="..."> with Chart.js (static/vendor/chart.umd.js).
// The page sends plain data: {"kind": "pie" | "bar" | "line", "labels": [...],
// "series": [{"name": ..., "cents": [...]}]}. Money stays in whole cents until it is shown.
(function () {
  "use strict";
  var styles = getComputedStyle(document.documentElement);
  var surface = styles.getPropertyValue("--surface").trim();
  Chart.defaults.color = styles.getPropertyValue("--muted").trim();
  Chart.defaults.borderColor = styles.getPropertyValue("--line").trim();
  var dollars = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
  var colors = ["#2f6f9f", "#c0612b", "#4b8b3b", "#8a5aa8", "#b8963a", "#3a8f8a", "#a8485a", "#6b6b6b"];

  function money(cents) {
    return dollars.format(cents / 100);
  }

  function config(chart) {
    var pie = chart.kind === "pie";
    var datasets = chart.series.map(function (series, index) {
      return {
        label: series.name,
        data: series.cents.map(function (cents) { return cents / 100; }),
        backgroundColor: pie ? colors : colors[index % colors.length],
        borderColor: pie ? surface : colors[index % colors.length],
      };
    });
    var options = {
      animation: false,
      plugins: {
        tooltip: {
          callbacks: {
            label: function (item) {
              var name = pie ? item.label : item.dataset.label;
              return name + ": " + money(Math.round(item.raw * 100));
            },
          },
        },
      },
    };
    if (!pie) {
      options.scales = { y: { ticks: { callback: function (value) { return money(Math.round(value * 100)); } } } };
    }
    return { type: chart.kind, data: { labels: chart.labels, datasets: datasets }, options: options };
  }

  document.querySelectorAll("canvas[data-chart]").forEach(function (canvas) {
    try {
      new Chart(canvas, config(JSON.parse(canvas.dataset.chart)));
      canvas.dataset.drawn = "yes";
    } catch (error) {
      canvas.dataset.drawn = "error";
    }
  });
})();
