/**
 * Banking Transaction Monitoring — Upload Workflow Controller
 *
 * Flow:  Upload CSV  →  Preview & Validate  →  [Auto] Run Analysis  →  Dashboard
 *
 * sessionStorage keys used by this page and all sub-pages:
 *   sessionDatasetId   – numeric DB dataset_id of the active session dataset
 *   sessionDatasetName – filename string
 *   sessionDatasetRows – total_rows integer
 */

'use strict';

let currentPreviewData = null;   // response from /api/datasets/preview
let currentDataset     = null;   // response from /api/datasets/confirm (Dataset record)

/* =========================================================================
   Boot
========================================================================= */
document.addEventListener('DOMContentLoaded', async () => {
  setupDropZone();
  setupNavigationButtons();
  setupDatasetSwitcher();

  const urlParams = new URLSearchParams(window.location.search);
  const forceUpload = urlParams.get('upload') === '1';
  const activeSessionId = sessionStorage.getItem('sessionDatasetId');

  // If a session dataset is active and not explicitly in upload mode, restore dashboard
  if (activeSessionId && !forceUpload) {
    currentDataset = {
      dataset_id: parseInt(activeSessionId),
      filename: sessionStorage.getItem('sessionDatasetName') || 'Active Dataset',
      total_rows: parseInt(sessionStorage.getItem('sessionDatasetRows')) || 0,
      status: 'ANALYSED'
    };
    showDashboardView();
  } else {
    // New application visit or explicit upload intent — show landing page
    showWorkflowSection('step-landing');
    await loadPreviousDatasetsList();
  }
});

/* =========================================================================
   View switching helpers
========================================================================= */

/**
 * Show the given workflow section (step-landing | step-preview).
 * Hides sidebar and dashboard; shows workflow-wrapper.
 */
function showWorkflowSection(sectionId) {
  const workflowWrapper = document.getElementById('workflow-wrapper');
  const sidebar         = document.querySelector('.app-sidebar');
  const mainWrapper     = document.querySelector('.main-wrapper');

  if (workflowWrapper) workflowWrapper.style.display = 'flex';
  if (sidebar)         sidebar.style.display         = 'none';
  if (mainWrapper)     mainWrapper.style.display      = 'none';

  ['step-landing', 'step-preview'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = (id === sectionId) ? 'block' : 'none';
  });
}

/**
 * Reveal the monitoring dashboard.
 * Writes sessionStorage so all sub-pages (transactions, alerts, …) know a
 * dataset is active and can skip the route guard redirect.
 */
function showDashboardView() {
  const workflowWrapper = document.getElementById('workflow-wrapper');
  const sidebar         = document.querySelector('.app-sidebar');
  const mainWrapper     = document.querySelector('.main-wrapper');

  if (workflowWrapper) workflowWrapper.style.display = 'none';
  if (sidebar)         sidebar.style.display         = 'flex';
  if (mainWrapper)     mainWrapper.style.display      = 'flex';

  if (currentDataset) {
    sessionStorage.setItem('sessionDatasetId',   currentDataset.dataset_id);
    sessionStorage.setItem('sessionDatasetName', currentDataset.filename);
    sessionStorage.setItem('sessionDatasetRows', currentDataset.total_rows || 0);
    updateActiveDatasetBadge(currentDataset);
  }

  if (typeof initDashboard === 'function') {
    // Set filter to "All Transactions" (days=0) so the full uploaded dataset is shown by default
    const daysFilter = document.getElementById('filter-days');
    if (daysFilter) daysFilter.value = '0';
    initDashboard();
  }
}

/**
 * Called when user clicks "Overview Dashboard" in the sidebar.
 * Keeps the dashboard visible (does NOT navigate to "/").
 */
function handleOverviewNavClick(event) {
  event.preventDefault();

  // If the dashboard is already visible just refresh its data
  const mainWrapper = document.querySelector('.main-wrapper');
  if (mainWrapper && mainWrapper.style.display !== 'none') {
    if (typeof initDashboard === 'function') initDashboard();
    return;
  }

  // Otherwise show it (happens when switching back from switcher modal)
  showDashboardView();
}
window.handleOverviewNavClick = handleOverviewNavClick;

