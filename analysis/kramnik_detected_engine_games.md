# Kramnik Detected Engine Games Overview

## Dataset coverage
- The consolidated PGN archive now contains 50 games spanning from 2020 through March 2024, covering Kramnik's flagged encounters on chess.com and lichess.【35f668†L1-L4】【6d893c†L1-L6】
- The metadata export lists every event, round, opponent and rating for quick reference, from the March 2024 Titled Tuesday rounds down to the December 2020 Levitov Christmas Final games.【F:data/metadata/kramnik_detected_engine_games.csv†L1-L10】【F:data/metadata/kramnik_detected_engine_games.csv†L42-L51】
- The PGN file explicitly includes the two Levitov knockout losses that bookend the dataset, ensuring historical completeness for later comparisons.【F:data/pgn/kramnik_detected_engine_games.pgn†L1328-L1377】

## Performance patterns
- Kramnik scored no wins in this subset: 32 losses and 18 draws, underscoring why these games raised engine-usage suspicions.【6d893c†L1-L3】
- Color makes little difference—he recorded 17 losses/12 draws as White and 15 losses/6 draws as Black, highlighting issues independent of opening initiative.【3e9918†L1-L4】
- Despite averaging a 332-point Elo edge over opponents (and more than 400 points in 2024), adverse results persisted across all years.【6d893c†L1-L9】
- The longest uninterrupted skid reached seven straight defeats, illustrating multi-round stretches of anomalous play.【3e9918†L1-L8】

## Opponents and event trends
- Repeat pairings—Cherniaiev, Bluebaum, Bortnyk, Lysyj and Tsydypov—surface multiple times, giving focal points for deeper manual review or statistical anomaly detection.【3e9918†L8-L11】
- Titled Tuesday remains the primary source, with events like “Titled Tue 26th Mar Early,” “Titled Tue 23rd Jan Late,” and “Titled Tue 22nd Aug Late” each contributing three games to the corpus.【6d893c†L8-L10】
- With metadata and PGNs aligned, the dataset is ready for future comparison runs—either across different Titled Tuesday editions or against control sets of verified fair-play games.
