"""Preview the same API handler and public files without a Vercel account."""
import argparse
from http.server import ThreadingHTTPServer
import importlib.util
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('vercel_entry', ROOT/'api/index.py')
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)


class PreviewHandler(entry.handler):
    def do_GET(self):
        if self.endpoint() is not None:
            return super().do_GET()
        files = {'/': ('index.html', 'text/html; charset=utf-8'),
                 '/index.html': ('index.html', 'text/html; charset=utf-8'),
                 '/app.js': ('app.js', 'application/javascript; charset=utf-8'),
                 '/style.css': ('style.css', 'text/css; charset=utf-8')}
        target = files.get(urlsplit(self.path).path)
        if not target:
            return self.reply(404, {'error': 'Unknown resource'})
        filename, content_type = target
        data = (ROOT/'public'/filename).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Content-Security-Policy', "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8011)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), PreviewHandler)
    print(f'Preview: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
