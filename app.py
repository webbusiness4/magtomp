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
    .preview-card {
        background-color: #131d31;
        border: 1px solid #1e293b;
        border-radius: 16px;
        padding: 1.5rem;
        margin-top: 1.5rem;
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
sb_default_url = os.environ.get("SUPABASE_URL", "")
sb_default_key = os.environ.get("SUPABASE_KEY", "")
sb_default_table = os.environ.get("SUPABASE_TABLE", "videos")

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
    if "SUPABASE_KEY" in st.secrets:
        sb_default_key = st.secrets["SUPABASE_KEY"]
    if "SUPABASE_TABLE" in st.secrets:
        sb_default_table = st.secrets["SUPABASE_TABLE"]
except Exception:
    pass

# Header Section
st.markdown("""
<div class="hero-container">
    <div class="hero-title">⚡ MagToMP ➔ Streamtape & Supabase Hub</div>
    <div class="hero-sub">Convert magnet/Seedr links to MP4, upload to Streamtape, and publish metadata directly to your Supabase database.</div>
    <div class="badge-container">
        <span class="badge-sb">⚡ Direct Supabase Push</span>
        <span class="badge-st">🚀 Streamtape Direct</span>
        <span class="badge">📝 Manual Metadata Form</span>
        <span class="badge">💻 Zero PC Bandwidth</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Sidebar Settings
with st.sidebar:
    st.header("⚡ Database & Account Settings")
    
    st.subheader("1. Supabase Database")
    sb_url = st.text_input("Supabase Project URL", value=sb_default_url, placeholder="https://xxxx.supabase.co")
    sb_key = st.text_input("Supabase API Key (service_role or anon)", value=sb_default_key, type="password", placeholder="eyJhbGciOi...")
    sb_table = st.text_input("Table Name", value=sb_default_table, placeholder="videos")
    
    with st.expander("⚙️ Supabase Column Mapping"):
        col_title = st.text_input("Title Column", value="title")
        col_desc = st.text_input("Description Column", value="description")
        col_tags = st.text_input("Tags Column", value="tags")
        col_image = st.text_input("Image / Poster Column", value="image")
        col_video = st.text_input("Video URL Column", value="video_url")
        
    if sb_url and sb_key:
        st.success("✅ Supabase Configured")
        
    st.markdown("---")
    st.subheader("2. Streamtape Account")
    st_login = st.text_input("Streamtape API Login", value=st_default_login, type="default")
    st_key = st.text_input("Streamtape API Key", value=st_default_key, type="password")
    
    st.markdown("---")
    st.subheader("3. Secondary Hosts (Optional)")
    ls_key = st.text_input("LuluStream API Key", value=ls_default_key, type="password")
    vd_key = st.text_input("Vidara.so API Key", value=vd_default_key, type="password")
    
    st.markdown("---")
    st.markdown("Created with ❤️ by **[webbusiness4](https://github.com/webbusiness4/magtomp)**")

# Main Form
st.markdown("### 1. 📥 Video Source")
link_input = st.text_area(
    "Magnet Link or Direct Video URL (Seedr, Debrid, Web)",
    placeholder="magnet:?xt=urn:btih:... OR https://rd22.seedr.cc/ff_get/.../video.mp4...",
    height=90,
    help="Paste any torrent magnet link or direct HTTP video URL."
)

st.markdown("### 2. 📝 Manual Video Details (Pushed to Supabase)")
col_t1, col_t2 = st.columns([2, 1])
with col_t1:
    user_title = st.text_input("Video Title", placeholder="e.g. Emilie Knows How To Take Charge (2026)")
with col_t2:
    user_tags = st.text_input("Tags (Comma-separated)", placeholder="e.g. 1080p, HD, Series")

user_image = st.text_input("Poster / Thumbnail Image URL", placeholder="e.g. https://example.com/posters/movie.jpg")
user_desc = st.text_area("Video Description", placeholder="e.g. Full 1080p high-definition video release with complete scenes and audio.", height=80)

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
        headers = {"Content-Type": monitor.content_type, "User-Agent": "Mozilla/5.0"}
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
            "api_key": api_key,
            "file": (custom_filename, f, "video/mp4"),
            "file_title": custom_filename
        })
        monitor = MultipartEncoderMonitor(encoder, on_ls_progress)
        headers = {"Content-Type": monitor.content_type, "User-Agent": "Mozilla/5.0"}
        upload_res = requests.post(upload_server_url, data=monitor, headers=headers, timeout=3600).json()

    if upload_res.get("status") == 200 and upload_res.get("files"):
        file_code = upload_res["files"][0].get("filecode")
        return f"https://lulustream.com/{file_code}"
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

    if upload_res.get("url"):
        return upload_res["url"]
    elif upload_res.get("filecode"):
        return f"https://vidara.so/v/{upload_res['filecode']}"
    elif upload_res.get("result", {}).get("url"):
        return upload_res["result"]["url"]
    elif upload_res.get("result", {}).get("filecode"):
        return f"https://vidara.so/v/{upload_res['result']['filecode']}"
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
    
    # 1. Download via aria2c (16 parallel connections)
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
            job["error"] = "Download failed on cloud server. Verify the URL/Magnet is accessible."
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
    
    # Priority for title: User custom title if provided, otherwise parsed torrent title
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

    # 3. Fault-Tolerant Multi-Host Uploads
    upload_errors = []
    
    # Streamtape
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

    # 4. Insert into Supabase (if enabled)
    if supabase_config.get("enabled") and job.get("streamtape_url"):
        job["message"] = "⚡ Step 4/4: Inserting video record into Supabase Database..."
        
        # Prepare payload matching user columns
        cols = supabase_config.get("cols", {})
        meta = job.get("user_meta", {})
        
        # Process tags (list or string)
        raw_tags = meta.get("tags", "")
        parsed_tags = [t.strip() for t in raw_tags.split(",") if t.strip()] if raw_tags else []
        
        payload = {
            cols.get("title", "title"): meta.get("title") or target_filename,
            cols.get("description", "description"): meta.get("description") or "",
            cols.get("tags", "tags"): parsed_tags if parsed_tags else raw_tags,
            cols.get("image", "image"): meta.get("image") or "",
            cols.get("video_url", "video_url"): job["streamtape_url"]
        }
        
        success, sb_res = insert_to_supabase(
            supabase_config["url"],
            supabase_config["key"],
            supabase_config["table"],
            payload
        )
        if success:
            job["supabase_status"] = "✅ Successfully inserted record into Supabase Database!"
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
                "table": sb_table.strip() if sb_table else "videos",
                "cols": {
                    "title": col_title.strip() if 'col_title' in locals() else "title",
                    "description": col_desc.strip() if 'col_desc' in locals() else "description",
                    "tags": col_tags.strip() if 'col_tags' in locals() else "tags",
                    "image": col_image.strip() if 'col_image' in locals() else "image",
                    "video_url": col_video.strip() if 'col_video' in locals() else "video_url"
                }
            }
            
            user_meta = {
                "title": user_title.strip(),
                "description": user_desc.strip(),
                "tags": user_tags.strip(),
                "image": user_image.strip()
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
                    st.success(f"⚡ **Supabase Database:** {job['supabase_status']}")
                else:
                    st.warning(f"{job['supabase_status']}")
            
            # Streamtape Card
            if job.get("streamtape_url"):
                st.markdown("#### 🚀 Streamtape Direct Video Link:")
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
                
            # Display Image Preview if user provided
            if meta.get("image"):
                st.markdown("#### 🖼️ Poster Preview:")
                st.image(meta["image"], width=300)
                
            if job.get("error"):
                st.warning(f"⚠️ Note: {job['error']}")
            
        elif job["status"] == "error":
            st.error(f"❌ Error: {job.get('error', 'Unknown cloud processing error')}")

# Footer / Instructions
st.markdown("---")
with st.expander("ℹ️ How To Configure Supabase Direct Publishing"):
    st.markdown("""
    1. In the sidebar on the left, enter your **Supabase Project URL** (e.g. `https://xyz.supabase.co`) and **API Key** (`service_role` or `anon`).
    2. Set your **Table Name** (e.g. `videos`).
    3. Fill in your manual **Title**, **Description**, **Tags**, and **Poster Image URL** in the form.
    4. When you click **Convert, Upload & Publish**, MagToMP uploads the video to Streamtape, gets the direct link, and automatically inserts the full row into your Supabase database table so it appears on your Vercel website immediately!
    """)