"""Proxy behavioral tests: all network mocked, no real key or credit use."""
import io
import os
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import tripo_proxy as proxy


class Response(io.BytesIO):
    def __init__(self, data):
        super().__init__(json.dumps(data).encode())


class FakeClient:
    base = 'https://example.invalid/v1'
    def __init__(self, result=None, failure=None):
        self.calls = []
        self.result = result or {'task_id': 'task-1'}
        self.failure = failure
    def api(self, route, body=None, **kwargs):
        self.calls.append((route, body, kwargs))
        if body is None:
            return {'balance': 500, 'is_rigged': True}
        if self.failure:
            raise self.failure
        return self.result


class Tests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'TRIPO_PROXY_BASE_URL': 'https://example.invalid/v1', 'TRIPO_PROXY_KEY_FILE': '/nonexistent/test-key'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.req = {'endpoint': '/tasks', 'payload': {'type': 'text_to_model', 'prompt': 'One character'}}
    def tearDown(self):
        self.tmp.cleanup()
        proxy.upstream.SECRET = ''
    def test_proxy_envelope_and_utf8_and_idempotency(self):
        client = proxy.Client('https://example.invalid/v1', 'tp_test_fake_secret')
        with patch.object(client.opener, 'open', return_value=Response({'code': 'ok', 'data': {'task_id': 'one'}})) as send:
            self.assertEqual(client.api('/tasks', {'prompt': '\u4eba\u7269'}, idem='job-1'), {'task_id': 'one'})
            req = send.call_args.args[0]
            self.assertEqual(req.full_url, 'https://example.invalid/v1/tasks')
            self.assertEqual(json.loads(req.data), {'prompt': '\u4eba\u7269'})
            self.assertEqual(req.get_header('Idempotency-key'), 'job-1')
    def test_no_post_retry_on_503(self):
        client = proxy.Client('https://example.invalid/v1', 'tp_test_fake_secret')
        error = urllib.error.HTTPError('https://example.invalid', 503, 'busy', {}, io.BytesIO(b'{"code":"no_upstream_account","request_id":"r1"}'))
        with patch.object(client.opener, 'open', side_effect=error) as send:
            with self.assertRaisesRegex(proxy.Error, 'r1'):
                client.api('/tasks', self.req['payload'])
            self.assertEqual(send.call_count, 1)
    def test_no_duplicate_job_submission(self):
        client = FakeClient()
        first = proxy.submit(client, self.req, self.root/'job')
        again = proxy.submit(client, self.req, self.root/'job')
        self.assertEqual(first['task_id'], again['task_id'])
        self.assertEqual(sum(body is not None for _, body, _ in client.calls), 1)
        self.assertTrue(first['idempotency_key'])
    def test_uncertain_post_blocks_resubmission(self):
        client = FakeClient(failure=proxy.Error('timeout'))
        with self.assertRaises(proxy.Error):
            proxy.submit(client, self.req, self.root/'job')
        self.assertEqual(proxy.upstream.read(self.root/'job/job.json')['submission'], 'unknown')
        with self.assertRaisesRegex(proxy.Error, 'Reconcile'):
            proxy.submit(client, self.req, self.root/'job')
        self.assertEqual(sum(body is not None for _, body, _ in client.calls), 1)
    def test_sync_prerig_does_not_require_task_id(self):
        req = {'endpoint': '/tasks', 'payload': {'type': 'animate_prerigcheck', 'original_model_task_id': 'model-1'}}
        record = proxy.submit(FakeClient(result={'riggable': True}), req, self.root/'job')
        self.assertEqual(record['submission'], 'synchronous')
        self.assertEqual(record['result'], {'riggable': True})
    def test_multiview_order_and_wrong_schema_rejection(self):
        req = {'endpoint': '/tasks', 'payload': {'type': 'multiview_to_model', 'files': [{'file_token': 'front'}, None, {'file_token': 'back'}, None]}}
        proxy.validate(req)
        req['payload']['files'][0] = 'front'
        with self.assertRaises(proxy.Error):
            proxy.validate(req)
        with self.assertRaises(proxy.Error):
            proxy.validate({'endpoint': '/v3/generation/text-to-model', 'payload': {'prompt': 'x'}})
    def test_dry_run_does_not_read_key_or_create_client(self):
        path = self.root/'request.json'
        proxy.upstream.save(path, self.req)
        with patch.object(proxy, 'read_key') as key, patch.object(proxy, 'Client') as client, patch('sys.stdout', new=io.StringIO()) as out:
            self.assertEqual(proxy.main(['submit', '--request', str(path), '--job', str(self.root/'job'), '--dry-run']), 0)
            self.assertEqual(json.loads(out.getvalue())['network_requests'], 0)
            key.assert_not_called()
            client.assert_not_called()
        self.assertFalse((self.root/'job').exists())
    def test_online_doctor_only_three_gets(self):
        with patch.object(proxy, 'read_key', return_value='tp_test_fake_secret'), patch.object(proxy.Client, 'api', return_value={}) as api, patch('sys.stdout', new=io.StringIO()):
            proxy.main(['doctor', '--online'])
        self.assertEqual([c.args for c in api.call_args_list], [('/balance',), ('/models',), ('/openapi.json',)])
    def test_key_read_and_redaction(self):
        path = self.root/'key'
        path.write_text('\ufefftp_live_fake_secret\n', encoding='utf-8')
        self.assertEqual(proxy.read_key(path), 'tp_live_fake_secret')
        self.assertNotIn('tp_live_fake_secret', proxy.upstream.redact('error tp_live_fake_secret'))
    def test_host_and_redirect_guards(self):
        client = proxy.Client('https://example.invalid/v1', 'tp_test_fake_secret')
        for route in ('//other.invalid/balance', 'https://other.invalid/balance', '/tasks/../balance'):
            with self.assertRaises(proxy.Error):
                client.api(route)
        with self.assertRaises(proxy.Error):
            proxy.upstream.NoRedirect().redirect_request(None, None, 307, 'redirect', {}, 'https://cdn.invalid')

    def test_wait_reuses_proxy_task_route_and_never_posts(self):
        job = self.root/'job'
        proxy.upstream.save(job/'job.json', {'api_base': 'https://example.invalid/v1', 'task_id': 'task-1', 'submission': 'submitted'})
        calls = []
        def api(client, route, body=None, **kw):
            calls.append((route, body))
            return {'status': 'success', 'progress': 100} if route.startswith('/tasks/') else {'balance': 500}
        with patch.object(proxy, 'settings', return_value=('https://example.invalid/v1', self.root/'key')), patch.object(proxy, 'read_key', return_value='tp_test_fake_secret'), patch.object(proxy.Client, 'api', api), patch('sys.stdout', new=io.StringIO()):
            self.assertEqual(proxy.main(['wait', '--job', str(job), '--timeout', '0']), 0)
        self.assertEqual(calls, [('/tasks/task-1', None), ('/balance', None)])

    def test_download_uses_native_json_link_and_separate_fetch(self):
        job = self.root/'job'
        client = FakeClient()
        client.task = lambda value: {'status': 'success'}
        proxy.upstream.save(job/'job.json', {'api_base': client.base, 'task_id': 'task-1'})
        def download_asset(url, target):
            target.write_bytes(b'example-data')
            return 12, 'sha256-placeholder'
        with patch.object(client, 'api', return_value={'url': 'https://cdn.invalid/model.obj', 'filename': 'model.obj'}) as api, patch.object(proxy.upstream, 'fetch_asset', side_effect=download_asset) as fetch:
            manifest = proxy.download(client, job)
        api.assert_called_once_with('/tasks/task-1/download?link=1')
        self.assertEqual(len(fetch.call_args.args), 2)
        self.assertEqual(manifest['bytes'], 12)

    def test_retarget_requires_rigged_source(self):
        client = FakeClient()
        req = {'endpoint': '/tasks', 'payload': {'type': 'animate_retarget', 'original_model_task_id': 'model-1', 'animations': ['idle']}}
        with patch.object(client, 'api', return_value={'is_rigged': False}) as api:
            with self.assertRaisesRegex(proxy.Error, 'is_rigged'):
                proxy.submit(client, req, self.root/'job')
            self.assertTrue(all(len(call.args) == 1 for call in api.call_args_list))


if __name__ == '__main__':
    unittest.main()
