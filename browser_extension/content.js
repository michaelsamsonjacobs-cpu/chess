/**
 * ChessGuard Browser Extension - Content Script
 * 
 * Injects "Analyze with ChessGuard" button on Lichess and Chess.com game pages.
 */

(function () {
    'use strict';

    const CHESSGUARD_SERVER = 'http://localhost:8000';

    // Detect which platform we're on
    const isLichess = window.location.hostname.includes('lichess.org');
    const isChessCom = window.location.hostname.includes('chess.com');

    /**
     * Extract game ID from current URL
     */
    function getGameId() {
        const path = window.location.pathname;

        if (isLichess) {
            // Lichess: /abc12345 or /abc12345/white
            const match = path.match(/^\/([a-zA-Z0-9]{8,12})/);
            return match ? match[1] : null;
        }

        if (isChessCom) {
            // Chess.com: /game/live/12345678 or /analysis/game/live/12345678
            const match = path.match(/\/(?:game|analysis)\/(?:live|daily)\/(\d+)/);
            return match ? match[1] : null;
        }

        return null;
    }

    /**
     * Extract username from game page
     */
    function getOpponentUsername() {
        if (isLichess) {
            const userLink = document.querySelector('.ruser-top a.user-link, .ruser-bottom a.user-link');
            return userLink ? userLink.textContent.trim() : null;
        }

        if (isChessCom) {
            const userEl = document.querySelector('.user-username-component');
            return userEl ? userEl.textContent.trim() : null;
        }

        return null;
    }

    /**
     * Create the ChessGuard button
     */
    function createButton() {
        const btn = document.createElement('button');
        btn.id = 'chessguard-analyze-btn';
        btn.innerHTML = '🔍 ChessGuard';
        btn.title = 'Analyze this game with ChessGuard';

        btn.addEventListener('click', handleAnalyzeClick);

        return btn;
    }

    /**
     * Handle analyze button click
     */
    async function handleAnalyzeClick(e) {
        e.preventDefault();

        const btn = e.target;
        const gameId = getGameId();
        const platform = isLichess ? 'lichess' : 'chesscom';

        if (!gameId) {
            showToast('Could not detect game ID', 'error');
            return;
        }

        btn.disabled = true;
        btn.innerHTML = '⏳ Analyzing...';

        try {
            // Send to ChessGuard server
            const response = await fetch(`${CHESSGUARD_SERVER}/api/games/import`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    lichess_id: gameId,
                    source: platform,
                    force: false,
                }),
            });

            if (!response.ok) {
                throw new Error(`Server returned ${response.status}`);
            }

            const data = await response.json();

            showToast(`Game queued for analysis! ID: ${data.id}`, 'success');

            // Open ChessGuard in new tab
            window.open(`${CHESSGUARD_SERVER}/#analysis-${data.id}`, '_blank');

        } catch (error) {
            console.error('ChessGuard error:', error);
            showToast(`Analysis failed: ${error.message}`, 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '🔍 ChessGuard';
        }
    }

    /**
     * Show toast notification
     */
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `chessguard-toast chessguard-toast-${type}`;
        toast.textContent = message;

        document.body.appendChild(toast);

        setTimeout(() => toast.classList.add('show'), 10);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    /**
     * Inject button into page
     */
    function injectButton() {
        // Don't inject if already present
        if (document.getElementById('chessguard-analyze-btn')) {
            return;
        }

        // Only inject on game pages
        const gameId = getGameId();
        if (!gameId) {
            return;
        }

        const btn = createButton();

        if (isLichess) {
            // Lichess: Add to game controls
            const controls = document.querySelector('.rcontrols, .analyse__controls');
            if (controls) {
                controls.appendChild(btn);
            } else {
                // Fallback: fixed position
                btn.style.position = 'fixed';
                btn.style.bottom = '20px';
                btn.style.right = '20px';
                btn.style.zIndex = '9999';
                document.body.appendChild(btn);
            }
        }

        if (isChessCom) {
            // Chess.com: Add near share buttons
            const shareArea = document.querySelector('.share-menu-component, .game-buttons');
            if (shareArea) {
                shareArea.appendChild(btn);
            } else {
                btn.style.position = 'fixed';
                btn.style.bottom = '20px';
                btn.style.right = '20px';
                btn.style.zIndex = '9999';
                document.body.appendChild(btn);
            }
        }

        console.log('ChessGuard: Button injected for game', gameId);
    }

    /**
     * Initialize extension
     */
    function init() {
        // Initial injection
        injectButton();

        // Re-check on navigation (SPA support)
        let lastUrl = location.href;
        new MutationObserver(() => {
            if (location.href !== lastUrl) {
                lastUrl = location.href;
                setTimeout(injectButton, 500);
            }
        }).observe(document, { subtree: true, childList: true });
    }

    // Run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
