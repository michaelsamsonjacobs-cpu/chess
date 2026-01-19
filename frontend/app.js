const AUTH_STORAGE_KEY = 'chessguard_token';

const state = {
  token: sessionStorage.getItem(AUTH_STORAGE_KEY),
  connected: false,
  lichessUsername: null,
  games: [],
  reports: [],
};

let dashboardPollingInterval = null;
let currentBatchId = null;
let currentBatchPlatform = null;
let currentBatchUsername = null;
let searchTimeout = null;
let tokenCheckInterval = null;

// ============================================
// Stripe Checkout Integration
// ============================================
// NOTE: Replace with your actual Stripe publishable key and price ID
const STRIPE_PUBLISHABLE_KEY = 'pk_test_REPLACE_WITH_YOUR_KEY';
const STRIPE_PRICE_ID = 'price_9p95_monthly'; // Create this in Stripe Dashboard

/**
 * Start Stripe Checkout for $9.95/mo subscription with 3-day trial
 */
window.startStripeCheckout = async function () {
  // For now, redirect to sign-in first (user must authenticate before subscribing)
  const token = sessionStorage.getItem('chessguard_token');
  if (!token) {
    // Scroll to sign-in section
    document.querySelector('.sign-in-section')?.scrollIntoView({ behavior: 'smooth' });
    const loginStatus = document.getElementById('login-status');
    if (loginStatus) {
      loginStatus.textContent = 'Please sign in first to start your free trial.';
      loginStatus.classList.add('info');
    }
    return;
  }

  // When you have Stripe set up, uncomment this:
  /*
  try {
    const response = await fetch('/api/stripe/create-checkout-session', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        priceId: STRIPE_PRICE_ID,
        trialDays: 3
      })
    });
    const { sessionId } = await response.json();
    const stripe = Stripe(STRIPE_PUBLISHABLE_KEY);
    await stripe.redirectToCheckout({ sessionId });
  } catch (error) {
    console.error('Stripe checkout failed:', error);
    alert('Payment system is temporarily unavailable. Please try again later.');
  }
  */

  // Temporary: Just scroll to sign-in
  document.querySelector('.sign-in-section')?.scrollIntoView({ behavior: 'smooth' });
};

// ============================================
// Session Management
// ============================================

/**
 * Check if JWT token is expired by decoding the payload
 */
function isTokenExpired(token) {
  if (!token) return true;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    const exp = payload.exp * 1000; // Convert to milliseconds
    const now = Date.now();
    // Consider expired if less than 5 minutes remaining
    return now >= (exp - 5 * 60 * 1000);
  } catch (e) {
    console.warn('Failed to decode token:', e);
    return true;
  }
}

/**
 * Handle session expiration gracefully
 */
function handleSessionExpired(message = 'Your session has expired. Please log in again.') {
  console.log('Session expired, redirecting to login');
  sessionStorage.removeItem(AUTH_STORAGE_KEY);
  state.token = null;

  // Stop any active polling
  if (dashboardPollingInterval) {
    clearInterval(dashboardPollingInterval);
    dashboardPollingInterval = null;
  }
  if (tokenCheckInterval) {
    clearInterval(tokenCheckInterval);
    tokenCheckInterval = null;
  }

  updateVisibility();

  // Show friendly message on login screen
  const loginStatus = document.getElementById('login-status');
  if (loginStatus) {
    loginStatus.textContent = message;
    loginStatus.classList.add('error');
  }
}

/**
 * Start periodic token expiration check
 */
function startTokenExpiryCheck() {
  if (tokenCheckInterval) return;

  tokenCheckInterval = setInterval(() => {
    const token = sessionStorage.getItem(AUTH_STORAGE_KEY);
    if (token && isTokenExpired(token)) {
      handleSessionExpired('Your session expired due to inactivity.');
    }
  }, 60000); // Check every minute
}

// ============================================
// Mobile Sidebar Toggle
// ============================================

function initMobileSidebar() {
  const toggle = document.getElementById('mobile-menu-toggle');
  const sidebar = document.querySelector('.sidebar');
  const overlay = document.getElementById('sidebar-overlay');

  if (!toggle || !sidebar) return;

  toggle.addEventListener('click', () => {
    sidebar.classList.toggle('open');
    overlay?.classList.toggle('active');
  });

  overlay?.addEventListener('click', () => {
    sidebar.classList.remove('open');
    overlay.classList.remove('active');
  });

  // Close sidebar when nav item clicked on mobile
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
      if (window.innerWidth <= 768) {
        sidebar.classList.remove('open');
        overlay?.classList.remove('active');
      }
    });
  });
}

// Initialize mobile sidebar on DOM ready
document.addEventListener('DOMContentLoaded', initMobileSidebar);

const elements = {
  appShell: document.getElementById('app-shell'),
  loginLayout: document.getElementById('login-layout'),
  loginForm: document.getElementById('login-form'),
  loginStatus: document.getElementById('login-status'),

  connectSection: document.getElementById('connection'),
  gamesSection: document.getElementById('games'),
  reportsSection: document.getElementById('reports'),
  dashboardSection: document.getElementById('dashboard-section'),
  auditSection: document.getElementById('audit-search'),
  pricingSection: document.getElementById('pricing-section'),

  connectForm: document.getElementById('connect-form'),
  username: document.getElementById('lichess-username'),
  token: document.getElementById('lichess-token'),
  connectStatus: document.getElementById('connect-status'),
  maxGames: document.getElementById('max-games'),
  syncButton: document.getElementById('sync-games'),
  gamesStatus: document.getElementById('games-status'),
  gamesTableBody: document.querySelector('#games-table tbody'),

  reportForm: document.getElementById('report-form'),
  reportStatus: document.getElementById('report-status'),
  reportsList: document.getElementById('reports-list'),

  auditForm: document.getElementById('audit-form'),
  auditStatus: document.getElementById('audit-status'),
  auditResults: document.getElementById('audit-results'),
  auditTableBody: document.querySelector('#audit-table tbody'),
  analyzeAllBtn: document.getElementById('analyze-all-btn'),

  logoutBtns: document.querySelectorAll('.logout-btn'),
  navItems: document.querySelectorAll('.nav-item'),
};

// Sidebar Navigation Logic
elements.navItems.forEach(item => {
  item.addEventListener('click', (e) => {
    e.preventDefault();
    const targetSectionId = item.getAttribute('data-section');
    switchSection(targetSectionId);
  });
});

function switchSection(sectionId) {
  // Hide all sections
  document.querySelectorAll('.content-section').forEach(s => s.style.display = 'none');
  // Deactivate all nav items
  elements.navItems.forEach(i => i.classList.remove('active'));

  // Show target
  const target = document.getElementById(sectionId);
  if (target) {
    target.style.display = 'block';
    // Active nav item
    const navItem = document.querySelector(`.nav-item[data-section="${sectionId}"]`);
    if (navItem) navItem.classList.add('active');
  }

  // Auto-refresh dashboard if entering it
  if (sectionId === 'dashboard-section') loadDashboard();
}

// Logout behavior
elements.logoutBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    sessionStorage.removeItem(AUTH_STORAGE_KEY);
    state.token = null;
    updateVisibility();
    resetIntegrationState();
  });
});

function setStatus(element, message, type = 'info') {
  element.textContent = message || '';
  element.classList.remove('error', 'success');
  if (type === 'error') {
    element.classList.add('error');
  } else if (type === 'success') {
    element.classList.add('success');
  }
}

function syncToken() {
  const token = sessionStorage.getItem(AUTH_STORAGE_KEY);
  if (token !== state.token) {
    state.token = token;
  }
  return state.token;
}

async function callApi(path, options = {}) {
  if (path === 'login') {
    const headers = Object.assign({}, options.headers || {});
    // Login ignores auth header
    headers['Content-Type'] = 'application/x-www-form-urlencoded';
    const body = new URLSearchParams(options.body).toString();
    const fetchOptions = {
      method: 'POST',
      headers,
      body
    };
    const response = await fetch('/login', fetchOptions); // Root endpoint
    if (!response.ok) throw new Error('Login failed');
    return await response.json();
  }

  const token = syncToken();
  if (!token) {
    throw new Error('Sign in through the Chess Observer client before performing this action.');
  }
  const headers = Object.assign(
    {
      Authorization: `Bearer ${token}`,
    },
    options.headers || {}
  );
  const fetchOptions = {
    method: options.method || 'GET',
    headers,
  };
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    fetchOptions.body = JSON.stringify(options.body);
  }

  let resultPath = path;
  if (!path.startsWith('/')) {
    resultPath = `/api/lichess/${path}`;
  }
  const response = await fetch(resultPath, fetchOptions);
  let data = null;
  const contentType = response.headers.get('Content-Type') || '';
  if (contentType.includes('application/json')) {
    data = await response.json();
  } else {
    data = await response.text();
  }
  if (!response.ok) {
    // Handle 401 Unauthorized - session expired or invalid token
    if (response.status === 401) {
      handleSessionExpired('Invalid or expired session. Please log in again.');
      throw new Error('Session expired');
    }
    const errorMessage = data?.detail || data || 'Request failed';
    throw new Error(errorMessage);
  }
  return data;
}

function formatTimestamp(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '—';
  }
  return date.toLocaleString();
}

