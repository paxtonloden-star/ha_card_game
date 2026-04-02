export const el = (id, root = document) => root.getElementById(id);

export function show(node, visible) {
  if (!node) return;
  node.classList.toggle('hidden', !visible);
}

export function escapeHtml(value) {
  return String(value || '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
}

export function escapeAttr(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

export function formatJoinUrl(value) {
  if (!value) return '—';
  try {
    const parsed = new URL(value, window.location.origin);
    return parsed.host + parsed.pathname + parsed.search;
  } catch (_err) {
    return value;
  }
}

export function describeState(state) {
  if (state.state === 'lobby' || state.state === 'idle') return 'Waiting in the lobby for players to join.';
  if (state.state === 'submitting') return 'Players are choosing their answer.';
  if (state.state === 'judging') return 'Judge is reading anonymous submissions.';
  if (state.state === 'results') return state.winner ? `${state.winner} wins this round.` : 'Round complete.';
  return state.state || 'idle';
}

export function createCollapsibleSection({ title, id, bodyHtml = '', open = true }) {
  const expanded = open ? 'true' : 'false';
  return `
    <section class="card host-section" data-host-section="${escapeAttr(id)}">
      <button class="host-section-toggle" type="button" data-toggle-section="${escapeAttr(id)}" aria-expanded="${expanded}">
        <span>${escapeHtml(title)}</span>
        <span class="badge">${open ? 'Hide' : 'Show'}</span>
      </button>
      <div class="host-section-body${open ? '' : ' hidden'}" id="section-${escapeAttr(id)}">
        ${bodyHtml}
      </div>
    </section>
  `;
}