/* =========================================================================
   Drop-zone setup
========================================================================= */
function setupDropZone() {
  const dropZone  = document.getElementById('drop-zone');
  const fileInput = document.getElementById('csv-file-input');
  const browseBtn = document.getElementById('btn-browse-file');

  if (!dropZone || !fileInput) return;

  browseBtn.addEventListener('click', e => { e.stopPropagation(); fileInput.click(); });
  dropZone.addEventListener('click',  () => fileInput.click());

  ['dragenter', 'dragover'].forEach(ev =>
    dropZone.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); dropZone.classList.add('dragover'); }, false)
  );
  ['dragleave', 'drop'].forEach(ev =>
    dropZone.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); dropZone.classList.remove('dragover'); }, false)
  );

  dropZone.addEventListener('drop', e => {
    const files = e.dataTransfer.files;
    if (files && files.length > 0) handleFileSelected(files[0]);
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files.length > 0) handleFileSelected(fileInput.files[0]);
  });
}

/* =========================================================================
   File selection → Preview API
========================================================================= */
async function handleFileSelected(file) {
  if (!file.name.toLowerCase().endsWith('.csv')) {
    ApiClient.showToast('Please select a valid CSV file (.csv)', 'error');
    return;
  }

  const statusText = document.getElementById('drop-zone-status-text');
  if (statusText) statusText.textContent = `Validating ${file.name}…`;

  const formData = new FormData();
  formData.append('file', file);

  try {
    const previewRes = await ApiClient.post('/datasets/preview', formData);
    currentPreviewData = previewRes;
    renderPreviewScreen(previewRes);
    showWorkflowSection('step-preview');
  } catch (err) {
    console.error('CSV preview failed:', err);
    if (statusText) statusText.textContent = 'Drag & drop transaction CSV here';
  }
}

