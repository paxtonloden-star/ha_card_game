import { setHost, setState } from './state.js';

function findParentHass() {
  try {
    if (window.parent && window.parent !== window) {
      const roots = window.parent.document.querySelectorAll('home-assistant, hc-main, home-assistant-main');
      for (const root of roots) {
        if (root && root.hass) return root.hass;
        if (root && root.__data && root.__data.hass) return root.__data.hass;
      }
      const first = window.parent.document.querySelector('home-assistant');
      if (first && first.hass) return first.hass;
    }
  } catch (_err) {}
  return null;
}

function getBearerToken() {
  try {
    const parentHass = findParentHass();
    const token = parentHass?.auth?.data?.accessToken;
    if (token) return token;
  } catch (_err) {}

  try {
    const raw = window.localStorage.getItem('hassTokens');
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed?.access_token) return parsed.access_token;
    }
  } catch (_err) {}

  return null;
}

export async function api(path, method = 'GET', body = null) {
  const options = { method, headers: {}, credentials: 'same-origin' };
  if (body) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body);
  }
  const token = getBearerToken();
  if (token) options.headers.Authorization = 'Bearer ' + token;
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.ok === false) throw new Error(data.error || 'Request failed');
  return data;
}

export async function fetchState(sessionToken = '') {
  const suffix = sessionToken ? `?token=${encodeURIComponent(sessionToken)}` : '';
  const data = await api(`/api/ha_card_game/state${suffix}`);
  setState(data.state);
  return data.state;
}

export async function fetchHostBootstrap() {
  const data = await api('/api/ha_card_game/host/bootstrap');
  setHost(data.host || null);
  setState(data.state);
  return data;
}

export async function hostAction(action, extra = {}) {
  const data = await api('/api/ha_card_game/host/action', 'POST', { action, ...extra });
  if (data.state) setState(data.state);
  return data;
}
