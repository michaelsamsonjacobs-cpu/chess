# How to Use Chess Observer ♟️

Welcome to your AI-powered fair play companion! This guide will help you automate your cheat detection and interpret the results.

## 🤖 1. Connecting Your Account (Agent Console)

To let Chess Observer automatically monitor your opponents:
1.  Click **Agent Console** 🤖 in the left sidebar.
2.  Under **Link New Account**, select your platform (Lichess or Chess.com).
3.  Enter your **username** (e.g., `MagnusCarlsen`).
4.  *(Optional)* Enter an OAuth Token if you want to analyze private games.
5.  Click **Link Account**.

> **Note:** Once linked, Chess Observer will immediately fetch your last 10 games to look for cheaters.

## 🔄 2. Syncing Games

Chess Observer runs automatically in the background, but you can force an update anytime:

1.  Go to the **Agent Console**.
2.  Click the **🔄 Sync All Now** button at the top right.
3.  Watch the **Sync Status** panel to see the progress.

## 🚨 3. Interpreting Reports

When Chess Observer spots a suspicious player, they will appear in the **Flagged Players** table.

*   **Risk Levels**:
    *   🔴 **CRITICAL**: Extremely high probability of cheating (99%+).
    *   🟠 **HIGH**: Strong evidence of unfair play.
    *   🔵 **MODERATE**: Suspicious patterns, worth reviewing.
    *   🟢 **LOW**: Likely clean.

### Viewing the Explanation
Click the **View** button next to any flagged player. The AI will generate a plain-English report explaining *why* they were flagged, for example:

> *"This player matched the top chess engine 95% of the time in complex tactical positions, which is highly unlikely for a player of their rating (1500 ELO)."*

## 🔍 4. Use "Detective Mode" (Audit Search)

Want to check a specific player manually?

1.  Click **Detective Mode** 🔍 in the sidebar.
2.  Enter any Lichess or Chess.com username.
3.  Select a timeframe (e.g., "Last 3 Months").
4.  Click **Search Games**.
5.  If games are found, click **"Analyze All Games"** to run a deep scan on their recent history.

## ❓ FAQ

**Q: Is my password safe?**
A: Yes! Chess Observer uses secure Login with Google/Apple. We never see or store your passwords.

**Q: Can I get banned for using this?**
A: No. Chess Observer analyzes *publicly available* game data (PGNs). It does not interact with the game board while you are playing.

**Q: What is "ToM Score"?**
A: "Theory of Mind" score. It measures how "human-like" the moves are. A very low ToM score often indicates computer assistance.
