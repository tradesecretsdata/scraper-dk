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

13. Feature: slate_display column (DONE)

- Insert a column called slate_display (position it near the other slate-related columns) that shows "{slate_start_str} - {num_games} games"

14. Fix: Drop the 'playerid' column in the combined data. I thought we dropped it before but it is still there. (DONE)

15. Add "fpts_complete" column

- Boolean column. True if none of the required fields are empty.
- Insert to the right of the 'fpts' column.
- Required fields for "Batter" role: singles, doubles, triples, home_runs, stolen_bases, runs, rbis, walks_batter, hit_by_pitch
- Required fields for "Pitcher" role: earned_runs_allowed, outs_recorded, strikeouts_thrown, hits_allowed, walks_allowed

16. One-sided walks (batter) market

- Repeat the steps in item (1) but for "Walks (Batter)" instead of "Home Runs"

17. Extract game betting data (DONE)

- The first json that gets grabbed, "Game Lines / Game", contains betting information on each game. Extract the following information into a table: team, team_abbr (team abbreviation, e.g. MIA), opp (opponent), opp_abbr, side ("Home" or "Away"), moneyline, spread_amount (e.g. -3.5), spread_price (e.g. -171), total
- An example of that data is located in "data/20250703T173730Z-games.json"

18. Calculated columns based on game betting data (DONE)

- With the data extracted in the previous item ("17. Extract game betting data"), calculate three new columns: vig_free_spread, vig_free_moneyline, and pct_win (percent chance the team wins the game, computed using vig_free_moneyline).

19. Merge with combined data before the upload to s3 step (DONE)

- Insert some of the new columns into the combined data table using "team" as the join key from the combined player data table and "team_abbr" from the game betting data table.
- Columns to insert: "vig_free_spread", "vig_free_moneyline", "pct_win".
- Insert the columns between "opponent_sp" and "game_type" in the combined data table.

20. Fix: in combined data, replace "vig_free_spread" with "spread_amount" and just call that column "spread". (DONE)

21. Fix: insert "total" (from game betting data) just after the "spread" column from the previous step. (DONE)

22. Feature: Fantasy point projections for pitchers (DONE)

- Create a new column "innings_pitched" equal to outs_recorded/3.
- Create a new column "hit_batsman" equal to (0.42/9)\*(innings_pitched)/9. If innings_pitched is blank (no data or player is not a pitcher) leave the cell blank.
- Implement the pitcher fantasy points projection as outlined in the docstring in projections.py. Here is how the categories line up to columns in our table: "Innings pitched" = innings_pitched, "Strikeout" = strikeouts_thrown, "Earned run allowed" = earned_runs_allowed, "Hit against" = hits_allowed, "Base on balls against" = walks_allowed, "Hit batsman" = hit_batsman.

23. Fix: the "hit_by_pitch" column should be blank for players who are pitchers. (DONE)

24. Fix: move the columns total_bases, hits, and hits runs rbis to the left of earned_runs_allowed (immediately following hit_by_pitch). (DONE)

25. Fix: fpts_complete for pitchers is showing False even though it seems all fields are present. Is one of the fields being filled after fpts_complete = false is determined? Figure out what is going wrong and fix it. (DONE)

26. Feature: fill in empty stolen_bases (for batters only) with 0. (DONE)

27. Feature: fill in empty walks_batter (for batters) with equation: walks_batter = 5e-5 \* dk_salary + 0.1806. This must be done after props data is combined with salary data. (DONE)

28. Feature: fill in empty triples (for batters) with 0.01. Be sure to put this before 'fpts_complete' logic because the value of fpts_complete depends on whether 'triples' is empty. (DONE)

29. Feature: scale down projections. Before uploading combined data, but after applying other adjustments to 'fpts', if 'role' = "Pitcher", multiply 'fpts' by 0.941. If 'role' = "Batter", multiply 'fpts' by 0.938. (DONE)

30. Feature: Instead of computing pct_pitcher_win from the team's moneyline, use the two-way prop market "to_record_a_win" from "pitcher_props". Compute the vig-free odds of a win and convert it to a percentage. See file "to_record_a_win_temp" for an example of the raw data.

31. Feature: replace 'spread' and 'total' columns with 'team_total' and 'opp_total'. Plug the vig-free moneyline and game total into pythagorian expectation with exponent 1.83 to compute the run totals (team_total and opp_total) for the game.
