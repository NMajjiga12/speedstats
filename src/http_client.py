import requests
from concurrent.futures import ThreadPoolExecutor
from .config import HTTP_API_BASE, MAX_RUNNERS, REQUEST_TIMEOUT
from .state import runs, tracked_runners, state_lock

def fetch_initial_runs(usernames):
    def fetch_single(username):
        try:
            response = requests.get(
                f"{HTTP_API_BASE}/{username}",
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching {username}: {str(e)}")
            return None

    with ThreadPoolExecutor(max_workers=MAX_RUNNERS) as executor:
        futures = {executor.submit(fetch_single, username): username 
                 for username in usernames[:MAX_RUNNERS]}
        
        for future in futures:
            data = future.result()
            if not data:
                continue
            
            with state_lock:
                login = data["login"].lower()
                if login in tracked_runners:
                    runs[login] = {
                        "currentTime": data["currentTime"],
                        "insertedAt": int(data["insertedAt"]),
                        "splitIndex": data.get("currentSplitIndex", 0),
                        "finished": data.get("runPercentage", 0.0) >= 1.0,
                        "currentSplitName": data.get("currentSplitName", ""),
                        "delta": data.get("delta", 0),
                        "bestPossible": data.get("bestPossible", 0),
                        "pb": data.get("pb", 0),
                    }