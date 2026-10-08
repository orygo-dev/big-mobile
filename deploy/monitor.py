"""Run from aaPanel Cron; no user data or token is written to logs."""
import os, json, urllib.request, sys
from datetime import datetime, timezone

def check():
    try:
        with urllib.request.urlopen(os.environ["APP_BASE_URL"].rstrip("/")+"/api/health",timeout=15) as response:
            result=json.load(response)
        if result.get("status")!="ready": raise RuntimeError("Application unavailable")
        print(json.dumps({"time":datetime.now(timezone.utc).isoformat(),"status":"healthy"}))
    except Exception as error:
        print(json.dumps({"time":datetime.now(timezone.utc).isoformat(),"status":"failed","error_type":type(error).__name__}))
        # Configure aaPanel Cron notification on non-zero exit; no outgoing
        # notification is sent unless the operator configures that channel.
        sys.exit(1)

if __name__=="__main__": check()
