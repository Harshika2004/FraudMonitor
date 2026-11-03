/**
 * Banking Transaction Monitoring - Transactions View Controller
 */

let currentPage = 1;
const pageSize = 20;

document.addEventListener('DOMContentLoaded', () => {
  loadTransactions(1);

  // Filter bindings
  document.getElementById('search-input')?.addEventListener('input', debounce(() => loadTransactions(1), 300));
  document.getElementById('filter-type')?.addEventListener('change', () => loadTransactions(1));
  document.getElementById('filter-channel')?.addEventListener('change', () => loadTransactions(1));
  document.getElementById('filter-status')?.addEventListener('change', () => loadTransactions(1));
  document.getElementById('filter-risk')?.addEventListener('change', () => loadTransactions(1));

  // CSV Modal bindings
  document.getElementById('btn-open-csv')?.addEventListener('click', openCsvModal);
  document.getElementById('btn-close-csv')?.addEventListener('click', closeCsvModal);
  document.getElementById('form-csv-upload')?.addEventListener('submit', handleCsvUpload);

  // Batch evaluation
  document.getElementById('btn-eval-unevaluated')?.addEventListener('click', evaluateUnevaluated);

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

async function loadTransactions(page = 1) {
  currentPage = page;
  const tbody = document.getElementById('transactions-tbody');
  if (!tbody) return;

  tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding: 24px;">Loading transactions...</td></tr>`;

  const params = {
    page: currentPage,
    page_size: pageSize,
    search: document.getElementById('search-input')?.value || '',
    transaction_type: document.getElementById('filter-type')?.value || '',
    channel: document.getElementById('filter-channel')?.value || '',
    is_evaluated: document.getElementById('filter-status')?.value || '',
    risk_category: document.getElementById('filter-risk')?.value || '',
    sort_by: 'timestamp',
    sort_order: 'desc'
  };

  try {
    const data = await ApiClient.get('/transactions', params);
    renderTable(data.items);
    renderPagination(data.total, data.page, data.page_size);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color: var(--risk-critical); padding: 24px;">Failed to load transactions.</td></tr>`;
  }
}

function renderTable(items) {
  const tbody = document.getElementById('transactions-tbody');
  if (!items || items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding: 32px; color: var(--text-muted);">No transactions matching the selected filters.</td></tr>`;
    return;
  }

  tbody.innerHTML = items.map(tx => {
    const statusPill = tx.is_evaluated
      ? (tx.has_alert
          ? Formatters.riskBadge(tx.alert_risk_category, tx.alert_risk_score)
          : `<span class="badge" style="background:#f1f5f9; color:#475569;">EVALUATED (CLEAN)</span>`)
      : `<span class="badge" style="background:#e0f2fe; color:#0369a1;">UNEVALUATED</span>`;

    return `
      <tr>
        <td><strong>${tx.transaction_ref}</strong></td>
        <td>${tx.account_number || 'ACCT-' + tx.account_id}</td>
        <td>${tx.customer_name || 'Synthetic Customer'}</td>
        <td><strong>${Formatters.currency(tx.amount, tx.currency)}</strong></td>
        <td><span style="font-size: 0.8rem; font-weight:600; color: #475569;">${tx.transaction_type}</span></td>
        <td>${tx.channel}</td>
        <td>${tx.location_city}, ${tx.location_country}</td>
        <td>${statusPill}</td>
        <td style="white-space: nowrap;">
          <button class="btn btn-secondary btn-sm" onclick="viewTransactionDetails(${tx.transaction_id})">View</button>
          <button class="btn btn-primary btn-sm" onclick="evaluateSingleTxn(${tx.transaction_id})">Evaluate</button>
        </td>
      </tr>
    `;
  }).join('');
}

function renderPagination(total, page, size) {
  const infoEl = document.getElementById('pagination-info');
  const controlsEl = document.getElementById('pagination-controls');
  if (!infoEl || !controlsEl) return;

  const totalPages = Math.ceil(total / size) || 1;
  const start = total === 0 ? 0 : (page - 1) * size + 1;
  const end = Math.min(page * size, total);

  infoEl.textContent = `Showing ${start}-${end} of ${total.toLocaleString()} transactions`;

  controlsEl.innerHTML = `
    <button class="btn btn-secondary btn-sm" ${page <= 1 ? 'disabled' : ''} onclick="loadTransactions(${page - 1})">Previous</button>
    <span style="padding: 0 8px; font-weight:600; font-size:0.85rem; align-self:center;">Page ${page} of ${totalPages}</span>
    <button class="btn btn-secondary btn-sm" ${page >= totalPages ? 'disabled' : ''} onclick="loadTransactions(${page + 1})">Next</button>
  `;
}

async function viewTransactionDetails(txId) {
  try {
    const data = await ApiClient.get(`/transactions/${txId}`);
    const tx = data.transaction;
    const acct = data.account;
    const cust = data.customer;
    const alert = data.alert;

    document.getElementById('modal-txn-ref').textContent = tx.transaction_ref;
    document.getElementById('detail-amount').textContent = Formatters.currency(tx.amount, tx.currency);
    document.getElementById('detail-type').textContent = tx.transaction_type;
    document.getElementById('detail-channel').textContent = tx.channel;
    document.getElementById('detail-time').textContent = Formatters.dateTime(tx.timestamp);
    document.getElementById('detail-location').textContent = `${tx.location_city}, ${tx.location_country} (Lat: ${tx.latitude || '-'}, Lon: ${tx.longitude || '-'})`;
    document.getElementById('detail-merchant').textContent = tx.merchant_name ? `${tx.merchant_name} (${tx.merchant_category || 'General'})` : 'N/A';
    document.getElementById('detail-ip').textContent = tx.ip_address || 'Documentation RFC IP';
    document.getElementById('detail-device').textContent = tx.device_id || 'N/A';

    document.getElementById('detail-customer-name').textContent = cust.name;
    document.getElementById('detail-customer-ref').textContent = cust.customer_ref;
    document.getElementById('detail-account-num').textContent = acct.account_number;
    document.getElementById('detail-account-bal').textContent = Formatters.currency(acct.current_balance);

    const alertBanner = document.getElementById('detail-alert-status');
    if (alert) {
      alertBanner.innerHTML = `
        <div style="padding: 12px; background: #fff1f2; border: 1px solid #fecdd3; border-radius: 6px; margin-top: 12px;">
          <strong>Suspicious Risk Indicator Detected:</strong> ${Formatters.riskBadge(alert.risk_category, alert.risk_score)}
          <a href="/alerts?alert_id=${alert.alert_id}" class="btn btn-primary btn-sm" style="margin-left: 10px;">Go to Investigation</a>
        </div>
      `;
    } else {
      alertBanner.innerHTML = tx.is_evaluated
        ? `<div style="padding: 10px; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; margin-top: 12px; font-size:0.85rem; color:#166534;">Evaluated: No fraud rules triggered. Routine transaction.</div>`
        : `<div style="padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; margin-top: 12px; font-size:0.85rem; color:#475569;">Unevaluated transaction.</div>`;
    }

    document.getElementById('modal-txn-detail').classList.add('active');
  } catch (err) {
    // Toast handled in ApiClient
  }
}

async function evaluateSingleTxn(txId) {
  try {
    const res = await ApiClient.post(`/transactions/${txId}/evaluate?force_reevaluate=true`, {});
    const container = document.getElementById('eval-results-container');

    let triggersHtml = '';
    if (res.triggered_rules && res.triggered_rules.length > 0) {
      triggersHtml = res.triggered_rules.map(t => `
        <div class="trigger-card">
          <div class="trigger-header">
            <span class="trigger-rule-name">${t.rule_name} (${t.rule_code})</span>
            <span class="trigger-points">+${t.points} pts</span>
          </div>
          <div class="trigger-reason">${t.reason}</div>
        </div>
      `).join('');
    } else {
      triggersHtml = `<p style="color: var(--risk-low); font-weight:600; padding: 12px 0;">No suspicious indicators identified. Score: 0 (LOW).</p>`;
    }

    container.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 16px;">
        <div>
          <h4>Transaction: ${res.transaction_ref}</h4>
          <p style="color:var(--text-muted); font-size:0.85rem;">Deterministic Rule Engine Output</p>
        </div>
        <div>
          ${Formatters.riskBadge(res.risk_category, res.risk_score)}
        </div>
      </div>
      <div style="margin-bottom: 16px;">
        <h5 style="margin-bottom: 8px;">Triggered Rule Indicators (${res.triggers_count}):</h5>
        ${triggersHtml}
      </div>
    `;

    document.getElementById('modal-eval-result').classList.add('active');
    loadTransactions(currentPage);
  } catch (err) {
    // Toast handled
  }
}

async function evaluateUnevaluated() {
  const btn = document.getElementById('btn-eval-unevaluated');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Evaluating all...';
  }

  try {
    const res = await ApiClient.post('/transactions/evaluate-batch?only_unevaluated=true', {});
    ApiClient.showToast(res.message, 'success');
    loadTransactions(1);
  } catch (err) {
    // Toast handled
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<span>⚡</span> Evaluate Unevaluated`;
    }
  }
}

function openCsvModal() {
  document.getElementById('modal-csv-upload')?.classList.add('active');
}

function closeCsvModal() {
  document.getElementById('modal-csv-upload')?.classList.remove('active');
}

async function handleCsvUpload(e) {
  e.preventDefault();
  const fileInput = document.getElementById('csv-file-input');
  if (!fileInput.files.length) {
    ApiClient.showToast('Please select a valid CSV file.', 'error');
    return;
  }

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);

  const submitBtn = document.getElementById('btn-submit-csv');
  submitBtn.disabled = true;
  submitBtn.textContent = 'Importing...';

  try {
    const res = await ApiClient.post('/transactions/import-csv', formData);
    if (res.success) {
      ApiClient.showToast(`Imported ${res.imported_count} transactions. (${res.error_count} errors)`, 'success');
      closeCsvModal();
      loadTransactions(1);
    } else {
      ApiClient.showToast(res.error || 'Import failed', 'error');
    }
  } catch (err) {
    // Toast handled
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Upload & Import';
  }
}
