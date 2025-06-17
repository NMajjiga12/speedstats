import asyncio
import json
import aiohttp
import websockets
from .config import HTTP_API_BASE, WS_API_BASE, POLL_INTERVAL, MAX_RUNNERS, REQUEST_TIMEOUT
from .state import runs, tracked_runners, state_lock

async def ws_handler():
    async with websockets.connect(WS_API_BASE) as ws:
        async for message in ws:
            data = json.loads(message)
            if "login" not in data:
                continue
            
            login = data["login"].lower()
            
            with state_lock:
                if login not in tracked_runners:
                    continue
                
                existing = runs.get(login, {})
                runs[login] = {
                    "currentTime": data.get("currentTime", existing.get("currentTime", 0)),
                    "insertedAt": int(data.get("insertedAt", existing.get("insertedAt", 0))),
                    "splitIndex": data.get("currentSplitIndex", existing.get("splitIndex", -1)),
                    "finished": data.get("runPercentage", 0.0) >= 1.0,
                    "currentSplitName": data.get("currentSplitName", existing.get("currentSplitName", "")),
                    "delta": data.get("delta", existing.get("delta", 0)),
                    "bestPossible": data.get("bestPossible", existing.get("bestPossible", 0)),
                    "pb": data.get("pb", existing.get("pb", 0)),
                }

async def poll_runner(username):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as session:
        while True:
            try:
                async with session.get(f"{HTTP_API_BASE}/{username}") as resp:
                    data = await resp.json()
                    login = data["login"].lower()
                    
                    with state_lock:
                        if login not in tracked_runners:
                            break
                        
                        existing = runs.get(login, {})
                        runs[login] = {
                            "currentTime": data.get("currentTime", existing.get("currentTime", 0)),
                            "insertedAt": int(data.get("insertedAt", existing.get("insertedAt", 0))),
                            "splitIndex": data.get("currentSplitIndex", existing.get("splitIndex", -1)),
                            "finished": data.get("runPercentage", 0.0) >= 1.0,
                            "currentSplitName": data.get("currentSplitName", existing.get("currentSplitName", "")),
                            "delta": data.get("delta", existing.get("delta", 0)),
                            "bestPossible": data.get("bestPossible", existing.get("bestPossible", 0)),
                            "pb": data.get("pb", existing.get("pb", 0)),
                        }
            except Exception as e:
                print(f"Polling error for {username}: {str(e)}")
            
            await asyncio.sleep(POLL_INTERVAL)

async def main_async():
    async with aiohttp.ClientSession() as session:
        ws_task = asyncio.create_task(ws_handler())
        
        with state_lock:
            runners = list(tracked_runners)[:MAX_RUNNERS]
        
        poll_tasks = [asyncio.create_task(poll_runner(username)) 
                     for username in runners]
        
        done, pending = await asyncio.wait(
            [ws_task] + poll_tasks,
            return_when=asyncio.FIRST_EXCEPTION
        )
        
        for task in pending:
            task.cancel()