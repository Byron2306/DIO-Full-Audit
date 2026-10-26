#!/usr/bin/env python3
"""Expose the canonical customer protocol to the DIO website through a tunnel."""
from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.vesper_public_web import PublicWebAccessError
from scripts.serve_vesper_web_chat import VesperWebChatHandler

WEBSITE_ORIGIN = 'https://dioworkflows.co.za'
HEALTH_PATH = '/api/vesper/health'
# One 2 MiB binary attachment expands to about 2.8 MiB in Base64.
PUBLIC_MAX_REQUEST_BYTES = 4 * 1024 * 1024
METHOD_PATHS = {
    'GET': {'/api/vesper/web/session', '/api/vesper/web/replies'},
    'POST': {'/api/vesper/web/session', '/api/vesper/web/message', '/api/vesper/web/voice'},
}


class PublicVesperHandler(VesperWebChatHandler):
    """A route allowlist around the existing engine, never a second engine."""
    site_root = None
    server_version = 'DIOVesperPublic/1.0'

    def _website_origin(self) -> None:
        if self.headers.get('Origin') != WEBSITE_ORIGIN:
            raise PublicWebAccessError('website origin refused')

    def _cors(self) -> None:
        if self.headers.get('Origin') == WEBSITE_ORIGIN:
            self.send_header('Access-Control-Allow-Origin', WEBSITE_ORIGIN)
        self.send_header('Vary', 'Origin')

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        # Preserve protocol state/error markers, but do not return exceptions
        # containing local paths or other host details to public clients.
        if status >= 400:
            payload = {key: payload[key] for key in ('error', 'processing_state') if key in payload}
            payload['message'] = ('Request refused.' if status == 403 else
                                  'Request could not be completed. Retain the original submission for retry.')
        super().send_json(payload, status)

    def _permitted(self, method: str) -> bool:
        path = urlsplit(self.path).path
        if path not in METHOD_PATHS[method]:
            self.send_json({'error': 'not_found'}, HTTPStatus.NOT_FOUND)
            return False
        try:
            self._website_origin()
        except PublicWebAccessError:
            self.send_json({'error': 'origin_refused'}, HTTPStatus.FORBIDDEN)
            return False
        return True

    def do_GET(self) -> None:
        if urlsplit(self.path).path == HEALTH_PATH:
            self.send_json({'ok': True, 'service': 'vesper-public-api',
                            'canonical_presence_engine': True, 'external_send': 'REFUSE',
                            'external_release': 'REFUSE', 'authority_created': False})
        elif self._permitted('GET'):
            super().do_GET()

    def do_POST(self) -> None:
        if not self._permitted('POST'):
            return
        # Chunked request decoding is not implemented at this boundary.
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except (TypeError, ValueError):
            length = 0
        if (not 2 <= length <= PUBLIC_MAX_REQUEST_BYTES
                or self.headers.get('Transfer-Encoding')):
            self.close_connection = True
            self.send_json({'error': 'invalid_request_size'}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        super().do_POST()

    def do_OPTIONS(self) -> None:
        path = urlsplit(self.path).path
        if path not in METHOD_PATHS['GET'] | METHOD_PATHS['POST']:
            self.send_json({'error': 'not_found'}, HTTPStatus.NOT_FOUND)
            return
        try:
            self._website_origin()
        except PublicWebAccessError:
            self.send_json({'error': 'origin_refused'}, HTTPStatus.FORBIDDEN)
            return
        super().do_OPTIONS()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', choices=['127.0.0.1'], default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8772)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), PublicVesperHandler)
    print(f'Vesper public customer API: http://{args.host}:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
