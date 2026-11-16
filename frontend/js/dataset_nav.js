/**
 * Dataset Navigation & Switching Header Helper for all views
 */

document.addEventListener('DOMContentLoaded', async () => {
  injectDatasetHeader();
  await loadActiveDatasetHeader();
});

function injectDatasetHeader() {
  const topbar = document.querySelector('.topbar');
  if (!topbar) return;

  const actions = topbar.querySelector('.topbar-actions');
  if (!actions) return;

  // Insert dataset badge and switch button if not already present
  if (!document.getElementById('active-dataset-badge')) {
    const badge = document.createElement('div');
    badge.id = 'active-dataset-badge';
    badge.className = 'dataset-badge';
    badge.innerHTML = '<span>📁</span> <span>Loading dataset...</span>';
    actions.insertBefore(badge, actions.firstChild);
  }

  if (!document.getElementById('btn-switch-dataset')) {
    const switchBtn = document.createElement('button');
    switchBtn.id = 'btn-switch-dataset';
    switchBtn.className = 'btn btn-secondary btn-sm';
    switchBtn.innerHTML = '<span>🔄</span> Switch / Upload Dataset';
    switchBtn.addEventListener('click', openGlobalDatasetSwitcherModal);
    actions.insertBefore(switchBtn, actions.children[1] || null);
  }

  // Inject modal into document body if not present
  if (!document.getElementById('modal-dataset-switcher')) {
    const modal = document.createElement('div');
    modal.id = 'modal-dataset-switcher';
    modal.className = 'modal-backdrop';
    modal.style.display = 'none';
    modal.innerHTML = `
      <div class="dataset-modal-card">
        <div class="modal-header">
          <div style="font-weight:700; font-size:1.1rem; color:var(--primary-navy);">
            Select or Switch Active Dataset
          </div>
          <button id="btn-close-dataset-modal" style="background:none; border:none; font-size:1.2rem; cursor:pointer;">&times;</button>
        </div>
        <div class="modal-body" id="modal-dataset-list">
          <div style="text-align:center; padding:20px;">Loading datasets...</div>
        </div>
        <div class="modal-footer">
          <button id="btn-modal-upload-new" class="btn btn-primary btn-sm">
            <span>➕</span> Upload New Dataset
          </button>
          <button id="btn-modal-close-action" class="btn btn-secondary btn-sm">Close</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    modal.querySelector('#btn-close-dataset-modal').addEventListener('click', () => modal.style.display = 'none');
    modal.querySelector('#btn-modal-close-action').addEventListener('click', () => modal.style.display = 'none');
    modal.querySelector('#btn-modal-upload-new').addEventListener('click', () => {
      // Clear session before returning to upload workflow
      sessionStorage.removeItem('sessionDatasetId');
      sessionStorage.removeItem('sessionDatasetName');
      sessionStorage.removeItem('sessionDatasetRows');
      window.location.href = '/';
    });
  }
}

async function loadActiveDatasetHeader() {
  const badge = document.getElementById('active-dataset-badge');
  if (!badge) return;

  // Read from sessionStorage first (set when user enters dashboard from workflow)
  const dsId = sessionStorage.getItem('sessionDatasetId');
  const dsName = sessionStorage.getItem('sessionDatasetName');
  const dsRows = sessionStorage.getItem('sessionDatasetRows');

  if (dsId && dsName) {
    const rowsNum = parseInt(dsRows) || 0;
    badge.innerHTML = `📁 <strong>Dataset:</strong> ${dsName} (${rowsNum.toLocaleString()} txns)`;
    return;
  }

  // Fallback: query API (for cases where sessionStorage not set yet)
  try {
    const res = await ApiClient.get('/datasets/active');
    const ds = res && res.dataset_id ? res : (res ? res.dataset : null);
    if (ds) {
      badge.innerHTML = `📁 <strong>Dataset:</strong> ${ds.filename} (${ds.total_rows.toLocaleString()} txns)`;
    } else {
      badge.innerHTML = '⚠️ <strong>No Active Dataset</strong>';
      badge.style.backgroundColor = '#fef2f2';
      badge.style.borderColor = '#fecaca';
      badge.style.color = '#dc2626';
    }
  } catch (err) {
    console.error('Failed to load active dataset badge:', err);
  }
}

async function openGlobalDatasetSwitcherModal() {
  const modal = document.getElementById('modal-dataset-switcher');
  const list = document.getElementById('modal-dataset-list');
  if (!modal || !list) return;

  list.innerHTML = '<div style="text-align:center; padding:20px;">Loading datasets...</div>';
  modal.style.display = 'flex';

  try {
    const res = await ApiClient.get('/datasets');
    const datasets = res.items || res.datasets || [];

    if (datasets.length === 0) {
      list.innerHTML = '<div style="text-align:center; color:var(--text-muted); padding:20px;">No datasets uploaded yet. Click "Upload New Dataset" below.</div>';
      return;
    }

    list.innerHTML = '';
    datasets.forEach(ds => {
      const item = document.createElement('div');
      item.className = `dataset-list-item ${ds.is_active ? 'active' : ''}`;
      item.innerHTML = `
        <div>
          <div style="font-weight:700; color:var(--primary-navy); display:flex; align-items:center; gap:8px;">
            <span>📁</span> ${ds.filename}
            ${ds.is_active ? '<span class="dataset-badge" style="padding:2px 8px; font-size:0.75rem;">Active</span>' : ''}
          </div>
          <div style="font-size:0.8rem; color:var(--text-muted); margin-top:2px;">
            ${ds.total_rows.toLocaleString()} transactions &bull; Status: <strong>${ds.status}</strong> &bull; Uploaded ${Formatters.date(ds.created_at)}
          </div>
        </div>
        <div>
          ${ds.is_active 
            ? '<span style="font-size:0.85rem; font-weight:600; color:var(--accent-blue);">Current View</span>' 
            : `<button class="btn btn-secondary btn-sm" onclick="switchGlobalDataset(${ds.dataset_id})">Switch to Dataset</button>`
          }
        </div>
      `;
      list.appendChild(item);
    });
  } catch (err) {
    console.error('Failed to load datasets for switcher:', err);
    list.innerHTML = '<div style="color:red; text-align:center;">Failed to load datasets.</div>';
  }
}

async function switchGlobalDataset(datasetId) {
  try {
    const res = await ApiClient.post(`/datasets/switch/${datasetId}`);
    if (res && res.dataset_id) {
      sessionStorage.setItem('sessionDatasetId', res.dataset_id);
      sessionStorage.setItem('sessionDatasetName', res.filename);
      sessionStorage.setItem('sessionDatasetRows', res.total_rows || 0);
    }
    window.location.reload();
  } catch (err) {
    console.error('Failed to switch dataset:', err);
  }
}

window.switchGlobalDataset = switchGlobalDataset;
