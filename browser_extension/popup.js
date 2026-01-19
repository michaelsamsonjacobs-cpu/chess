/**
 * ChessGuard Extension Popup Script
 */

const CHESSGUARD_SERVER = 'http://localhost:8000';

document.addEventListener('DOMContentLoaded', async () => {
    // Check server status
    await checkServerStatus();

    // Load recent analyses
    await loadRecentAnalyses();

    // Button handlers
    document.getElementById('open-dashboard').addEventListener('click', () => {
        chrome.tabs.create({ url: CHESSGUARD_SERVER });
    });

    document.getElementById('analyze-current').addEventListener('click', analyzeCurrentPage);
});

/**
 * Check if ChessGuard server is running
 */
async function checkServerStatus() {
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');

    try {
        const response = await fetch(`${CHESSGUARD_SERVER}/api/analyses`, {
            method: 'GET',
            signal: AbortSignal.timeout(3000),
        });

        if (response.ok) {
            statusDot.classList.add('online');
            statusText.textContent = 'Server Online';
        } else {
            throw new Error('Server error');
        }
    } catch (error) {
        statusDot.classList.add('offline');
        statusText.textContent = 'Server Offline';
    }
}

/**
 * Load recent analyses from server
 */
async function loadRecentAnalyses() {
    const list = document.getElementById('recent-list');

    try {
        const response = await fetch(`${CHESSGUARD_SERVER}/api/batch-analyze/recent?limit=5`);

        if (!response.ok) {
            throw new Error('Failed to load');
        }

        const data = await response.json();

        if (!data.length) {
            list.innerHTML = '<li class="recent-item"><span>No recent analyses</span></li>';
            return;
        }

        list.innerHTML = data.map(item => {
            const badgeClass = item.risk_level === 'high' || item.risk_level === 'critical'
                ? 'badge-high'
                : item.risk_level === 'medium'
                    ? 'badge-medium'
                    : 'badge-low';

            return `
        <li class="recent-item">
          <div>
            <span class="username">${item.username}</span>
            <span class="platform">${item.source}</span>
          </div>
          <span class="badge ${badgeClass}">${item.risk_level || 'low'}</span>
        </li>
      `;
        }).join('');

    } catch (error) {
        list.innerHTML = '<li class="recent-item"><span>Could not load</span></li>';
    }
}

/**
 * Analyze the current page
 */
async function analyzeCurrentPage() {
    const btn = document.getElementById('analyze-current');
    btn.disabled = true;
    btn.textContent = '⏳ Analyzing...';

    try {
        // Get current tab
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

        // Send message to content script
        const response = await chrome.tabs.sendMessage(tab.id, { action: 'getGameInfo' });

        if (response && response.gameId) {
            // Submit to server
            const result = await fetch(`${CHESSGUARD_SERVER}/api/games/import`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    lichess_id: response.gameId,
                    source: response.platform,
                    force: false,
                }),
            });

            if (result.ok) {
                btn.textContent = '✓ Queued!';
                setTimeout(() => {
                    btn.textContent = '🔍 Analyze Current Page';
                    btn.disabled = false;
                }, 2000);
            } else {
                throw new Error('Server error');
            }
        } else {
            btn.textContent = '✗ No game found';
            setTimeout(() => {
                btn.textContent = '🔍 Analyze Current Page';
                btn.disabled = false;
            }, 2000);
        }
    } catch (error) {
        btn.textContent = '✗ Error';
        setTimeout(() => {
            btn.textContent = '🔍 Analyze Current Page';
            btn.disabled = false;
        }, 2000);
    }
}
