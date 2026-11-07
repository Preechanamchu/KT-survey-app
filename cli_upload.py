#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KT Survey Pro — Quick CLI APK Uploader
สคริปต์อัปโหลด APK ขึ้น GitHub ผ่าน Command Line หรือลากไฟล์มาวางบนไฟล์ .bat
"""

import os
import sys
import json
import re
import urllib.request
import urllib.error
import urllib.parse

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

def save_config(cfg):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def make_request(url, method='GET', headers=None, data=None):
    if headers is None:
        headers = {}
    headers.setdefault('User-Agent', 'KTSurvey-CliUploader/1.0')
    headers.setdefault('Accept', 'application/vnd.github.v3+json')
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8')
        try:
            err_json = json.loads(err_body)
        except Exception:
            err_json = {"message": err_body}
        return e.code, err_json
    except Exception as e:
        return 500, {"message": str(e)}

def main():
    print("=" * 60)
    print("  KT Survey Pro — Quick APK Uploader")
    print("=" * 60)

    # 1. Check APK argument
    apk_path = None
    if len(sys.argv) > 1:
        apk_path = sys.argv[1].strip('"\'')
    else:
        # Search parent directory for latest apk
        parent = os.path.dirname(BASE_DIR)
        candidates = [os.path.join(parent, f) for f in os.listdir(parent) if f.lower().endswith('.apk')]
        if candidates:
            candidates.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            apk_path = candidates[0]
            print(f"[*] พบไฟล์ APK ล่าสุดอัตโนมัติ: {os.path.basename(apk_path)}")

    if not apk_path or not os.path.exists(apk_path):
        print("[!] ไม่พบไฟล์ APK ที่ต้องการอัปโหลด กรุณาระบุพาธไฟล์ เช่น:")
        print("    python cli_upload.py ../KT-SurveyPlus-v0.0.92.apk")
        input("\nกด Enter เพื่อออก...")
        return

    apk_filename = os.path.basename(apk_path)
    file_size_mb = os.path.getsize(apk_path) / (1024 * 1024)
    print(f"[*] ไฟล์ที่เลือก: {apk_filename} ({file_size_mb:.2f} MB)")

    # 2. Extract tag from filename
    tag_match = re.search(r'v?(\d+\.\d+\.\d+)', apk_filename, re.I)
    default_tag = f"v{tag_match.group(1)}" if tag_match else "v1.0.0"

    cfg = load_config()
    owner = cfg.get('owner', '').strip()
    repo = cfg.get('repo', '').strip()
    token = cfg.get('token', '').strip()

    if not owner or not repo or not token:
        print("\n[!] กรุณาตั้งค่าข้อมูล GitHub:")
        if not owner:
            owner = input("  GitHub Owner (เช่น your-username): ").strip()
        if not repo:
            repo = input("  Repository Name (เช่น kt-survey-app): ").strip()
        if not token:
            token = input("  Personal Access Token (PAT): ").strip()
        cfg['owner'] = owner
        cfg['repo'] = repo
        cfg['token'] = token
        save_config(cfg)

    tag = input(f"\nระบุ Tag Name [{default_tag}]: ").strip() or default_tag
    title = f"KT Survey Plus {tag} - อัปเดตล่าสุด"
    notes = f"### รายการอัปเดต ({tag})\n- ปรับปรุงประสิทธิภาพและความเสถียรของแอปพลิเคชัน\n- ปรับปรุงฟังก์ชันการใช้งานล่าสุด"

    cfg['last_tag'] = tag
    save_config(cfg)

    print(f"\n[*] กำลังเชื่อมต่อไปยัง GitHub ({owner}/{repo})...")
    headers = {
        'Authorization': f"Bearer {token}",
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'KTSurvey-CliUploader/1.0'
    }

    # Step 1: Check existing release
    rel_url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}"
    code, rel_obj = make_request(rel_url, headers=headers)

    upload_url = None
    if code == 200:
        print(f"[*] พบ Release {tag} อยู่แล้ว กำลังเตรียมอัปเดตไฟล์ Asset...")
        upload_url = rel_obj.get('upload_url')
        for asset in rel_obj.get('assets', []):
            if asset.get('name') == apk_filename:
                del_url = f"https://api.github.com/repos/{owner}/{repo}/releases/assets/{asset.get('id')}"
                print(f"[*] ลบ Asset เก่าที่ชื่อซ้ำ ({apk_filename})...")
                make_request(del_url, method='DELETE', headers=headers)
    else:
        print(f"[*] กำลังสร้าง Release ใหม่ ({tag})...")
        create_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
        payload = json.dumps({
            "tag_name": tag,
            "name": title,
            "body": notes,
            "draft": False,
            "prerelease": False
        }).encode('utf-8')
        c_headers = headers.copy()
        c_headers['Content-Type'] = 'application/json'
        code, rel_obj = make_request(create_url, method='POST', headers=c_headers, data=payload)
        if code not in [200, 201]:
            print(f"[!] สร้าง Release ไม่สำเร็จ: {rel_obj.get('message', f'HTTP {code}')}")
            input("\nกด Enter เพื่อออก...")
            return
        upload_url = rel_obj.get('upload_url')

    # Step 2: Upload APK
    print(f"[*] กำลังอัปโหลดไฟล์ APK ({file_size_mb:.2f} MB)... กรุณารอสักครู่")
    with open(apk_path, 'rb') as f:
        apk_bytes = f.read()

    clean_upload_url = upload_url.split('{')[0]
    target_upload_url = f"{clean_upload_url}?name={urllib.parse.quote(apk_filename)}"
    u_headers = {
        'Authorization': f"Bearer {token}",
        'Content-Type': 'application/vnd.android.package-archive',
        'Content-Length': str(len(apk_bytes)),
        'User-Agent': 'KTSurvey-CliUploader/1.0'
    }

    code, asset_obj = make_request(target_upload_url, method='POST', headers=u_headers, data=apk_bytes)
    if code in [200, 201]:
        print("\n" + "=" * 60)
        print("  🎉 อัปโหลดไฟล์ APK ขึ้น GitHub สำเร็จเรียบร้อย!")
        print("=" * 60)
        print(f"  Tag:           {tag}")
        print(f"  Repository:    {owner}/{repo}")
        print(f"  Release URL:   {rel_obj.get('html_url')}")
        print(f"  Download URL:  {asset_obj.get('browser_download_url')}")
        print("=" * 60)
        print(f"\n[+] คำแนะนำสำหรับมือถือ:")
        print(f"    ให้ผู้ใช้งานเปิดแอป ➔ ไปที่แท็บ 'ผู้ใช้' ➔ กดปุ่ม 'อัพเดทแอป'")
        print(f"    (ตรวจสอบให้แน่ใจว่าคลังในแอปตั้งเป็น: {owner}/{repo})")
    else:
        print(f"\n[!] อัปโหลดไฟล์ไม่สำเร็จ: {asset_obj.get('message', f'HTTP {code}')}")

    input("\nกด Enter เพื่อเสร็จสิ้น...")

if __name__ == '__main__':
    main()