function updateState(snapshot) {
  if (!snapshot) return;
  state.connected = snapshot.connected;
  state.lichessUsername = snapshot.lichessUsername;
  state.games = snapshot.games || [];
  state.reports = snapshot.reports || [];

  elements.username.value = snapshot.lichessUsername || '';
  if (state.connected) {
    setStatus(
      elements.connectStatus,
      `Connected to Lichess as ${snapshot.lichessUsername}.`,
      'success'
    );
  } else {
    setStatus(elements.connectStatus, 'Lichess account not linked yet.');
  }

  renderGames();
  renderReports();
}

function renderGames() {
  const rows = state.games.map((game) => {
    const link = document.createElement('a');
    link.href = game.url;
    link.textContent = game.id;
    link.target = '_blank';
    link.rel = 'noopener';

    const resultLabel = (() => {
      if (!game.winner) return '½–½';
      if (game.winner === 'white') return '1–0';
      if (game.winner === 'black') return '0–1';
      return game.status || '—';
    })();

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td></td>
      <td>${game.white || '—'}</td>
      <td>${game.black || '—'}</td>
      <td>${resultLabel}</td>
      <td>${game.speed || '—'}</td>
      <td>${game.moves ?? '—'}</td>
      <td>
        <button class="analyze-btn" data-id="${game.id}">Analyze</button>
      </td>
    `;
    const btn = tr.querySelector('.analyze-btn');
    btn.onclick = () => handleAnalyze(game.id);

    tr.cells[0].appendChild(link);
    return tr;
  });

  elements.gamesTableBody.replaceChildren(...rows);
  if (rows.length === 0) {
    const emptyRow = document.createElement('tr');
    emptyRow.innerHTML = '<td colspan="6">No games synchronised yet.</td>';
    elements.gamesTableBody.appendChild(emptyRow);
  }
}

function renderReports() {
  if (!state.reports.length) {
    elements.reportsList.innerHTML = '<p>No reports submitted yet.</p>';
    return;
  }

  const items = state.reports.map((report) => {
    const div = document.createElement('div');
    div.className = 'report-item';
    div.innerHTML = `
      <h3>Game ${report.gameId}</h3>
      <p><strong>Player:</strong> ${report.playerId}</p>
      <p><strong>Reason:</strong> ${report.reason}</p>
      <p><strong>Status:</strong> ${report.statusCode}</p>
      <p>${report.description || 'No additional notes provided.'}</p>
      <small>Submitted ${formatTimestamp(report.createdAt)}</small>
    `;
    return div;
  });

  elements.reportsList.replaceChildren(...items);
}

function resetIntegrationState() {
  state.connected = false;
  state.lichessUsername = null;
  state.games = [];
  state.reports = [];
  elements.username.value = '';
  elements.token.value = '';
  renderGames();
  renderReports();
  setStatus(
    elements.connectStatus,
    'Sign in via the Chess Observer client to manage your Lichess connection.',
    'error'
  );
  setStatus(elements.gamesStatus, '');
  setStatus(elements.reportStatus, '');
}

async function refreshState() {
  if (!syncToken()) {
    resetIntegrationState();
    return;
  }
  try {
    const snapshot = await callApi('state');
    updateState(snapshot);
  } catch (error) {
    console.error('Failed to refresh state', error);
    setStatus(elements.connectStatus, error.message || 'Unable to load account state.', 'error');
  }
}

elements.connectForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!syncToken()) {
    setStatus(
      elements.connectStatus,
      'Sign in through the Chess Observer client before linking your Lichess account.',
      'error'
    );
    return;
  }

  try {
    const payload = {
      username: elements.username.value.trim(),
      accessToken: elements.token.value.trim(),
    };
    if (!payload.username || !payload.accessToken) {
      throw new Error('Both username and token are required.');
    }
    const snapshot = await callApi('connect', {
      method: 'POST',
      body: payload,
    });
    elements.token.value = '';
    updateState(snapshot);
  } catch (error) {
    console.error('Connect failed', error);
    setStatus(elements.connectStatus, error.message, 'error');
  }
});

async function handleSync() {
  if (!syncToken()) {
    setStatus(
      elements.gamesStatus,
      'Sign in through the Chess Observer client before syncing games.',
      'error'
    );
    return;
  }
  if (!state.connected) {
    setStatus(elements.gamesStatus, 'Connect your Lichess account first.', 'error');
    return;
  }
  try {
    setStatus(elements.gamesStatus, 'Fetching games…');
    const payload = {
      maxGames: Number.parseInt(elements.maxGames.value, 10) || 20,
    };
    const response = await callApi('sync', {
      method: 'POST',
      body: payload,
    });
    updateState({
      connected: state.connected,
      lichessUsername: state.lichessUsername,
      games: response.games,
      reports: state.reports,
    });
    setStatus(
      elements.gamesStatus,
      `Fetched ${response.count} games. Last sync: ${formatTimestamp(response.lastSync)}`,
      'success'
    );
  } catch (error) {
    console.error('Sync failed', error);
    setStatus(elements.gamesStatus, error.message, 'error');
  }
}

elements.syncButton.addEventListener('click', handleSync);

elements.reportForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!syncToken()) {
    setStatus(
      elements.reportStatus,
      'Sign in through the Chess Observer client before submitting reports.',
      'error'
    );
    return;
  }
  if (!state.connected) {
    setStatus(elements.reportStatus, 'Connect your Lichess account first.', 'error');
    return;
  }
  try {
    setStatus(elements.reportStatus, 'Submitting report…');
    const body = {
      gameId: document.getElementById('report-game').value.trim(),
      playerId: document.getElementById('report-player').value.trim(),
      reason: document.getElementById('report-reason').value.trim() || 'cheat',
      description: document.getElementById('report-notes').value.trim(),
    };
    if (!body.gameId || !body.playerId) {
      throw new Error('Game ID and player username are required.');
    }
    const response = await callApi('report', {
      method: 'POST',
      body,
    });
    state.reports = [...state.reports, response.report];
    renderReports();
    setStatus(elements.reportStatus, 'Report submitted to Lichess.', 'success');
    elements.reportForm.reset();
  } catch (error) {
    console.error('Report failed', error);
    setStatus(elements.reportStatus, error.message, 'error');
  }
});

elements.loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value.trim();

  try {
    setStatus(elements.loginStatus, 'Logging in...');
    const data = await callApi('login', { body: { username, password } });
    sessionStorage.setItem(AUTH_STORAGE_KEY, data.access_token);
    state.token = data.access_token;
    setStatus(elements.loginStatus, '');

    // Start periodic token expiry check
    startTokenExpiryCheck();

    // Switch to dashboard view
    updateVisibility();
    refreshState();
  } catch (error) {
    console.error(error);
    setStatus(elements.loginStatus, error.message, 'error');
  }
});

elements.auditForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const platform = document.getElementById('audit-platform').value;
  const username = document.getElementById('audit-username').value.trim();

  if (!username) return;

  // Reset previous search state
  const progressContainer = document.getElementById('batch-progress');
  if (progressContainer) progressContainer.style.display = 'none';
  const existingReport = document.querySelector('.investigation-report');
  if (existingReport) existingReport.remove();

  setStatus(elements.auditStatus, `Checking ${platform} account status for ${username}...`);
  elements.auditResults.style.display = 'none';
  elements.auditTableBody.innerHTML = '';

  // Remove any existing status banner
  const existingBanner = document.getElementById('player-status-banner');
  if (existingBanner) existingBanner.remove();

  try {
    // First, check player ban/TOS violation status
    let playerStatus = null;
    try {
      const statusUrl = platform === 'lichess'
        ? `/api/audit/lichess/${username}/status`
        : `/api/audit/chesscom/${username}/status`;
      const statusResponse = await fetch(statusUrl);
      if (statusResponse.ok) {
        playerStatus = await statusResponse.json();
      }
    } catch (e) {
      console.warn('Could not fetch player status:', e);
    }

    // Display player status banner
    if (playerStatus) {
      const bannerHtml = playerStatus.is_cheater_marked
        ? `<div id="player-status-banner" style="background: #dc3545; color: white; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
             <h4 style="margin: 0 0 10px 0;">⚠️ CONFIRMED CHEATER - Account Marked for TOS Violation</h4>
             <p style="margin: 0;">This account has been flagged by ${playerStatus.platform} for fair play violations. Games from this player are <strong>HIGH VALUE</strong> for training cheat detection models.</p>
           </div>`
        : (playerStatus.account_closed
          ? `<div id="player-status-banner" style="background: #ffc107; color: #000; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
               <h4 style="margin: 0 0 10px 0;">⚠️ Account Closed</h4>
               <p style="margin: 0;">This account has been closed. Reason: ${playerStatus.status || 'Unknown'}</p>
             </div>`
          : `<div id="player-status-banner" style="background: #28a745; color: white; padding: 10px; border-radius: 8px; margin-bottom: 15px;">
               <strong>✓ Account Status: Active</strong> - No fair play violations detected.
             </div>`
        );
      elements.auditForm.insertAdjacentHTML('afterend', bannerHtml);
    }

    // Fetch games
    let games = [];
    setStatus(elements.auditStatus, `Fetching games for ${username}...`);

    if (platform === 'chesscom') {
      const response = await fetch(`/api/audit/chesscom/${username}/games`);
      if (!response.ok) throw new Error('Failed to fetch Chess.com games');
      games = await response.json();
    } else if (platform === 'lichess') {
      const response = await fetch(`/api/audit/lichess/${username}/games?max_games=50`);
      if (!response.ok) throw new Error('Failed to fetch Lichess games');
      games = await response.json();
    }

    renderAuditGames(games, platform);

    const statusSuffix = playerStatus?.is_cheater_marked ? ' 🚨 CHEATER MARKED' : '';
    setStatus(elements.auditStatus, `Found ${games.length} games.${statusSuffix}`);
    elements.auditResults.style.display = 'block';

    // Show "Analyze All" button if games found
    const analyzeAllBtn = document.getElementById('analyze-all-btn');
    if (games.length > 0 && analyzeAllBtn) {
      analyzeAllBtn.style.display = 'inline-block';
    }

  } catch (error) {
    console.error(error);
    setStatus(elements.auditStatus, error.message, 'error');
  }
});

function renderAuditGames(games, platform = 'chesscom') {
  if (!games.length) {
    elements.auditTableBody.innerHTML = '<tr><td colspan="6">No games found.</td></tr>';
    return;
  }
  const platformLabel = platform === 'lichess' ? 'Lichess' : 'Chess.com';
  elements.auditTableBody.innerHTML = games.map(g => `
        <tr>
            <td>${platformLabel}</td>
            <td>${g.white.username} (${g.white.rating})</td>
            <td>${g.black.username} (${g.black.rating})</td>
            <td><a href="${g.url}" target="_blank">View</a></td>
            <td>${g.white.result} / ${g.black.result}</td>
            <td>
                <button class="audit-analyze-btn" data-id="${g.url.split('/').pop()}" data-pgn="${encodeURIComponent(g.pgn)}">Analyze</button>
            </td>
        </tr>
    `).join('');

  // Attach listeners
  const rows = elements.auditTableBody.querySelectorAll('tr');
  rows.forEach(row => {
    const btn = row.querySelector('.audit-analyze-btn');
    if (btn) {
      btn.onclick = () => {
        const pgn = decodeURIComponent(btn.dataset.pgn);
        // Use URL ID or construct one
        handleAnalyze(btn.dataset.id, 'chesscom', pgn);
      };
    }
  });
}

function updateVisibility() {
  const token = syncToken();
  if (token) {
    elements.loginLayout.style.display = 'none';
    elements.appShell.style.display = 'grid';
    // Default to dashboard
    switchSection('dashboard-section');
  } else {
    elements.loginLayout.style.display = 'flex';
    elements.appShell.style.display = 'none';
  }
}

// Initial check
updateVisibility();

// Check for token in URL (OAuth Callback)
const urlParams = new URL(window.location.href);
const tokenFromUrl = urlParams.searchParams.get('token');
if (tokenFromUrl) {
  sessionStorage.setItem(AUTH_STORAGE_KEY, tokenFromUrl);
  state.token = tokenFromUrl;
  // Clean URL
  window.history.replaceState({}, document.title, "/");
  updateVisibility();
  refreshState();
}

if (state.token) {
  startTokenExpiryCheck();
  refreshState();
} else {
  resetIntegrationState();
}

window.addEventListener('storage', (event) => {
  if (event.key === AUTH_STORAGE_KEY) {
    state.token = sessionStorage.getItem(AUTH_STORAGE_KEY);
    updateVisibility();
    refreshState();
  }
});

// Load WikiHow Help
async function loadHelp() {
  const container = document.getElementById('help-content');
  if (!container) return;

  if (!container.innerHTML) {
    try {
      const res = await fetch('assets/help.md');
      if (res.ok) {
        const text = await res.text();
        container.innerHTML = marked.parse(text);
      } else {
        container.innerHTML = "<h3>Help Center</h3><p>Loading documentation...</p>";
      }
    } catch (e) {
      container.innerHTML = "<h3>Help Unreachable</h3>";
    }
  }
}
// Preload Help
loadHelp();

async function handleAnalyze(id, source = 'lichess', pgn = null) {
  try {
    setStatus(elements.gamesStatus, `Starting analysis for ${id}...`);

    const body = {
      lichess_id: String(id),
      force: true,
      source: source
    };
    if (pgn) body.pgn = pgn;

    console.log("Starting analysis with:", body);

    const game = await callApi('/api/games/import', {
      method: 'POST',
      body: body
    });

    // Show results section
    showAnalysisResults(game);
    setStatus(elements.gamesStatus, `Analysis started for ${id}.`, 'success');

  } catch (error) {
    console.error('Analysis failed', error);
    setStatus(elements.gamesStatus, `Analysis failed: ${error.message}`, 'error');
  }
}

function showAnalysisResults(game) {
  // Simple alert-like display or append to a new section.
  // Let's create a visual representation if we can.
  // For now, let's log it and maybe alert.
  console.log("Analysis Result:", game);

  // Create detailed view
  const metrics = game.investigation?.details;
  let detailsHtml = '';

  if (metrics) {
    detailsHtml = `
            <div class="analysis-card success" style="margin-top: 20px; padding: 15px; background: #1a1a1a; border: 1px solid #333; border-radius: 4px;">
                <h3 style="margin-top:0;">Analysis Results: ${game.lichess_id}</h3>
                <div class="metrics-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px;">
                    <div class="metric"><strong>Suspicion Score:</strong> ${metrics.suspicion_score}</div>
                    <div class="metric"><strong>ToM Score:</strong> ${metrics.tom_score}</div>
                    <div class="metric"><strong>Tension:</strong> ${metrics.tension_complexity}</div>
                    <div class="metric"><strong>Sabotage:</strong> ${metrics.sabotage_score}</div>
                    <div class="metric"><strong>Engine Match (#1):</strong> ${(metrics.engine_agreement * 100).toFixed(1)}%</div>
                    <div class="metric"><strong>Top-2 Match:</strong> ${(metrics.top2_engine_agreement * 100).toFixed(1)}%</div>
                </div>
                <p style="margin-bottom:0; margin-top:10px;"><strong>Status:</strong> ${game.analysis_status}</p>
            </div>
        `;
  } else {
    detailsHtml = `<div class="analysis-card" style="margin-top: 20px; padding: 15px; border: 1px solid #333;"><p>Analysis queued. Check back shortly.</p></div>`;
  }

  // Insert into DOM - maybe above the table?
  const existing = document.getElementById('analysis-display');
  if (existing) existing.remove();

  const container = document.createElement('div');
  container.id = 'analysis-display';
  container.innerHTML = detailsHtml;
  // Insert after table wrapper
  const wrapper = elements.gamesSection.querySelector('.table-wrapper');
  wrapper.insertAdjacentElement('afterend', container);

  // Re-fetch after 3 seconds if queued
  if (game.analysis_status === 'queued' || game.analysis_status === 'analyzing') {
    setTimeout(async () => {
      const updated = await callApi(`/api/analyses/${game.id}`);
      showAnalysisResults(updated);
    }, 3000);
  }
}

// ============================================
// Batch Analysis ("Analyze All" Functionality)
// ============================================

if (elements.analyzeAllBtn) {
  elements.analyzeAllBtn.addEventListener('click', async () => {
    const platform = document.getElementById('audit-platform').value;
    const username = document.getElementById('audit-username').value.trim();
    const timeframe = document.getElementById('audit-timeframe').value;

    if (!username) {
      setStatus(elements.auditStatus, 'Please enter a username first.', 'error');
      return;
    }

    elements.analyzeAllBtn.disabled = true;
    elements.analyzeAllBtn.textContent = 'Starting...';
    setStatus(elements.auditStatus, `Starting batch analysis for ${username} (${timeframe})...`);

    // Show progress bar immediately
    const progressContainer = document.getElementById('batch-progress');
    const progressLabel = document.getElementById('progress-label');
    const progressPercentage = document.getElementById('progress-percentage');
    const progressFill = document.getElementById('progress-fill');
    const progressCurrent = document.getElementById('progress-current');

    if (progressContainer) {
      progressContainer.style.display = 'block';
      if (progressLabel) progressLabel.textContent = `Analyzing ${username}...`;
      if (progressPercentage) progressPercentage.textContent = '0%';
      if (progressFill) progressFill.style.width = '0%';
      if (progressCurrent) progressCurrent.textContent = 'Starting analysis...';
    }

    try {
      const batch = await callApi('/api/batch-analyze', {
        method: 'POST',
        body: { source: platform, username, timeframe }
      });

      currentBatchId = batch.id;
      currentBatchPlatform = platform;
      currentBatchUsername = username;
      setStatus(elements.auditStatus, `Batch analysis started (ID: ${batch.id}). Analyzing games...`, 'success');

      // Re-enable button for concurrent searches
      elements.analyzeAllBtn.disabled = false;
      currentBatchPlatform = platform;
      currentBatchUsername = username;

      // Start polling for progress
      pollBatchProgress(currentBatchId);

    } catch (error) {
      console.error(error);
      setStatus(elements.auditStatus, error.message, 'error');
      elements.analyzeAllBtn.disabled = false;
      elements.analyzeAllBtn.innerHTML = 'Analyze All Games';
    }
  });

  // ============================================
  // Agent Console Logic
  // ============================================

  const agentElements = {
    section: document.getElementById('agent-console'),
    accountsList: document.getElementById('accounts-list'),
    connectForm: document.getElementById('agent-connect-form'),
    connectStatus: document.getElementById('agent-connect-status'),
    syncBtn: document.getElementById('trigger-sync-btn'),
    reportsTable: document.querySelector('#agent-reports-table tbody'),
    jobsList: document.getElementById('sync-jobs-list'),
    modal: document.getElementById('report-modal'),
    modalBody: document.getElementById('report-modal-body'),
    closeModal: document.querySelector('.close-modal'),
  };

  // Auto-load agent data when section is active
  function loadAgentConsole() {
    fetchAccounts();
    fetchAgentReports();
    fetchSyncJobs();
  }

  // Hook into switchSection to load data
  const originalSwitchSection = switchSection;
  switchSection = function (sectionId) {
    originalSwitchSection(sectionId);
    if (sectionId === 'agent-console') {
      loadAgentConsole();
    }
  };

  async function fetchAccounts() {
    try {
      const accounts = await callApi('/api/agents/accounts');
      renderAccounts(accounts);
    } catch (e) {
      agentElements.accountsList.innerHTML = '<p class="error">Failed to load accounts</p>';
    }
  }

  function renderAccounts(accounts) {
    if (accounts.length === 0) {
      agentElements.accountsList.innerHTML = '<p class="muted">No accounts linked yet.</p>';
      return;
    }

    agentElements.accountsList.innerHTML = accounts.map(acc => `
    <div class="account-item" style="display: flex; justify-content: space-between; align-items: center; padding: 10px; border-bottom: 1px solid #eee;">
      <div>
        <span class="platform-badge ${acc.platform}">${acc.platform}</span>
        <strong>${acc.username}</strong>
        <div style="font-size: 0.85em; color: #666;">
          ${acc.last_synced_at ? 'Last Sync: ' + formatTimestamp(acc.last_synced_at) : 'Not synced yet'}
        </div>
      </div>
      <button class="small-btn danger" onclick="disconnectAgentAccount(${acc.id})">×</button>
    </div>
  `).join('');
  }

  async function fetchAgentReports() {
    try {
      const reports = await callApi('/api/agents/reports?min_score=50');
      renderAgentReports(reports);
    } catch (e) {
      console.error(e);
    }
  }

  function renderAgentReports(reports) {
    if (reports.length === 0) {
      agentElements.reportsTable.innerHTML = '<tr><td colspan="5">No active alerts. Clean record!</td></tr>';
      return;
    }

    agentElements.reportsTable.innerHTML = reports.map(r => `
    <tr>
      <td>${r.flagged_player}</td>
      <td>${r.platform}</td>
      <td><span class="risk-badge ${r.risk_level.toLowerCase()}">${r.risk_level}</span></td>
      <td>${r.ensemble_score}</td>
      <td>
        <button class="small-btn" onclick="viewAgentReport(${r.id})">View</button>
      </td>
    </tr>
  `).join('');
  }

  async function fetchSyncJobs() {
    try {
      const jobs = await callApi('/api/agents/jobs?limit=5');
      agentElements.jobsList.innerHTML = jobs.map(j => `
            <div class="job-item" style="padding: 5px 0; border-bottom: 1px solid #eee; font-size: 0.9em;">
                <span class="status-dot ${j.status}"></span>
                <strong>${j.status.toUpperCase()}</strong>
                <span>Fetched: ${j.games_fetched}</span>
                <span style="color: #666; float: right;">${formatTimestamp(j.created_at)}</span>
            </div>
        `).join('');
    } catch (e) { console.warn(e); }
  }

  agentElements.connectForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const data = {
      platform: formData.get('platform'),
      username: formData.get('username'),
      access_token: formData.get('token')
    };

    try {
      setStatus(agentElements.connectStatus, 'Linking...');
      await callApi('/api/agents/accounts', { method: 'POST', body: data });
      setStatus(agentElements.connectStatus, 'Linked successfully!', 'success');
      e.target.reset();
      fetchAccounts();
    } catch (err) {
      setStatus(agentElements.connectStatus, err.message, 'error');
    }
  });

  agentElements.syncBtn.addEventListener('click', async () => {
    try {
      agentElements.syncBtn.disabled = true;
      agentElements.syncBtn.textContent = 'Syncing...';
      await callApi('/api/agents/sync/now', { method: 'POST' });
      setTimeout(() => {
        agentElements.syncBtn.disabled = false;
        agentElements.syncBtn.textContent = '🔄 Sync All Now';
        fetchSyncJobs();
      }, 2000);
    } catch (e) {
      alert('Sync failed to start: ' + e.message);
      agentElements.syncBtn.disabled = false;
    }
  });

  // Global scope functions for HTML onclick
  window.disconnectAgentAccount = async (id) => {
    if (!confirm('Disconnect this account?')) return;
    try {
      await callApi(`/api/agents/accounts/${id}`, { method: 'DELETE' });
      fetchAccounts();
    } catch (e) { alert(e.message); }
  };

  window.viewAgentReport = async (id) => {
    // Find report in state or fetch? We rendered from fetch, so let's refetch list or better yet, pass data? 
    // For simplicity, just fetch lists again or store global
    const reports = await callApi(`/api/agents/reports`);
    const report = reports.find(r => r.id === id);
    if (!report) return;

    agentElements.modalBody.innerHTML = `
    <h2>Analysis Report: ${report.flagged_player}</h2>
    <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0;">
      <h3 class="risk-${report.risk_level.toLowerCase()}">RISK LEVEL: ${report.risk_level} (${report.ensemble_score}/100)</h3>
      <div class="explanation-text" style="line-height: 1.6; font-size: 1.1em;">
        ${marked.parse(report.summary)} 
      </div>
    </div>
    <div style="text-align: right;">
      <button class="secondary-btn" onclick="document.getElementById('report-modal').style.display='none'">Close</button>
    </div>
  `;
    // Assuming 'marked' library is available or just use textContent if not
    if (typeof marked === 'undefined') {
      agentElements.modalBody.querySelector('.explanation-text').textContent = report.summary;
    }

    agentElements.modal.style.display = 'block';
  };

  if (agentElements.closeModal) {
    agentElements.closeModal.onclick = () => agentElements.modal.style.display = 'none';
  }

  window.onclick = (event) => {
    if (event.target == agentElements.modal) {
      agentElements.modal.style.display = "none";
    }
  };
}

async function pollBatchStatus(batchId) {
  const progressContainer = document.getElementById('batch-progress');
  const progressFill = document.getElementById('progress-fill');
  const progressPercentage = document.getElementById('progress-percentage');
  const progressCurrent = document.getElementById('progress-current');
  const progressLabel = document.getElementById('progress-label');

  try {
    const response = await fetch(`/api/batch-analyze/${batchId}`);
    if (!response.ok) throw new Error('Failed to get batch status');
    const batch = await response.json();

    // Show progress container
    if (progressContainer) {
      progressContainer.style.display = 'block';
    }

    // Calculate progress percentage
    const total = batch.total_games || 0;
    const analyzed = batch.analyzed_count || 0;
    const rawPercent = total > 0 ? (analyzed / total) * 100 : 0;
    // Show at least 1% if analysis has started, use 1 decimal for precision
    const percent = analyzed > 0 ? Math.max(0.1, rawPercent) : 0;
    const displayPercent = rawPercent < 1 ? rawPercent.toFixed(2) : Math.round(rawPercent);

    // Update progress bar
    if (progressFill) progressFill.style.width = `${Math.max(percent, 1)}%`;
    if (progressPercentage) progressPercentage.textContent = `${displayPercent}%`;
    if (progressCurrent) progressCurrent.textContent = `Game ${analyzed} of ${total.toLocaleString()}`;
    if (progressLabel) progressLabel.textContent = `Analyzing ${currentBatchUsername}...`;

    // Update text status with live results
    const flaggedEmoji = batch.flagged_count > 0 ? '🚩' : '🏳️';
    const suspicionPercent = Math.round(batch.avg_suspicion * 100);
    const statusText = `${analyzed}/${total} games analyzed | ${flaggedEmoji} ${batch.flagged_count} flagged | 📊 ${suspicionPercent}% susp`;
    setStatus(elements.auditStatus, statusText);

    // Update label to show more detail
    if (progressLabel) {
      progressLabel.innerHTML = `Analyzing ${currentBatchUsername}... <span class="live-stats">(${flaggedEmoji} ${batch.flagged_count} | 📊 ${suspicionPercent}%)</span>`;
    }

    if (batch.status === 'completed') {
      // Progress complete
      if (progressLabel) progressLabel.textContent = 'Analysis Complete!';
      if (progressPercentage) progressPercentage.textContent = '100%';
      if (progressFill) progressFill.style.width = '100%';

      // Hide progress bar after delay
      setTimeout(() => {
        if (progressContainer) progressContainer.style.display = 'none';
      }, 3000);

      showBatchResults(batch);
      if (elements.analyzeAllBtn) {
        elements.analyzeAllBtn.disabled = false;
        elements.analyzeAllBtn.textContent = 'Analyze All Games';
      }
    } else if (batch.status === 'error') {
      if (progressLabel) progressLabel.textContent = 'Analysis Error';
      setStatus(elements.auditStatus, `Error: ${batch.error_message}`, 'error');
      if (analyzeAllBtn) {
        analyzeAllBtn.disabled = false;
        analyzeAllBtn.textContent = 'Analyze All Games';
      }
      if (progressContainer) progressContainer.style.display = 'none';
    } else {
      // Continue polling
      setTimeout(() => pollBatchStatus(batchId), 2000);
    }
  } catch (error) {
    console.error('Polling error', error);
    if (progressContainer) progressContainer.style.display = 'none';
  }
}

function showBatchResults(batch) {
  const riskColors = {
    'low': '#10b981',
    'medium': '#f59e0b',
    'high': '#f97316',
    'critical': '#ef4444'
  };
  const riskEmojis = { 'low': '✅', 'medium': '⚠️', 'high': '🔶', 'critical': '🚨' };

  const riskColor = riskColors[batch.risk_level] || '#6b7280';
  const riskEmoji = riskEmojis[batch.risk_level] || '❓';
  const suspicionPercent = Math.round(batch.avg_suspicion * 100);

  // Generate human-readable risk explanation
  function generateRiskExplanation(batch) {
    const reasons = [];
    const level = batch.risk_level || 'unknown';
    const susp = batch.avg_suspicion * 100;
    const flaggedPct = batch.total_games > 0 ? (batch.flagged_count / batch.total_games * 100) : 0;

    if (level === 'low') {
      return `<div class="risk-explanation low">
        <h5>✅ Why LOW Risk?</h5>
        <ul>
          <li>Average suspicion score (${susp.toFixed(1)}%) is within normal range</li>
          <li>Only ${batch.flagged_count} of ${batch.total_games} games flagged (${flaggedPct.toFixed(1)}%)</li>
          <li>No statistically improbable patterns detected</li>
        </ul>
        <p class="conclusion">This player's performance appears consistent with human play.</p>
      </div>`;
    } else if (level === 'medium') {
      if (flaggedPct > 1) reasons.push(`${flaggedPct.toFixed(1)}% of games flagged (above typical 0.5%)`);
      if (susp > 15) reasons.push(`Suspicion score ${susp.toFixed(1)}% is elevated`);
      if (batch.longest_win_streak > 8) reasons.push(`Unusually long win streak (${batch.longest_win_streak} games)`);
      return `<div class="risk-explanation medium">
        <h5>⚠️ Why MEDIUM Risk?</h5>
        <ul>${reasons.map(r => `<li>${r}</li>`).join('')}</ul>
        <p class="conclusion">Some indicators warrant attention, but not conclusive. Consider reviewing flagged games.</p>
      </div>`;
    } else if (level === 'high') {
      if (flaggedPct > 5) reasons.push(`<strong>${flaggedPct.toFixed(1)}%</strong> of games flagged (significantly above normal)`);
      if (susp > 40) reasons.push(`High suspicion score: <strong>${susp.toFixed(1)}%</strong>`);
      if (batch.streak_improbability_score > 0.3) reasons.push(`Streak patterns are statistically improbable`);
      if (batch.longest_win_streak > 12) reasons.push(`Extended win streak: ${batch.longest_win_streak} consecutive wins`);
      return `<div class="risk-explanation high">
        <h5>🔶 Why HIGH Risk?</h5>
        <ul>${reasons.map(r => `<li>${r}</li>`).join('')}</ul>
        <p class="conclusion">Multiple strong indicators of potential unfair play. Detailed review recommended.</p>
      </div>`;
    } else if (level === 'critical') {
      if (flaggedPct > 10) reasons.push(`<strong>${flaggedPct.toFixed(1)}%</strong> of games flagged - extremely high rate`);
      if (susp > 60) reasons.push(`Suspicion score ${susp.toFixed(1)}% indicates likely engine assistance`);
      if (batch.max_streak_improbability > 10000) reasons.push(`Win streak probability: 1 in ${formatImprobability(batch.max_streak_improbability)}`);
      reasons.push(`Combined signals strongly suggest artificial play enhancement`);
      return `<div class="risk-explanation critical">
        <h5>🚨 Why CRITICAL Risk?</h5>
        <ul>${reasons.map(r => `<li>${r}</li>`).join('')}</ul>
        <p class="conclusion"><strong>High confidence of unfair play.</strong> Consider reporting to platform.</p>
      </div>`;
    }
    return '';
  }

  // Generate metric contribution bars
  function generateMetricBars(batch) {
    const metrics = [
      { name: 'Suspicion Score', value: batch.avg_suspicion * 100, max: 100, color: riskColor, icon: '📊' },
      { name: 'Flagged Games', value: batch.total_games > 0 ? (batch.flagged_count / batch.total_games * 100) : 0, max: 20, color: '#ef4444', icon: '🚩' },
      { name: 'Streak Suspicion', value: (batch.streak_improbability_score || 0) * 100, max: 100, color: '#f97316', icon: '🔥' },
    ];

    return metrics.map(m => {
      const width = Math.min((m.value / m.max) * 100, 100);
      const displayVal = m.value.toFixed(1);
      return `
        <div class="metric-bar-row">
          <span class="metric-bar-label">${m.icon} ${m.name}</span>
          <div class="metric-bar-container">
            <div class="metric-bar-fill" style="width: ${width}%; background: ${m.color};"></div>
            <span class="metric-bar-value">${displayVal}%</span>
          </div>
        </div>
      `;
    }).join('');
  }

  // Helper to format improbability nicely
  function formatImprobability(value) {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
    if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
    return Math.round(value).toLocaleString();
  }

  // X.com share URL
  const shareText = `🔍 Chess Observer Analysis: ${batch.username} (${batch.source})

${riskEmoji} Risk Level: ${batch.risk_level?.toUpperCase() || 'N/A'}
📊 Suspicion: ${suspicionPercent}%
🚩 Flagged: ${batch.flagged_count}/${batch.total_games} games

#Chess Observer #FairPlay #Chess`;

  const shareUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}`;

  // Platform-specific action buttons
  const reportButtonHtml = batch.source === 'lichess'
    ? `<button onclick="autoReportLichess(${batch.id})" class="action-btn danger">🚨 Auto-Report to Lichess</button>`
    : `<button onclick="generateChessComEmail(${batch.id}, '${batch.username}')" class="action-btn info">📧 Generate Report Email</button>`;

  const resultsHtml = `
    <div class="investigation-report" style="margin-top: 1.5rem;">
      <!-- Header with Share -->
      <div class="report-header">
        <h3>🔍 Investigation Report</h3>
        <a href="${shareUrl}" target="_blank" class="share-x-btn">
          <span>Share on</span>
          <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
        </a>
      </div>

      <!-- Player Info -->
      <div class="player-info">
        <span class="player-name">${batch.username}</span>
        <span class="platform-badge ${batch.source}">${batch.source}</span>
        <span class="title-badge" id="title-badge-${batch.id}"></span>
      </div>

      <!-- Risk Gauge -->
      <div class="risk-gauge-container">
        <div class="risk-gauge">
          <div class="risk-gauge-fill" style="width: ${Math.min(suspicionPercent * 2, 100)}%; background: ${riskColor};"></div>
          <div class="risk-gauge-marker" style="left: ${Math.min(suspicionPercent * 2, 100)}%;"></div>
        </div>
        <div class="risk-gauge-labels">
          <span>0% (Clean)</span>
          <span class="risk-value" style="color: ${riskColor};">${suspicionPercent}% ${riskEmoji}</span>
          <span>50%+ (Suspicious)</span>
        </div>
        <div class="risk-level" style="background: ${riskColor}20; border-color: ${riskColor};">
          ${riskEmoji} ${batch.risk_level?.toUpperCase() || 'UNKNOWN'} RISK
        </div>
      </div>

      <!-- NEW: Risk Explanation Section -->
      ${generateRiskExplanation(batch)}

      <!-- NEW: Metrics Breakdown Chart -->
      <div class="metrics-breakdown">
        <h4>📈 Signal Breakdown</h4>
        <div class="metric-bars">
          ${generateMetricBars(batch)}
        </div>
      </div>

      <!-- Expandable Details Section -->
      <div class="expandable-section">
        <div class="expandable-header" onclick="toggleReportDetails(${batch.id})">
          <span>📋 Detailed Statistics</span>
          <span class="expand-icon" id="expand-icon-${batch.id}">▼</span>
        </div>
        <div id="report-details-${batch.id}" class="expandable-content" style="display: none;">
          <!-- Metrics Grid -->
          <div class="metrics-grid">
            <div class="metric-card">
              <span class="metric-label">Games Analyzed</span>
              <span class="metric-value">${batch.analyzed_count}/${batch.total_games}</span>
            </div>
            <div class="metric-card ${batch.flagged_count > 0 ? 'flagged' : ''}">
              <span class="metric-label">Flagged Games</span>
              <span class="metric-value">${batch.flagged_count}</span>
            </div>
            <div class="metric-card">
              <span class="metric-label">Avg Suspicion</span>
              <span class="metric-value">${suspicionPercent}%</span>
            </div>
            <div class="metric-card">
              <span class="metric-label">Reported</span>
              <span class="metric-value">${batch.reported_count}</span>
            </div>
          </div>

          <!-- Streak Analysis Section -->
          ${batch.longest_win_streak > 0 ? `
          <div class="streak-analysis-section">
            <h4>🔥 Streak Analysis</h4>
            <div class="streak-metrics">
              <div class="streak-metric">
                <span class="streak-label">Longest Win Streak</span>
                <span class="streak-value ${batch.longest_win_streak >= 10 ? 'highlight' : ''}">${batch.longest_win_streak} games</span>
              </div>
              <div class="streak-metric">
                <span class="streak-label">Streak Suspicion</span>
                <span class="streak-value ${batch.streak_improbability_score > 0.3 ? 'warning' : ''}">${Math.round((batch.streak_improbability_score || 0) * 100)}%</span>
              </div>
              ${batch.suspicious_streak_count > 0 ? `
              <div class="streak-metric flagged">
                <span class="streak-label">Suspicious Streaks</span>
                <span class="streak-value">${batch.suspicious_streak_count}</span>
              </div>
              ` : ''}
              ${batch.max_streak_improbability > 1000 ? `
              <div class="streak-metric improbable">
                <span class="streak-label">Max Improbability</span>
                <span class="streak-value">1 in ${formatImprobability(batch.max_streak_improbability)}</span>
              </div>
              ` : ''}
            </div>
            ${batch.streak_improbability_score > 0.5 ? `
            <div class="streak-warning">
              ⚠️ Streak analysis detected statistically improbable winning patterns
            </div>
            ` : ''}
          </div>
          ` : ''}

          <!-- Expected Context (title-aware) -->
          <div id="title-context-${batch.id}" class="title-context"></div>
        </div>
      </div>

      <!-- Flagged Games Section -->
      <div class="flagged-section">
        <div class="flagged-header" onclick="toggleFlaggedGames(${batch.id})">
          <h4>🚩 Flagged Games (${batch.flagged_count})</h4>
          <span class="toggle-icon" id="toggle-icon-${batch.id}">▼</span>
        </div>
        <div id="flagged-games-${batch.id}" class="flagged-games-list" style="display: none;"></div>
      </div>

      <!-- Action Buttons -->
      <div class="action-buttons">
        ${reportButtonHtml}
        <button onclick="loadFlaggedGames(${batch.id})" class="action-btn secondary">📋 View Flagged Details</button>
        <a href="${shareUrl}" target="_blank" class="action-btn share">𝕏 Share Results</a>
      </div>

      <!-- Email Draft Area -->
      <div id="email-draft-${batch.id}" class="email-draft"></div>
    </div>
  `;

  // Insert results
  const existingResults = document.querySelector('.investigation-report');
  if (existingResults) existingResults.remove();

  elements.auditResults.insertAdjacentHTML('afterend', resultsHtml);
  setStatus(elements.auditStatus, `Analysis complete! Risk: ${batch.risk_level?.toUpperCase()}`, 'success');

  // Auto-load flagged games if any
  if (batch.flagged_count > 0) {
    loadFlaggedGames(batch.id);
  }
}

// Toggle flagged games visibility
function toggleFlaggedGames(batchId) {
  const container = document.getElementById(`flagged-games-${batchId}`);
  const icon = document.getElementById(`toggle-icon-${batchId}`);
  if (container) {
    const isHidden = container.style.display === 'none';
    container.style.display = isHidden ? 'block' : 'none';
    if (icon) icon.textContent = isHidden ? '▲' : '▼';
  }
}

// Toggle report details visibility
function toggleReportDetails(batchId) {
  const container = document.getElementById(`report-details-${batchId}`);
  const icon = document.getElementById(`expand-icon-${batchId}`);
  if (container) {
    const isHidden = container.style.display === 'none';
    container.style.display = isHidden ? 'block' : 'none';
    if (icon) icon.textContent = isHidden ? '▲' : '▼';
  }
}

// Load and display flagged games with COA-style cards
async function loadFlaggedGames(batchId) {
  const container = document.getElementById(`flagged-games-${batchId}`);
  if (!container) return;

  container.innerHTML = '<p>Loading flagged games...</p>';

  try {
    const response = await fetch(`/api/batch-analyze/${batchId}/games?flagged_only=true`);
    if (!response.ok) throw new Error('Failed to load games');
    const games = await response.json();

    if (games.length === 0) {
      container.innerHTML = '<p style="color: #28a745;">✅ No flagged games found. Account appears clean.</p>';
      return;
    }

    const cardsHtml = games.map(g => createCOACard(g)).join('');
    container.innerHTML = `<h4>Flagged Games (${games.length})</h4>${cardsHtml}`;

  } catch (error) {
    container.innerHTML = `<p style="color: #dc3545;">Error: ${error.message}</p>`;
  }
}

// Create a COA-style card for a flagged game
function createCOACard(game) {
  const suspicionPct = (game.suspicion_score * 100).toFixed(1);
  const enginePct = (game.engine_agreement * 100).toFixed(1);
  const recommendation = game.suspicion_score > 0.7 ? 'REPORT' : (game.suspicion_score > 0.5 ? 'INVESTIGATE' : 'MONITOR');
  const confidence = Math.min(95, Math.round(game.suspicion_score * 100 + 20));

  return `
    <div class="coa-card" data-game-id="${game.game_id}">
      <div class="coa-header">
        <strong>GAME: ${game.lichess_id}</strong>
        <span>${game.white} vs ${game.black}</span>
      </div>
      <div class="coa-info-grid">
        <div><strong>SITUATION:</strong><br>${game.source}, ${game.played_at ? new Date(game.played_at).toLocaleDateString() : 'N/A'}</div>
        <div><strong>RESULT:</strong> ${game.result || 'N/A'}</div>
      </div>
      <div class="coa-findings">
        <strong>KEY FINDINGS:</strong>
        <ul>
          <li>Suspicion Score: <span class="${game.suspicion_score > 0.5 ? 'text-danger' : 'text-success'}">${suspicionPct}%</span></li>
          <li>Engine Agreement: ${enginePct}%</li>
          <li>ToM Score: ${game.tom_score}</li>
          <li>Tension: ${game.tension_complexity}</li>
        </ul>
      </div>
      
      <!-- Move Visualization Toggle -->
      <div class="move-viz-section">
        <button class="move-viz-toggle" onclick="toggleMoveVisualization(${game.game_id})">
          📊 Show Move Analysis
        </button>
        <div id="move-viz-${game.game_id}" class="move-viz-container" style="display: none;"></div>
      </div>
      
      <div class="coa-footer">
        <strong class="recommendation-${recommendation.toLowerCase()}">
          RECOMMENDATION: ${recommendation}
        </strong>
        <span>Confidence: ${confidence}%</span>
      </div>
    </div>
  `;
}

// ============================================
// Move-by-Move Visualization
// ============================================

async function toggleMoveVisualization(gameId) {
  const container = document.getElementById(`move-viz-${gameId}`);
  const button = document.querySelector(`[onclick="toggleMoveVisualization(${gameId})"]`);

  if (!container) return;

  if (container.style.display === 'none') {
    container.style.display = 'block';
    button.textContent = '📊 Hide Move Analysis';

    // Load if not already loaded
    if (!container.dataset.loaded) {
      await renderMoveVisualization(gameId);
      container.dataset.loaded = 'true';
    }
  } else {
    container.style.display = 'none';
    button.textContent = '📊 Show Move Analysis';
  }
}

async function renderMoveVisualization(gameId) {
  const container = document.getElementById(`move-viz-${gameId}`);
  if (!container) return;

  container.innerHTML = '<p class="loading-text">Loading move analysis...</p>';

  try {
    const response = await fetch(`/api/analyses/${gameId}/moves`);
    if (!response.ok) throw new Error('Failed to load move data');
    const data = await response.json();

    if (!data.moves || data.moves.length === 0) {
      container.innerHTML = '<p class="no-data">No move data available</p>';
      return;
    }

    // Build move visualization grid
    const moveHtml = data.moves.map((move, i) => {
      const accuracyPct = Math.round(move.accuracy * 100);
      const colorClass = move.flagged ? 'move-flagged' :
        accuracyPct >= 90 ? 'move-excellent' :
          accuracyPct >= 70 ? 'move-good' :
            accuracyPct >= 50 ? 'move-okay' : 'move-poor';
      const playerClass = move.player === 'white' ? 'move-white' : 'move-black';

      return `
        <div class="move-bar ${colorClass} ${playerClass}" 
             title="Move ${Math.ceil(move.ply / 2)}${move.player === 'black' ? '...' : '.'} ${move.move_san}
Accuracy: ${accuracyPct}%
CP Loss: ${move.cp_loss}
Best: ${move.best_move || 'N/A'}${move.flagged ? '\n⚠️ FLAGGED' : ''}">
          <span class="move-number">${Math.ceil(move.ply / 2)}</span>
          <div class="move-accuracy-bar" style="width: ${accuracyPct}%;"></div>
        </div>
      `;
    }).join('');

    // Calculate stats
    const avgAccuracy = Math.round(data.moves.reduce((sum, m) => sum + m.accuracy, 0) / data.moves.length * 100);
    const flaggedCount = data.moves.filter(m => m.flagged).length;
    const excellentCount = data.moves.filter(m => m.accuracy >= 0.9).length;

    container.innerHTML = `
      <div class="move-viz-header">
        <h4>Move-by-Move Analysis</h4>
        <div class="move-stats">
          <span class="stat">📊 Avg: ${avgAccuracy}%</span>
          <span class="stat">✨ Excellent: ${excellentCount}</span>
          <span class="stat text-danger">🚩 Flagged: ${flaggedCount}</span>
        </div>
      </div>
      <div class="move-legend">
        <span class="legend-item"><span class="legend-color move-excellent"></span>Excellent (90%+)</span>
        <span class="legend-item"><span class="legend-color move-good"></span>Good (70-89%)</span>
        <span class="legend-item"><span class="legend-color move-okay"></span>Okay (50-69%)</span>
        <span class="legend-item"><span class="legend-color move-poor"></span>Poor (&lt;50%)</span>
        <span class="legend-item"><span class="legend-color move-flagged"></span>Flagged</span>
      </div>
      <div class="move-grid">
        ${moveHtml}
      </div>
      <p class="move-legend-hint">Hover over moves for details. Top row is white, bottom is black.</p>
    `;

  } catch (error) {
    console.error('Move visualization error:', error);
    container.innerHTML = `<p class="error-text">Failed to load: ${error.message}</p>`;
  }
}

// Make globally available
window.toggleMoveVisualization = toggleMoveVisualization;
window.renderMoveVisualization = renderMoveVisualization;

// Auto-report flagged games to Lichess
async function autoReportLichess(batchId) {
  if (!confirm('This will submit cheat reports to Lichess for all high-confidence flagged games. Continue?')) {
    return;
  }

  setStatus(elements.auditStatus, 'Submitting reports to Lichess...', 'info');

  try {
    const response = await fetch(`/api/batch-analyze/${batchId}/report-all`, {
      method: 'POST'
    });

    if (!response.ok) throw new Error('Failed to submit reports');
    const result = await response.json();

    setStatus(elements.auditStatus, `Reports submitted! ${result.message || ''}`, 'success');

  } catch (error) {
    setStatus(elements.auditStatus, `Error: ${error.message}`, 'error');
  }
}

// Generate email draft for Chess.com reporting
async function generateChessComEmail(batchId, username) {
  const container = document.getElementById(`email-draft-${batchId}`);
  if (!container) return;

  container.innerHTML = '<p>Generating report email...</p>';

  try {
    const response = await fetch(`/api/batch-analyze/${batchId}/games?flagged_only=true`);
    if (!response.ok) throw new Error('Failed to load games');
    const games = await response.json();

    const batchResponse = await fetch(`/api/batch-analyze/${batchId}`);
    const batch = await batchResponse.json();

    // Generate email content
    const emailSubject = `Fair Play Report: ${username} - Suspicious Activity Detected`;
    const emailBody = generateEmailBody(username, batch, games);

    container.innerHTML = `
      <div style="background: #1a1a1a; border: 1px solid #4ecdc4; border-radius: 8px; padding: 20px; margin-top: 15px;">
        <h4 style="margin-top: 0; color: #4ecdc4;">📧 Chess.com Report Email</h4>
        <p><strong>To:</strong> feedback@chess.com</p>
        <p><strong>Subject:</strong> ${emailSubject}</p>
        <hr style="border-color: #333;">
        <div id="email-body-${batchId}" style="background: #111; padding: 15px; border-radius: 4px; white-space: pre-wrap; font-family: monospace; font-size: 0.85em; max-height: 300px; overflow-y: auto;">${emailBody}</div>
        <div style="margin-top: 15px;">
          <button onclick="copyEmailToClipboard(${batchId})" style="background: #4ecdc4; color: #000; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">
            📋 Copy Email to Clipboard
          </button>
          <a href="mailto:feedback@chess.com?subject=${encodeURIComponent(emailSubject)}&body=${encodeURIComponent(emailBody)}" style="background: #28a745; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; display: inline-block; margin-left: 10px;">
            ✉️ Open in Email Client
          </a>
        </div>
      </div>
    `;

  } catch (error) {
    container.innerHTML = `<p style="color: #dc3545;">Error: ${error.message}</p>`;
  }
}

function generateEmailBody(username, batch, flaggedGames) {
  const gameDetails = flaggedGames.map(g => {
    const suspicionPct = (g.suspicion_score * 100).toFixed(1);
    const enginePct = (g.engine_agreement * 100).toFixed(1);
    return `
Game URL: https://chess.com/game/${g.lichess_id}
Date: ${g.played_at ? new Date(g.played_at).toLocaleDateString() : 'N/A'}
Result: ${g.result || 'N/A'}
Suspicion Score: ${suspicionPct}%
Engine Agreement: ${enginePct}%
ToM Score: ${g.tom_score}
---`;
  }).join('\n');

  return `Dear Chess.com Fair Play Team,

I am submitting this report regarding suspicious activity detected on the account "${username}".

ANALYSIS SUMMARY:
- Total Games Analyzed: ${batch.total_games}
- Flagged Games: ${batch.flagged_count}
- Average Suspicion Score: ${(batch.avg_suspicion * 100).toFixed(1)}%
- Risk Level: ${batch.risk_level?.toUpperCase() || 'N/A'}

FLAGGED GAMES DETAILS:
${gameDetails}

The analysis was performed using Chess Observer, which examines engine correlation, move timing patterns, and Theory of Mind (ToM) metrics to identify potentially computer-assisted play.

Key indicators observed:
- Consistently high engine agreement in complex positions
- Moves exhibiting low visual saliency (uncommon human pattern recognition)
- Statistical anomalies in move quality distribution

I request that your Fair Play team review these games and take appropriate action.

Thank you for your attention to maintaining fair play on Chess.com.

Best regards,
Chess Observer Analysis Report
Generated: ${new Date().toISOString()}`;
}

function copyEmailToClipboard(batchId) {
  const emailBody = document.getElementById(`email-body-${batchId}`);
  if (!emailBody) return;

  navigator.clipboard.writeText(emailBody.textContent).then(() => {
    alert('Email copied to clipboard!');
  }).catch(err => {
    console.error('Failed to copy:', err);
    // Fallback: select text
    const range = document.createRange();
    range.selectNode(emailBody);
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(range);
    document.execCommand('copy');
    alert('Email copied to clipboard!');
  });
}

// Show Analyze All button after successful audit search
const originalRenderAudit = window.renderAuditGames;
if (typeof renderAuditGames === 'function') {
  const _origRender = renderAuditGames;
  window.renderAuditGames = function (games, platform) {
    _origRender(games, platform);
    if (games.length > 0 && analyzeAllBtn) {
      analyzeAllBtn.style.display = 'inline-block';
    }
  };
}

// ============================================
// Stripe Subscription Handler
// ============================================

// Note: In production, you would:
// 1. Create a Stripe account at https://stripe.com
// 2. Get your publishable key from the Stripe Dashboard
// 3. Create a Price in Stripe for $10/month
// 4. Create a backend endpoint to create Checkout Sessions

const STRIPE_PUBLISHABLE_KEY = 'pk_test_YOUR_STRIPE_PUBLISHABLE_KEY'; // Replace with your key
const STRIPE_PRICE_ID = 'price_YOUR_PRICE_ID'; // Replace with your Price ID

async function handleSubscribe() {
  const subscribeBtn = document.getElementById('subscribe-btn');

  // For demo purposes, show a modal explaining setup
  if (STRIPE_PUBLISHABLE_KEY === 'pk_test_YOUR_STRIPE_PUBLISHABLE_KEY') {
    showSubscriptionModal();
    return;
  }

  subscribeBtn.disabled = true;
  subscribeBtn.textContent = 'Loading...';

  try {
    // In production, this would call your backend to create a Checkout Session
    const response = await fetch('/api/subscriptions/create-checkout', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(state.token ? { 'Authorization': `Bearer ${state.token}` } : {})
      },
      body: JSON.stringify({ priceId: STRIPE_PRICE_ID })
    });

    if (!response.ok) throw new Error('Failed to create checkout session');

    const { sessionId, url } = await response.json();

    // Redirect to Stripe Checkout
    window.location.href = url;

  } catch (error) {
    console.error('Subscription error:', error);
    alert('Failed to start subscription. Please try again.');
    subscribeBtn.disabled = false;
    subscribeBtn.textContent = 'Subscribe Now';
  }
}

function showSubscriptionModal() {
  const modalHtml = `
    <div id="subscription-modal" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.8); display: flex; align-items: center; justify-content: center; z-index: 9999;">
      <div style="background: #1a1a25; border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 16px; padding: 2rem; max-width: 500px; margin: 1rem; box-shadow: 0 0 60px rgba(99, 102, 241, 0.3);">
        <h3 style="margin: 0 0 1rem; color: white; font-size: 1.25rem;">🎉 Stripe Integration Ready!</h3>
        <p style="color: #a1a1aa; margin-bottom: 1rem; line-height: 1.6;">
          This platform is ready to accept $10/month subscriptions via Stripe.
        </p>
        <div style="background: #12121a; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
          <p style="color: #6ee7b7; font-size: 0.875rem; margin: 0 0 0.5rem;"><strong>To enable payments:</strong></p>
          <ol style="color: #a1a1aa; font-size: 0.8125rem; margin: 0; padding-left: 1.25rem; line-height: 1.8;">
            <li>Create a <a href="https://stripe.com" target="_blank" style="color: #6366f1;">Stripe account</a></li>
            <li>Create a Product with $10/month pricing</li>
            <li>Add your Stripe keys to the config</li>
            <li>Create backend checkout endpoint</li>
          </ol>
        </div>
        <p style="color: #f59e0b; font-size: 0.8125rem; margin-bottom: 1.5rem;">
          ⚠️ Stripe keys not configured. Demo mode active.
        </p>
        <button onclick="document.getElementById('subscription-modal').remove()" 
                style="width: 100%; background: linear-gradient(135deg, #6366f1, #8b5cf6); border: none; padding: 0.875rem; border-radius: 8px; color: white; font-weight: 600; cursor: pointer;">
          Got it!
        </button>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML('beforeend', modalHtml);
}

// Make handleSubscribe available globally for onclick
window.handleSubscribe = handleSubscribe;

// ============================================
// Analysis Dashboard Functions
// ============================================

async function loadDashboard() {
  const activeGrid = document.getElementById('active-analyses');
  const historyList = document.getElementById('player-history');
  const activeCount = document.getElementById('active-count');

  try {
    // Fetch active analyses
    const activeResponse = await fetch('/api/batch-analyze/active');
    const activeData = await activeResponse.json();

    // Update count
    if (activeCount) {
      activeCount.textContent = `(${activeData.count}/${activeData.max_concurrent})`;
    }

    // Render active grid
    if (activeGrid) {
      if (activeData.active.length === 0) {
        activeGrid.innerHTML = `
          <div class="active-card placeholder">
            <p>No active analyses</p>
            <small>Start auditing a player to begin</small>
          </div>
        `;
      } else {
        activeGrid.innerHTML = activeData.active.map(analysis => `
          <div class="active-card">
            <div class="card-header">
              <span class="username">
                ${analysis.username}
                <span class="platform-dot ${analysis.platform} ${analysis.status === 'RUNNING' ? 'running' : ''}"></span>
              </span>
              <span class="status-badge ${analysis.status.toLowerCase()}">${analysis.status}</span>
            </div>
            <div class="progress-row">
              <div class="progress-bar-container">
                <div class="progress-bar-fill" style="width: ${analysis.progress}%;"></div>
              </div>
              <div class="progress-text">
                <span>${analysis.analyzed_count}/${analysis.total_games} games</span>
                <span class="progress-percent">${analysis.progress}%</span>
              </div>
            </div>
            <div class="stats-row">
              <span class="stat ${analysis.flagged_count > 0 ? 'flagged' : ''}">
                🚩 <strong>${analysis.flagged_count}</strong> flagged
              </span>
              <span class="stat">
                📊 <strong>${Math.round(analysis.avg_suspicion * 100)}%</strong> susp
              </span>
            </div>
            ${analysis.eta_minutes ? `<div class="eta">⏱️ ~${analysis.eta_minutes}min remaining</div>` : ''}
          </div>
        `).join('');
      }
    }

    // Fetch history
    const historyResponse = await fetch('/api/batch-analyze/history');
    const historyData = await historyResponse.json();

    // Render history
    if (historyList) {
      if (historyData.history.length === 0) {
        historyList.innerHTML = '<p class="muted">No previous investigations</p>';
      } else {
        historyList.innerHTML = historyData.history.slice(0, 10).map(player => `
          <div class="history-item">
            <div class="player-info">
              <span class="player-name">👤 ${player.username}</span>
              <span class="player-meta">${player.platform} • ${player.total_games} games • ${player.analyzed_date || 'Unknown'}</span>
            </div>
            <span class="risk-badge ${player.risk_level || 'unknown'}">${player.risk_level || 'N/A'}</span>
            <span class="player-meta">${player.flagged_count} flagged</span>
            <div class="actions">
              <button class="small-btn" onclick="viewAnalysis(${player.id})">View</button>
              <button class="small-btn" onclick="reanalyzePlayer('${player.platform}', '${player.username}')">Re-analyze</button>
            </div>
          </div>
        `).join('');
      }
    }

    // Start polling if there are active analyses
    if (activeData.count > 0 && !dashboardPollingInterval) {
      dashboardPollingInterval = setInterval(loadDashboard, 5000);
    } else if (activeData.count === 0 && dashboardPollingInterval) {
      clearInterval(dashboardPollingInterval);
      dashboardPollingInterval = null;
    }

  } catch (error) {
    console.error('Failed to load dashboard:', error);
  }
}

function viewAnalysis(batchId) {
  // Scroll to results and show batch results
  fetch(`/api/batch-analyze/${batchId}`)
    .then(res => res.json())
    .then(batch => {
      showBatchResults(batch);
      document.querySelector('.investigation-report')?.scrollIntoView({ behavior: 'smooth' });
    })
    .catch(err => console.error('Failed to load analysis:', err));
}

function reanalyzePlayer(platform, username) {
  // Pre-fill audit form and trigger analysis
  const platformSelect = document.getElementById('audit-platform');
  const usernameInput = document.getElementById('audit-username');

  if (platformSelect) platformSelect.value = platform;
  if (usernameInput) usernameInput.value = username;

  // Switch to Auditor tab
  switchSection('audit-search');
}

// Make dashboard functions globally available
window.loadDashboard = loadDashboard;
window.viewAnalysis = viewAnalysis;
window.reanalyzePlayer = reanalyzePlayer;

// Load dashboard on page load if authenticated
document.addEventListener('DOMContentLoaded', () => {
  // Show dashboard section if logged in (will be handled by existing auth logic)
  const dashboardSection = document.getElementById('dashboard-section');
  if (dashboardSection && state.token) {
    dashboardSection.style.display = 'block';
    loadDashboard();
  }

  // Initialize quick search
  initQuickSearch();
});

// ============================================
// Quick Search Functions
// ============================================

function initQuickSearch() {
  const searchInput = document.getElementById('player-search');
  const searchResults = document.getElementById('search-results');

  if (!searchInput) return;

  searchInput.addEventListener('input', (e) => {
    const query = e.target.value.trim();

    // Debounce search
    if (searchTimeout) clearTimeout(searchTimeout);

    if (query.length < 2) {
      searchResults.style.display = 'none';
      return;
    }

    searchTimeout = setTimeout(() => {
      performSearch(query);
    }, 300);
  });

  // Hide results when clicking outside
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.quick-search')) {
      searchResults.style.display = 'none';
    }
  });
}

