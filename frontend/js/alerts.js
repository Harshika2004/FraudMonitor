/**
 * Banking Transaction Monitoring - Alerts Investigation Controller
 */

let currentPage = 1;
const pageSize = 20;
let currentAlertId = null;

document.addEventListener('DOMContentLoaded', () => {
  loadAlerts(1);

  // Filter bindings
  document.getElementById('search-alerts')?.addEventListener('input', debounce(() => loadAlerts(1), 300));
  document.getElementById('filter-category')?.addEventListener('change', () => loadAlerts(1));
  document.getElementById('filter-status')?.addEventListener('change', () => loadAlerts(1));
  document.getElementById('filter-score')?.addEventListener('change', () => loadAlerts(1));

  // Note form binding
  document.getElementById('form-add-note')?.addEventListener('submit', handleAddNote);

  // Status form binding
  document.getElementById('form-update-status')?.addEventListener('submit', handleUpdateStatus);

  // Check query parameter for direct link: alerts?alert_id=123
  const urlParams = new URLSearchParams(window.location.search);
  const directAlertId = urlParams.get('alert_id');
  if (directAlertId) {
    openAlertInvestigation(parseInt(directAlertId));
  }

  // Modal close handlers
  document.querySelectorAll('.modal-close, [data-close-modal]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('active'));
    });
  });
});

function debounce(func, wait) {
  let timeout;
  return function(...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(this, args), wait);
  };
}

async function loadAlerts(page = 1) {
  currentPage = page;
  const tbody = document.getElementById('alerts-tbody');
  if (!tbody) return;

  tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 24px;">Loading alert queue...</td></tr>`;

  const params = {
    page: currentPage,
    page_size: pageSize,
    search: document.getElementById('search-alerts')?.value || '',
    risk_category: document.getElementById('filter-category')?.value || '',
    status: document.getElementById('filter-status')?.value || '',
    min_score: document.getElementById('filter-score')?.value || '',
    sort_by: 'created_at',
    sort_order: 'desc'
  };

  try {
    const data = await ApiClient.get('/alerts', params);
    renderAlertsTable(data.items);
    renderAlertsPagination(data.total, data.page, data.page_size);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color: var(--risk-critical); padding: 24px;">Failed to load alerts.</td></tr>`;
  }
}

function renderAlertsTable(items) {
  const tbody = document.getElementById('alerts-tbody');
  if (!items || items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 32px; color: var(--text-muted);">No alerts matching current filters. All suspicious indicators resolved or cleared.</td></tr>`;
    return;
  }

  tbody.innerHTML = items.map(alert => `
    <tr>
      <td><strong>${alert.alert_ref}</strong></td>
      <td>
        <div><strong>${alert.customer_name || 'Synthetic Customer'}</strong></div>
        <div style="font-size:0.75rem; color:var(--text-muted);">${alert.account_number || ''}</div>
      </td>
      <td>
        <div><strong>${Formatters.currency(alert.amount, alert.currency)}</strong></div>
        <div style="font-size:0.75rem; color:var(--text-muted);">${alert.transaction_type}</div>
      </td>
      <td>${Formatters.riskBadge(alert.risk_category, alert.risk_score)}</td>
      <td>${Formatters.statusBadge(alert.status)}</td>
      <td>${alert.assigned_to || '<span style="color:var(--text-light);">Unassigned</span>'}</td>
      <td>${Formatters.dateTime(alert.created_at)}</td>
      <td>
        <button class="btn btn-primary btn-sm" onclick="openAlertInvestigation(${alert.alert_id})">Investigate</button>
      </td>
    </tr>
  `).join('');
}

function renderAlertsPagination(total, page, size) {
  const infoEl = document.getElementById('pagination-info');
  const controlsEl = document.getElementById('pagination-controls');
  if (!infoEl || !controlsEl) return;

  const totalPages = Math.ceil(total / size) || 1;
  const start = total === 0 ? 0 : (page - 1) * size + 1;
  const end = Math.min(page * size, total);

  infoEl.textContent = `Showing ${start}-${end} of ${total.toLocaleString()} alerts in queue`;

  controlsEl.innerHTML = `
    <button class="btn btn-secondary btn-sm" ${page <= 1 ? 'disabled' : ''} onclick="loadAlerts(${page - 1})">Previous</button>
    <span style="padding: 0 8px; font-weight:600; font-size:0.85rem; align-self:center;">Page ${page} of ${totalPages}</span>
    <button class="btn btn-secondary btn-sm" ${page >= totalPages ? 'disabled' : ''} onclick="loadAlerts(${page + 1})">Next</button>
  `;
}

