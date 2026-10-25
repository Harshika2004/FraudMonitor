/**
 * Banking Transaction Monitoring - Detection Rules Controller
 */

let rulesCache = [];
let editingRule = null;

document.addEventListener('DOMContentLoaded', () => {
  loadRules();

  // Form submit
  document.getElementById('form-edit-rule')?.addEventListener('submit', handleSaveRule);

  // Modal close handlers
  document.querySelectorAll('.modal-close, [data-close-modal]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('active'));
    });
  });
});

async function loadRules() {
  const container = document.getElementById('rules-list-container');
  if (!container) return;

  container.innerHTML = `<div style="text-align:center; padding: 32px; color: var(--text-muted);">Loading fraud rules...</div>`;

  try {
    rulesCache = await ApiClient.get('/rules');
    renderRules(rulesCache);
  } catch (err) {
    container.innerHTML = `<div style="text-align:center; padding: 32px; color: var(--risk-critical);">Failed to load fraud rules.</div>`;
  }
}

function renderRules(rules) {
  const container = document.getElementById('rules-list-container');
  if (!rules || rules.length === 0) {
    container.innerHTML = `<div style="text-align:center; padding: 32px; color: var(--text-muted);">No rules configured.</div>`;
    return;
  }

  container.innerHTML = rules.map(rule => {
    const isEnabled = rule.is_enabled;
    const badge = isEnabled
      ? `<span class="badge" style="background:#ecfdf5; color:#10b981; border:1px solid rgba(16,185,129,0.2);">ACTIVE / ENABLED</span>`
      : `<span class="badge" style="background:#f1f5f9; color:#64748b; border:1px solid #e2e8f0;">DISABLED</span>`;

    // Format parameters prettily
    const paramsFormatted = Object.entries(rule.parameters_json || {})
      .map(([k, v]) => `<code>${k}: ${v}</code>`)
      .join(' &bull; ');

    return `
      <div class="data-card" style="margin-bottom: 20px;">
        <div class="data-card-header">
          <div style="display:flex; align-items:center; gap: 12px;">
            <span style="font-size: 1.25rem;">⚖️</span>
            <div>
              <div class="data-card-title">${rule.rule_name}</div>
              <div style="font-size:0.75rem; color:var(--text-muted); font-family: monospace;">${rule.rule_code} &bull; Type: ${rule.rule_type}</div>
            </div>
          </div>
          <div style="display:flex; align-items:center; gap: 12px;">
            ${badge}
            <span class="badge" style="background:#fff7ed; color:#f97316; font-weight:700;">+${rule.risk_points} Points</span>
            <button class="btn btn-secondary btn-sm" onclick="openEditRule(${rule.rule_id})">Edit Config</button>
          </div>
        </div>
        <div style="padding: 20px 24px;">
          <p style="color:var(--text-main); font-size:0.9rem; margin-bottom: 12px;">${rule.description}</p>
          <div style="background:#f8fafc; border:1px solid var(--border-color); border-radius:6px; padding: 10px 14px; font-size:0.85rem;">
            <strong>Configured Parameters:</strong> ${paramsFormatted || 'None'}
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function openEditRule(ruleId) {
  editingRule = rulesCache.find(r => r.rule_id === ruleId);
  if (!editingRule) return;

  document.getElementById('edit-rule-id').value = editingRule.rule_id;
  document.getElementById('edit-rule-name').value = editingRule.rule_name;
  document.getElementById('edit-rule-desc').value = editingRule.description;
  document.getElementById('edit-rule-points').value = editingRule.risk_points;
  document.getElementById('edit-rule-enabled').checked = editingRule.is_enabled;

  // Render parameters editor
  const paramsContainer = document.getElementById('edit-parameters-fields');
  paramsContainer.innerHTML = '';

  const params = editingRule.parameters_json || {};
  for (const [key, val] of Object.entries(params)) {
    const group = document.createElement('div');
    group.className = 'form-group';
    group.innerHTML = `
      <label class="form-label">${key.replace(/_/g, ' ').toUpperCase()}</label>
      <input type="${typeof val === 'number' ? 'number' : 'text'}" step="any" class="form-control param-input" data-param-key="${key}" value="${val}">
    `;
    paramsContainer.appendChild(group);
  }

  document.getElementById('modal-edit-rule').classList.add('active');
}

async function handleSaveRule(e) {
  e.preventDefault();
  if (!editingRule) return;

  const confirmed = confirm(`Are you sure you want to update the parameters for "${editingRule.rule_name}"? New evaluations will use these updated parameters.`);
  if (!confirmed) return;

  const points = parseInt(document.getElementById('edit-rule-points').value);
  const isEnabled = document.getElementById('edit-rule-enabled').checked;

  const updatedParams = {};
  document.querySelectorAll('.param-input').forEach(input => {
    const key = input.dataset.paramKey;
    let val = input.value;
    if (input.type === 'number') {
      val = parseFloat(val);
    }
    updatedParams[key] = val;
  });

  const payload = {
    rule_name: document.getElementById('edit-rule-name').value.trim(),
    description: document.getElementById('edit-rule-desc').value.trim(),
    risk_points: points,
    is_enabled: isEnabled,
    parameters_json: updatedParams
  };

  try {
    await ApiClient.put(`/rules/${editingRule.rule_id}`, payload);
    ApiClient.showToast('Rule configuration successfully saved.', 'success');
    document.getElementById('modal-edit-rule').classList.remove('active');
    await loadRules();
  } catch (err) {
    // Toast handled
  }
}
