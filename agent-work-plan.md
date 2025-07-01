## Branch - combine

1. utils/s3_utils.py - Add s3 util function for reading .json and .csv files from a specified s3 bucket/key.
2. combine.py - Read in all .csv files from s3://{bucket}/dk-contests/{date}/{sport}/, where {bucket} is the s3 bucket, {date} is today's date (yyyy-mm-dd), and {sport} is the same sport from dk-api.yaml ('mlb' in this case). The name of each file (example: 129974) is its draftkings slate_id. This data contains information on draftable players for a given draftkings slate, such as position, salary, and more.
3. combine.py - Merge the data on player name. For the player prop bet data (player_rows) the merge key will be 'player', and in the draftable players data the merge key is 'name'. Keep all columns from both sets of data. Return this merged data from the main function in combine.py. Be sure to add print statements with the size and shape of the data before and after any fetching or transformation.
4. handler.py - Upload the merged data to build_key(proc_prefix, "combined", f"{timestamp}.csv")
5. Write and update tests for any new or changed files.

## Branch - projection
