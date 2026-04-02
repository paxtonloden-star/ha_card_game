import { fetchHostBootstrap, fetchState, hostAction } from './api.js';
import { initRuntime, getRuntime, setSession } from './state.js';
import { el } from './utils.js';
import { renderHostLayout } from './components/host.js';
import { renderPlayerLayout } from './components/player.js';
import { renderTvLayout } from './components/tv.js';

function bindHostEvents() {
  const modeSelect = el('modularGameModeSelect');
  const applyModeBtn = el('modularApplyGameModeBtn');
  const startBtn = el('modularStartRoundBtn');
  const nextBtn = el('modularNextRoundBtn');
  const setTimerBtn = el('modularSetTimerBtn');
  const clearTimerBtn = el('modularClearTimerBtn');

  applyModeBtn?.addEventListener('click', async () => {
    await hostAction('set_game_mode', { game_mode: modeSelect?.value || 'cards' });
    await renderApp();
  });
  startBtn?.addEventListener('click', async () => {
    const state = getRuntime().state || {};
    await hostAction('start_game', { game_mode: state.game_mode || 'cards' });
    await renderApp();
  });
  nextBtn?.addEventListener('click', async () => {
    await hostAction('next_round');
    await renderApp();
  });
  setTimerBtn?.addEventListener('click', async () => {
    const seconds = parseInt(el('modularRoundTimer')?.value || '15', 10);
    await hostAction('set_round_timer', { seconds });
    await renderApp();
  });
  clearTimerBtn?.addEventListener('click', async () => {
    await hostAction('clear_round_timer');
    await renderApp();
  });
}

function bindPlayerEvents(runtimeMeta) {
  el('modularJoinBtn')?.addEventListener('click', async () => {
    const name = el('modularPlayerNameInput')?.value?.trim() || '';
    const joinCode = runtimeMeta.joinCodeFromUrl || getRuntime().state?.join_code || '';
    const response = await fetch('/api/ha_card_game/join', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ join_code: joinCode, player_name: name }),
      credentials: 'same-origin',
    });
    const data = await response.json();
    if (!response.ok || data.ok === false) throw new Error(data.error || 'Join failed');
    setSession({ player_name: data.player_name, session_token: data.session_token });
    await fetchState(data.session_token);
    await renderApp();
  });
}

export async function renderApp() {
  const runtime = getRuntime();
  const state = runtime.state || {};
  const host = runtime.host || {};
  const hostMount = el('modularHostMount');
  const playerMount = el('modularPlayerMount');
  const tvMount = el('modularTvMount');
  if (hostMount) hostMount.innerHTML = renderHostLayout(state, host);
  if (playerMount) playerMount.innerHTML = renderPlayerLayout(state);
  if (tvMount) tvMount.innerHTML = renderTvLayout(state);
  bindHostEvents();
  bindPlayerEvents(runtime.meta || {});
}

async function main() {
  const meta = initRuntime();
  getRuntime().meta = meta;
  try {
    await fetchHostBootstrap();
  } catch (_err) {
    // host bootstrap is optional for non-host viewers
  }
  await fetchState(meta.session?.session_token || '');
  await renderApp();
}

main().catch((err) => {
  console.error('Failed to bootstrap modular frontend', err);
});
