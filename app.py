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
from urllib.parse import urlparse, unquote
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
    .badge-st {
        background-color: #312e81;
        color: #a5b4fc;
        padding: 0.3rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        border: 1px solid #4338ca;
    }
    .badge-ls {
        background-color: #701a75;
        color: #f0abfc;
        padding: 0.3rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        border: 1px solid #86198f;
    }
    .badge-vd {
        background-color: #065f46;
        color: #6ee7b7;
        padding: 0.3rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        border: 1px solid #047857;
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

# Retrieve Default Secrets
st_default_login = os.environ.get("STREAMTAPE_LOGIN", "1508538fc96ca7edcd0b")
st_default_key = os.environ.get("STREAMTAPE_KEY", "9OpkRzZj6OuawrD")
ls_default_key = os.environ.get("LULUSTREAM_KEY", "")
vd_default_key = os.environ.get("VIDARA_KEY", "")

try:
    if "STREAMTAPE_LOGIN" in st.secrets:
        st_default_login = st.secrets["STREAMTAPE_LOGIN"]
    if "STREAMTAPE_KEY" in st.secrets:
        st_default_key = st.secrets["STREAMTAPE_KEY"]
    if "LULUSTREAM_KEY" in st.secrets:
        ls_default_key = st.secrets["LULUSTREAM_KEY"]
    if "VIDARA_KEY" in st.secrets:
        vd_default_key = st.secrets["VIDARA_KEY"]
except Exception:
    pass

# Header Section
st.markdown("""
<div class="hero-container">
    <div class="hero-title">⚡ MagToMP Cloud Video Hub</div>
    <div class="hero-sub">Mirror torrent magnets & Seedr/Direct HTTP links directly to Streamtape, LuluStream & Vidara.</div>
    <div class="badge-container">
        <span class="badge">🧲 Magnet & 🔗 HTTP Direct</span>
        <span class="badge-st">🚀 Streamtape</span>
        <span class="badge-ls">🟣 LuluStream</span>
        <span class="badge-vd">🟢 Vidara.so</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Sidebar Settings
with st.sidebar:
    st.header("⚡ Cloud Video Host Accounts")
    
    st.subheader("1. Streamtape Account")
    st_login = st.text_input("Streamtape API Login", value=st_default_login, type="default", placeholder="e.g. 1508538fc...")
    st_key = st.text_input("Streamtape API Key", value=st_default_key, type="password", placeholder="e.g. 9OpkRzZ...")
    if st_login and st_key:
        st.success("✅ Streamtape Connected")
        
    st.markdown("---")
    st.subheader("2. LuluStream Account")
    ls_key = st.text_input("LuluStream API Key", value=ls_default_key, type="password", placeholder="e.g. 45e38snhs9wa0unhv")
    if ls_key:
        st.success("✅ LuluStream Connected")
        
    st.markdown("---")
    st.subheader("3. Vidara.so Account")
    vd_key = st.text_input("Vidara.so API Key", value=vd_default_key, type="password", placeholder="e.g. 106616nzdp9q106rynvzm0")
    if vd_key:
        st.success("✅ Vidara Connected")
        
    st.markdown("---")
    st.markdown("Created with ❤️ by **[webbusiness4](https://github.com/webbusiness4/magtomp)**")

# Input Section
link_input = st.text_area(
    "Paste Magnet Link or Direct Download URL (Seedr, Debrid, Web)",
    placeholder="Paste magnet:?xt=urn:btih:... OR https://rd22.seedr.cc/ff_get/.../video.mp4...",
    height=110,
    help="Supports both torrent magnet links AND direct HTTP/HTTPS video URLs (Seedr, Real-Debrid, direct mp4 links)."
)

# Upload Destination Selection
available_destinations = ["Streamtape", "LuluStream", "Vidara.so"]
default_selected = []
if st_login and st_key:
    default_selected.append("Streamtape")
if ls_key:
    default_selected.append("LuluStream")
if vd_key:
    default_selected.append("Vidara.so")

if not default_selected:
    default_selected = ["Streamtape"]

selected_destinations = st.multiselect(
    "Select Upload Destination(s):",
    available_destinations,
    default=default_selected
)

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

def upload_to_streamtape(file_path: str, custom_filename: str, login: str, key: str, job_dict):
    """Uploads directly to Streamtape with live MB tracking."""
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
        headers = {"Content-Type": monitor.content_type}
        upload_res = requests.post(upload_url, data=monitor, headers=headers, timeout=3600).json()

    if upload_res.get("status") == 200:
        return upload_res["result"]["url"]
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
            "file": (custom_filename, f, "video/mp4"),
            "file_title": custom_filename
        })
        monitor = MultipartEncoderMonitor(encoder, on_ls_progress)
        headers = {"Content-Type": monitor.content_type}
        upload_res = requests.post(upload_server_url, data=monitor, headers=headers, timeout=3600).json()

    if upload_res.get("status") == 200 and upload_res.get("files"):
        file_code = upload_res["files"][0].get("filecode")
        view_url = f"https://lulustream.com/{file_code}"
        return view_url
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
            "api_key": api_key,
            "file": (custom_filename, f, "video/mp4"),
            "title": custom_filename
        })
        monitor = MultipartEncoderMonitor(encoder, on_vd_progress)
        headers = {"Content-Type": monitor.content_type}
        upload_res = requests.post(upload_server_url, data=monitor, headers=headers, timeout=3600).json()

    if upload_res.get("url"):
        return upload_res["url"]
    elif upload_res.get("filecode"):
        return f"https://vidara.so/v/{upload_res['filecode']}"
    else:
        raise Exception(f"Vidara upload failed: {upload_res}")

def background_worker_task(job_id: str, input_url: str, targets: list, st_creds: tuple, ls_key: str, vd_key: str):
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
    
    # 1. Download via aria2c (Handles both torrent magnets AND direct HTTP/HTTPS URLs with 16 connections!)
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
    else:
        # Extract suggested filename from HTTP URL path
        parsed_url = urlparse(input_url)
        path_name = os.path.basename(unquote(parsed_url.path))
        out_opt = [f"--out={path_name}"] if path_name else []
        
        job["message"] = f"📥 Step 1/3: Downloading direct file at Gigabit speed... (5%)"
        cmd_aria = [
            "aria2c",
            "--max-connection-per-server=16",
            "--split=16",
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
            match = re.search(r'\((\d+)%\)', line)
            if match:
                dl_pct = int(match.group(1))
                overall_pct = int(5 + (dl_pct * 0.45))
                if overall_pct > last_pct:
                    last_pct = overall_pct
                    job["progress"] = overall_pct
                    job["message"] = f"📥 Step 1/3: Downloading Data ({dl_pct}% downloaded | {overall_pct}% total)"
        
        proc.wait()
        if proc.returncode != 0:
            job["status"] = "error"
            job["error"] = "Download failed on cloud server. Verify the URL is valid and accessible."
            cleanup_workspace([work_dir, converted_dir])
            return
            
    except Exception as e:
        job["status"] = "error"
        job["error"] = f"Download error: {str(e)}"
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
        job["status"] = "error"
        job["error"] = "No valid video stream found in the downloaded file."
        cleanup_workspace([work_dir, converted_dir])
        return

    largest_video = max(all_videos, key=os.path.getsize)
    original_raw_name = os.path.basename(largest_video)
    
    base_title, _ = os.path.splitext(original_raw_name)
    target_filename = f"{base_title}.mp4"
    output_mp4 = os.path.join(converted_dir, target_filename)
    
    job["filename"] = target_filename
    job["progress"] = 62
    job["message"] = f"🎬 Step 2/3: Processing '{original_raw_name}' ➔ '{target_filename}' (62%)"
    
    if largest_video.endswith(".mp4"):
        shutil.copyfile(largest_video, output_mp4)
    else:
        cmd_ffmpeg = [
            "ffmpeg", "-y",
            "-i", largest_video,
            "-c:v", "copy",
            "-c:a", "aac",
            output_mp4
        ]
        subprocess.run(cmd_ffmpeg, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
    file_size_mb = round(os.path.getsize(output_mp4) / (1024 * 1024), 2)
    job["size_mb"] = file_size_mb
    job["progress"] = 70
    job["message"] = f"✅ Step 2/3: MP4 Ready: '{target_filename}' ({file_size_mb} MB) (70%)"
    time.sleep(0.5)

    # 3. Upload to Selected Destinations
    try:
        # Streamtape
        if "Streamtape" in targets and st_creds[0] and st_creds[1]:
            job["progress"] = 75
            job["message"] = f"🚀 Step 3/3: Uploading to Streamtape ({file_size_mb} MB)..."
            st_url = upload_to_streamtape(output_mp4, target_filename, st_creds[0], st_creds[1], job)
            job["streamtape_url"] = st_url

        # LuluStream
        if "LuluStream" in targets and ls_key:
            job["progress"] = 82
            job["message"] = f"🟣 Step 3/3: Uploading to LuluStream ({file_size_mb} MB)..."
            ls_url = upload_to_lulustream(output_mp4, target_filename, ls_key, job)
            job["lulustream_url"] = ls_url

        # Vidara.so
        if "Vidara.so" in targets and vd_key:
            job["progress"] = 90
            job["message"] = f"🟢 Step 3/3: Uploading to Vidara.so ({file_size_mb} MB)..."
            vd_url = upload_to_vidara(output_mp4, target_filename, vd_key, job)
            job["vidara_url"] = vd_url

        job["progress"] = 100
        job["status"] = "completed"
        job["message"] = f"🎉 Successfully converted & mirrored '{target_filename}' ({file_size_mb} MB)!"

    except Exception as e:
        job["status"] = "error"
        job["error"] = f"Upload error: {str(e)}"
    finally:
        cleanup_workspace([work_dir, converted_dir])

# Action Trigger Buttons
col1, col2 = st.columns([4, 1])
with col1:
    convert_clicked = st.button("🚀 Convert & Mirror to Selected Hosts")
with col2:
    if st.button("Clear / Reset"):
        st.session_state.current_job_id = None
        st.rerun()

if convert_clicked:
    clean_input = link_input.strip()
    
    if not clean_input:
        st.warning("⚠️ Please paste a magnet link or direct HTTP/HTTPS video URL into the box above.")
    elif not (clean_input.startswith("magnet:?") or clean_input.startswith("http://") or clean_input.startswith("https://")):
        st.error("⚠️ Invalid format. Input must be a `magnet:?` link or a direct `https://` / `http://` URL.")
    elif not selected_destinations:
        st.error("⚠️ Please select at least one upload destination (Streamtape, LuluStream, or Vidara).")
    else:
        if "Streamtape" in selected_destinations and (not st_login or not st_key):
            st.error("⚠️ Please enter Streamtape Login and Key in the sidebar.")
        elif "LuluStream" in selected_destinations and not ls_key:
            st.error("⚠️ Please enter your LuluStream API Key in the sidebar.")
        elif "Vidara.so" in selected_destinations and not vd_key:
            st.error("⚠️ Please enter your Vidara.so API Key in the sidebar.")
        else:
            job_id = hashlib.md5(clean_input.encode()).hexdigest()[:10]
            st.session_state.current_job_id = job_id
            
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
                    "error": ""
                }
                thread = threading.Thread(
                    target=background_worker_task,
                    args=(
                        job_id,
                        clean_input,
                        selected_destinations,
                        (st_login.strip(), st_key.strip()),
                        ls_key.strip(),
                        vd_key.strip()
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
        st.markdown("### 🔄 Cloud Processing Status")
        
        progress_bar = st.progress(job["progress"], text=f"{job['message']}")
        
        if job["status"] == "running" or job["status"] == "starting":
            st.info(f"⏳ {job['message']}")
            st.caption("📱 **Phone Safe:** You can minimize this tab, lock your screen, or switch apps. The cloud server continues in the background.")
            time.sleep(2)
            st.rerun()
            
        elif job["status"] == "completed":
            st.balloons()
            st.success(f"🎉 **Video Conversion & Multi-Host Mirroring Ready!**")
            st.markdown(f"**Exact File Title:** `{job['filename']}` | **Size:** `{job['size_mb']} MB`")
            
            # Streamtape Card
            if job.get("streamtape_url"):
                st.markdown("#### 🚀 Streamtape Video Link:")
                st.code(job["streamtape_url"], language="text")
                st.markdown(f"👉 [**▶️ Open on Streamtape**]({job['streamtape_url']})")
                
            # LuluStream Card
            if job.get("lulustream_url"):
                st.markdown("#### 🟣 LuluStream Video Link:")
                st.code(job["lulustream_url"], language="text")
                st.markdown(f"👉 [**▶️ Open on LuluStream**]({job['lulustream_url']})")

            # Vidara Card
            if job.get("vidara_url"):
                st.markdown("#### 🟢 Vidara.so Video Link:")
                st.code(job["vidara_url"], language="text")
                st.markdown(f"👉 [**▶️ Open on Vidara.so**]({job['vidara_url']})")
            
        elif job["status"] == "error":
            st.error(f"❌ Error: {job.get('error', 'Unknown cloud processing error')}")

# Footer / Instructions
st.markdown("---")
with st.expander("ℹ️ Supported Inputs & Video Hosts"):
    st.markdown("""
    - **Dual Input Protocol:** Supports both BitTorrent `magnet:?` links AND direct HTTP/HTTPS download links (Seedr, Real-Debrid, Alldebrid, Web direct `.mp4`/`.mkv` URLs).
    - **16-Stream Fast Download:** `aria2c` downloads both torrents and HTTP files with 16 parallel chunks at Gigabit datacenter speeds.
    - **Multi-Host Mirroring:** Automatically mirrors to Streamtape, LuluStream, and Vidara.so in one go!
    """)