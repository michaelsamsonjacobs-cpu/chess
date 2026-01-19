const state = {
  token: sessionStorage.getItem("chessguard_token") || null,
};

const authUrlInput = document.getElementById("auth-url");
const serverUrlInput = document.getElementById("server-url");

const registerForm = document.getElementById("register-form");
const loginForm = document.getElementById("login-form");
const profileForm = document.getElementById("profile-form");
const gameForm = document.getElementById("game-form");

const registerMessage = document.getElementById("register-message");
const loginMessage = document.getElementById("login-message");
const profileMessage = document.getElementById("profile-message");
const gamesList = document.getElementById("games-list");

function resolveAuthUrl() {
  return authUrlInput.value || authUrlInput.placeholder;
}

function resolveServerUrl() {
  return serverUrlInput.value || serverUrlInput.placeholder;
}

function setMessage(element, message, variant = "info") {
  element.textContent = message;
  element.dataset.variant = variant;
}

function setToken(token) {
  state.token = token;
  if (token) {
    sessionStorage.setItem("chessguard_token", token);
  } else {
    sessionStorage.removeItem("chessguard_token");
  }
}

async function callAuth(path, options) {
  const url = new URL(path, resolveAuthUrl());
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
    ...options,
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail?.detail || response.statusText);
  }

  return response.json();
}

async function callServer(path, options = {}) {
  if (!state.token) {
    throw new Error("You must sign in first.");
  }

  const url = new URL(path, resolveServerUrl());
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${state.token}`,
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail?.detail || response.statusText);
  }

  return response.json();
}

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setMessage(registerMessage, "Creating account…");

  const payload = {
    email: document.getElementById("register-email").value,
    full_name: document.getElementById("register-name").value,
    password: document.getElementById("register-password").value,
  };

  try {
    await callAuth("/register", { method: "POST", body: JSON.stringify(payload) });
    setMessage(registerMessage, "Account created. You can now sign in.", "success");
  } catch (error) {
    setMessage(registerMessage, error.message || "Unable to register.", "error");
  }
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setMessage(loginMessage, "Signing in…");

  const payload = {
    email: document.getElementById("login-email").value,
    password: document.getElementById("login-password").value,
  };

  try {
    const data = await callAuth("/login", { method: "POST", body: JSON.stringify(payload) });
    setToken(data.access_token);
    setMessage(loginMessage, "Signed in successfully.", "success");
    await Promise.all([refreshProfile(), refreshGames()]);
  } catch (error) {
    setToken(null);
    setMessage(loginMessage, error.message || "Invalid credentials.", "error");
  }
});

profileForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setMessage(profileMessage, "Saving profile…");

  const payload = {
    display_name: document.getElementById("profile-display").value,
    bio: document.getElementById("profile-bio").value,
    rating: parseInt(document.getElementById("profile-rating").value, 10) || undefined,
  };

  try {
    const data = await callServer("/profile", { method: "PUT", body: JSON.stringify(payload) });
    setMessage(profileMessage, "Profile updated.", "success");
    updateProfileForm(data);
  } catch (error) {
    setMessage(profileMessage, error.message, "error");
  }
});

gameForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = {
    opponent: document.getElementById("game-opponent").value,
    result: document.getElementById("game-result").value,
    moves: document.getElementById("game-moves").value,
  };

  try {
    await callServer("/games", { method: "POST", body: JSON.stringify(payload) });
    document.getElementById("game-form").reset();
    await refreshGames();
  } catch (error) {
    alert(error.message);
  }
});

function updateProfileForm(profile) {
  document.getElementById("profile-display").value = profile?.display_name || "";
  document.getElementById("profile-bio").value = profile?.bio || "";
  document.getElementById("profile-rating").value = profile?.rating ?? "";
}

async function refreshProfile() {
  try {
    const data = await callServer("/profile");
    updateProfileForm(data);
    setMessage(profileMessage, "Profile loaded.", "success");
  } catch (error) {
    setMessage(profileMessage, error.message, "error");
  }
}

function renderGames(games) {
  gamesList.innerHTML = "";
  if (!games.length) {
    gamesList.innerHTML = '<li class="empty">No games recorded yet.</li>';
    return;
  }

  for (const game of games) {
    const li = document.createElement("li");
    li.innerHTML = `<strong>${game.opponent}</strong> — ${game.result}<br /><small>${
      new Date(game.created_at).toLocaleString()
    }</small>`;
    gamesList.appendChild(li);
  }
}

async function refreshGames() {
  try {
    const games = await callServer("/games");
    renderGames(games);
  } catch (error) {
    gamesList.innerHTML = `<li class="error">${error.message}</li>`;
  }
}

if (state.token) {
  Promise.all([refreshProfile(), refreshGames()]).catch(() => {
    setToken(null);
  });
}
