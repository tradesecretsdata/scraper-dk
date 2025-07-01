## Branch - projections

xxx Add "Home Runs" player props

- Currently, parse.py filters out markets without "over" or "under". There is one market that needs to be excepted - "Home Runs".
- The home runs market, instead of being over/under, offers prices for 1+ home run, 2+ home runs, etc., for each player. We will need to transform it so that it has the same fields as the over/under markets in the table that parse_main() returns.
- The home runs market is one-sided. That is, there is no price for betting that the player hits zero home runs. Because of this, there is vigorish built into this one-sided market. I have determined the vig amount to be 13.0%. Create a function that takes the price for 1+ home runs, for instance +290, applies the 13.0% vig, and returns vig-free odds (in this example case, roughly +340).
- Now we can convert the home runs market into an over/under market - over/under 0.5 home runs. The value for the 'points' field will be 0.5, and we can fill in the vig-free odds field and then calculate the poisson mean just like in the other markets.

2. Also in parse.py, assign a value of 0.04 for 'hit_by_pitch' for each player.
3. Fantasy point projections for batters

- After parse.py returns data to handler.py, that data will be fed into a function in projections.py called compute_batter_fpts() which will compute a fantasy points projection for batters called 'fpts_batter'.
- Since at this point we do not know each player's position, just compute this value for all players.
- You can find the point value that each batter statistic contributes to fpts_batter in the docstring at the top of projections.py.
- The compute_batter_fpts() will happen in handler.py between steps 3 and 4, and that's what will be uploaded to s3 instead of the output from parse_and_pivot.

4. Fantasy point projections for pitchers