/* =========================================================================
   Preview screen renderer
========================================================================= */
function renderPreviewScreen(data) {
  document.getElementById('preview-filename').textContent = data.filename;
  document.getElementById('preview-filesize').textContent = Formatters.fileSize(data.file_size_bytes);
  document.getElementById('preview-rows').textContent     = `${data.total_rows.toLocaleString()} rows`;
  document.getElementById('preview-cols').textContent     = `${data.total_columns} columns`;

  // Validation banner
  const bannerContainer = document.getElementById('validation-banner-container');
  bannerContainer.innerHTML = '';

  const banner = document.createElement('div');
  if (data.validation_passed) {
    banner.className = 'validation-banner success';
    banner.innerHTML = `
      <div style="font-size:1.4rem;">&#x2705;</div>
      <div>
        <strong>Validation Passed:</strong> ${data.validation_summary}
        ${data.invalid_amounts_count  > 0 ? `<div style="margin-top:4px;font-size:0.85rem;">&#x26A0;&#xFE0F; ${data.invalid_amounts_count} rows with non-positive or malformed amounts.</div>` : ''}
        ${data.invalid_timestamps_count > 0 ? `<div style="margin-top:4px;font-size:0.85rem;">&#x26A0;&#xFE0F; ${data.invalid_timestamps_count} rows with unrecognised timestamp formats.</div>` : ''}
        ${data.duplicate_refs_count > 0 ? `<div style="margin-top:4px;font-size:0.85rem;">&#x26A0;&#xFE0F; ${data.duplicate_refs_count} duplicate transaction references detected.</div>` : ''}
      </div>`;
  } else {
    banner.className = 'validation-banner error';
    banner.innerHTML = `
      <div style="font-size:1.4rem;">&#x26A0;&#xFE0F;</div>
      <div>
        <strong>Validation Issue Detected:</strong> ${data.validation_summary}
        <div style="margin-top:4px;">Please check the column mapping or ensure all required fields are present.</div>
      </div>`;
  }
  bannerContainer.appendChild(banner);

  // Column mapping panel — always shown, all supported fields
  const mappingCard      = document.getElementById('column-mapping-card');
  const mappingContainer = document.getElementById('column-mapping-fields');
  mappingContainer.innerHTML = '';

  const csvColumns   = data.columns || [];           // raw headers from uploaded CSV
  const autoMappings = data.detected_mappings || {}; // auto-detected field → CSV column
  const missing      = data.missing_required_columns || [];

  // All fields grouped for display
  const FIELD_GROUPS = [
    {
      title: '📋 Required Fields',
      subtitle: 'These five fields must be mapped to continue.',
      fields: [
        { key: 'account_id',       label: 'Account ID',        required: true },
        { key: 'amount',           label: 'Amount',            required: true },
        { key: 'transaction_type', label: 'Transaction Type',  required: true },
        { key: 'timestamp',        label: 'Timestamp / Date',  required: true },
        { key: 'location_city',    label: 'Location City',     required: true }
      ]
    },
    {
      title: '👤 Customer Fields',
      subtitle: 'Optional. Identify the person who made the transaction.',
      fields: [
        { key: 'customer_id',       label: 'Customer ID',       required: false },
        { key: 'customer_name',     label: 'Customer Name',     required: false },
        { key: 'customer_email',    label: 'Customer Email',    required: false },
        { key: 'customer_category', label: 'Customer Category', required: false },
        { key: 'email',             label: 'Email (generic)',   required: false },
        { key: 'account_balance',   label: 'Account Balance',   required: false }
      ]
    },
    {
      title: '🏪 Merchant Fields',
      subtitle: 'Optional. Identify the business where the transaction occurred.',
      fields: [
        { key: 'merchant_name',     label: 'Merchant Name',     required: false },
        { key: 'merchant_category', label: 'Merchant Category', required: false }
      ]
    },
    {
      title: '⚙️ Other Optional Fields',
      subtitle: 'Additional enrichment data.',
      fields: [
        { key: 'currency',          label: 'Currency',           required: false },
        { key: 'channel',           label: 'Channel / Medium',   required: false },
        { key: 'transaction_ref',   label: 'Transaction Ref',    required: false },
        { key: 'location_country',  label: 'Location Country',   required: false },
        { key: 'latitude',          label: 'Latitude',           required: false },
        { key: 'longitude',         label: 'Longitude',          required: false },
        { key: 'device_id',         label: 'Device ID',          required: false },
        { key: 'ip_address',        label: 'IP Address',         required: false }
      ]
    }
  ];

  // Build options HTML — blank first + all CSV columns
  function buildOptions(selectedCol) {
    let html = '<option value="">— Not Mapped —</option>';
    csvColumns.forEach(col => {
      const sel = col === selectedCol ? ' selected' : '';
      html += `<option value="${col}"${sel}>${col}</option>`;
    });
    return html;
  }

  FIELD_GROUPS.forEach(group => {
    // Group header
    const groupDiv = document.createElement('div');
    groupDiv.style.cssText = 'margin-bottom:18px;';

    const groupTitle = document.createElement('div');
    groupTitle.style.cssText = 'font-weight:700; font-size:0.88rem; color:var(--primary-navy); margin-bottom:2px;';
    groupTitle.textContent = group.title;
    groupDiv.appendChild(groupTitle);

    const groupSub = document.createElement('div');
    groupSub.style.cssText = 'font-size:0.78rem; color:var(--text-muted); margin-bottom:8px;';
    groupSub.textContent = group.subtitle;
    groupDiv.appendChild(groupSub);

    // Grid wrapper for field rows
    const grid = document.createElement('div');
    grid.style.cssText = 'display:grid; grid-template-columns:1fr 1fr; gap:8px;';

    group.fields.forEach(field => {
      const autoCol  = autoMappings[field.key] || '';
      const isMissing = field.required && missing.includes(field.key);

      const cell = document.createElement('div');
      cell.style.cssText = `display:flex; align-items:center; gap:8px; background:${isMissing ? '#fff5f5' : '#f8fafc'}; border:1px solid ${isMissing ? '#fca5a5' : 'var(--border-color)'}; border-radius:6px; padding:7px 10px;`;

      const labelEl = document.createElement('label');
      labelEl.style.cssText = 'flex:0 0 140px; font-size:0.82rem; font-weight:600; color:var(--primary-navy); white-space:nowrap;';
      labelEl.textContent = field.label + (field.required ? ' *' : '');
      if (isMissing) labelEl.style.color = '#dc2626';

      const selectEl = document.createElement('select');
      selectEl.className = 'filter-select mapping-select';
      selectEl.setAttribute('data-target', field.key);
      selectEl.style.cssText = 'flex:1; font-size:0.82rem; min-width:0;';
      selectEl.innerHTML = buildOptions(autoCol);

      // Visual indicator when auto-mapped
      if (autoCol) {
        selectEl.style.borderColor = '#86efac'; // green border = auto-detected
        selectEl.title = `Auto-detected: "${autoCol}"`;
      }

      // Update border color on manual change
      selectEl.addEventListener('change', () => {
        selectEl.style.borderColor = selectEl.value ? '#93c5fd' : '';
        const parentCell = selectEl.closest('div[style]');
        if (parentCell && field.required) {
          parentCell.style.background = selectEl.value ? '#f8fafc' : '#fff5f5';
          parentCell.style.borderColor = selectEl.value ? 'var(--border-color)' : '#fca5a5';
          labelEl.style.color = selectEl.value ? 'var(--primary-navy)' : '#dc2626';
        }
      });

      cell.appendChild(labelEl);
      cell.appendChild(selectEl);
      grid.appendChild(cell);
    });

    groupDiv.appendChild(grid);
    mappingContainer.appendChild(groupDiv);
  });

  // Legend
  const legend = document.createElement('div');
  legend.style.cssText = 'margin-top:10px; font-size:0.78rem; color:var(--text-muted); display:flex; gap:16px; flex-wrap:wrap;';
  legend.innerHTML = `
    <span style="display:flex;align-items:center;gap:5px;"><span style="display:inline-block;width:12px;height:12px;border:2px solid #86efac;border-radius:2px;"></span> Auto-detected</span>
    <span style="display:flex;align-items:center;gap:5px;"><span style="display:inline-block;width:12px;height:12px;border:2px solid #93c5fd;border-radius:2px;"></span> Manually selected</span>
    <span style="display:flex;align-items:center;gap:5px;"><span style="display:inline-block;width:12px;height:12px;border:2px solid #fca5a5;background:#fff5f5;border-radius:2px;"></span> Required — missing</span>
  `;
  mappingContainer.appendChild(legend);

  mappingCard.style.display = 'block';

  // Preview table
  const thead = document.getElementById('preview-table-thead');
  const tbody = document.getElementById('preview-table-tbody');
  thead.innerHTML = '';
  tbody.innerHTML = '';

  if (data.preview_rows && data.preview_rows.length > 0) {
    const headers = Object.keys(data.preview_rows[0]);
    const headerRow = document.createElement('tr');
    headers.forEach(h => {
      const th = document.createElement('th');
      th.textContent = h;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);

    data.preview_rows.forEach(r => {
      const tr = document.createElement('tr');
      headers.forEach(h => {
        const td = document.createElement('td');
        td.textContent = (r[h] !== null && r[h] !== undefined) ? String(r[h]) : '';
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
  }

  // Reset action bar state
  const actionBar = document.getElementById('preview-action-bar');
  const runningCard = document.getElementById('analysis-running-card');
  if (actionBar)    actionBar.style.display    = 'flex';
  if (runningCard)  runningCard.style.display  = 'none';
}

/* =========================================================================
   Navigation button bindings
========================================================================= */
function setupNavigationButtons() {

  // ── Back to Upload ──────────────────────────────────────────────────────
  const btnCancel = document.getElementById('btn-cancel-preview');
  if (btnCancel) {
    btnCancel.addEventListener('click', () => {
      currentPreviewData = null;
      const fileInput = document.getElementById('csv-file-input');
      if (fileInput) fileInput.value = '';
      const statusText = document.getElementById('drop-zone-status-text');
      if (statusText) statusText.textContent = 'Drag & drop transaction CSV here';
      showWorkflowSection('step-landing');
    });
  }

  // ── Confirm & Run Fraud Analysis ────────────────────────────────────────
  const btnConfirm = document.getElementById('btn-confirm-preview');
  if (btnConfirm) {
    btnConfirm.addEventListener('click', async () => {
      if (!currentPreviewData) return;

      // Collect ALL column mappings from the mapping panel
      const customMapping = {};
      document.querySelectorAll('.mapping-select').forEach(sel => {
        const target = sel.getAttribute('data-target');
        const chosen = sel.value;
        if (target && chosen) customMapping[target] = chosen;
      });

      // Validate required fields are mapped
      const REQUIRED_KEYS = ['account_id', 'amount', 'transaction_type', 'timestamp', 'location_city'];
      const unmappedRequired = REQUIRED_KEYS.filter(k => !customMapping[k]);
      if (unmappedRequired.length > 0) {
        ApiClient.showToast(
          `Please map required fields: ${unmappedRequired.map(k => k.replace(/_/g, ' ')).join(', ')}`,
          'error'
        );
        // Highlight missing selects
        unmappedRequired.forEach(k => {
          const sel = document.querySelector(`.mapping-select[data-target="${k}"]`);
          if (sel) {
            sel.style.borderColor = '#dc2626';
            sel.style.outline = '2px solid #fca5a5';
            setTimeout(() => { sel.style.outline = ''; }, 3000);
          }
        });
        return;
      }

      // --- UI: show loading state ---
      const actionBar   = document.getElementById('preview-action-bar');
      const runningCard = document.getElementById('analysis-running-card');
      if (actionBar)   actionBar.style.display   = 'none';
      if (runningCard) runningCard.style.display  = 'block';

      try {
        // 1. Import the CSV into the DB → returns Dataset record
        const importedDataset = await ApiClient.post('/datasets/confirm', {
          temp_file_token: currentPreviewData.temp_file_token,
          filename:        currentPreviewData.filename,
          file_size_bytes: currentPreviewData.file_size_bytes,
          column_mapping:  customMapping
        });

        currentDataset = importedDataset;

        // 2. Run fraud analysis (auto, no extra click)
        await ApiClient.post(`/datasets/${currentDataset.dataset_id}/analyze`);
        currentDataset.status = 'ANALYSED';

        // 3. Set session and jump straight to dashboard
        ApiClient.showToast('Fraud analysis completed successfully.', 'success');
        showDashboardView();

      } catch (err) {
        console.error('Import / Analysis failed:', err);
        // Restore action bar so user can retry
        if (actionBar)   actionBar.style.display   = 'flex';
        if (runningCard) runningCard.style.display  = 'none';
      }
    });
  }
}

/* =========================================================================
   Previous Datasets list (landing page)
========================================================================= */
async function loadPreviousDatasetsList() {
  try {
    const res      = await ApiClient.get('/datasets');
    const datasets = res.items || res.datasets || [];
    const container = document.getElementById('previous-datasets-container');
    const listEl    = document.getElementById('previous-datasets-list');
    if (!container || !listEl) return;

    const analysed = datasets.filter(ds => ds.status === 'ANALYSED');
    if (analysed.length > 0) {
      container.style.display = 'block';
      listEl.innerHTML = '';
      analysed.slice(0, 5).forEach(ds => {
        const btn = document.createElement('button');
        btn.className = 'dataset-pill-btn';
        btn.innerHTML = `<span>&#x1F4C1;</span> <strong>${ds.filename}</strong> (${ds.total_rows.toLocaleString()} txns) <span style="color:var(--risk-low); font-weight:600;">&#x2714; Analysed</span>`;
        btn.addEventListener('click', () => switchDataset(ds.dataset_id));
        listEl.appendChild(btn);
      });
    } else {
      container.style.display = 'none';
    }
  } catch (err) {
    console.error('Failed to load previous datasets:', err);
  }
}

