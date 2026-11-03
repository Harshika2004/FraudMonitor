/**
 * Banking Transaction Monitoring - REST API Client
 */

const API_BASE = '/api';

class ApiClient {
  static async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const defaultHeaders = {
      'Accept': 'application/json'
    };

    if (!(options.body instanceof FormData)) {
      defaultHeaders['Content-Type'] = 'application/json';
    }

    const config = {
      ...options,
      headers: {
        ...defaultHeaders,
        ...options.headers
      }
    };

    try {
      const response = await fetch(url, config);
      const data = await response.json().catch(() => null);

      if (!response.ok) {
        let errorMsg = 'An unexpected server error occurred.';
        if (data && data.detail) {
          if (Array.isArray(data.detail)) {
            errorMsg = data.detail.map(d => `${d.loc ? d.loc.join('.') + ': ' : ''}${d.msg}`).join(', ');
          } else {
            errorMsg = data.detail;
          }
        }
        throw new Error(errorMsg);
      }

      return data;
    } catch (err) {
      console.error(`API Error on [${options.method || 'GET'}] ${endpoint}:`, err);
      ApiClient.showToast(err.message || 'Network connection failed', 'error');
      throw err;
    }
  }

  static get(endpoint, params = {}) {
    const query = new URLSearchParams();
    for (const [key, val] of Object.entries(params)) {
      if (val !== undefined && val !== null && val !== '') {
        query.append(key, val);
      }
    }
    const qStr = query.toString();
    const url = qStr ? `${endpoint}?${qStr}` : endpoint;
    return this.request(url, { method: 'GET' });
  }

  static post(endpoint, body) {
    return this.request(endpoint, {
      method: 'POST',
      body: body instanceof FormData ? body : JSON.stringify(body)
    });
  }

  static put(endpoint, body) {
    return this.request(endpoint, {
      method: 'PUT',
      body: JSON.stringify(body)
    });
  }

  static patch(endpoint, body) {
    return this.request(endpoint, {
      method: 'PATCH',
      body: JSON.stringify(body)
    });
  }

  static showToast(message, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.className = 'toast-container';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }
}

// Utility formatting helpers
const Formatters = {
  currency(amount, currency = 'USD') {
    if (amount === null || amount === undefined) return '$0.00';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD',
      maximumFractionDigits: 2
    }).format(amount);
  },

  compactCurrency(amount, currency = 'USD') {
    if (amount === null || amount === undefined) return '$0.00';
    const abs = Math.abs(amount);
    if (abs >= 1_000_000_000) {
      return (amount < 0 ? '-' : '') + '$' + (abs / 1_000_000_000).toFixed(2) + 'B';
    }
    if (abs >= 1_000_000) {
      return (amount < 0 ? '-' : '') + '$' + (abs / 1_000_000).toFixed(2) + 'M';
    }
    return this.currency(amount, currency);
  },

  dateTime(isoString) {
    if (!isoString) return '-';
    const date = new Date(isoString);
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  },

  dateOnly(isoString) {
    if (!isoString) return '-';
    const date = new Date(isoString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  },

  riskBadge(category, score) {
    const cat = (category || 'LOW').toUpperCase();
    const scoreText = score !== undefined && score !== null ? `(${score})` : '';
    let badgeClass = 'badge-low';
    if (cat === 'CRITICAL') badgeClass = 'badge-critical';
    else if (cat === 'HIGH') badgeClass = 'badge-high';
    else if (cat === 'MEDIUM') badgeClass = 'badge-medium';

    return `<span class="badge ${badgeClass}">${cat} ${scoreText}</span>`;
  },

  statusBadge(status) {
    const st = (status || 'OPEN').toUpperCase();
    let badgeClass = 'badge-status-open';
    if (st === 'UNDER_INVESTIGATION') badgeClass = 'badge-status-investigating';
    else if (st === 'RESOLVED') badgeClass = 'badge-status-resolved';

    const label = st.replace(/_/g, ' ');
    return `<span class="badge ${badgeClass}">${label}</span>`;
  }
};
