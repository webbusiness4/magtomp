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
            
    # 2. Direct HTTP / Seedr URLs
    elif url.startswith(("http://", "https://")):
        try:
            path = urlsplit(url).path
            filename = os.path.basename(unquote(path))
            if filename:
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

# Header Section
st.markdown("""
<div class="hero-container">
    <div class="hero-title">⚡ MagToMP ➔ Streamtape & Supabase Hub</div>
    <div class="hero-sub">Auto-convert torrents/Seedr links, upload to Streamtape, and auto-insert title & embed_url into Supabase.</div>
    <div class="badge-container">
        <span class="badge-st">🎬 Streamtape /e/ Auto-Upload</span>
        <span class="badge-sb">⚡ Supabase 'streams' Auto-Publish</span>
        <span class="badge">🚀 1-Click Fully Automated</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Sidebar Settings
with st.sidebar:
    st.header("⚡ Database & Account Settings")
    
    st.subheader("1. Supabase Database ('streams' Table)")
    sb_url = st.text_input("Supabase Project URL", value=sb_default_url, placeholder="https://xxxx.supabase.co")
    sb_key = st.text_input("Supabase API Key", value=sb_default_key, type="password", placeholder="eyJhbGciOi...")
    sb_table = st.text_input("Table Name", value=sb_default_table, placeholder="streams")
    
    if sb_url and sb_key:
        st.success("✅ Supabase Connected")
        
    st.markdown("---")
    st.subheader("2. Streamtape Account")
    st_login = st.text_input("Streamtape API Login", value=st_default_login, type="default")
    st_key = st.text_input("Streamtape API Key", value=st_default_key, type="password")
    if st_login and st_key:
        st.success("✅ Streamtape Connected")
    
    st.markdown("---")
    st.markdown("Created with ❤️ by **[webbusiness4](https://github.com/webbusiness4/magtomp)**")

# Initialize Form Session State for Auto-Title
if "input_url_prev" not in st.session_state:
    st.session_state.input_url_prev = ""
if "form_title" not in st.session_state:
    st.session_state.form_title = ""

# Main Input Section
link_input = st.text_area(
    "Paste Magnet Link or Direct Video URL (Seedr, Debrid, Web)",
    placeholder="Paste magnet:?xt=urn:btih:... OR https://rd22.seedr.cc/ff_get/.../video.mp4...",
    height=100,
    help="Supports both torrent magnet links AND direct HTTP/HTTPS video URLs."
)

# Detect if URL changed to auto-extract title
if link_input.strip() != st.session_state.input_url_prev:
    st.session_state.input_url_prev = link_input.strip()
    detected = extract_auto_title(link_input.strip())
    if detected:
        st.session_state.form_title = detected

# Auto-Detected Title (Editable if user wants to tweak it)
user_title = st.text_input(
    "Video Title (Auto-Detected)",
    value=st.session_state.form_title,
    placeholder="Auto-detected from link (e.g. Emilie Knows How To Take Charge)",
    help="Automatically filled from your link. Sent as 'title' and auto-generates 'slug' in Supabase."
)

# Optional Extra Fields Expander (Collapsed by default for clean 1-click UX)
with st.expander("➕ Optional Extra Fields (Poster, Description)"):
    user_image = st.text_input("Poster Image URL (poster_url)", placeholder="https://example.com/poster.jpg")
    user_desc = st.text_area("Video Description (description)", placeholder="Optional description...")

push_to_supabase = st.checkbox("⚡ Auto-publish to Supabase 'streams' table on completion", value=True if sb_url and sb_key else False)

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

def background_worker_task(job_id: str, input_url: str, st_creds: tuple, supabase_config: dict):
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
    
    # 1. Download via aria2c
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

    # 3. Upload to Streamtape (Returns /e/ embed player link)
    try:
        job["progress"] = 75
        job["message"] = f"🚀 Step 3/3: Uploading to Streamtape ({file_size_mb} MB)..."
        st_url = upload_to_streamtape(output_mp4, target_filename, st_creds[0], st_creds[1], job)
        job["streamtape_url"] = st_url
    except Exception as e:
        job["status"] = "error"
        job["error"] = f"Streamtape upload error: {str(e)}"
        cleanup_workspace([work_dir, converted_dir])
        return

    # 4. Insert into Supabase ('streams' Table: title, slug, embed_url, is_stream, status)
    if supabase_config.get("enabled") and job.get("streamtape_url"):
        job["message"] = "⚡ Step 4/4: Inserting video record into Supabase 'streams' table..."
        
        meta = job.get("user_meta", {})
        final_post_title = meta.get("title") or target_filename.replace(".mp4", "")
        slug = generate_slug(final_post_title)
        
        payload = {
            "title": final_post_title,
            "slug": slug,
            "embed_url": job["streamtape_url"], # https://streamtape.com/e/XXXXX/
            "is_stream": True,
            "status": "active"
        }
        
        if meta.get("image"):
            payload["poster_url"] = meta["image"]
            payload["backdrop_url"] = meta["image"]
        if meta.get("description"):
            payload["description"] = meta["description"]
            
        success, sb_res = insert_to_supabase(
            supabase_config["url"],
            supabase_config["key"],
            supabase_config["table"],
            payload
        )
        if success:
            job["supabase_status"] = f"✅ Successfully published '{final_post_title}' to Supabase (embed_url: {job['streamtape_url']})!"
        else:
            job["supabase_status"] = f"⚠️ Supabase Warning: {sb_res}"

    job["progress"] = 100
    job["status"] = "completed"
    job["message"] = f"🎉 Successfully mirrored '{target_filename}' ({file_size_mb} MB)!"
    cleanup_workspace([work_dir, converted_dir])

# Action Trigger Buttons
col1, col2 = st.columns([4, 1])
with col1:
    convert_clicked = st.button("🚀 Convert, Upload to Streamtape & Auto-Publish to Supabase")
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
    elif not st_login or not st_key:
        st.error("⚠️ Please enter Streamtape Login and Key in the sidebar or Secrets.")
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
            "description": user_desc.strip() if 'user_desc' in locals() else "",
            "image": user_image.strip() if 'user_image' in locals() else ""
        }
        
        if job_id not in GLOBAL_STORAGE or GLOBAL_STORAGE[job_id].get("status") in ["error", "completed"]:
            GLOBAL_STORAGE[job_id] = {
                "status": "starting",
                "progress": 0,
                "message": "⚡ Starting background cloud task...",
                "filename": "",
                "size_mb": 0,
                "streamtape_url": "",
                "supabase_status": "",
                "user_meta": user_meta,
                "error": ""
            }
            thread = threading.Thread(
                target=background_worker_task,
                args=(
                    job_id,
                    clean_input,
                    (st_login.strip(), st_key.strip()),
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
            st.success(f"🎉 **Video Processed & Published to Supabase!**")
            
            meta = job.get("user_meta", {})
            st.markdown(f"**Title:** `{meta.get('title') or job['filename']}` | **Size:** `{job['size_mb']} MB`")
            
            if job.get("supabase_status"):
                if "Successfully" in job["supabase_status"]:
                    st.success(f"⚡ **Supabase 'streams':** {job['supabase_status']}")
                else:
                    st.warning(f"{job['supabase_status']}")
            
            # Streamtape Card
            if job.get("streamtape_url"):
                st.markdown("#### 🚀 Streamtape Direct Player URL (`embed_url`):")
                st.code(job["streamtape_url"], language="text")
                st.markdown(f"👉 [**▶️ Open Streamtape Player**]({job['streamtape_url']})")
                
        elif job["status"] == "error":
            st.error(f"❌ Error: {job.get('error', 'Unknown cloud processing error')}")

# Footer / Instructions
st.markdown("---")
with st.expander("ℹ️ How Automated Publishing Works"):
    st.markdown("""
    - **1-Click Automatic Pipeline:** Paste your link and click Convert. The app extracts the `title`, generates the `slug`, uploads to Streamtape, and inserts `title`, `slug`, and `embed_url` directly into your Supabase `streams` table!
    """)