async function performSearch(query) {
  const searchResults = document.getElementById('search-results');

  try {
    const response = await fetch(`/api/batch-analyze/search?q=${encodeURIComponent(query)}`);
    const data = await response.json();

    if (data.results.length === 0) {
      searchResults.innerHTML = `
        <div class="search-no-results">
          <p>No analysis found for "${query}"</p>
          <button class="analyze-btn" onclick="quickAnalyze('${query}')">🔍 Analyze Now</button>
        </div>
      `;
    } else {
      searchResults.innerHTML = data.results.map(player => {
        const isRunning = player.status === 'running' || player.status === 'queued';
        const statusClass = player.status || 'unknown';
        const progressHtml = isRunning ? `
          <div class="search-progress">
            <div class="search-progress-fill" style="width: ${player.progress}%"></div>
          </div>
        ` : '';

        return `
          <div class="search-result-item ${isRunning ? 'is-running' : ''}" onclick="viewPlayerAnalysis(${player.id}, '${player.status}')">
            <div class="player-info">
              <span class="player-name">👤 ${player.username}</span>
              <span class="player-meta">${player.platform} • ${player.total_games} games</span>
              ${progressHtml}
            </div>
            <div class="player-status-side">
              ${isRunning
            ? `<span class="status-badge ${statusClass}">${player.status.toUpperCase()} (${player.progress}%)</span>`
            : `<span class="risk-badge ${player.risk_level || 'unknown'}">${player.risk_level || 'N/A'}</span>`
          }
              <span class="player-meta">${player.flagged_count} flagged</span>
            </div>
          </div>
        `;
      }).join('');
    }

    searchResults.style.display = 'block';

  } catch (error) {
    console.error('Search failed:', error);
  }
}

