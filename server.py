#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KT Survey Pro — GitHub APK Uploader Server
เว็บเซิร์ฟเวอร์ขนาดกะทัดรัดสำหรับอัปโหลดไฟล์ APK ขึ้น GitHub Releases
ไม่จำเป็นต้องติดตั้งไลบรารีภายนอก (ใช้ Python Standard Library ล้วนๆ)
"""

import os
import sys
import json
import urllib.request
import urllib.error
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import webbrowser
import threading
import time

PORT = 8765
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"owner": "", "repo": "", "token": "", "last_tag": ""}

def save_config(data):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def make_github_request(url, method='GET', headers=None, data=None):
    if headers is None:
        headers = {}
    headers.setdefault('User-Agent', 'KTSurvey-Uploader/1.0')
    headers.setdefault('Accept', 'application/vnd.github.v3+json')

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read()
            return response.status, json.loads(res_body.decode('utf-8'))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8')
        try:
            err_json = json.loads(err_body)
        except Exception:
            err_json = {"message": err_body}
        return e.code, err_json
    except Exception as e:
        return 500, {"message": str(e)}

def parse_multipart_form_data(rfile, content_type, content_length):
    boundary = content_type.split('boundary=')[1].encode('utf-8')
    body = rfile.read(content_length)
    parts = body.split(b'--' + boundary)
    
    fields = {}
    files = {}

    for part in parts:
        if not part or part == b'--\r\n' or part == b'--':
            continue
        header_and_data = part.split(b'\r\n\r\n', 1)
        if len(header_and_data) != 2:
            continue
        headers_raw, data = header_and_data
        data = data.rstrip(b'\r\n')
        
        headers_str = headers_raw.decode('utf-8', errors='ignore')
        disposition = ''
        for h in headers_str.split('\r\n'):
            if h.lower().startswith('content-disposition:'):
                disposition = h
                break
        
        name = ''
        filename = ''
        for item in disposition.split(';'):
            item = item.strip()
            if item.startswith('name='):
                name = item.split('=', 1)[1].strip('"\'')
            elif item.startswith('filename='):
                filename = item.split('=', 1)[1].strip('"\'')

        if filename:
            files[name] = {
                'filename': filename,
                'data': data
            }
        elif name:
            fields[name] = data.decode('utf-8', errors='ignore')

    return fields, files

class UploaderHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # Clean log format
        sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] {args[0]} {args[1]}\n")
        sys.stdout.flush()

    def send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == '/' or path == '/index.html':
            html_path = os.path.join(BASE_DIR, 'index.html')
            if os.path.exists(html_path):
                with open(html_path, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "index.html not found")
        elif path == '/api/config':
            self.send_json(200, load_config())
        elif path == '/api/detected-apks':
            # Scan root folder and parent folder for APKs
            apks = []
            scan_dirs = [BASE_DIR, os.path.dirname(BASE_DIR)]
            for d in scan_dirs:
                if os.path.exists(d):
                    for f in os.listdir(d):
                        if f.lower().endswith('.apk'):
                            full_path = os.path.join(d, f)
                            size_mb = os.path.getsize(full_path) / (1024 * 1024)
                            apks.append({
                                'fileName': f,
                                'path': full_path,
                                'sizeMb': round(size_mb, 2),
                                'modified': os.path.getmtime(full_path)
                            })
            apks.sort(key=lambda x: x['modified'], reverse=True)
            self.send_json(200, apks)
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get('Content-Length', 0))
        content_type = self.headers.get('Content-Type', '')

        if path == '/api/config':
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
                save_config(data)
                self.send_json(200, {"success": True, "message": "บันทึกการตั้งค่าเรียบร้อย"})
            except Exception as e:
                self.send_json(400, {"success": False, "message": str(e)})

        elif path == '/api/test-github':
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
                owner = data.get('owner', '').strip()
                repo = data.get('repo', '').strip()
                token = data.get('token', '').strip()

                if not owner or not repo:
                    self.send_json(400, {"success": False, "message": "กรุณาระบุ Owner และ Repo"})
                    return

                headers = {}
                if token:
                    headers['Authorization'] = f"Bearer {token}"

                url = f"https://api.github.com/repos/{owner}/{repo}"
                code, resp = make_github_request(url, headers=headers)

                if code == 200:
                    self.send_json(200, {
                        "success": True,
                        "repoName": resp.get("full_name"),
                        "isPrivate": resp.get("private"),
                        "description": resp.get("description") or "",
                        "htmlUrl": resp.get("html_url")
                    })
                elif code == 404:
                    self.send_json(404, {
                        "success": False,
                        "message": f"ไม่พบ Repository '{owner}/{repo}' บน GitHub (กรุณาตรวจสอบชื่อคลัง หรือ Token หากเป็น Private)"
                    })
                elif code == 401 or code == 403:
                    self.send_json(code, {
                        "success": False,
                        "message": f"สิทธิ์การเข้าถึงไม่ถูกต้อง หรือ Token หมดอายุ (HTTP {code})"
                    })
                else:
                    self.send_json(code, {
                        "success": False,
                        "message": resp.get("message", f"HTTP {code}")
                    })
            except Exception as e:
                self.send_json(500, {"success": False, "message": str(e)})

        elif path == '/api/upload-release':
            try:
                if 'multipart/form-data' in content_type:
                    fields, files = parse_multipart_form_data(self.rfile, content_type, content_length)
                    owner = fields.get('owner', '').strip()
                    repo = fields.get('repo', '').strip()
                    token = fields.get('token', '').strip()
                    tag = fields.get('tag', '').strip()
                    title = fields.get('title', '').strip() or tag
                    notes = fields.get('notes', '').strip() or f"KT Survey Plus {tag}"
                    local_path = fields.get('localPath', '').strip()

                    apk_bytes = None
                    apk_filename = None

                    if 'apkFile' in files:
                        apk_bytes = files['apkFile']['data']
                        apk_filename = files['apkFile']['filename']
                    elif local_path and os.path.exists(local_path):
                        apk_filename = os.path.basename(local_path)
                        with open(local_path, 'rb') as f:
                            apk_bytes = f.read()

                    if not apk_bytes or not apk_filename:
                        self.send_json(400, {"success": False, "message": "ไม่พบไฟล์ APK ที่ต้องการอัปโหลด"})
                        return
                else:
                    # JSON payload specifying local file path
                    body = self.rfile.read(content_length).decode('utf-8')
                    data = json.loads(body)
                    owner = data.get('owner', '').strip()
                    repo = data.get('repo', '').strip()
                    token = data.get('token', '').strip()
                    tag = data.get('tag', '').strip()
                    title = data.get('title', '').strip() or tag
                    notes = data.get('notes', '').strip() or f"KT Survey Plus {tag}"
                    local_path = data.get('localPath', '').strip()

                    if not local_path or not os.path.exists(local_path):
                        self.send_json(400, {"success": False, "message": f"ไม่พบไฟล์ APK ที่: {local_path}"})
                        return

                    apk_filename = os.path.basename(local_path)
                    with open(local_path, 'rb') as f:
                        apk_bytes = f.read()

                if not owner or not repo or not token or not tag:
                    self.send_json(400, {"success": False, "message": "กรุณากรอก Owner, Repo, Token และ Tag Name ให้ครบถ้วน"})
                    return

                # Save config
                save_config({"owner": owner, "repo": repo, "token": token, "last_tag": tag})

                headers = {
                    'Authorization': f"Bearer {token}",
                    'Accept': 'application/vnd.github.v3+json',
                    'User-Agent': 'KTSurvey-Uploader/1.0'
                }

                # Step 1: Check if release exists
                release_url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}"
                code, release_obj = make_github_request(release_url, headers=headers)

                release_id = None
                upload_url = None

                if code == 200:
                    release_id = release_obj.get('id')
                    upload_url = release_obj.get('upload_url', '')
                    # Check existing assets to delete duplicate filename
                    assets = release_obj.get('assets', [])
                    for asset in assets:
                        if asset.get('name') == apk_filename:
                            del_url = f"https://api.github.com/repos/{owner}/{repo}/releases/assets/{asset.get('id')}"
                            make_github_request(del_url, method='DELETE', headers=headers)
                else:
                    # Create release
                    create_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
                    payload = json.dumps({
                        "tag_name": tag,
                        "name": title,
                        "body": notes,
                        "draft": False,
                        "prerelease": False
                    }).encode('utf-8')

                    create_headers = headers.copy()
                    create_headers['Content-Type'] = 'application/json'

                    code, release_obj = make_github_request(create_url, method='POST', headers=create_headers, data=payload)
                    if code not in [200, 201]:
                        err_msg = release_obj.get('message', f'สร้าง Release ไม่สำเร็จ (HTTP {code})')
                        self.send_json(code, {"success": False, "message": f"สร้าง Release ไม่สำเร็จ: {err_msg}"})
                        return
                    release_id = release_obj.get('id')
                    upload_url = release_obj.get('upload_url', '')

                # Step 2: Upload APK asset
                # upload_url format: https://uploads.github.com/repos/{owner}/{repo}/releases/{release_id}/assets{?name,label}
                clean_upload_url = upload_url.split('{')[0]
                target_upload_url = f"{clean_upload_url}?name={urllib.parse.quote(apk_filename)}"

                upload_headers = {
                    'Authorization': f"Bearer {token}",
                    'Content-Type': 'application/vnd.android.package-archive',
                    'Content-Length': str(len(apk_bytes)),
                    'User-Agent': 'KTSurvey-Uploader/1.0'
                }

                code, asset_obj = make_github_request(target_upload_url, method='POST', headers=upload_headers, data=apk_bytes)

                if code in [200, 201]:
                    download_url = asset_obj.get('browser_download_url')
                    self.send_json(200, {
                        "success": True,
                        "message": "อัปโหลดไฟล์ APK ขึ้น GitHub สำเร็จเรียบร้อย!",
                        "tagName": tag,
                        "title": title,
                        "fileName": apk_filename,
                        "fileSizeMb": round(len(apk_bytes) / (1024 * 1024), 2),
                        "downloadUrl": download_url,
                        "releaseHtmlUrl": release_obj.get('html_url') or f"https://github.com/{owner}/{repo}/releases/tag/{tag}",
                        "repoFullName": f"{owner}/{repo}"
                    })
                else:
                    err_msg = asset_obj.get('message', f'อัปโหลดไฟล์ไม่สำเร็จ (HTTP {code})')
                    self.send_json(code, {"success": False, "message": f"อัปโหลดไฟล์ APK ไม่สำเร็จ: {err_msg}"})

            except Exception as e:
                self.send_json(500, {"success": False, "message": f"ระบบขัดข้อง: {str(e)}"})
        else:
            self.send_error(404, "Not Found")

def open_browser():
    time.sleep(1.2)
    url = f"http://localhost:{PORT}"
    print(f"กำลังเปิดหน้าต่างระบบอัปโหลดที่: {url}")
    webbrowser.open(url)

def run_server():
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, UploaderHandler)
    print("=" * 60)
    print(f"  KT Survey Pro — GitHub APK Uploader Server")
    print(f"  เปิดใช้งานบน: http://localhost:{PORT}")
    print(f"  กด Ctrl+C เพื่อหยุดการทำงาน")
    print("=" * 60)

    threading.Thread(target=open_browser, daemon=True).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nหยุดการทำงานเซิร์ฟเวอร์เรียบร้อย")
        httpd.server_close()

if __name__ == '__main__':
    run_server()
