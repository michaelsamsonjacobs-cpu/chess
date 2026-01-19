/**
 * ChessGuard Extension Background Service Worker
 */

const CHESSGUARD_SERVER = 'http://localhost:8000';

// Handle messages from content script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'submitGame') {
        submitGame(request.gameId, request.platform)
            .then(result => sendResponse({ success: true, data: result }))
            .catch(error => sendResponse({ success: false, error: error.message }));
        return true; // Will respond asynchronously
    }
});

/**
 * Submit a game for analysis
 */
async function submitGame(gameId, platform) {
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

    return response.json();
}

// Context menu for right-click analysis
chrome.runtime.onInstalled.addListener(() => {
    chrome.contextMenus.create({
        id: 'chessguard-analyze',
        title: '🔍 Analyze with ChessGuard',
        contexts: ['page', 'link'],
        documentUrlPatterns: [
            'https://lichess.org/*',
            'https://www.chess.com/*',
        ],
    });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
    if (info.menuItemId === 'chessguard-analyze') {
        chrome.tabs.sendMessage(tab.id, { action: 'analyzeGame' });
    }
});
