"""Local interface and HTTP backend; no external services required."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from datetime import datetime, timezone
from uuid import uuid4
from .common import ROOT, write_json, csv_write, event
from . import __version__
from .engine import simulate, point_prediction, load_artifacts

def serve(port=8010):
    artifacts=load_artifacts()
    class Handler(BaseHTTPRequestHandler):
        def reply(self,status,body):
            data=json.dumps(body,allow_nan=False).encode()
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
        def do_GET(self):
            assets={'/':('index.html','text/html; charset=utf-8'),
                    '/index.html':('index.html','text/html; charset=utf-8'),
                    '/style.css':('style.css','text/css; charset=utf-8'),
                    '/app.js':('app.js','text/javascript; charset=utf-8')}
            if self.path in assets:
                name,mime=assets[self.path];data=(ROOT/'web'/name).read_bytes()
                self.send_response(200);self.send_header('Content-Type',mime)
                self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Content-Security-Policy',"default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
                self.end_headers();self.wfile.write(data)
            elif self.path=='/health':self.reply(200,dict(status='ok',version=__version__))
            elif self.path=='/v1/model':self.reply(200,artifacts['model_card'])
            else:self.reply(404,dict(error='Unknown endpoint'))
        def do_POST(self):
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=16384:raise ValueError('JSON body must be 1..16384 bytes')
                request=json.loads(self.rfile.read(length))
                if not isinstance(request,dict):raise ValueError('JSON object required')
                if self.path=='/v1/simulate':
                    # Keep the HTTP path bounded. CLI permits larger research exports.
                    if request.get('draws',10000)>20000:raise ValueError('HTTP draw limit is 20000')
                    result=simulate(request,artifacts)
                    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid4().hex[:8]
                    samples=result.pop('samples');result['run_id']=run_id
                    result['record_type']='simulation_not_physical_measurement'
                    dest=ROOT/'results/ui_runs'/run_id
                    write_json(dest/'summary.json',result);csv_write(dest/'samples.csv',samples)
                    event('interface_simulation',run_id=run_id,config=result['config'],
                          evidence=result['evidence_level'],kind='simulation_not_physical_measurement')
                    self.reply(200,result)
                elif self.path=='/v1/predict':
                    self.reply(200,point_prediction(request['question'],request['method'],artifacts))
                else:self.reply(404,dict(error='Unknown endpoint'))
            except (ValueError,TypeError,KeyError) as exc:self.reply(422,dict(error=str(exc)))
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'Search Simulator: http://127.0.0.1:{port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
