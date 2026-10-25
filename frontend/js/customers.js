/**
 * Banking Transaction Monitoring - Customers Directory Controller
 */

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
  if (!tbody) return;

  tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 24px;">Loading synthetic customer directory...</td></tr>`;

  const search = document.getElementById('search-customers')?.value || '';

  try {
    const customers = await ApiClient.get('/customers', { search, limit: 50 });
    renderCustomersTable(customers);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color: var(--risk-critical); padding: 24px;">Failed to load customers.</td></tr>`;
  }
}

function renderCustomersTable(customers) {
  const tbody = document.getElementById('customers-tbody');
  if (!customers || customers.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 32px; color: var(--text-muted);">No customers found.</td></tr>`;
    return;
  }

  tbody.innerHTML = customers.map(c => `
    <tr>
      <td><strong>${c.customer_ref}</strong></td>
      <td><strong>${c.name}</strong></td>
      <td>${c.email}</td>
      <td>
        <span class="badge" style="background:#f1f5f9; color:#334155;">${c.risk_segment}</span>
      </td>
      <td>${c.account_count} accounts</td>
      <td><strong>${Formatters.currency(c.total_balance)}</strong></td>
      <td>
        ${c.alert_count > 0 
          ? `<span class="badge badge-high">${c.alert_count} Flagged Alert(s)</span>` 
          : `<span class="badge" style="background:#f0fdf4; color:#166534;">0 Alerts</span>`}
      </td>
      <td>
        <button class="btn btn-secondary btn-sm" onclick="viewCustomerDossier(${c.customer_id})">View Profile</button>
      </td>
    </tr>
  `).join('');
}

async function viewCustomerDossier(customerId) {
  try {
    const data = await ApiClient.get(`/customers/${customerId}`);
    const c = data.customer;

    document.getElementById('cust-modal-ref').textContent = c.customer_ref;
    document.getElementById('cust-dossier-name').textContent = `${c.first_name} ${c.last_name}`;
    document.getElementById('cust-dossier-email').textContent = c.email;
    document.getElementById('cust-dossier-phone').textContent = c.phone || 'N/A';
    document.getElementById('cust-dossier-segment').textContent = c.risk_segment;
    document.getElementById('cust-dossier-status').textContent = c.account_status;
    const joinedEl = document.getElementById('cust-dossier-joined');
    if (joinedEl) joinedEl.textContent = Formatters.dateOnly(c.created_at);

    // Accounts
    const acctsContainer = document.getElementById('cust-accounts-list');
    acctsContainer.innerHTML = data.accounts.map(a => `
      <div style="background:#f8fafc; border:1px solid var(--border-color); border-radius:6px; padding:12px 14px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
        <div>
          <div style="font-weight:700; color:var(--primary-navy);">${a.account_number} (${a.account_type})</div>
          <div style="font-size:0.75rem; color:var(--text-muted);">Status: ${a.status}</div>
        </div>
        <div style="font-weight:700; font-size:1.05rem; color:var(--accent-blue);">
          ${Formatters.currency(a.current_balance, a.currency)}
        </div>
      </div>
    `).join('');

    // Alerts
    const alertsContainer = document.getElementById('cust-alerts-list');
    if (data.alerts && data.alerts.length > 0) {
      alertsContainer.innerHTML = data.alerts.map(a => `
        <div style="border-left: 3px solid var(--risk-critical); background:#fff1f2; padding:8px 12px; margin-bottom:8px; border-radius:0 6px 6px 0; display:flex; justify-content:space-between; align-items:center;">
          <div>
            <div style="font-weight:700; font-size:0.85rem;">Alert: ${a.alert_ref} (Txn: ${a.transaction_ref})</div>
            <div style="font-size:0.75rem; color:var(--text-muted);">Amount: ${Formatters.currency(a.amount)} &bull; ${Formatters.dateTime(a.created_at)}</div>
          </div>
          <div>
            ${Formatters.riskBadge(a.risk_category, a.risk_score)}
            <a href="/alerts?alert_id=${a.alert_id}" class="btn btn-secondary btn-sm" style="margin-left:8px;">Investigate</a>
          </div>
        </div>
      `).join('');
    } else {
      alertsContainer.innerHTML = `<p style="font-size:0.85rem; color:var(--text-muted);">No risk indicator alerts recorded for this customer's accounts.</p>`;
    }

    document.getElementById('modal-customer-detail').classList.add('active');
  } catch (err) {
    // Toast handled
  }
}
