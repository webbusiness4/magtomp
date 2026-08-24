import os
import sys
import argparse
import subprocess
import glob
import shutil
import requests
import re
import time
import urllib.parse
from urllib.parse import urlparse, unquote, urlsplit, parse_qs
from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor

def generate_slug(title: str) -> str:
    """Generates a clean URL slug from title."""
    s = re.sub(r'[^a-zA-Z0-9\s-]', '', title.lower()).strip()
    s = re.sub(r'[\s-]+', '-', s)
    if not s:
        s = f"stream-{int(time.time())}"
    return s

def extract_auto_title(url: str) -> str:
    """Extracts and cleans the original video title automatically from magnet or direct HTTP URL."""
    if not url:
        return ""
    url = url.strip()
    
    # 1. Magnet Links
    if url.startswith("magnet:?"):
        try:
            qs = parse_qs(urlsplit(url).query)
            dn = qs.get("dn", [""])[0]
            if dn:
                raw_name = unquote(dn)
                base, _ = os.path.splitext(raw_name)
                return base.replace(".", " ").replace("_", " ").strip()
        except Exception:
            pass
            
    # 2. Direct HTTP / Seedr / PikPak / CDN URLs
    elif url.startswith(("http://", "https://")):
        try:
            path = urlsplit(url).path
            filename = os.path.basename(unquote(path))
            if filename and any(filename.lower().endswith(ext) for ext in [".mp4", ".mkv", ".avi", ".ts", ".mov", ".webm", ".m4v", ".flv", ".zip", ".rar"]):
                base, _ = os.path.splitext(filename)
                return base.replace(".", " ").replace("_", " ").strip()
            
            try:
                head_res = requests.get(url, stream=True, timeout=4, headers={"User-Agent": "Mozilla/5.0"})
                cd = head_res.headers.get("Content-Disposition", "")
                head_res.close()
                if cd:
                    match = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';\r\n]+)["\']?', cd, re.IGNORECASE)
                    if match:
                        raw_fn = unquote(match.group(1).strip())
                        base, _ = os.path.splitext(raw_fn)
                        clean = base.replace(".", " ").replace("_", " ").strip()
                        if clean:
                            return clean
            except Exception:
                pass
                
            if filename and filename.lower() not in ["download", "get", "view", "index.html", ""]:
                base, _ = os.path.splitext(filename)
                return base.replace(".", " ").replace("_", " ").strip()
        except Exception:
            pass
            
    return ""

def cleanup_workspace(dirs_to_clean):
    for d in dirs_to_clean:
        if os.path.exists(d):
            if os.path.isdir(d):
                shutil.rmtree(d, ignore_errors=True)
            else:
                try:
                    os.remove(d)
                except Exception:
                    pass

