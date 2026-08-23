import streamlit as st
import subprocess
import os
import glob
import shutil
import requests
import re
import time
import threading
import hashlib
import urllib.parse
from urllib.parse import urlparse, unquote, urlsplit, parse_qs
from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor

# Page Configuration
st.set_page_config(
    page_title="MagToMP - Cloud Video Hub",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS for Premium UI
st.markdown("""
<style>
    .stApp {
        background-color: #0b0f19;
        color: #f1f5f9;
    }
    .hero-container {
        text-align: center;
        padding: 1.5rem 0 1rem 0;
    }
    .hero-title {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .hero-sub {
        color: #94a3b8;
        font-size: 1rem;
        margin-bottom: 1.2rem;
    }
    .badge-container {
        display: flex;
        justify-content: center;
        gap: 0.5rem;
        margin-bottom: 1.5rem;
        flex-wrap: wrap;
    }
    .badge {
        background-color: #1e293b;
        color: #38bdf8;
        padding: 0.3rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        border: 1px solid #334155;
    }
    .badge-sb {
        background-color: #064e3b;
        color: #34d399;
        padding: 0.3rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        border: 1px solid #059669;
    }
    .badge-st {
        background-color: #312e81;
        color: #a5b4fc;
        padding: 0.3rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        border: 1px solid #4338ca;
    }
    .badge-auto {
        background-color: #78350f;
        color: #fde68a;
        padding: 0.3rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        border: 1px solid #b45309;
    }
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 3.2rem;
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        color: white;
        font-weight: 700;
        font-size: 1.05rem;
        border: none;
        box-shadow: 0 4px 14px 0 rgba(99, 102, 241, 0.39);
        transition: all 0.2s ease-in-out;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(99, 102, 241, 0.6);
    }
</style>
""", unsafe_allow_html=True)

# Global Server-Side Job Manager
@st.cache_resource
def get_global_job_storage():
    return {}

GLOBAL_STORAGE = get_global_job_storage()

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
            # If filename has a recognizable media extension
            if filename and any(filename.lower().endswith(ext) for ext in [".mp4", ".mkv", ".avi", ".ts", ".mov", ".webm", ".m4v", ".flv", ".zip", ".rar"]):
                base, _ = os.path.splitext(filename)
                return base.replace(".", " ").replace("_", " ").strip()
            
            # Dynamic / CDN query-based URLs (PikPak, Debrid, Drive): Inspect Content-Disposition header
            try:
                head_res = requests.get(url, stream=True, timeout=3.5, headers={"User-Agent": "Mozilla/5.0"})
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

# Retrieve Default Secrets & Aliases
st_default_login = os.environ.get("STREAMTAPE_LOGIN", "1508538fc96ca7edcd0b")
st_default_key = os.environ.get("STREAMTAPE_KEY", "9OpkRzZj6OuawrD")
ls_default_key = os.environ.get("LULUSTREAM_KEY", "")
vd_default_key = os.environ.get("VIDARA_KEY", "")
sb_default_url = os.environ.get("SUPABASE_URL", os.environ.get("NEXT_PUBLIC_SUPABASE_URL", ""))
sb_default_key = os.environ.get("SUPABASE_KEY", os.environ.get("SUPABASE_SERVICE_ROLE_KEY", os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")))
sb_default_table = os.environ.get("SUPABASE_TABLE", "streams")

try:
    if "STREAMTAPE_LOGIN" in st.secrets:
        st_default_login = st.secrets["STREAMTAPE_LOGIN"]
    if "STREAMTAPE_KEY" in st.secrets:
        st_default_key = st.secrets["STREAMTAPE_KEY"]
    if "LULUSTREAM_KEY" in st.secrets:
        ls_default_key = st.secrets["LULUSTREAM_KEY"]
    if "VIDARA_KEY" in st.secrets:
        vd_default_key = st.secrets["VIDARA_KEY"]
        
    if "SUPABASE_URL" in st.secrets:
        sb_default_url = st.secrets["SUPABASE_URL"]
    elif "NEXT_PUBLIC_SUPABASE_URL" in st.secrets:
        sb_default_url = st.secrets["NEXT_PUBLIC_SUPABASE_URL"]

    if "SUPABASE_KEY" in st.secrets:
        sb_default_key = st.secrets["SUPABASE_KEY"]
    elif "SUPABASE_SERVICE_ROLE_KEY" in st.secrets:
        sb_default_key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
    elif "NEXT_PUBLIC_SUPABASE_ANON_KEY" in st.secrets:
        sb_default_key = st.secrets["NEXT_PUBLIC_SUPABASE_ANON_KEY"]
        
    if "SUPABASE_TABLE" in st.secrets:
        sb_default_table = st.secrets["SUPABASE_TABLE"]
except Exception:
    pass


# Sidebar Settings
with st.sidebar:
    st.header("⚡ Database & Account Settings")
    
    st.subheader("1. Supabase Database ('streams' Table)")
    sb_url = st.text_input("Supabase Project URL", value=sb_default_url, placeholder="https://xxxx.supabase.co")
    sb_key = st.text_input("Supabase API Key (service_role or anon)", value=sb_default_key, type="password", placeholder="eyJhbGciOi...")
    sb_table = st.text_input("Table Name", value=sb_default_table, placeholder="streams")
    
    if sb_url and sb_key:
        st.success("✅ Supabase Configured")
        
    st.markdown("---")
    st.subheader("2. Streamtape Account")
    st_login = st.text_input("Streamtape API Login", value=st_default_login, type="default")
    st_key = st.text_input("Streamtape API Key", value=st_default_key, type="password")
    if st_login and st_key:
        st.success("✅ Streamtape Connected")
        
    st.markdown("---")
    st.subheader("3. Secondary Hosts (Optional)")
    ls_key = st.text_input("LuluStream API Key", value=ls_default_key, type="password")
    vd_key = st.text_input("Vidara.so API Key", value=vd_default_key, type="password")
    
    st.markdown("---")
    st.markdown("Created with ❤️ by **[webbusiness4](https://github.com/webbusiness4/magtomp)**")

# Initialize Form Session State for Auto-Title
if "input_url_prev" not in st.session_state:
    st.session_state.input_url_prev = ""
if "form_title" not in st.session_state:
    st.session_state.form_title = ""

# Main Form
st.markdown("### 1. 📥 Video Source")
link_input = st.text_area(
    "Paste Magnet Link or Direct Video URL (Seedr, Debrid, Web)",
    placeholder="Paste magnet:?xt=urn:btih:... OR https://rd22.seedr.cc/ff_get/.../video.mp4...",
    height=90,
    help="Supports both torrent magnet links AND direct HTTP/HTTPS video URLs."
)

# Detect if URL changed to auto-extract title
if link_input.strip() != st.session_state.input_url_prev:
    st.session_state.input_url_prev = link_input.strip()
    detected = extract_auto_title(link_input.strip())
    if detected:
        st.session_state.form_title = detected

st.markdown("### 2. 📝 Video Details (Pushed to Supabase 'streams')")

# 1. Full-Width Video Title (title & slug)
user_title = st.text_input(
    "Video Title (Auto-Detected from Link)",
    value=st.session_state.form_title,
    placeholder="e.g. Emilie Knows How To Take Charge (2026)",
    help="Automatically detected from your magnet or Seedr URL. Mapped to 'title' and generates 'slug'."
)

# 2. Full-Width Poster Image URL (poster_url)
user_image = st.text_input(
    "Poster Image URL (poster_url)",
    placeholder="e.g. https://example.com/posters/movie.jpg",
    help="Direct link to the video poster image. (backdrop_url remains empty)."
)

# 3. Full-Width Description (description)
user_desc = st.text_area(
    "Video Description (description)",
    placeholder="e.g. Full 1080p high-definition video release with complete scenes and audio.",
    height=90,
    help="Mapped to 'description' column in Supabase."
)

# 4. Full-Width Tags (Mapped to cast_members column in Supabase)
user_tags = st.text_area(
    "Tags (Comma-separated ➔ Saved to 'cast_members')",
    placeholder="e.g. AssParade, 26, 08, 17, Lucky, Kay, XXX, 1080p",
    height=70,
    help="Comma-separated keywords/tags. Directly saved into your 'cast_members' column in Supabase!"
)

# Upload Destination Selection
available_destinations = ["Streamtape"]
if ls_key:
    available_destinations.append("LuluStream")
if vd_key:
    available_destinations.append("Vidara.so")

selected_destinations = st.multiselect(
    "Upload Video To:",
    available_destinations,
    default=["Streamtape"]
)

push_to_supabase = st.checkbox("⚡ Automatically insert record into Supabase Database on completion", value=True if sb_url and sb_key else False)

def cleanup_workspace(dirs_to_clean):
    """Safely cleans up temporary download files."""
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
    """Inserts record into Supabase via REST API."""
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

def upload_to_streamtape(file_path: str, custom_filename: str, login: str, key: str, job_dict):
    """Uploads directly to Streamtape and returns the /e/ direct player URL with live MB tracking."""
    url_req = f"https://api.streamtape.com/file/ul?login={login}&key={key}"
    res = requests.get(url_req, timeout=15).json()
    if res.get("status") != 200:
        raise Exception(f"Streamtape API Error: {res.get('msg')}")
    
    upload_url = res["result"]["url"]
    file_size = os.path.getsize(file_path)
    file_size_mb = round(file_size / (1024 * 1024), 2)

    def on_progress(monitor):
        up_bytes = monitor.bytes_read
        up_mb = round(up_bytes / (1024 * 1024), 2)
        rem_mb = round(max(0.0, file_size_mb - up_mb), 2)
        upload_pct = min(100, int((up_bytes / file_size) * 100)) if file_size > 0 else 0
        job_dict["message"] = f"🚀 Uploading to Streamtape: {up_mb} MB / {file_size_mb} MB • Remaining: {rem_mb} MB ({upload_pct}%)"

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

def upload_to_lulustream(file_path: str, custom_filename: str, api_key: str, job_dict):
    """Uploads directly to LuluStream with live MB tracking."""
    srv_req = f"https://lulustream.com/api/upload/server?key={api_key}"
    srv_res = requests.get(srv_req, timeout=15).json()
    if srv_res.get("status") != 200:
        raise Exception(f"LuluStream Server Error: {srv_res.get('msg')}")
        
    upload_server_url = srv_res.get("result")
    file_size = os.path.getsize(file_path)
    file_size_mb = round(file_size / (1024 * 1024), 2)

    def on_ls_progress(monitor):
        up_bytes = monitor.bytes_read
        up_mb = round(up_bytes / (1024 * 1024), 2)
        rem_mb = round(max(0.0, file_size_mb - up_mb), 2)
        upload_pct = min(100, int((up_bytes / file_size) * 100)) if file_size > 0 else 0
        job_dict["message"] = f"🟣 Uploading to LuluStream: {up_mb} MB / {file_size_mb} MB • Remaining: {rem_mb} MB ({upload_pct}%)"

    with open(file_path, "rb") as f:
        encoder = MultipartEncoder(fields={
            "key": api_key,
            "api_key": api_key,
            "file": (custom_filename, f, "video/mp4"),
            "file_title": custom_filename
        })
        monitor = MultipartEncoderMonitor(encoder, on_ls_progress)
        headers = {"Content-Type": monitor.content_type, "User-Agent": "Mozilla/5.0"}
        upload_res = requests.post(upload_server_url, data=monitor, headers=headers, timeout=3600).json()

    if upload_res.get("status") == 200 and upload_res.get("files"):
        file_code = upload_res["files"][0].get("filecode")
        return f"https://lulustream.com/e/{file_code}"
    else:
        raise Exception(f"LuluStream upload failed: {upload_res}")

def upload_to_vidara(file_path: str, custom_filename: str, api_key: str, job_dict):
    """Uploads directly to Vidara.so with live MB tracking."""
    srv_req = f"https://api.vidara.so/v1/upload/server?api_key={api_key}"
    srv_res = requests.get(srv_req, timeout=15).json()
    if srv_res.get("status") != 200 or not srv_res.get("result", {}).get("upload_server"):
        raise Exception(f"Vidara Server Error: {srv_res.get('msg')}")
        
    upload_server_url = srv_res["result"]["upload_server"]
    file_size = os.path.getsize(file_path)
    file_size_mb = round(file_size / (1024 * 1024), 2)

    def on_vd_progress(monitor):
        up_bytes = monitor.bytes_read
        up_mb = round(up_bytes / (1024 * 1024), 2)
        rem_mb = round(max(0.0, file_size_mb - up_mb), 2)
        upload_pct = min(100, int((up_bytes / file_size) * 100)) if file_size > 0 else 0
        job_dict["message"] = f"🟢 Uploading to Vidara: {up_mb} MB / {file_size_mb} MB • Remaining: {rem_mb} MB ({upload_pct}%)"

    with open(file_path, "rb") as f:
        encoder = MultipartEncoder(fields={
            "key": api_key,
            "api_key": api_key,
            "file": (custom_filename, f, "video/mp4"),
            "title": custom_filename,
            "file_title": custom_filename
        })
        monitor = MultipartEncoderMonitor(encoder, on_vd_progress)
        headers = {"Content-Type": monitor.content_type, "User-Agent": "Mozilla/5.0"}
        upload_res = requests.post(upload_server_url, data=monitor, headers=headers, timeout=3600).json()

    if upload_res.get("filecode"):
        return f"https://vidara.so/e/{upload_res['filecode']}"
    elif upload_res.get("url"):
        return upload_res["url"]
    elif upload_res.get("result", {}).get("filecode"):
        return f"https://vidara.so/e/{upload_res['result']['filecode']}"
    else:
        err_msg = upload_res.get("error") or upload_res.get("msg") or upload_res
        raise Exception(f"Vidara error: {err_msg}")

def background_worker_task(job_id: str, input_url: str, targets: list, st_creds: tuple, ls_key: str, vd_key: str, supabase_config: dict):
    """Executes the complete pipeline in a detached background thread."""
    work_dir = f"./cloud_downloads_{job_id}"
    converted_dir = f"./converted_{job_id}"
    
    cleanup_workspace([work_dir, converted_dir])
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(converted_dir, exist_ok=True)
    
    job = GLOBAL_STORAGE[job_id]
    job["status"] = "running"
    job["progress"] = 5
    
    is_magnet = input_url.startswith("magnet:?")
    
    # 1. Download via aria2c or direct Python stream
    download_success = False
    download_error_log = []

    if is_magnet:
        job["message"] = "📥 Step 1/3: Downloading torrent in cloud at Gigabit speed... (5%)"
        cmd_aria = [
            "aria2c",
            "--seed-time=0",
            "--max-connection-per-server=16",
            "--split=16",
            "--summary-interval=1",
            f"--dir={work_dir}",
            input_url
        ]
        try:
            proc = subprocess.Popen(
                cmd_aria,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            last_pct = 5
            for line in proc.stdout:
                download_error_log.append(line.strip())
                if len(download_error_log) > 15:
                    download_error_log.pop(0)
                match = re.search(r'\((\d+)%\)', line)
                if match:
                    dl_pct = int(match.group(1))
                    overall_pct = int(5 + (dl_pct * 0.45))
                    if overall_pct > last_pct:
                        last_pct = overall_pct
                        job["progress"] = overall_pct
                        job["message"] = f"📥 Step 1/3: Downloading Torrent ({dl_pct}% downloaded | {overall_pct}% total)"
            proc.wait()
            if proc.returncode == 0:
                download_success = True
        except Exception as e:
            download_error_log.append(str(e))
    else:
        # Direct HTTP / Seedr / PikPak / Debrid URL
        job["message"] = "📥 Step 1/3: Connecting to direct video stream... (5%)"
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
            "--summary-interval=1",
            f"--dir={work_dir}"
        ] + out_opt + [input_url]

        try:
            proc = subprocess.Popen(
                cmd_aria,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            last_pct = 5
            for line in proc.stdout:
                download_error_log.append(line.strip())
                if len(download_error_log) > 15:
                    download_error_log.pop(0)
                match = re.search(r'\((\d+)%\)', line)
                if match:
                    dl_pct = int(match.group(1))
                    overall_pct = int(5 + (dl_pct * 0.45))
                    if overall_pct > last_pct:
                        last_pct = overall_pct
                        job["progress"] = overall_pct
                        job["message"] = f"📥 Step 1/3: Downloading Data ({dl_pct}% downloaded | {overall_pct}% total)"
            proc.wait()
            if proc.returncode == 0:
                download_success = True
        except Exception as e:
            download_error_log.append(str(e))

        # Direct Python Stream Fallback if aria2 failed on direct HTTP URL
        if not download_success:
            try:
                job["message"] = "📥 Step 1/3: Downloading via Cloud Stream Pipeline... (10%)"
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
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
                        last_pct = 10
                        with open(target_file_path, "wb") as f_out:
                            for chunk in r.iter_content(chunk_size=1024 * 1024 * 2): # 2MB chunks
                                if chunk:
                                    f_out.write(chunk)
                                    downloaded += len(chunk)
                                    if total_bytes > 0:
                                        dl_pct = int((downloaded / total_bytes) * 100)
                                        overall_pct = int(5 + (dl_pct * 0.45))
                                        if overall_pct > last_pct:
                                            last_pct = overall_pct
                                            job["progress"] = overall_pct
                                            dl_mb = round(downloaded / (1024 * 1024), 1)
                                            tot_mb = round(total_bytes / (1024 * 1024), 1)
                                            job["message"] = f"📥 Step 1/3: Streaming Data: {dl_mb} MB / {tot_mb} MB ({dl_pct}%)"
                        download_success = True
                    else:
                        download_error_log.append(f"HTTP Error {r.status_code}: {r.reason}")
            except Exception as ex:
                download_error_log.append(f"Stream error: {str(ex)}")

    if not download_success:
        job["status"] = "error"
        err_detail = " | ".join([l for l in download_error_log if l])[-200:]
        job["error"] = f"Download failed: {err_detail if err_detail else 'Link was inaccessible or expired.'}"
        cleanup_workspace([work_dir, converted_dir])
        return

    job["progress"] = 50
    job["message"] = "✅ Step 1/3: Cloud Download Completed! (50%)"
    time.sleep(0.5)

    # 2. Locate & Remux Video
    job["progress"] = 55
    job["message"] = "🎬 Step 2/3: Inspecting media codecs & remuxing container (55%)..."
    
    media_exts = ("*.mkv", "*.avi", "*.mp4", "*.ts", "*.mov", "*.webm", "*.m4v", "*.flv")
    all_videos = []
    for ext in media_exts:
        all_videos.extend(glob.glob(f"{work_dir}/**/{ext}", recursive=True))

    if not all_videos:
        # Fallback: scan all non-aria2 files > 1MB in work_dir
        candidates = []
        for root, _, files in os.walk(work_dir):
            for f in files:
                if not f.endswith(".aria2"):
                    full_p = os.path.join(root, f)
                    try:
                        if os.path.getsize(full_p) > 1024 * 1024:
                            candidates.append(full_p)
                    except Exception:
                        pass
        if candidates:
            all_videos = candidates

    if not all_videos:
        job["status"] = "error"
        job["error"] = "No valid video stream found in the downloaded file."
        cleanup_workspace([work_dir, converted_dir])
        return

    largest_video = max(all_videos, key=os.path.getsize)
    original_raw_name = os.path.basename(largest_video)
    
    if job.get("user_meta", {}).get("title"):
        clean_user_title = job["user_meta"]["title"].strip()
        target_filename = f"{clean_user_title}.mp4"
    else:
        base_title, _ = os.path.splitext(original_raw_name)
        target_filename = f"{base_title}.mp4"
        
    output_mp4 = os.path.join(converted_dir, target_filename)
    job["filename"] = target_filename
    job["progress"] = 62
    job["message"] = f"🎬 Step 2/3: Processing '{target_filename}' (62%)"
    
    if largest_video.endswith(".mp4"):
        shutil.move(largest_video, output_mp4)
    else:
        # 1. Instantaneous direct stream copy (-map main video/audio, strip incompatible subtitles)
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
        
        # 2. Fall back to AAC audio transcoding only if -c copy fails
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
    job["size_mb"] = file_size_mb
    job["progress"] = 70
    job["message"] = f"✅ Step 2/3: MP4 Ready: '{target_filename}' ({file_size_mb} MB) (70%)"
    time.sleep(0.5)

    # 3. Fault-Tolerant Multi-Host Uploads
    upload_errors = []
    
    # Streamtape (Returns /e/ embed player link)
    if "Streamtape" in targets and st_creds[0] and st_creds[1]:
        try:
            job["progress"] = 75
            job["message"] = f"🚀 Step 3/3: Uploading to Streamtape ({file_size_mb} MB)..."
            st_url = upload_to_streamtape(output_mp4, target_filename, st_creds[0], st_creds[1], job)
            job["streamtape_url"] = st_url
        except Exception as e:
            upload_errors.append(f"Streamtape: {str(e)}")

    # LuluStream
    if "LuluStream" in targets and ls_key:
        try:
            job["progress"] = 82
            job["message"] = f"🟣 Step 3/3: Uploading to LuluStream ({file_size_mb} MB)..."
            ls_url = upload_to_lulustream(output_mp4, target_filename, ls_key, job)
            job["lulustream_url"] = ls_url
        except Exception as e:
            upload_errors.append(f"LuluStream: {str(e)}")

    # Vidara.so
    if "Vidara.so" in targets and vd_key:
        try:
            job["progress"] = 90
            job["message"] = f"🟢 Step 3/3: Uploading to Vidara.so ({file_size_mb} MB)..."
            vd_url = upload_to_vidara(output_mp4, target_filename, vd_key, job)
            job["vidara_url"] = vd_url
        except Exception as e:
            upload_errors.append(f"Vidara.so: {str(e)}")

    # 4. Insert into Supabase ('streams' Table: backdrop_url kept empty)
    if supabase_config.get("enabled") and job.get("streamtape_url"):
        job["message"] = "⚡ Step 4/4: Inserting video record into Supabase 'streams' table..."
        
        meta = job.get("user_meta", {})
        final_post_title = meta.get("title") or target_filename.replace(".mp4", "")
        slug = generate_slug(final_post_title)
        
        # Build exact 'streams' row payload with empty backdrop_url
        payload = {
            "title": final_post_title,
            "slug": slug,
            "embed_url": job["streamtape_url"], # https://streamtape.com/e/XXXXX/
            "poster_url": meta.get("image") or "",
            "backdrop_url": None, # Kept strictly empty
            "description": meta.get("description") or "",
            "cast_members": meta.get("tags") or "",  # Exactly saved to cast_members column!
            "is_stream": True,
            "status": "published"
        }
            
        success, sb_res = insert_to_supabase(
            supabase_config["url"],
            supabase_config["key"],
            supabase_config["table"],
            payload
        )
        if success:
            job["supabase_status"] = f"✅ Successfully published '{final_post_title}' to Supabase (Slug: {slug})!"
        else:
            job["supabase_status"] = f"⚠️ Supabase Warning: {sb_res}"

    job["progress"] = 100
    
    if job.get("streamtape_url") or job.get("lulustream_url") or job.get("vidara_url"):
        job["status"] = "completed"
        if upload_errors:
            job["error"] = " | ".join(upload_errors)
        job["message"] = f"🎉 Successfully mirrored '{target_filename}' ({file_size_mb} MB)!"
    else:
        job["status"] = "error"
        job["error"] = " | ".join(upload_errors) if upload_errors else "All destination uploads failed."
        
    cleanup_workspace([work_dir, converted_dir])

# Action Trigger Buttons
col1, col2 = st.columns([4, 1])
with col1:
    convert_clicked = st.button("🚀 Convert, Upload & Publish to Supabase")
with col2:
    if st.button("Clear / Reset"):
        st.session_state.current_job_id = None
        st.session_state.form_title = ""
        st.session_state.input_url_prev = ""
        st.rerun()

if convert_clicked:
    clean_input = link_input.strip()
    
    if not clean_input:
        st.warning("⚠️ Please paste a magnet link or direct video URL above.")
    elif not (clean_input.startswith("magnet:?") or clean_input.startswith("http://") or clean_input.startswith("https://")):
        st.error("⚠️ Invalid format. Input must be a `magnet:?` link or direct `https://` / `http://` URL.")
    elif not selected_destinations:
        st.error("⚠️ Please select at least one upload destination.")
    else:
        if "Streamtape" in selected_destinations and (not st_login or not st_key):
            st.error("⚠️ Please enter Streamtape Login and Key in the sidebar.")
        else:
            job_id = hashlib.md5(clean_input.encode()).hexdigest()[:10]
            st.session_state.current_job_id = job_id
            
            sb_config = {
                "enabled": push_to_supabase and bool(sb_url and sb_key),
                "url": sb_url.strip() if sb_url else "",
                "key": sb_key.strip() if sb_key else "",
                "table": sb_table.strip() if sb_table else "streams"
            }
            
            final_title = user_title.strip() if user_title.strip() else extract_auto_title(clean_input)
            
            user_meta = {
                "title": final_title,
                "description": user_desc.strip(),
                "image": user_image.strip(),
                "tags": user_tags.strip() # Saved to cast_members
            }
            
            if job_id not in GLOBAL_STORAGE or GLOBAL_STORAGE[job_id].get("status") in ["error", "completed"]:
                GLOBAL_STORAGE[job_id] = {
                    "status": "starting",
                    "progress": 0,
                    "message": "⚡ Starting background cloud task...",
                    "filename": "",
                    "size_mb": 0,
                    "streamtape_url": "",
                    "lulustream_url": "",
                    "vidara_url": "",
                    "supabase_status": "",
                    "user_meta": user_meta,
                    "error": ""
                }
                thread = threading.Thread(
                    target=background_worker_task,
                    args=(
                        job_id,
                        clean_input,
                        selected_destinations,
                        (st_login.strip(), st_key.strip()),
                        ls_key.strip() if ls_key else "",
                        vd_key.strip() if vd_key else "",
                        sb_config
                    ),
                    daemon=True
                )
                thread.start()
                
            st.rerun()

# Real-Time Live Job Monitor
if "current_job_id" in st.session_state and st.session_state.current_job_id:
    active_id = st.session_state.current_job_id
    if active_id in GLOBAL_STORAGE:
        job = GLOBAL_STORAGE[active_id]
        
        st.markdown("---")
        st.markdown("### 🔄 Cloud Processing & Publishing Status")
        
        progress_bar = st.progress(job["progress"], text=f"{job['message']}")
        
        if job["status"] == "running" or job["status"] == "starting":
            st.info(f"⏳ {job['message']}")
            st.caption("📱 **Phone Safe:** You can minimize this tab, lock your screen, or switch apps. The cloud server continues in the background.")
            time.sleep(2)
            st.rerun()
            
        elif job["status"] == "completed":
            st.balloons()
            st.success(f"🎉 **Video Processed & Published Successfully!**")
            
            meta = job.get("user_meta", {})
            st.markdown(f"**Title:** `{meta.get('title') or job['filename']}` | **Size:** `{job['size_mb']} MB`")
            
            if job.get("supabase_status"):
                if "Successfully" in job["supabase_status"]:
                    st.success(f"⚡ **Supabase 'streams':** {job['supabase_status']}")
                else:
                    st.warning(f"{job['supabase_status']}")
            
            # Streamtape Card
            if job.get("streamtape_url"):
                st.markdown("#### 🚀 Streamtape Player Link (`embed_url`):")
                st.code(job["streamtape_url"], language="text")
                st.markdown(f"👉 [**▶️ Open Streamtape Player**]({job['streamtape_url']})")
                
            # LuluStream Card
            if job.get("lulustream_url"):
                st.markdown("#### 🟣 LuluStream Direct Player Link:")
                st.code(job["lulustream_url"], language="text")
                st.markdown(f"👉 [**▶️ Open LuluStream Player**]({job['lulustream_url']})")

            # Vidara Card
            if job.get("vidara_url"):
                st.markdown("#### 🟢 Vidara.so Direct Player Link:")
                st.code(job["vidara_url"], language="text")
                st.markdown(f"👉 [**▶️ Open Vidara Player**]({job['vidara_url']})")
                
            # Display Image Preview if user provided
            if meta.get("image"):
                st.markdown("#### 🖼️ Poster Preview (`poster_url`):")
                st.image(meta["image"], width=300)
                
            if job.get("error"):
                st.warning(f"⚠️ Note: {job['error']}")
            
        elif job["status"] == "error":
            st.error(f"❌ Error: {job.get('error', 'Unknown cloud processing error')}")

# Footer / Instructions
st.markdown("---")
with st.expander("ℹ️ How Auto-Title & Supabase Integration Works"):
    st.markdown("""
    - **✨ Automatic Title & Slug:** The app auto-extracts the title from magnet/Seedr links and generates the clean `slug` required by your Supabase table.
    - **Tags ➔ 'cast_members':** Whatever tags/keywords you enter in the Tags box are automatically saved into your Supabase `cast_members` column.
    - **`backdrop_url`:** Kept strictly empty (`null`).
    - **Streamtape Player Link (`/e/`):** Formats Streamtape uploads into `https://streamtape.com/e/Je0ZqOama0cjj89/` for instant playback.
    """)