/* =========================================================================
   Dataset Switcher Modal (in dashboard header)
========================================================================= */
function setupDatasetSwitcher() {
  const switchBtn   = document.getElementById('btn-switch-dataset');
  const modal       = document.getElementById('modal-dataset-switcher');
  const closeBtn    = document.getElementById('btn-close-dataset-modal');
  const uploadNewBtn = document.getElementById('btn-modal-upload-new');

  if (switchBtn && modal) {
    switchBtn.addEventListener('click', () => openDatasetSwitcherModal());
  }
  if (closeBtn && modal) {
    closeBtn.addEventListener('click', () => { modal.style.display = 'none'; });
  }
  if (uploadNewBtn) {
    uploadNewBtn.addEventListener('click', () => {
      if (modal) modal.style.display = 'none';
      sessionStorage.removeItem('sessionDatasetId');
      sessionStorage.removeItem('sessionDatasetName');
      sessionStorage.removeItem('sessionDatasetRows');
      currentDataset     = null;
      currentPreviewData = null;
      showWorkflowSection('step-landing');
      loadPreviousDatasetsList();
    });
  }
}

async function openDatasetSwitcherModal() {
  const modal = document.getElementById('modal-dataset-switcher');
  const list  = document.getElementById('modal-dataset-list');
  if (!modal || !list) return;

  list.innerHTML = '<div style="text-align:center; padding:20px;">Loading datasets...</div>';
  modal.style.display = 'flex';

  try {
    const res      = await ApiClient.get('/datasets');
    const datasets = res.items || res.datasets || [];

    if (datasets.length === 0) {
      list.innerHTML = '<div style="text-align:center; color:var(--text-muted); padding:20px;">No datasets uploaded yet.</div>';
      return;
    }

    list.innerHTML = '';
    datasets.forEach(ds => {
      const item = document.createElement('div');
      item.className = `dataset-list-item ${ds.is_active ? 'active' : ''}`;
      item.innerHTML = `
        <div>
          <div style="font-weight:700; color:var(--primary-navy); display:flex; align-items:center; gap:8px;">
            <span>&#x1F4C1;</span> ${ds.filename}
            ${ds.is_active ? '<span class="dataset-badge" style="padding:2px 8px; font-size:0.75rem;">Active</span>' : ''}
          </div>
          <div style="font-size:0.8rem; color:var(--text-muted); margin-top:2px;">
            ${ds.total_rows.toLocaleString()} transactions &bull; Status: <strong>${ds.status}</strong> &bull; Uploaded ${Formatters.date(ds.created_at)}
          </div>
        </div>
        <div>
          ${ds.is_active
            ? '<span style="font-size:0.85rem; font-weight:600; color:var(--accent-blue);">Current View</span>'
            : `<button class="btn btn-secondary btn-sm" onclick="switchDataset(${ds.dataset_id})">Switch to Dataset</button>`
          }
        </div>`;
      list.appendChild(item);
    });
  } catch (err) {
    console.error('Dataset switcher load failed:', err);
    list.innerHTML = '<div style="color:red; text-align:center;">Failed to load datasets.</div>';
  }
}

