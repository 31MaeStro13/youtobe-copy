const API_BASE = '/api/v1';

async function request(method, path, body = null, isForm = false, isRetry = false) {
  const headers = {};
  const token = localStorage.getItem('access_token');
  if (token) headers['Authorization'] = `Bearer ${token}`;

  let bodyData = null;
  if (body && !isForm) {
    headers['Content-Type'] = 'application/json';
    bodyData = JSON.stringify(body);
  } else if (isForm) {
    bodyData = body; // FormData
  }

  const res = await fetch(API_BASE + path, { method, headers, body: bodyData });

  if (res.status === 401 && !isRetry && path !== '/auth/refresh' && path !== '/auth/login') {
    // Попытка обновить токен (ровно 1 раз)
    const refreshed = await tryRefresh();
    if (refreshed) return request(method, path, body, isForm, true);
    logout();
    return null;
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    let msg = 'Request failed';
    if (typeof err.detail === 'string') {
      msg = err.detail;
    } else if (Array.isArray(err.detail)) {
      msg = err.detail.map(d => `${d.loc ? d.loc.slice(1).join('.'): ''}: ${d.msg}`).join(', ');
    } else if (err.detail) {
      msg = JSON.stringify(err.detail);
    }
    throw new Error(msg);
  }

  if (res.status === 204) return null;
  return res.json();
}

async function tryRefresh() {
  const rt = localStorage.getItem('refresh_token');
  if (!rt) return false;
  try {
    const res = await fetch(API_BASE + '/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: rt }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    saveTokens(data);
    return true;
  } catch {
    return false;
  }
}

function saveTokens(data) {
  localStorage.setItem('access_token', data.access_token);
  localStorage.setItem('refresh_token', data.refresh_token);
  localStorage.setItem('user_id', data.user_id);
  localStorage.setItem('username', data.username);
  localStorage.setItem('role', data.role);
}

function logout() {
  localStorage.clear();
  window.location.href = '/auth.html';
}

function getCurrentUser() {
  const uid = localStorage.getItem('user_id');
  if (!uid) return null;
  return {
    id: parseInt(uid),
    username: localStorage.getItem('username'),
    role: localStorage.getItem('role'),
  };
}

function isLoggedIn() {
  return !!localStorage.getItem('access_token');
}

function isModerator() {
  const role = localStorage.getItem('role');
  return role === 'moderator' || role === 'admin';
}

function isAdmin() {
  return localStorage.getItem('role') === 'admin';
}

// Helpers
function fmtDuration(secs) {
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function fmtViews(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}

function fmtDate(iso) {
  const d = new Date(iso);
  const diff = (Date.now() - d) / 1000;
  if (diff < 3600) return Math.floor(diff / 60) + ' min ago';
  if (diff < 86400) return Math.floor(diff / 3600) + ' hours ago';
  if (diff < 2592000) return Math.floor(diff / 86400) + ' days ago';
  return d.toLocaleDateString();
}

function showToast(msg, type = 'info') {
  let toast = document.getElementById('toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toast';
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.className = `toast toast-${type} show`;
  setTimeout(() => toast.classList.remove('show'), 3000);
}

function escHtml(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

window.API = { request, saveTokens, logout, getCurrentUser, isLoggedIn, isModerator, isAdmin };
window.Utils = { fmtDuration, fmtViews, fmtDate, showToast, escHtml };
window.escHtml = escHtml;
