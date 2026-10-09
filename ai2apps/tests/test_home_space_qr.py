"""Verify stable account URL selection without importing the entire runtime."""
import ast
import json
from pathlib import Path
import unittest
from urllib.parse import urlsplit

class Response:
    def __init__(self, content=None, status_code=200, headers=None):
        self.body = json.dumps(content).encode()
        self.status_code = status_code
        self.headers = headers

class HTTPException(Exception):
    def __init__(self, **kwargs):
        self.status_code = kwargs['status_code']

source = ast.parse((Path(__file__).parents[1] / 'api/cloud.py').read_text())
node = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == '_space_response_with_qr')
namespace = dict(Response=Response, JSONResponse=Response, json=json, urlsplit=urlsplit,
                 HTTPException=HTTPException, svg_qr_data_url=lambda url: 'QR:' + url,
                 _apply_browser_cookie=lambda response: response)
exec(compile(ast.Module(body=[node], type_ignores=[]), 'cloud.py', 'exec'), namespace)
transform = namespace['_space_response_with_qr']

class SpaceQRTest(unittest.TestCase):
    def test_account_url_only(self):
        url = 'https://account.example/u/owner-id'
        result = transform(Response({'spaceUrl': url, 'ownerUserId': 'owner-id',
                                     'primaryDevice': {'publicOrigin': 'https://device.example'}}))
        self.assertEqual(json.loads(result.body), {'spaceUrl': url, 'spaceQrDataUrl': 'QR:' + url})
        self.assertEqual(result.headers['Cache-Control'], 'no-store')

    def test_reject_device_or_temporary_urls(self):
        for url in ['https://device.example', 'https://account.example/u/other',
                    'https://account.example/u/owner-id#handoff=secret',
                    'https://account.example/u/owner-id?token=secret']:
            with self.subTest(url=url), self.assertRaises(HTTPException):
                transform(Response({'spaceUrl': url, 'ownerUserId': 'owner-id'}))

    def test_auth_error_preserved(self):
        response = Response({'error': 'unauthorized'}, 401)
        self.assertIs(transform(response), response)

if __name__ == '__main__':
    unittest.main()
