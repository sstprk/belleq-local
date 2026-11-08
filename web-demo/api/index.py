"""Vercel Python entry point. Inference only; no local file writes or live LLM calls."""
from datetime import datetime, timezone
from functools import lru_cache
from http.server import BaseHTTPRequestHandler
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from belleq_sim.engine import load_artifacts, point_prediction, simulate


@lru_cache(maxsize=1)
def artifacts():
    return load_artifacts()


class handler(BaseHTTPRequestHandler):
    def reply(self, status, body):
        data = json.dumps(body, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def endpoint(self):
        url = urlsplit(self.path)
        # Support both the original request path and Vercel's rewritten destination.
        direct = {'/health': 'health', '/v1/model': 'model',
                  '/v1/simulate': 'simulate', '/v1/predict': 'predict'}
        if url.path in direct:
            return direct[url.path]
        if url.path.rstrip('/') in ['/api/index', '/api/index.py']:
            return parse_qs(url.query).get('endpoint', ['health'])[0]
        return None

    def do_GET(self):
        name = self.endpoint()
        if name == 'health':
            self.reply(200, {'status': 'ok', 'app_version': '0.3.0',
                             'hosting': 'vercel', 'persistence': 'download_only'})
        elif name == 'model':
            self.reply(200, artifacts()['model_card'])
        else:
            self.reply(404, {'error': 'Unknown endpoint'})

    def do_POST(self):
        name = self.endpoint()
        if name not in ['simulate', 'predict']:
            self.reply(404, {'error': 'Unknown endpoint'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 16384:
                self.reply(413, {'error': 'Provide a JSON body of 1 to 16384 bytes.'})
                return
            request = json.loads(self.rfile.read(length))
            if not isinstance(request, dict):
                raise ValueError('Provide a JSON object.')
            if name == 'predict':
                self.reply(200, point_prediction(request['question'], request['method'], artifacts()))
                return
            if request.get('draws', 10000) > 20000:
                raise ValueError('This demo supports at most 20000 repetitions per request.')
            result = simulate(request, artifacts())
            result.pop('samples')
            result['run_id'] = (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
                                + '_' + uuid4().hex[:8])
            result['record_type'] = 'simulation_not_physical_measurement'
            result['persistence'] = 'download_only'
            result['warnings'].append(
                'This hosted demo does not permanently store runs. Download results to keep a copy.')
            self.reply(200, result)
        except (ValueError, TypeError, KeyError, UnicodeError) as exc:
            self.reply(422, {'error': str(exc)})
