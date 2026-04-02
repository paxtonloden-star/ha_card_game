import { createCollapsibleSection, escapeAttr, escapeHtml } from '../utils.js';

function modeOptionsMarkup(currentMode, gameModes = []) {
  return gameModes.map((item) => `<option value="${escapeAttr(item.value)}"${item.value === currentMode ? ' selected' : ''}>${escapeHtml(item.label)}</option>`).join('');
}

export function renderHostLayout(state, host = {}) {
  const currentMode = state?.game_mode || 'cards';
  const gameModes = host?.game_modes || [
    { value: 'trivia', label: 'Trivia' },
    { value: 'cards', label: 'Cards Against Us' },
    { value: 'judge_party', label: 'Kids Cards Against Us' },
  ];

  const modeSection = createCollapsibleSection({
    title: 'Game mode',
    id: 'game-mode',
    open: true,
    bodyHtml: `
      <div class="control-grid">
        <div>
          <label class="label" for="modularGameModeSelect">Mode</label>
          <select id="modularGameModeSelect">${modeOptionsMarkup(currentMode, gameModes)}</select>
        </div>
        <div>
          <label class="label" for="modularModeSummary">Summary</label>
          <input id="modularModeSummary" readonly value="${currentMode === 'trivia' ? 'Trivia questions and answer timing' : currentMode === 'judge_party' ? 'Family-friendly card deck mode' : 'Standard card mode'}" />
        </div>
      </div>
      <div class="actions wrap" style="margin-top:12px;">
        <button id="modularApplyGameModeBtn">Apply mode</button>
      </div>
    `,
  });

  const roundSection = createCollapsibleSection({
    title: 'Round controls',
    id: 'round-controls',
    open: true,
    bodyHtml: `
      <div class="control-grid">
        <div>
          <label class="label" for="modularRoundTimer">Round timer</label>
          <input id="modularRoundTimer" type="number" min="5" step="5" value="15" />
        </div>
        <div>
          <label class="label" for="modularPromptPreview">Current prompt</label>
          <input id="modularPromptPreview" readonly value="${escapeAttr(state?.current_prompt || 'Waiting for next round')}" />
        </div>
      </div>
      <div class="actions wrap" style="margin-top:12px;">
        <button id="modularStartRoundBtn">${currentMode === 'trivia' ? 'Start trivia' : 'Start game'}</button>
        <button class="secondary" id="modularNextRoundBtn">Next round</button>
        <button class="secondary" id="modularSetTimerBtn">Set timer</button>
        <button class="secondary" id="modularClearTimerBtn">Clear timer</button>
      </div>
    `,
  });

  const cardsSection = createCollapsibleSection({
    title: 'Cards mode settings',
    id: 'cards-settings',
    open: currentMode !== 'trivia',
    bodyHtml: `
      <div class="muted">Show deck chooser, deck import/export, and card-mode options here while card modes are active.</div>
    `,
  });

  const triviaSection = createCollapsibleSection({
    title: 'Trivia settings',
    id: 'trivia-settings',
    open: currentMode === 'trivia',
    bodyHtml: `
      <div class="control-grid">
        <div><label class="label" for="modularTriviaCategory">Category</label><input id="modularTriviaCategory" value="${escapeAttr(state?.trivia?.category || 'fun_facts')}" /></div>
        <div><label class="label" for="modularTriviaRemaining">Questions remaining</label><input id="modularTriviaRemaining" readonly value="${escapeAttr(String(state?.trivia?.remaining ?? 0))}" /></div>
      </div>
      <div class="actions wrap" style="margin-top:12px;">
        <button class="secondary" id="modularPrepareTriviaBtn">Prepare trivia</button>
        <button class="secondary" id="modularGradeTriviaBtn">Grade round</button>
      </div>
    `,
  });

  return `
    <div class="modular-host-layout">
      ${modeSection}
      ${roundSection}
      ${cardsSection}
      ${triviaSection}
    </div>
  `;
}
