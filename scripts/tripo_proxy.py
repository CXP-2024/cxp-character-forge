#!/usr/bin/env python3
"""Tripo proxy v1 client. Python standard library; credentials stay in the key file."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import tripo as upstream

Error = upstream.TripoError
CONFIG = Path(__file__).resolve().parent.parent / 'proxy-config.json'
BAD = {'failed', 'cancelled', 'canceled', 'expired', 'banned'}
CHAIN = {'texture_model', 'texture_upscaler', 'pbr_generate', 'retexture_generate',
         'animate_prerigcheck', 'animate_rig', 'animate_retarget', 'convert_model',
         'highpoly_to_lowpoly', 'mesh_segmentation', 'smart_segment', 'mesh_fill',
         'mesh_completion', 'apply_indices', 'apply_retexture'}
TYPES = CHAIN | {'text_to_model', 'image_to_model', 'multiview_to_model',
                 'text_to_image', 'generate_image', 'generate_multiview_image',
                 'edit_multiview_image', 'image_upscale', 'image_split', 'motion_generate'}


def settings():
    cfg = upstream.read(CONFIG) if CONFIG.exists() else {}
    base = os.environ.get('TRIPO_PROXY_BASE_URL', cfg.get('base_url', '')).rstrip('/')
    parsed = urllib.parse.urlsplit(base)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise Error('Proxy base URL must be an HTTPS URL without credentials/query/fragment.')
    key_file = Path(os.environ.get('TRIPO_PROXY_KEY_FILE', cfg.get('key_file', '~/.config/cxp-character-forge/tripo_key'))).expanduser()
    return base, key_file


def read_key(path):
    key = path.read_text(encoding='utf-8-sig').strip()
    upstream.SECRET = key
    if not re.fullmatch(r'tp_(live|test)_[A-Za-z0-9_-]+', key):
        raise Error('Expected one tp_live_/tp_test_ key in the configured local file.')
    return key


def task_id(value):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise Error('Invalid task ID.')
    return value


class Client:
    def __init__(self, base, key):
        self.base, self.key = base, key
        self.opener = urllib.request.build_opener(upstream.NoRedirect())

    def api(self, route, body=None, content_type='application/json', idem=None):
        parsed = urllib.parse.urlsplit(route)
        if not route.startswith('/') or route.startswith('//') or parsed.scheme or parsed.netloc or parsed.fragment or '..' in parsed.path or '\\' in route:
            raise Error('Expected a relative proxy API route.')
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
        headers = {'Authorization': 'Bearer ' + self.key, 'Content-Type': content_type,
                   'User-Agent': 'TripoProxySkill/1.0'}
        if idem:
            headers['Idempotency-Key'] = idem
        req = urllib.request.Request(self.base + route, data=data, headers=headers,
                                     method='GET' if body is None else 'POST')
        # Never replay a mutation automatically. Query retries are bounded.
        attempts = 3 if body is None else 1
        for attempt in range(attempts):
            try:
                with self.opener.open(req, timeout=30) as response:
                    result = json.load(response)
                if parsed.path == '/openapi.json':
                    return result
                if not isinstance(result, dict) or result.get('code') != 'ok' or 'data' not in result:
                    raise Error('Unexpected proxy response: ' + json.dumps(upstream.redact(result), ensure_ascii=False)[:600])
                return result['data']
            except urllib.error.HTTPError as error:
                try:
                    detail = json.loads(error.read(65536))
                except (ValueError, OSError):
                    detail = {'code': 'unparseable_error'}
                code = detail.get('code') if isinstance(detail, dict) else None
                if body is None and (error.code in (502, 503) or (error.code == 429 and code == 'rate_limited')) and attempt + 1 < attempts:
                    retry = error.headers.get('Retry-After', '1')
                    time.sleep(min(max(float(retry) if retry.isdigit() else 2 ** attempt, 1), 10))
                    continue
                cls = upstream.Rejected if 400 <= error.code < 500 and error.code not in (408, 409) else Error
                raise cls('HTTP ' + str(error.code) + ': ' + json.dumps(upstream.redact(detail), ensure_ascii=False)[:1000]) from None
            except (urllib.error.URLError, TimeoutError, OSError):
                if body is None and attempt + 1 < attempts:
                    time.sleep(2 ** attempt)
                    continue
                raise Error('Connection failed; no mutation was retried. Reconcile any saved job before resubmitting.') from None

    def task(self, value):
        return self.api('/tasks/' + task_id(value))


def validate(request):
    if not isinstance(request, dict) or set(request) != {'endpoint', 'payload'} or request['endpoint'] != '/tasks':
        raise Error('Proxy request must be {endpoint:"/tasks",payload:{type:...}}. Official v3 requests are incompatible.')
    p = request['payload']
    if not isinstance(p, dict) or p.get('type') not in TYPES:
        raise Error('Unsupported or missing proxy task type.')
    if re.search(r'tp_(?:live|test)_|tsk_|api_key|authorization', json.dumps(p), re.I):
        raise Error('Credentials must not appear in request payloads.')
    if 'model_version' in p:
        raise Error('Proxy uses model, not model_version.')
    kind = p['type']
    if kind in CHAIN:
        task_id(p.get('original_model_task_id', ''))
    if kind in {'text_to_model', 'text_to_image'} and not str(p.get('prompt', '')).strip():
        raise Error('A nonempty prompt is required.')
    if kind == 'image_to_model' and not (p.get('input') or isinstance(p.get('file'), dict) and p['file'].get('file_token')):
        raise Error('Image generation requires input or file.file_token.')
    if kind == 'multiview_to_model':
        views = p.get('files')
        if not isinstance(views, list) or len(views) != 4 or not isinstance(views[0], dict):
            raise Error('files must have four slots: front,left,back,right; front is required.')
        if any(v is not None and (not isinstance(v, dict) or not isinstance(v.get('file_token'), str) or not v['file_token']) for v in views) or sum(v is not None for v in views) < 2:
            raise Error('At least two {file_token:...} objects are required; unused slots are null.')
    if kind == 'animate_retarget':
        if bool(p.get('animations')) == bool(p.get('motion_asset_id')):
            raise Error('Use exactly one of animations or motion_asset_id.')
        if p.get('animations') and (not isinstance(p['animations'], list) or not all(isinstance(v, str) and v for v in p['animations'])):
            raise Error('animations must be a nonempty list of motion names.')
    if kind == 'convert_model' and p.get('format') not in {'glb', 'gltf', 'fbx', 'obj', 'stl', 'usdz', '3mf'}:
        raise Error('Use a supported lowercase conversion format.')
    if p.get('generate_parts') and (p.get('texture', True) or p.get('pbr', True)):
        raise Error('generate_parts requires texture=false and pbr=false on this proxy.')
    return p


def submit(client, request, job):
    p = validate(request)
    path = Path(job) / 'job.json'
    with upstream.job_lock(job):
        if path.exists():
            record = upstream.read(path)
            if record.get('request') != request or record.get('api_base') != client.base:
                raise Error('Job belongs to another request/provider; use a new job directory.')
            if record.get('task_id') or record.get('submission') == 'synchronous':
                return record
            raise Error('Previous attempt has an uncertain/rejected outcome. Reconcile first; no automatic POST replay.')
        if p['type'] == 'animate_retarget':
            flags = client.api('/tasks/' + task_id(p['original_model_task_id']) + '/flags')
            if flags.get('is_rigged') is not True:
                raise Error('Source flags do not confirm is_rigged=true.')
        record = {'request': request, 'api_base': client.base, 'idempotency_key': 'skill-' + uuid.uuid4().hex,
                  'created_at': time.time(), 'submission': 'unknown', 'balance_before': client.api('/balance')}
        upstream.save(path, upstream.redact(record))
        try:
            response = client.api('/tasks', p, idem=record['idempotency_key'])
            if p['type'] == 'animate_prerigcheck':
                record.update(submission='synchronous', result=response)
            elif response.get('task_id'):
                record.update(task_id=response['task_id'], submission='submitted')
            else:
                raise Error('Submission returned no task_id; reconcile this saved job.')
        except Exception as exc:
            record.update(submission='rejected' if isinstance(exc, upstream.Rejected) else 'unknown', error=str(upstream.redact(str(exc))))
            upstream.save(path, upstream.redact(record))
            raise
        upstream.save(path, upstream.redact(record))
        return record


def check_job(client, job):
    record = upstream.read(Path(job) / 'job.json')
    if record.get('api_base') != client.base:
        raise Error('Saved job belongs to another provider.')
    return record


def upload(client, file, record_path):
    suffix = file.suffix.lower()
    model = suffix in {'.glb', '.obj', '.fbx', '.stl'}
    if not model and suffix not in {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'}:
        raise Error('Unsupported image/model extension.')
    if not 0 < file.stat().st_size <= (150 if model else 20) * 1024 ** 2:
        raise Error('File exceeds upload size limit.')
    content = file.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if record_path.exists():
        old = upstream.read(record_path)
        if old.get('sha256') != digest or old.get('api_base') != client.base:
            raise Error('Upload record belongs to another file/provider.')
        return old
    boundary = 'TripoProxy' + uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="input{suffix}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode() + content + f'\r\n--{boundary}--\r\n'.encode()
    if not model and len(body) > 20 * 1024 ** 2:
        raise Error('Entire image multipart body must fit 20 MiB.')
    result = client.api('/uploads/model' if model else '/uploads', body, 'multipart/form-data; boundary=' + boundary)
    if not isinstance(result, dict) or not result.get('task_id' if model else 'file_token'):
        raise Error('Upload returned no expected reference; inspect remote state before retrying.')
    result.update(sha256=digest, api_base=client.base, filename=file.name)
    upstream.save(record_path, upstream.redact(result))
    return result


def download(client, job, extract=False):
    record = check_job(client, job)
    result = client.task(record['task_id'])
    if result.get('status') != 'success':
        raise Error('Only a successful task can be downloaded.')
    # link=1 returns JSON; omit type to avoid conversion charges. Never forward Bearer to CDN.
    link = client.api('/tasks/' + task_id(record['task_id']) + '/download?link=1')
    if not isinstance(link, dict) or not link.get('url'):
        raise Error('Download returned no URL.')
    filename = str(link.get('filename') or Path(urllib.parse.urlsplit(link['url']).path).name or 'model.bin')
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename).strip(' .')
    if not filename or re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', filename, re.I):
        filename = 'asset.bin'
    folder = Path(job) / 'assets'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / filename
    if target.exists():
        raise Error('Asset already exists; use a fresh job copy to preserve local edits.')
    size, digest = upstream.fetch_asset(link['url'], target)
    with target.open('rb') as stream:
        magic = stream.read(4)
    actual = '.glb' if magic == b'glTF' else '.zip' if magic[:2] == b'PK' else target.suffix
    if actual != target.suffix:
        updated = target.with_suffix(actual)
        if updated.exists():
            raise Error('Detected-format destination already exists.')
        target.rename(updated)
        target = updated
    if actual == '.glb':
        from inspect_glb import inspect
        inspect(target)
    if extract and actual == '.zip':
        destination = target.with_suffix('')
        if destination.exists():
            raise Error('Extraction directory exists.')
        upstream.extract_zip(target, destination)
    manifest = {'task_id': record['task_id'], 'file': str(target.resolve()), 'bytes': size, 'sha256': digest}
    upstream.save(Path(job) / 'assets.json', manifest)
    record['result'] = result
    upstream.save(Path(job) / 'job.json', upstream.redact(record))
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    d = sub.add_parser('doctor'); d.add_argument('--online', action='store_true')
    for name in ('balance', 'usage', 'models'):
        sub.add_parser(name)
    for name in ('status', 'flags', 'animations'):
        q = sub.add_parser(name); q.add_argument('--task-id', required=True)
    q = sub.add_parser('upload'); q.add_argument('--file', type=Path, required=True); q.add_argument('--record', type=Path, required=True)
    q = sub.add_parser('submit'); q.add_argument('--request', type=Path, required=True); q.add_argument('--job', type=Path, required=True)
    mode = q.add_mutually_exclusive_group(required=True); mode.add_argument('--dry-run', action='store_true'); mode.add_argument('--execute', action='store_true')
    q = sub.add_parser('wait'); q.add_argument('--job', type=Path, required=True); q.add_argument('--timeout', type=float, default=45); q.add_argument('--interval', type=float, default=5)
    q = sub.add_parser('download'); q.add_argument('--job', type=Path, required=True); q.add_argument('--extract', action='store_true')
    q = sub.add_parser('recover'); q.add_argument('--job', type=Path, required=True); q.add_argument('--task-id', required=True)
    args = parser.parse_args(argv)
    base, key_file = settings()
    if args.command == 'doctor':
        upstream.emit({'provider': 'tripo-proxy-v1', 'api_base': base, 'key_file': str(key_file),
                       'key_file_exists': key_file.is_file(), 'python': sys.version.split()[0],
                       'optional_blender': shutil.which('blender'), 'paid_tasks_submitted': 0})
        if not args.online:
            return 0
    if args.command == 'submit':
        request = upstream.read(args.request)
        validate(request)
        if args.dry_run:
            upstream.emit({'would_submit': request, 'api_base': base, 'network_requests': 0})
            return 0
    client = Client(base, read_key(key_file))
    if args.command == 'doctor':
        balance = client.api('/balance')
        models = client.api('/models')
        spec = client.api('/openapi.json')
        upstream.emit({'connection_ok': True, 'balance': balance, 'models': models,
                       'task_types': sorted(k for k, v in spec.get('x-task-params', {}).items() if v.get('available') is True),
                       'verification': 'GET /balance, /models, /openapi.json only; no uploads or task submissions'})
    elif args.command in ('balance', 'usage', 'models'):
        upstream.emit(client.api('/' + args.command))
    elif args.command in ('status', 'flags', 'animations'):
        route = '/tasks/' + task_id(args.task_id)
        upstream.emit(client.api(route + ('' if args.command == 'status' else '/' + args.command)))
    elif args.command == 'upload':
        upstream.emit(upload(client, args.file, args.record))
    elif args.command == 'submit':
        upstream.emit(submit(client, request, args.job))
    elif args.command == 'wait':
        if not 0 <= args.timeout <= 55 or not 3 <= args.interval <= 60:
            raise Error('Use timeout 0..55 and interval 3..60; repeat wait to continue.')
        record = check_job(client, args.job)
        if record.get('submission') == 'synchronous':
            upstream.emit(record['result']); return 0
        # Reuse bounded polling and saved task state from the upstream skill.
        class PollClient:
            task = client.task
            def api(self, route):
                return client.api('/balance')
        record = upstream.wait_job(PollClient(), args.job, args.timeout, args.interval)
        upstream.emit(record if record is not None else {'pending': True, 'next': 'Repeat wait; do not resubmit.'})
        return 0 if record is not None else 3
    elif args.command == 'recover':
        with upstream.job_lock(args.job):
            record = check_job(client, args.job)
            if record.get('task_id') not in (None, args.task_id):
                raise Error('Job already has another task ID.')
            record.update(task_id=task_id(args.task_id), result=client.task(args.task_id), submission='recovered')
            upstream.save(args.job / 'job.json', upstream.redact(record))
            upstream.emit({'recovered': True, 'task_id': args.task_id})
    elif args.command == 'download':
        upstream.emit(download(client, args.job, args.extract))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (Error, OSError, ValueError, KeyError, TypeError) as exc:
        print('ERROR: ' + str(upstream.redact(str(exc))), file=sys.stderr)
        sys.exit(1)
