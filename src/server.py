from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
from .state import runs

class RequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory='web', **kwargs)
    
    def do_GET(self):
        if self.path.startswith('/data.json'):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-store, must-revalidate')
            self.end_headers()
            data = json.dumps([{**v, "login": k} for k, v in runs.items()])
            self.wfile.write(data.encode())
        elif self.path.startswith('/runner/'):
            self.path = '/obs.html'
            super().do_GET()
        else:
            super().do_GET()