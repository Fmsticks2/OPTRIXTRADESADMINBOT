# This file is deprecated as health checks are now handled by FastAPI in bot_runner.py
# Keeping this file for reference only

from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import json

# Health check functionality has been moved to bot_runner.py
# Do not use this file

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'status': 'healthy', 'service': 'optrixtrades-bot'}
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

def start_health_server():
    """Start health check server in background"""
    server = HTTPServer(('0.0.0.0', 8080), HealthHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    return server

if __name__ == '__main__':
    start_health_server()
    print("Health check server running on port 8080")
