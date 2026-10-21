/* Dashboard / Overview section */

async function loadDashboard() {
  const dateFrom = document.getElementById('dateFrom')?.value || '';
  const dateTo = document.getElementById('dateTo')?.value || '';
  const params = new URLSearchParams();
  if (dateFrom) params.set('date_from', dateFrom);
  if (dateTo) params.set('date_to', dateTo + 'T23:59:59');
  const qs = params.toString() ? '?' + params.toString() : '';

  try {
    const [statsRes, trendsRes, insightsRes] = await Promise.all([
      api('/stats' + qs),
      api('/trends' + qs),
      api('/insights'),
    ]);

    const s = statsRes.stats || {};
    document.getElementById('statTotal').textContent = s.total_feedback ?? 0;
    document.getElementById('statPositive').textContent = s.positive_count ?? 0;
    document.getElementById('statPositivePct').textContent =
      s.total_feedback ? `${s.positive_pct}%` : '';
    document.getElementById('statNegative').textContent = s.negative_count ?? 0;
    document.getElementById('statNegativePct').textContent =
      s.total_feedback ? `${s.negative_pct}%` : '';
    document.getElementById('statNeutral').textContent = s.neutral_count ?? 0;
    document.getElementById('statNeutralPct').textContent =
      s.total_feedback ? `${s.neutral_pct}%` : '';
    document.getElementById('statDocs').textContent = s.total_documents ?? 0;

    renderDoughnut(s);
    renderTrend(trendsRes.trends || []);

    const complaints = insightsRes.insights?.top_complaints || [];
    const positiveThemes = insightsRes.insights?.top_positive_keywords || [];
    const themeData = complaints.length ? complaints : positiveThemes;

    const listEl = document.getElementById('complaintList');
    if (!complaints.length) {
      listEl.innerHTML = '<p class="empty-state">No complaint data available yet.</p>';
    } else {
      listEl.innerHTML = '<ul class="complaint-list">' +
        complaints.map(c =>
          `<li><span>${escapeHtml(c.category)}</span><span class="complaint-count">${c.count}</span></li>`
        ).join('') + '</ul>';
    }

    renderThemeChart(themeData.map(item => ({
      label: item.category || item.keyword || 'Theme',
      value: item.count || 0,
    })));
  } catch (e) {
    console.error('Dashboard load failed', e);
  }
}

// Date filter change triggers refresh when on overview
document.addEventListener('DOMContentLoaded', () => {
  ['dateFrom', 'dateTo'].forEach(id => {
    document.getElementById(id)?.addEventListener('change', () => {
      const active = document.querySelector('.nav-item.active');
      if (active?.dataset.section === 'overview') loadDashboard();
    });
  });
});
