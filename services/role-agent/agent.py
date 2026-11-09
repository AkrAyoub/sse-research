"""Tiny read-only VM role heartbeat agent (stdlib, localhost by default).

Not a blockchain node or SLA monitoring oracle. Does NOT serve privileged methods,
control Docker, handle signing keys, or submit chain transactions.
"""
import argparse
import json
import os
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NAME = re.compile(r'^[a-z][a-z0-9-]{0,62}$')
ROLES = frozenset({'provider','consumer','monitor','ethereum_full_node','validator',
                   'rpc','observer','dashboard','logs'})


def config(environ=None):
    env = os.environ if environ is None else environ
    name = env.get('SSE_NODE_ID', 'sse-local-node')
    roles = [x.strip() for x in env.get('SSE_ROLES', 'observer').split(',') if x.strip()]
    if not NAME.fullmatch(name) or not roles or set(roles) - ROLES:
        raise ValueError('invalid node name or roles')
    host = env.get('SSE_AGENT_HOST', '127.0.0.1')
    if host != '127.0.0.1':  # intentionally local-only
        raise ValueError('agent only binds to loopback; use a secured reverse proxy')
    port = int(env.get('SSE_AGENT_PORT', '8765'))
    if not 1024 <= port <= 65535:
        raise ValueError('invalid port')
    revision = env.get('SSE_REVISION', 'local')
    if not re.fullmatch(r'[a-zA-Z0-9._-]{1,80}', revision):
        raise ValueError('invalid revision')
    return {'node_id': name, 'roles': roles, 'port':port, 'host':host, 'revision':revision}


def make_server(conf):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/healthz':
                body = {'ok': True, 'component': 'role-agent', 'chain_verified': False}
            elif self.path == '/v1/status':
                body = {'node_id':conf['node_id'], 'roles':conf['roles'],
                        'revision':conf['revision'], 'software_running': True,
                        'blockchain_synced': None, 'monitor_eligible': None,
                        'provider_capacity_verified': None,
                        'checked_at': datetime.now(timezone.utc).isoformat()}
            else:
                self.send_error(404)
                return
            encoded = json.dumps(body).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        def log_message(self, fmt, *args):
            return  # no potential sensitive request logs
    return ThreadingHTTPServer((conf['host'],conf['port']), Handler)


def main():
    parser = argparse.ArgumentParser(description='SSE loopback role heartbeat (read-only, no chain authority)')
    parser.parse_args()
    conf = config()
    print(f"SSE read-only agent running at http://{conf['host']}:{conf['port']}", flush=True)
    make_server(conf).serve_forever()


if __name__ == '__main__':
    main()
