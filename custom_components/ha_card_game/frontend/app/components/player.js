import { escapeAttr, escapeHtml } from '../utils.js';

export function renderPlayerLayout(state) {
  const joined = !!state?.is_joined;
  const playerName = state?.player_name || '';
  const hand = Array.isArray(state?.hand) ? state.hand : [];
  const triviaMode = state?.game_mode === 'trivia';
  const choices = state?.trivia?.current_question?.choices || [];

  if (!joined) {
    return `
      <section class="card">
        <h2>Join the game</h2>
        <p class="muted">Use your Home Assistant display name or enter a name to join.</p>
        <input id="modularPlayerNameInput" placeholder="Your name" />
        <div class="actions" style="margin-top:12px;">
          <button id="modularJoinBtn">Join game</button>
        </div>
      </section>
    `;
  }

  const cardsMarkup = triviaMode
    ? choices.map((choice, idx) => `<button class="hand-card" data-trivia-choice="${idx}" data-card="${escapeAttr(choice)}">${String.fromCharCode(65 + idx)}. ${escapeHtml(choice)}</button>`).join('')
    : hand.map((card) => `<button class="hand-card" data-card="${escapeAttr(card)}">${escapeHtml(card)}</button>`).join('');

  return `
    <section class="card">
      <h2>Player: ${escapeHtml(playerName)}</h2>
      <div class="label">${triviaMode ? 'Choices' : 'Your hand'}</div>
      <div class="hand">${cardsMarkup || '<div class="muted">Nothing to show yet.</div>'}</div>
      <div class="actions" style="margin-top:12px;">
        ${triviaMode ? '<button class="secondary" id="modularBuzzBtn">Buzz</button>' : ''}
        <button id="modularSubmitBtn">${triviaMode ? 'Submit answer' : 'Submit card'}</button>
      </div>
    </section>
  `;
}
