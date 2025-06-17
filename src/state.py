from threading import Lock

runs = {}
tracked_runners = set()
state_lock = Lock()