function viewPlayerAnalysis(batchId, status) {
  const searchResults = document.getElementById('search-results');
  const searchInput = document.getElementById('player-search');

  searchResults.style.display = 'none';
  if (searchInput) searchInput.value = '';

  if (status === 'running' || status === 'queued') {
    // Switch to Auditor tab and start polling
    switchSection('audit-search');
    currentBatchId = batchId;
    pollBatchStatus(batchId);
    return;
  }

  // Load and show the completed analysis
  fetch(`/api/batch-analyze/${batchId}`)
    .then(res => res.json())
    .then(batch => {
      showBatchResults(batch);
      document.querySelector('.investigation-report')?.scrollIntoView({ behavior: 'smooth' });
    })
    .catch(err => console.error('Failed to load analysis:', err));
}

function quickAnalyze(username) {
  const searchResults = document.getElementById('search-results');
  const searchInput = document.getElementById('player-search');

  searchResults.style.display = 'none';
  if (searchInput) searchInput.value = '';

  // Pre-fill audit form
  const usernameInput = document.getElementById('audit-username');
  if (usernameInput) {
    usernameInput.value = username;
    switchSection('audit-search');
  }
}

// Reset audit form state when starting a new search
function resetAuditState() {
  const progressContainer = document.getElementById('batch-progress');
  const auditStatus = document.getElementById('audit-status');
  const existingReport = document.querySelector('.investigation-report');

  if (progressContainer) progressContainer.style.display = 'none';
  if (auditStatus) {
    auditStatus.textContent = '';
    auditStatus.className = 'status';
  }
  if (existingReport) existingReport.remove();
}

// Make functions globally available
window.performSearch = performSearch;
window.viewPlayerAnalysis = viewPlayerAnalysis;
window.quickAnalyze = quickAnalyze;
window.resetAuditState = resetAuditState;
