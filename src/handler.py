import json, os

def lambda_handler(event, context):
    # Basic sanity check so the ZIP is never empty
    return {
        "statusCode": 200,
        "body": json.dumps({
            "stage": os.getenv("RAW_PREFIX", "unknown"),
            "msg":   "Hello from Lambda!"
        })
    }