def insert_to_supabase(sb_url, sb_key, sb_table, payload):
    endpoint = f"{sb_url.rstrip('/')}/rest/v1/{sb_table}"
    headers = {
        "apikey": sb_key,
        "Authorization": f"Bearer {sb_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    res = requests.post(endpoint, json=payload, headers=headers, timeout=15)
    if res.status_code in [200, 201]:
        return True, res.json()
    else:
        return False, f"Supabase Error ({res.status_code}): {res.text}"

def upload_to_streamtape(file_path: str, custom_filename: str, login: str, key: str):
    print(f"🚀 Getting upload URL from Streamtape for '{custom_filename}'...")
    url_req = f"https://api.streamtape.com/file/ul?login={login}&key={key}"
    res = requests.get(url_req, timeout=15).json()
    if res.get("status") != 200:
        raise Exception(f"Streamtape API Error: {res.get('msg')}")
    
    upload_url = res["result"]["url"]
    file_size = os.path.getsize(file_path)
    file_size_mb = round(file_size / (1024 * 1024), 2)
    last_reported_pct = -1

    def on_progress(monitor):
        nonlocal last_reported_pct
        up_bytes = monitor.bytes_read
        up_mb = round(up_bytes / (1024 * 1024), 2)
        upload_pct = min(100, int((up_bytes / file_size) * 100)) if file_size > 0 else 0
        if upload_pct >= last_reported_pct + 5 or upload_pct == 100:
            last_reported_pct = upload_pct
            print(f"   [Upload] {up_mb} MB / {file_size_mb} MB ({upload_pct}%)")

    with open(file_path, "rb") as f:
        encoder = MultipartEncoder(fields={"file": (custom_filename, f, "video/mp4")})
        monitor = MultipartEncoderMonitor(encoder, on_progress)
        headers = {"Content-Type": monitor.content_type, "User-Agent": "Mozilla/5.0"}
        upload_res = requests.post(upload_url, data=monitor, headers=headers, timeout=3600).json()

    if upload_res.get("status") == 200:
        raw_url = upload_res["result"]["url"]
        match = re.search(r'/v/([a-zA-Z0-9_-]+)', raw_url)
        if match:
            filecode = match.group(1)
            return f"https://streamtape.com/e/{filecode}/"
        return raw_url
    else:
        raise Exception(f"Streamtape upload error: {upload_res.get('msg')}")

def write_github_summary(title, streamtape_url, slug, supabase_res, file_size_mb):
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file and os.path.exists(os.path.dirname(summary_file)):
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(f"## 🎉 Video Published Successfully!\n\n")
            f.write(f"- **Title:** `{title}`\n")
            f.write(f"- **File Size:** `{file_size_mb} MB`\n")
            f.write(f"- **Streamtape Player Link:** [{streamtape_url}]({streamtape_url})\n")
            f.write(f"- **Supabase Status:** {supabase_res}\n\n")
            f.write(f"### Embed Link\n")
            f.write(f"`{streamtape_url}`\n")

def write_github_error(err_title, err_detail):
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file and os.path.exists(os.path.dirname(summary_file)):
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(f"## ❌ Job Failed: {err_title}\n\n")
            f.write(f"```text\n{err_detail}\n```\n\n")
            f.write(f"👉 **Tip:** If using PikPak, check that the link has not expired. If using Magnet, pass it through Seedr.cc for instant Gigabit cloud transfer.\n")

def main():
    parser = argparse.ArgumentParser(description="Headless MagToMP Video Worker for GitHub Actions")
    parser.add_argument("--url", default="", help="Magnet Link or Direct Video URL")
    parser.add_argument("--title", default="", help="Custom Video Title")
    parser.add_argument("--poster", default="", help="Poster Image URL")
    parser.add_argument("--tags", default="", help="Comma-separated tags (stored in cast_members)")
    parser.add_argument("--desc", default="", help="Video Description")
    parser.add_argument("--st-login", default="")
    parser.add_argument("--st-key", default="")
    parser.add_argument("--sb-url", default="")
    parser.add_argument("--sb-key", default="")
    parser.add_argument("--sb-table", default="")

    args = parser.parse_args()

    input_url = (args.url or os.environ.get("INPUT_URL") or "").strip()
    if not input_url:
        msg = "No video URL provided! Pass --url or set INPUT_URL environment variable."
        print(f"❌ Error: {msg}")
        write_github_error("Missing URL", msg)
        sys.exit(1)

    custom_title = (args.title or os.environ.get("INPUT_TITLE") or "").strip()
    custom_poster = (args.poster or os.environ.get("INPUT_POSTER") or "").strip()
    custom_tags = (args.tags or os.environ.get("INPUT_TAGS") or "").strip()
    custom_desc = (args.desc or os.environ.get("INPUT_DESC") or "").strip()

    st_login = (args.st_login or os.environ.get("STREAMTAPE_LOGIN") or "1508538fc96ca7edcd0b").strip()
    if not st_login:
        st_login = "1508538fc96ca7edcd0b"
    st_key = (args.st_key or os.environ.get("STREAMTAPE_KEY") or "9OpkRzZj6OuawrD").strip()
    if not st_key:
        st_key = "9OpkRzZj6OuawrD"

    sb_url = (args.sb_url or os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or "").strip()
    sb_key = (args.sb_key or os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY") or "").strip()
    sb_table = (args.sb_table or os.environ.get("SUPABASE_TABLE") or "streams").strip()
    if not sb_table:
        sb_table = "streams"

PUBLIC_TRACKERS = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.stealth.si:80/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://tracker.bittor.pw:1337/announce",
    "udp://public.popcorn-tracker.org:6969/announce",
    "udp://tracker.dler.org:6969/announce",
    "udp://exodus.desync.com:6969/announce",
    "udp://open.demonii.com:1337/announce",
    "http://tracker.openbittorrent.com:80/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
    "udp://opentracker.i2p.rocks:6969/announce",
    "udp://tracker.moeking.me:6969/announce"
]

def boost_magnet_link(magnet: str) -> str:
    """Automatically appends active high-speed public trackers to magnet links."""
    if not magnet.startswith("magnet:?"):
        return magnet
    existing_trackers = set()
    try:
        qs = parse_qs(urlsplit(magnet).query)
        existing_trackers = set(qs.get("tr", []))
    except Exception:
        pass
    
    new_tr = [f"tr={urllib.parse.quote(tr, safe='')}" for tr in PUBLIC_TRACKERS if tr not in existing_trackers]
    if new_tr:
        sep = "&" if "?" in magnet else "?"
        return magnet + sep + "&".join(new_tr)
    return magnet

    work_dir = "./worker_downloads"
    converted_dir = "./worker_converted"

    cleanup_workspace([work_dir, converted_dir])
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(converted_dir, exist_ok=True)

    is_magnet = input_url.startswith("magnet:?")

    print("=" * 60)
    print("🎬 MagToMP GitHub Actions Worker Started")
    print("=" * 60)

    # 1. Download
    print("📥 Step 1/3: Downloading Video Stream...")
    download_success = False

    if is_magnet:
        boosted_magnet = boost_magnet_link(input_url)
        print("⚡ Injected live BitTorrent trackers for accelerated peer discovery.")
        cmd_aria = [
            "aria2c",
            "--seed-time=0",
            "--max-connection-per-server=16",
            "--split=16",
            "--enable-dht=true",
            "--enable-peer-exchange=true",
            "--bt-enable-lpd=true",
            "--bt-max-peers=120",
            "--bt-tracker-connect-timeout=5",
            "--bt-tracker-timeout=5",
            "--file-allocation=none",
            "--summary-interval=2",
            f"--dir={work_dir}",
            boosted_magnet
        ]
        res = subprocess.run(cmd_aria)
        if res.returncode == 0:
            download_success = True
    else:
        parsed_url = urlparse(input_url)
        path_name = os.path.basename(unquote(parsed_url.path))
        has_ext = bool(re.search(r'\.[a-zA-Z0-9]{2,4}$', path_name)) and path_name.lower() not in ["download", "get", "view"]
        out_opt = [f"--out={path_name}"] if has_ext else []

        cmd_aria = [
            "aria2c",
            "--check-certificate=false",
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "--max-connection-per-server=8",
            "--split=8",
            "--summary-interval=2",
            f"--dir={work_dir}"
        ] + out_opt + [input_url]

        res = subprocess.run(cmd_aria)
        if res.returncode == 0:
            download_success = True
        else:
            print("⚠️ aria2 direct download failed; attempting Python streaming fallback...")
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                with requests.get(input_url, headers=headers, stream=True, timeout=30) as r:
                    if r.status_code == 200:
                        cd = r.headers.get("Content-Disposition", "")
                        match = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';\r\n]+)["\']?', cd, re.IGNORECASE)
                        fn = unquote(match.group(1).strip()) if match else (path_name if has_ext else "video.mp4")
                        if not any(fn.lower().endswith(ext) for ext in [".mp4", ".mkv", ".avi", ".ts", ".mov", ".webm", ".m4v"]):
                            fn = f"{fn}.mp4"
                        target_file_path = os.path.join(work_dir, fn)
                        total_bytes = int(r.headers.get("Content-Length", 0))
                        downloaded = 0
                        with open(target_file_path, "wb") as f_out:
                            for chunk in r.iter_content(chunk_size=1024 * 1024 * 4): # 4MB chunks
                                if chunk:
                                    f_out.write(chunk)
                                    downloaded += len(chunk)
                                    if total_bytes > 0:
                                        print(f"   [Stream] {round(downloaded/(1024*1024), 1)} MB / {round(total_bytes/(1024*1024), 1)} MB", end="\r")
                        print("\n✅ Stream download finished.")
                        download_success = True
            except Exception as ex:
                print(f"❌ Fallback stream error: {ex}")

    if not download_success:
        err_msg = "Download failed. Check if the URL/Magnet is active and accessible."
        print(f"❌ Error: {err_msg}")
        write_github_error("Download Failed", err_msg)
        cleanup_workspace([work_dir, converted_dir])
        sys.exit(1)

    print("✅ Step 1/3: Download Complete.")

    # 2. Remuxing
    print("🎬 Step 2/3: Inspecting & Remuxing Video...")
    media_exts = ("*.mkv", "*.avi", "*.mp4", "*.ts", "*.mov", "*.webm", "*.m4v", "*.flv")
    all_videos = []
    for ext in media_exts:
        all_videos.extend(glob.glob(f"{work_dir}/**/{ext}", recursive=True))

    if not all_videos:
        for root, _, files in os.walk(work_dir):
            for f in files:
                if not f.endswith(".aria2"):
                    fp = os.path.join(root, f)
                    if os.path.getsize(fp) > 1024 * 1024:
                        all_videos.append(fp)

    if not all_videos:
        err_msg = "No valid video file found in the downloaded archive/file."
        print(f"❌ Error: {err_msg}")
        write_github_error("No Media Found", err_msg)
        cleanup_workspace([work_dir, converted_dir])
        sys.exit(1)

    largest_video = max(all_videos, key=os.path.getsize)
    orig_name = os.path.basename(largest_video)

    final_title = custom_title if custom_title else extract_auto_title(input_url)
    if not final_title:
        base_t, _ = os.path.splitext(orig_name)
        final_title = base_t.replace(".", " ").replace("_", " ").strip()

    target_filename = f"{final_title}.mp4"
    output_mp4 = os.path.join(converted_dir, target_filename)

    print(f"   Target: '{target_filename}'")
    if largest_video.endswith(".mp4"):
        shutil.move(largest_video, output_mp4)
    else:
        cmd_fast = [
            "ffmpeg", "-y",
            "-i", largest_video,
            "-map", "0:v:0",
            "-map", "0:a:0?",
            "-c", "copy",
            "-sn",
            output_mp4
        ]
        res = subprocess.run(cmd_fast, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode != 0 or not os.path.exists(output_mp4) or os.path.getsize(output_mp4) == 0:
            cmd_fallback = [
                "ffmpeg", "-y",
                "-i", largest_video,
                "-map", "0:v:0",
                "-map", "0:a:0?",
                "-c:v", "copy",
                "-c:a", "aac",
                "-sn",
                output_mp4
            ]
            subprocess.run(cmd_fallback, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    file_size_mb = round(os.path.getsize(output_mp4) / (1024 * 1024), 2)
    print(f"✅ Step 2/3: MP4 Ready ({file_size_mb} MB).")

    # 3. Streamtape Upload
    print("🚀 Step 3/3: Uploading to Streamtape...")
    try:
        st_url = upload_to_streamtape(output_mp4, target_filename, st_login, st_key)
        print(f"🎉 Streamtape Player Link: {st_url}")
    except Exception as ex:
        err_msg = f"Streamtape upload failed: {str(ex)}"
        print(f"❌ Error: {err_msg}")
        write_github_error("Streamtape Upload Error", err_msg)
        cleanup_workspace([work_dir, converted_dir])
        sys.exit(1)

    # 4. Supabase Publish
    sb_status_msg = "Skipped (No credentials)"
    if sb_url and sb_key:
        print("⚡ Step 4/4: Inserting record into Supabase 'streams' table...")
        slug = generate_slug(final_title)
        payload = {
            "title": final_title,
            "slug": slug,
            "embed_url": st_url,
            "poster_url": custom_poster,
            "backdrop_url": None,
            "description": custom_desc,
            "cast_members": custom_tags,
            "is_stream": True,
            "status": "published"
        }
        success, sb_res = insert_to_supabase(sb_url, sb_key, sb_table, payload)
        if success:
            sb_status_msg = f"✅ Published to Supabase (Slug: {slug})"
            print(f"   {sb_status_msg}")
        else:
            sb_status_msg = f"⚠️ Supabase Error: {sb_res}"
            print(f"   {sb_status_msg}")

    write_github_summary(final_title, st_url, generate_slug(final_title), sb_status_msg, file_size_mb)
    cleanup_workspace([work_dir, converted_dir])

    print("=" * 60)
    print("🎉 ALL STEPS COMPLETED SUCCESSFULLY!")
    print(f"👉 Player Link: {st_url}")
    print("=" * 60)

if __name__ == "__main__":
    main()
