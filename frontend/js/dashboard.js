/**
 * Banking Transaction Monitoring - Dashboard Controller
 */

let trendsChart = null;
let riskDistChart = null;
let ruleFreqChart = null;
let channelChart = null;

document.addEventListener('DOMContentLoaded', () => {
  initDashboard();

  const batchBtn = document.getElementById('btn-batch-eval');
  if (batchBtn) {
    batchBtn.addEventListener('click', runBatchEvaluation);
  }

  const daysFilter = document.getElementById('filter-days');
  if (daysFilter) {
    daysFilter.addEventListener('change', () => loadDashboardData(parseInt(daysFilter.value) || 30));
  }
});

async function initDashboard() {
  await loadDashboardData(30);
  await loadRecentAlerts();
}

async function loadDashboardData(days = 30) {
  try {
    const data = await ApiClient.get('/analytics/dashboard', { days });
    renderKPICards(data.kpi);
    renderTrendsChart(data.daily_trends);
    renderRiskDistChart(data.risk_distribution);
    renderRuleFreqChart(data.rule_frequency);
    renderChannelChart(data.channel_breakdown);
  } catch (err) {
    console.error('Failed to load dashboard data:', err);
  }
}

function renderKPICards(kpi) {
  if (!kpi) return;
  document.getElementById('kpi-total-txns').textContent = kpi.total_transactions.toLocaleString();
  document.getElementById('kpi-flagged-txns').textContent = kpi.flagged_transactions.toLocaleString();
  document.getElementById('kpi-flag-rate').textContent = `${kpi.flag_rate_percentage}% Flag Rate`;
  document.getElementById('kpi-open-alerts').textContent = kpi.open_alerts.toLocaleString();
  document.getElementById('kpi-high-critical').textContent = kpi.high_critical_alerts.toLocaleString();
  document.getElementById('kpi-monitored-vol').textContent = Formatters.currency(kpi.total_monitored_volume);
  document.getElementById('kpi-flagged-vol').textContent = `${Formatters.currency(kpi.flagged_volume)} Flagged`;
}

function renderTrendsChart(dailyTrends) {
  const ctx = document.getElementById('chart-daily-trends');
  if (!ctx) return;

  const labels = dailyTrends.map(d => d.date);
  const totalCounts = dailyTrends.map(d => d.total_count);
  const flaggedCounts = dailyTrends.map(d => d.flagged_count);

  if (trendsChart) trendsChart.destroy();

  trendsChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels.length ? labels : ['No Data'],
      datasets: [
        {
          label: 'Total Transactions',
          data: totalCounts.length ? totalCounts : [0],
          borderColor: '#0284c7',
          backgroundColor: 'rgba(2, 132, 199, 0.1)',
          fill: true,
          tension: 0.35,
          borderWidth: 2,
          pointRadius: 3
        },
        {
          label: 'Flagged (Suspicious)',
          data: flaggedCounts.length ? flaggedCounts : [0],
          borderColor: '#ef4444',
          backgroundColor: 'rgba(239, 68, 68, 0.15)',
          fill: true,
          tension: 0.35,
          borderWidth: 2,
          pointRadius: 4,
          pointBackgroundColor: '#ef4444'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top', labels: { boxWidth: 12, font: { family: 'Inter', size: 12 } } },
        tooltip: { mode: 'index', intersect: false }
      },
      scales: {
        x: { grid: { display: false } },
        y: { beginAtZero: true, ticks: { precision: 0 } }
      }
    }
  });
}

function renderRiskDistChart(riskDist) {
  const ctx = document.getElementById('chart-risk-dist');
  if (!ctx) return;

  const labels = riskDist.map(r => r.category);
  const counts = riskDist.map(r => r.count);
  const colors = riskDist.map(r => r.color);

  if (riskDistChart) riskDistChart.destroy();

  riskDistChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: counts.some(c => c > 0) ? counts : [1],
        backgroundColor: counts.some(c => c > 0) ? colors : ['#e2e8f0'],
        borderWidth: 2,
        borderColor: '#ffffff'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '68%',
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 10, font: { family: 'Inter', size: 11 } } }
      }
    }
  });
}

function renderRuleFreqChart(ruleStats) {
  const ctx = document.getElementById('chart-rule-freq');
  if (!ctx) return;

  const labels = ruleStats.map(r => r.rule_name);
  const counts = ruleStats.map(r => r.trigger_count);

  if (ruleFreqChart) ruleFreqChart.destroy();

  ruleFreqChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels.length ? labels : ['No triggers recorded'],
      datasets: [{
        label: 'Triggers Count',
        data: counts.length ? counts : [0],
        backgroundColor: '#0d9488',
        borderRadius: 4
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        x: { beginAtZero: true, ticks: { precision: 0 } },
        y: { grid: { display: false } }
      }
    }
  });
}

function renderChannelChart(channels) {
  const ctx = document.getElementById('chart-channel-dist');
  if (!ctx) return;

  const labels = channels.map(c => c.channel);
  const counts = channels.map(c => c.transaction_count);

  if (channelChart) channelChart.destroy();

  channelChart = new Chart(ctx, {
    type: 'pie',
    data: {
      labels: labels,
      datasets: [{
        data: counts,
        backgroundColor: ['#0284c7', '#0d9488', '#6366f1', '#f59e0b', '#8b5cf6'],
        borderWidth: 2,
        borderColor: '#ffffff'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 10, font: { family: 'Inter', size: 11 } } }
      }
    }
  });
}

async function loadRecentAlerts() {
  const tbody = document.getElementById('recent-alerts-tbody');
  if (!tbody) return;

  try {
    const data = await ApiClient.get('/alerts', { page: 1, page_size: 6, sort_by: 'created_at', sort_order: 'desc' });
    if (!data.items || data.items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 24px; color: var(--text-muted);">No suspicious transactions flagged yet. Run batch evaluation to analyze transactions.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.items.map(alert => `
      <tr>
        <td><strong>${alert.alert_ref}</strong></td>
        <td>${alert.customer_name || 'Synthetic Customer'}</td>
        <td><strong>${Formatters.currency(alert.amount, alert.currency)}</strong></td>
        <td>${Formatters.riskBadge(alert.risk_category, alert.risk_score)}</td>
        <td>${Formatters.statusBadge(alert.status)}</td>
        <td>${Formatters.dateTime(alert.created_at)}</td>
        <td>
          <a href="/alerts?alert_id=${alert.alert_id}" class="btn btn-secondary btn-sm">Investigate</a>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Failed to load recent alerts:', err);
  }
}

async function runBatchEvaluation() {
  const btn = document.getElementById('btn-batch-eval');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Evaluating...';
  }

  try {
    const res = await ApiClient.post('/transactions/evaluate-batch?only_unevaluated=false&limit=1000', {});
    ApiClient.showToast(res.message, 'success');
    await loadDashboardData();
    await loadRecentAlerts();
  } catch (err) {
    // Toast handled in ApiClient
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<span>⚡</span> Run Full Evaluation`;
    }
  }
}
