## Branch - projections

1. Add "Home Runs" player props (DONE)

- Currently, parse.py filters out markets without "over" or "under". There is one market that needs to be excepted - "Home Runs".
- The home runs market, instead of being over/under, offers prices for 1+ home run, 2+ home runs, etc., for each player. We will need to transform it so that it has the same fields as the over/under markets in the table that parse_main() returns.
- The home runs market is one-sided. That is, there is no price for betting that the player hits zero home runs. Because of this, there is vigorish built into this one-sided market. I have determined the vig amount to be 13.0%. Create a function that takes the price for 1+ home runs, for instance +290, applies the 13.0% vig, and returns vig-free odds (in this example case, roughly +340).
- Now we can convert the home runs market into an over/under market - over/under 0.5 home runs. The value for the 'points' field will be 0.5, and we can fill in the vig-free odds field and then calculate the poisson mean just like in the other markets.

2. Also in parse.py, assign a value of 0.04 for 'hit_by_pitch' for each player. (DONE)

3. Fantasy point projections for batters (DONE)

- After parse.py returns data to handler.py, that data will be fed into a function in projections.py called compute_batter_fpts() which will compute a fantasy points projection for batters called 'fpts_batter'.
- Since at this point we do not know each player's position, just compute this value for all players.
- You can find the point value that each batter statistic contributes to fpts_batter in the docstring at the top of projections.py.
- The compute_batter_fpts() will happen in handler.py between steps 3 and 4, and that's what will be uploaded to s3 instead of the output from parse_and_pivot.

4. Feature: Add triples (DONE)

- Repeat the steps in item (1) but for "Triples" instead of "Home Runs"

5. Fix: batter fpts (DONE)

- Batter fantasy points are not being calculated correctly because the table fields do not match the keys in \_BATTER_WEIGHTS.
- In combine.py, let's clean up the column names. Remove the suffix '\_ou' or '\_OU' from every column name in the player_rows data.
- In projections.py, match column name to \_BATTER_WEIGHTS key as follows: {singles: singles, doubles: doubles, triples: triples, home_runs: home_runs, rbis: rbis, runs: runs, walks_batter: walks, hit_by_pitch: hit_by_pitch, stolen_bases: stolen}

6. Feature: create "role" column (DONE)

- Move the fantasy point projection computation to after the 'combine' step.
- Create a new column "role". The value should be "Pitcher" if the players position (pos) is "SP" or "RP", and otherwise the value should be "Batter"

7. Feature: Change "batter_fpts" to just "fpts" (DONE)

- Change the column name "batter_fpts" to just "fpts".
- If the player's role is "Batter", use the existing batter_fpts logic to calculate fpts. If the player's role is "Pitcher", leave the cell empty for now; we have not built the projection logic for pitchers yet.

8. Fix: clean up table (DONE)

- Drop duplicate rows in the combined table.
- Drop rows where the "slate_id" column equals 0.

9. Feature: add "pts/$" column (DONE)

- Add a column "pts/$" computed as "fpts" / "dk_salary"

10. Fix: rename, reorder, and drop columns in the combined table (DONE)

- Do these operations before uploading to s3
- Drop: slate_id, slate_start, playerid, game_start, player
- Rename: {slate_start_str: slate_start, name: player, pos: position, opp: opponent, opp_sp: opponent_sp}
- Reorder the remaining columns. Put the important stuff first, such as player, fpts, dk_salary, pts/$, position, team, opponent, opponent_sp, followed by the rest of the player descriptive information, then batter stats, then pitcher stats, and finally slate information.

11. Fix: multiply the pts/$ column by 1000 (DONE)

12. Fix: Reorder stat columns (DONE)

- Batter columns first, then pitcher columns, in order below
- Batter columns: singles, doubles, triples, home_runs, stolen_bases, runs, rbis, walks_batter, hit_by_pitch
- Pitcher columns: earned_runs_allowed, outs_recorded, strikeouts_thrown, hits_allowed, walks_allowed

13. Feature: Fantasy point projections for pitchers
