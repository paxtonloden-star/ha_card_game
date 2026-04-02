const runtime = {
  session: null,
  state: null,
  host: null,
};

export function initRuntime() {
  const storageKey = 'ha_card_game_session';
  const url = new URL(window.location.href);
  const joinCodeFromUrl = (url.searchParams.get('join') || '').toUpperCase();
  const modeFromUrl = (url.searchParams.get('mode') || '').toLowerCase();
  const tokenFromUrl = (url.searchParams.get('token') || '').trim();
  const nameFromUrl = (url.searchParams.get('name') || '').trim();

  let session = JSON.parse(localStorage.getItem(storageKey) || 'null');
  if (tokenFromUrl) {
    const persisted = {
      player_name: nameFromUrl || (session && session.player_name) || '',
      session_token: tokenFromUrl,
    };
    localStorage.setItem(storageKey, JSON.stringify(persisted));
    session = persisted;
  }

  runtime.session = session;
  return {
    storageKey,
    url,
    joinCodeFromUrl,
    modeFromUrl,
    tokenFromUrl,
    nameFromUrl,
    session,
  };
}

export function getRuntime() {
  return runtime;
}

export function setSession(session) {
  runtime.session = session;
  localStorage.setItem('ha_card_game_session', JSON.stringify(session));
}

export function setState(state) {
  runtime.state = state;
}

export function setHost(host) {
  runtime.host = host;
}

export function isTriviaMode() {
  return runtime.state?.game_mode === 'trivia';
}

export function isTvMode(modeFromUrl) {
  return modeFromUrl === 'tv';
}
