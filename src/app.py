import tkinter as tk
import threading
import os
import asyncio
from http.server import HTTPServer
from .config import generate_html, generate_obs_html, MAX_RUNNERS
from .http_client import fetch_initial_runs
from .server import RequestHandler
from .live_updater import main_async
from .state import runs, tracked_runners, state_lock

class RunTrackerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"Live Run Tracker (Max {MAX_RUNNERS})")
        self.server = None
        self.running = False
        self.loop = None
        self.server_thread = None
        self.async_thread = None

        self.entries = []
        self.copy_buttons = []
        
        self.create_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        self.main_frame = tk.Frame(self.root, padx=20, pady=20, bg='#F9FBFA')
        self.main_frame.pack()

        # Create input fields and copy buttons
        for i in range(MAX_RUNNERS):
            frame = tk.Frame(self.main_frame, bg='#E7EEEC', pady=2)
            frame.grid(row=i, column=0, sticky="ew", pady=2)
            
            lbl = tk.Label(
                frame, 
                text=f"Runner {i+1}:", 
                width=10, 
                anchor="w",
                bg='#E7EEEC',
                fg='#21313C'
            )
            lbl.pack(side=tk.LEFT)
            
            entry = tk.Entry(
                frame,
                width=25,
                bg='#F9FBFA',
                fg='#21313C',
                highlightbackground='#89989B',
                highlightthickness=1,
                relief=tk.FLAT
            )
            entry.pack(side=tk.LEFT, padx=5)
            self.entries.append(entry)
            
            copy_btn = tk.Button(
                frame, 
                text="Copy Link", 
                command=lambda idx=i: self.copy_obs_link(idx),
                width=8,
                bg='#C3E7CA',
                fg='#116149',
                activebackground='#B8C4C2',
                activeforeground='#0B3835',
                relief=tk.FLAT
            )
            copy_btn.pack(side=tk.LEFT, padx=2)
            self.copy_buttons.append(copy_btn)

        # Control buttons
        self.btn_frame = tk.Frame(self.main_frame, bg='#F9FBFA')
        self.btn_frame.grid(row=MAX_RUNNERS+1, column=0, pady=10)

        self.start_btn = tk.Button(
            self.btn_frame, 
            text="Start Tracking", 
            command=self.start_tracking,
            bg='#13AA52',
            fg='#E7EEEC',
            activebackground='#116149',
            activeforeground='#E7EEEC',
            relief=tk.FLAT
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = tk.Button(
            self.btn_frame,
            text="Stop Tracking",
            command=self.stop_tracking,
            state=tk.DISABLED,
            bg='#3D4F58',
            fg='#E7EEEC',
            activebackground='#5D6C74',
            activeforeground='#E7EEEC',
            relief=tk.FLAT
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # Status label
        self.status = tk.Label(
            self.main_frame, 
            text="Status: Inactive", 
            fg="#3D4F58",
            bg='#F9FBFA',
            font=('Arial', 10, 'bold')
        )
        self.status.grid(row=MAX_RUNNERS+2, column=0)

    def copy_obs_link(self, index):
        username = self.entries[index].get().strip()
        if not username:
            return
            
        url = f"http://localhost:8000/runner/{username}"
        try:
            import pyperclip
            pyperclip.copy(url)
        except ImportError:
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self.root.update()
        
        print(f"Copied OBS URL for runner {index+1}: {url}")

    def start_tracking(self):
        usernames = [e.get().strip() for e in self.entries]
        usernames = [u for u in usernames if u][:MAX_RUNNERS]
        
        if not usernames:
            return

        with state_lock:
            tracked_runners.clear()
            tracked_runners.update(u.lower() for u in usernames)
            runs.clear()

        threading.Thread(target=fetch_initial_runs, args=(usernames,)).start()

        # Update UI elements
        self.start_btn.config(
            state=tk.DISABLED,
            bg='#C3E7CA',
            fg='#116149'
        )
        self.stop_btn.config(
            state=tk.NORMAL,
            bg='#116149',
            fg='#E7EEEC'
        )
        self.status.config(text="Status: Active", fg="#13AA52")

        self.create_web_files()
        self.start_server()
        self.start_async_loop()

    def copy_obs_links(self):
        with state_lock:
            runners = list(tracked_runners)
        
        urls = [f"http://localhost:8000/runner/{u}" for u in runners]
        text = "\n".join(urls)
        
        try:
            import pyperclip
            pyperclip.copy(text)
        except ImportError:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        
        print(f"Copied {len(urls)} OBS URL")

    def create_web_files(self):
        os.makedirs('web', exist_ok=True)
        try:
            # Write main HTML file with UTF-8 encoding
            with open('web/index.html', 'w', encoding='utf-8', errors='replace') as f:
                f.write(generate_html())
            
            # Write OBS HTML file with UTF-8 encoding
            with open('web/obs.html', 'w', encoding='utf-8', errors='replace') as f:
                f.write(generate_obs_html())
        except Exception as e:
            print(f"Error creating web files: {e}")

    def start_server(self):
        self.server = HTTPServer(('localhost', 8000), RequestHandler)
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()

    def start_async_loop(self):
        self.async_thread = threading.Thread(target=self.run_async_loop)
        self.async_thread.daemon = True
        self.async_thread.start()

    def run_async_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(main_async())

    def stop_tracking(self):
        if self.server:
            self.server.shutdown()
        self.running = False
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
        with state_lock:
            runs.clear()
            tracked_runners.clear()
        
        # Reset UI elements
        self.start_btn.config(
            state=tk.NORMAL,
            bg='#13AA52',
            fg='#E7EEEC'
        )
        self.stop_btn.config(
            state=tk.DISABLED,
            bg='#3D4F58',
            fg='#E7EEEC'
        )
        self.status.config(text="Status: Inactive", fg="#3D4F58")

    def on_close(self):
        self.stop_tracking()
        self.root.destroy()

def main():
    app = RunTrackerApp()
    app.root.mainloop()