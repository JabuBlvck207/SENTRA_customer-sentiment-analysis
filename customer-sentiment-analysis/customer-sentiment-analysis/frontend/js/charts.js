/* Chart.js helpers */

let doughnutChart = null;
let trendChart = null;
let themeChart = null;

const SENTIMENT_COLORS = {
  Positive: '#16a34a',
  Negative: '#dc2626',
  Neutral: '#f59e0b',
};

function destroyChart(chart) {
  if (chart) {
    chart.destroy();
  }
  return null;
}

function renderDoughnut(stats) {
  const canvas = document.getElementById('doughnutChart');
  const empty = document.getElementById('doughnutEmpty');
  if (!canvas) return;

  const pos = stats.positive_count || 0;
  const neg = stats.negative_count || 0;
  const neu = stats.neutral_count || 0;
  const total = pos + neg + neu;

  doughnutChart = destroyChart(doughnutChart);

  if (total === 0) {
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');

  doughnutChart = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: ['Positive', 'Negative', 'Neutral'],
      datasets: [{
        data: [pos, neg, neu],
        backgroundColor: [SENTIMENT_COLORS.Positive, SENTIMENT_COLORS.Negative, SENTIMENT_COLORS.Neutral],
        borderWidth: 0,
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { usePointStyle: true, padding: 16, font: { size: 12 } },
        },
      },
      cutout: '62%',
    },
  });
}

function renderTrend(trends) {
  const canvas = document.getElementById('trendChart');
  const empty = document.getElementById('trendEmpty');
  if (!canvas) return;

  trendChart = destroyChart(trendChart);

  if (!trends || trends.length === 0) {
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');

  const labels = trends.map(t => t.date);
  const pos = trends.map(t => t.Positive || 0);
  const neg = trends.map(t => t.Negative || 0);
  const neu = trends.map(t => t.Neutral || 0);

  trendChart = new Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Positive',
          data: pos,
          borderColor: SENTIMENT_COLORS.Positive,
          backgroundColor: 'rgba(52,211,153,0.12)',
          fill: true,
          tension: 0.35,
          pointRadius: 3,
          pointBackgroundColor: SENTIMENT_COLORS.Positive,
        },
        {
          label: 'Negative',
          data: neg,
          borderColor: SENTIMENT_COLORS.Negative,
          backgroundColor: 'rgba(248,113,113,0.08)',
          fill: true,
          tension: 0.35,
          pointRadius: 3,
          pointBackgroundColor: SENTIMENT_COLORS.Negative,
        },
        {
          label: 'Neutral',
          data: neu,
          borderColor: SENTIMENT_COLORS.Neutral,
          backgroundColor: 'rgba(251,191,36,0.08)',
          fill: true,
          tension: 0.35,
          pointRadius: 3,
          pointBackgroundColor: SENTIMENT_COLORS.Neutral,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            usePointStyle: true,
            padding: 16,
            color: '#475569',
            font: { size: 12 },
          },
        },
      },
      scales: {
        x: {
          grid: { display: false, color: 'rgba(148,163,184,0.12)' },
          ticks: { color: '#64748b', font: { size: 11 }, maxRotation: 45 },
        },
        y: {
          beginAtZero: true,
          ticks: { precision: 0, color: '#64748b', font: { size: 11 } },
          grid: { color: 'rgba(148,163,184,0.12)' },
        },
      },
    },
  });
}

function renderThemeChart(items) {
  const canvas = document.getElementById('barChart');
  const empty = document.getElementById('barEmpty');
  if (!canvas) return;

  themeChart = destroyChart(themeChart);

  if (!items || items.length === 0) {
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');

  const topItems = items.slice(0, 6);
  const labels = topItems.map(item => item.label || item.category || item.keyword || 'Theme');
  const values = topItems.map(item => Number(item.value || 0));

  themeChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Count',
        data: values,
        backgroundColor: ['#8b5cf6', '#22c55e', '#f59e0b', '#38bdf8', '#f87171', '#a78bfa'],
        borderRadius: 10,
        borderSkipped: false,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: {
          beginAtZero: true,
          ticks: { color: '#64748b', font: { size: 11 } },
          grid: { color: 'rgba(148,163,184,0.12)' },
        },
        y: {
          ticks: { color: '#475569', font: { size: 11 } },
          grid: { display: false },
        },
      },
    },
  });
}