async function switchDataset(datasetId) {
  try {
    const res = await ApiClient.post(`/datasets/switch/${datasetId}`);
    currentDataset = res;

    const modal = document.getElementById('modal-dataset-switcher');
    if (modal) modal.style.display = 'none';

    if (res.status === 'ANALYSED') {
      sessionStorage.setItem('sessionDatasetId',   res.dataset_id);
      sessionStorage.setItem('sessionDatasetName', res.filename);
      sessionStorage.setItem('sessionDatasetRows', res.total_rows || 0);
      showDashboardView();
      ApiClient.showToast(`Switched to dataset: ${res.filename}`, 'info');
    } else {
      // Dataset exists but not yet analysed — go back to upload and let them run analysis
      showWorkflowSection('step-landing');
      loadPreviousDatasetsList();
      ApiClient.showToast(`Dataset "${res.filename}" has not been analysed yet. Upload a new file or select an analysed dataset.`, 'warning');
    }
  } catch (err) {
    console.error('Dataset switch failed:', err);
  }
}
window.switchDataset = switchDataset;

/* =========================================================================
   Active dataset badge helper
========================================================================= */
function updateActiveDatasetBadge(dataset) {
  const badge = document.getElementById('active-dataset-badge');
  if (badge && dataset) {
    badge.innerHTML = `&#x1F4C1; <strong>Dataset:</strong> ${dataset.filename} (${(dataset.total_rows || 0).toLocaleString()} txns)`;
  }
}