async function openAlertInvestigation(alertId) {
  currentAlertId = alertId;
  try {
    const alert = await ApiClient.get(`/alerts/${alertId}`);

    document.getElementById('modal-alert-ref').textContent = alert.alert_ref;
    document.getElementById('modal-alert-score-badge').innerHTML = Formatters.riskBadge(alert.risk_category, alert.risk_score);
    document.getElementById('modal-alert-status-badge').innerHTML = Formatters.statusBadge(alert.status);

    // Linked Transaction info
    document.getElementById('invest-txn-ref').textContent = alert.transaction_ref;
    document.getElementById('invest-amount').textContent = Formatters.currency(alert.amount, alert.currency);
    document.getElementById('invest-type').textContent = alert.transaction_type;
    document.getElementById('invest-channel').textContent = alert.channel;
    document.getElementById('invest-time').textContent = Formatters.dateTime(alert.transaction_timestamp);
    document.getElementById('invest-location').textContent = alert.location_city;

    // Customer & Account
    document.getElementById('invest-cust-name').textContent = alert.customer_name;
    document.getElementById('invest-cust-ref').textContent = alert.customer_ref;
    document.getElementById('invest-account').textContent = alert.account_number;

    // Triggers
    const triggersContainer = document.getElementById('invest-triggers-list');
    if (alert.triggers && alert.triggers.length > 0) {
      triggersContainer.innerHTML = alert.triggers.map(t => `
        <div class="trigger-card">
          <div class="trigger-header">
            <span class="trigger-rule-name">${t.rule_name}</span>
            <span class="trigger-points">+${t.points_awarded} pts</span>
          </div>
          <div class="trigger-reason">${t.trigger_reason}</div>
        </div>
      `).join('');
    } else {
      triggersContainer.innerHTML = `<p style="color:var(--text-muted);">No trigger details stored.</p>`;
    }

    // Set status form values
    document.getElementById('update-status-select').value = alert.status;
    document.getElementById('update-assigned-to').value = alert.assigned_to || '';
    document.getElementById('update-reason-select').value = alert.resolution_reason || '';

    // Render notes
    renderInvestigationNotes(alert.notes);

    document.getElementById('modal-alert-investigate').classList.add('active');
  } catch (err) {
    // Toast handled
  }
}

function renderInvestigationNotes(notes) {
  const container = document.getElementById('invest-notes-container');
  if (!notes || notes.length === 0) {
    container.innerHTML = `<p style="color:var(--text-muted); font-size:0.85rem; padding: 12px 0;">No investigation notes recorded yet. Add initial assessment below.</p>`;
    return;
  }

  container.innerHTML = notes.map(n => `
    <div class="note-item">
      <div>
        <span class="note-author">${n.author}</span>
        <span class="note-time">${Formatters.dateTime(n.created_at)}</span>
      </div>
      <div class="note-text">${n.note_text}</div>
      ${n.action_taken ? `<div style="font-size:0.75rem; color:var(--accent-teal); margin-top:2px; font-weight:600;">Action: ${n.action_taken}</div>` : ''}
    </div>
  `).join('');
}

async function handleUpdateStatus(e) {
  e.preventDefault();
  if (!currentAlertId) return;

  const payload = {
    status: document.getElementById('update-status-select').value,
    resolution_reason: document.getElementById('update-reason-select').value || null,
    assigned_to: document.getElementById('update-assigned-to').value.trim() || null,
    note: document.getElementById('update-status-note').value.trim() || null
  };

  try {
    const res = await ApiClient.patch(`/alerts/${currentAlertId}/status`, payload);
    ApiClient.showToast('Alert status successfully updated.', 'success');
    document.getElementById('update-status-note').value = '';
    await openAlertInvestigation(currentAlertId);
    loadAlerts(currentPage);
  } catch (err) {
    // Toast handled
  }
}

async function handleAddNote(e) {
  e.preventDefault();
  if (!currentAlertId) return;

  const author = document.getElementById('note-author').value.trim() || 'Risk Analyst';
  const text = document.getElementById('note-text').value.trim();
  const action = document.getElementById('note-action').value.trim() || null;

  if (!text) {
    ApiClient.showToast('Note text cannot be empty.', 'error');
    return;
  }

  try {
    await ApiClient.post(`/alerts/${currentAlertId}/notes`, {
      author: author,
      note_text: text,
      action_taken: action
    });
    ApiClient.showToast('Investigation note recorded.', 'success');
    document.getElementById('note-text').value = '';
    document.getElementById('note-action').value = '';
    await openAlertInvestigation(currentAlertId);
  } catch (err) {
    // Toast handled
  }
}
