/**
 * Banking Transaction Monitoring - Dynamic Customer / Account Directory Controller
 */

let currentDirectoryMode = 'CUSTOMER';
let currentHasBalance = false;

document.addEventListener('DOMContentLoaded', () => {
  loadCustomers();

  document.getElementById('search-customers')?.addEventListener('input', debounce(() => loadCustomers(), 300));

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

async function loadCustomers() {
  const tbody = document.getElementById('customers-tbody');
  const thead = document.getElementById('customers-thead');
  if (!tbody) return;

  tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 24px;">Loading directory...</td></tr>`;

  const search = document.getElementById('search-customers')?.value || '';
  const datasetId = sessionStorage.getItem('sessionDatasetId');

  try {
    const params = { limit: 100 };
    if (search) params.search = search;
    if (datasetId) params.dataset_id = datasetId;

    const res = await ApiClient.get('/customers', params);
    currentDirectoryMode = res.mode || 'CUSTOMER';
    currentHasBalance = !!res.has_balance;

    // Update dynamic titles
    const title = res.title || (currentDirectoryMode === 'CUSTOMER' ? 'Customer Directory' : 'Account Directory');
    const pageTitleEl = document.getElementById('page-directory-title');
    if (pageTitleEl) pageTitleEl.textContent = title;
    const navLabelEl = document.getElementById('nav-directory-label');
    if (navLabelEl) navLabelEl.textContent = title;
    const htmlTitleEl = document.getElementById('html-page-title');
    if (htmlTitleEl) htmlTitleEl.textContent = `${title} | Banking Transaction Monitoring`;

    renderTableHeader(currentDirectoryMode, currentHasBalance);
    renderTableBody(res.items, currentDirectoryMode, currentHasBalance);
  } catch (err) {
    console.error('Failed to load directory:', err);
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color: var(--risk-critical); padding: 24px;">Failed to load directory records.</td></tr>`;
  }
}

function renderTableHeader(mode, hasBalance) {
  const thead = document.getElementById('customers-thead');
  if (!thead) return;

  let headersHtml = '';
  if (mode === 'CUSTOMER') {
    headersHtml = `
      <tr>
        <th>Customer ID</th>
        <th>Full Name</th>
        <th>Email Address</th>
        <th>Category</th>
        <th>Accounts</th>
        <th>Transactions</th>
        <th>Flagged Alerts</th>
        ${hasBalance ? '<th>Total Balance</th>' : ''}
        <th>Risk Level</th>
        <th>Actions</th>
      </tr>
    `;
  } else {
    // In account mode: NO Accounts column! Account ID is the primary identifier.
    headersHtml = `
      <tr>
        <th>Account ID</th>
        <th>Full Name</th>
        <th>Email Address</th>
        <th>Category</th>
        <th>Transactions</th>
        <th>Flagged Alerts</th>
        ${hasBalance ? '<th>Account Balance</th>' : ''}
        <th>Risk Level</th>
        <th>Actions</th>
      </tr>
    `;
  }
  thead.innerHTML = headersHtml;
}

function renderTableBody(items, mode, hasBalance) {
  const tbody = document.getElementById('customers-tbody');
  if (!items || items.length === 0) {
    const emptyMsg = mode === 'CUSTOMER' ? 'No customers found in active dataset.' : 'No accounts found in active dataset.';
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 32px; color: var(--text-muted);">${emptyMsg}</td></tr>`;
    return;
  }

  tbody.innerHTML = items.map(item => {
    // Risk badge styling
    const riskBadge = getRiskBadge(item.risk_segment);
    const alertBadge = item.alert_count > 0
      ? `<span class="badge badge-high">${item.alert_count} Flagged Alert(s)</span>`
      : `<span class="badge" style="background:#f0fdf4; color:#166534;">0 Alerts</span>`;

    const balanceCell = hasBalance
      ? `<td><strong>${item.total_balance !== null && item.total_balance !== undefined ? Formatters.currency(item.total_balance) : '—'}</strong></td>`
      : '';

    const accountsCell = mode === 'CUSTOMER'
      ? `<td><span class="badge" style="background:#e0f2fe; color:#0369a1; font-weight:600;">${item.account_count} account${item.account_count === 1 ? '' : 's'}</span></td>`
      : '';

    return `
      <tr>
        <td><strong>${escapeHtml(item.identifier)}</strong></td>
        <td><strong>${escapeHtml(item.name)}</strong></td>
        <td style="color:${item.email === 'Not provided' ? 'var(--text-muted)' : 'inherit'}; font-style:${item.email === 'Not provided' ? 'italic' : 'normal'};">${escapeHtml(item.email)}</td>
        <td style="color:${(!item.customer_category || item.customer_category === 'Not provided') ? 'var(--text-muted)' : 'inherit'}; font-style:${(!item.customer_category || item.customer_category === 'Not provided') ? 'italic' : 'normal'};">${escapeHtml(item.customer_category || 'Not provided')}</td>
        ${accountsCell}
        <td><strong>${item.transaction_count}</strong> txns</td>
        <td>${alertBadge}</td>
        ${balanceCell}
        <td>${riskBadge}</td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="viewEntityDossier(${item.id}, '${mode}')">View Profile</button>
        </td>
      </tr>
    `;
  }).join('');
}

function getRiskBadge(segment) {
  const seg = (segment || 'LOW').toUpperCase();
  if (seg === 'CRITICAL') return `<span class="badge badge-critical">CRITICAL</span>`;
  if (seg === 'HIGH') return `<span class="badge badge-high">HIGH</span>`;
  if (seg === 'MEDIUM') return `<span class="badge badge-medium">MEDIUM</span>`;
  return `<span class="badge badge-low">LOW</span>`;
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function viewEntityDossier(entityId, mode) {
  try {
    const data = await ApiClient.get(`/customers/${entityId}`, { mode });
    const p = data.profile;

    document.getElementById('modal-profile-title').innerHTML = `${data.mode === 'CUSTOMER' ? 'Customer Profile' : 'Account Profile'}: <span id="cust-modal-ref">${escapeHtml(p.identifier)}</span>`;
    document.getElementById('cust-dossier-name').textContent = p.name;
    document.getElementById('cust-dossier-email').textContent = p.email;
    document.getElementById('cust-dossier-status').textContent = p.account_status || 'ACTIVE';

    const segEl = document.getElementById('cust-dossier-segment');
    segEl.textContent = p.risk_segment;
    segEl.className = `badge badge-${(p.risk_segment || 'low').toLowerCase()}`;

    const joinedEl = document.getElementById('cust-dossier-joined');
    if (joinedEl) joinedEl.textContent = p.created_at ? Formatters.dateOnly(p.created_at) : 'N/A';

    // Balance handling
    const balContainer = document.getElementById('modal-balance-container');
    const firstAcct = data.accounts && data.accounts.length > 0 ? data.accounts[0] : null;
    if (balContainer) {
      if (firstAcct && firstAcct.current_balance !== null && firstAcct.current_balance !== undefined) {
        balContainer.style.display = 'block';
        document.getElementById('cust-dossier-balance').textContent = Formatters.currency(firstAcct.current_balance, firstAcct.currency || 'USD');
      } else {
        balContainer.style.display = 'none';
      }
    }

    // Accounts section
    const acctsSection = document.getElementById('dossier-accounts-section');
    const acctsContainer = document.getElementById('cust-accounts-list');
    if (data.mode === 'ACCOUNT') {
      acctsSection.style.display = 'none';
    } else {
      acctsSection.style.display = 'block';
      acctsContainer.innerHTML = (data.accounts || []).map(a => `
        <div style="background:#f8fafc; border:1px solid var(--border-color); border-radius:6px; padding:10px 14px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
          <div>
            <div style="font-weight:700; color:var(--primary-navy);">${escapeHtml(a.account_number)} (${escapeHtml(a.account_type || 'CHECKING')})</div>
            <div style="font-size:0.75rem; color:var(--text-muted);">Status: ${a.status}</div>
          </div>
          ${a.current_balance !== null && a.current_balance !== undefined ? `
            <div style="font-weight:700; font-size:1.05rem; color:var(--accent-blue);">
              ${Formatters.currency(a.current_balance, a.currency)}
            </div>
          ` : ''}
        </div>
      `).join('') || '<div style="color:var(--text-muted); font-size:0.85rem;">No linked accounts.</div>';
    }

    // Alerts
    const alertsContainer = document.getElementById('cust-alerts-list');
    if (alertsContainer) {
      alertsContainer.innerHTML = (data.alerts && data.alerts.length > 0)
        ? data.alerts.map(alt => `
          <div style="background:#fff; border:1px solid var(--border-color); border-left:4px solid var(--risk-${(alt.risk_category || 'low').toLowerCase()}); border-radius:6px; padding:10px 14px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
            <div>
              <div style="font-weight:700; color:var(--primary-navy);">${escapeHtml(alt.alert_ref)}</div>
              <div style="font-size:0.75rem; color:var(--text-muted);">Txn: ${escapeHtml(alt.transaction_ref)} &bull; ${Formatters.date(alt.created_at)}</div>
            </div>
            <div style="text-align:right;">
              <span class="badge badge-${(alt.risk_category || 'low').toLowerCase()}">${alt.risk_category} (${alt.risk_score} pts)</span>
              <div style="font-weight:600; font-size:0.85rem; margin-top:3px;">${Formatters.currency(alt.amount)}</div>
            </div>
          </div>
        `).join('')
        : '<div style="color:var(--text-muted); font-size:0.85rem;">No fraud alerts recorded for this profile.</div>';
    }

    // Recent Transactions
    const txsContainer = document.getElementById('cust-txs-list');
    if (txsContainer) {
      txsContainer.innerHTML = (data.recent_transactions && data.recent_transactions.length > 0)
        ? data.recent_transactions.map(t => `
          <div style="background:#f8fafc; border:1px solid var(--border-color); border-radius:6px; padding:10px 14px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
            <div>
              <div style="font-weight:600; color:var(--primary-navy); font-size:0.85rem;">${escapeHtml(t.transaction_ref)} &bull; ${escapeHtml(t.transaction_type)}</div>
              <div style="font-size:0.75rem; color:var(--text-muted);">${Formatters.date(t.timestamp)} &bull; ${escapeHtml(t.location_city || 'N/A')}</div>
            </div>
            <div style="font-weight:700; color:var(--text-dark);">${Formatters.currency(t.amount)}</div>
          </div>
        `).join('')
        : '<div style="color:var(--text-muted); font-size:0.85rem;">No recent transactions recorded.</div>';
    }

    document.getElementById('modal-customer-detail')?.classList.add('active');
  } catch (err) {
    console.error('Failed to load profile dossier:', err);
    alert('Failed to load profile dossier.');
  }
}
