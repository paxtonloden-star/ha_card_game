import { escapeHtml, formatJoinUrl } from '../utils.js';

export function renderTvLayout(state) {
  const triviaMode = state?.game_mode === 'trivia';
  const players = Array.isArray(state?.players) ? state.players : [];
  const leaderboard = Array.isArray(state?.leaderboard) ? state.leaderboard : [];

  return `
    <section class="tv-shell">
      <div class="tv-topbar">
        <div class="tv-brand">
          <span class="eyebrow">HA Card Game</span>
          <strong>${triviaMode ? 'Trivia' : escapeHtml(state?.state || 'Lobby')}</strong>
        </div>
        <div class="tv-badges">
          <span class="badge badge-xl">Round ${escapeHtml(String(state?.round_number || 0))}</span>
          <span class="badge badge-xl">${triviaMode ? 'Trivia mode' : `Judge: ${escapeHtml(state?.judge || '—')}`}</span>
        </div>
      </div>
      <div class="tv-main">
        <section class="tv-prompt-card">
          <div class="label">Current prompt</div>
          <div class="tv-prompt">${escapeHtml(state?.current_prompt || 'Waiting for the next round…')}</div>
          <div class="muted">Join URL: ${escapeHtml(formatJoinUrl(state?.join_url || ''))}</div>
        </section>
        <section class="tv-side-column">
          <div class="tv-panel">
            <div class="label">Players</div>
            <div class="tv-player-list">${players.map((player) => `<div class="tv-player"><span>${escapeHtml(player.name)}</span><span>${escapeHtml(String(player.score || 0))} pts</span></div>`).join('') || '<div class="muted">No players</div>'}</div>
          </div>
          <div class="tv-panel">
            <div class="label">Scores</div>
            <div class="tv-score-list">${leaderboard.map((item, idx) => `<div class="tv-score-row ${idx === 0 ? 'leader' : ''}"><span>#${idx + 1} ${escapeHtml(item.name)}</span><strong>${escapeHtml(String(item.score || 0))}</strong></div>`).join('') || '<div class="muted">No scores</div>'}</div>
          </div>
        </section>
      </div>
    </section>
  `;
}
