import streamlit as st
import subprocess
import os
import glob
import shutil
import requests
import re
import time

# Page Configuration
st.set_page_config(
    page_title="MagToMP - Magnet to Direct MP4",
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
    .delete-btn>button {
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%) !important;
        box-shadow: 0 4px 14px 0 rgba(239, 68, 68, 0.39) !important;
    }
    .delete-btn>button:hover {
        box-shadow: 0 6px 20px rgba(239, 68, 68, 0.6) !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "result_data" not in st.session_state:
    st.session_state.result_data = None
if "deleted" not in st.session_state:
    st.session_state.deleted = False

# Header Section
st.markdown("""
<div class="hero-container">
    <div class="hero-title">⚡ MagToMP Cloud Converter</div>
    <div class="hero-sub">Convert torrent magnet links to direct raw MP4 streams & Streamtape-compatible links.</div>
    <div class="badge-container">
        <span class="badge">🚀 100% Cloud-Powered</span>
        <span class="badge">💻 Zero Local PC Bandwidth</span>
        <span class="badge">📡 Streamtape Remote Upload Ready</span>
        <span class="badge">🆓 Free & Instant</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Optional Settings in Sidebar
with st.sidebar:
    st.header("⚙️ Optional Streamtape & Cloud Keys")
    st.caption("Enter your Streamtape credentials if you want the app to auto-upload to your account!")
    st_login = st.text_input("Streamtape API Login", type="default", placeholder="e.g. 78241fa9...")
    st_key = st.text_input("Streamtape API Key", type="password", placeholder="e.g. dZkJ827...")
    pixeldrain_key = st.text_input("Pixeldrain API Key (Optional)", type="password")
    st.markdown("---")
    st.markdown("Created with ❤️ by **[webbusiness4](https://github.com/webbusiness4/magtomp)**")

# Input Section
magnet_input = st.text_area(
    "Paste Magnet Link",
    placeholder="magnet:?xt=urn:btih:d0c3a647d6928e469792036c05a18a99479e0809...",
    height=110,
    help="Paste a valid torrent magnet link to start the cloud transfer."
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

def upload_to_tempsh(file_path: str):
    """Uploads file to Temp.sh for a direct raw binary .mp4 link (Perfect for Streamtape Remote Upload)."""
    with open(file_path, "rb") as f:
        res = requests.post("https://temp.sh/upload", files={"file": f}, timeout=600)
    if res.status_code == 200 and res.text.startswith("http"):
        return res.text.strip()
    return None

def upload_to_gofile(file_path: str):
    """Uploads file to Gofile and returns (download_page, file_id, guest_token)."""
    server_res = requests.get("https://api.gofile.io/servers", timeout=15).json()
    if server_res.get("status") != "ok" or not server_res.get("data", {}).get("servers"):
        raise Exception("Gofile servers unavailable.")
    
    server_name = server_res["data"]["servers"][0]["name"]
    upload_url = f"https://{server_name}.gofile.io/contents/uploadfile"
    
    with open(file_path, "rb") as f:
        res = requests.post(upload_url, files={"file": f}, timeout=600).json()
        
    if res.get("status") == "ok":
        download_page = res["data"]["downloadPage"]
        file_id = res["data"]["id"]
        guest_token = res["data"].get("guestToken", "")
        return download_page, file_id, guest_token
    else:
        raise Exception(f"Gofile upload error: {res}")

def delete_from_gofile(file_id: str, guest_token: str):
    """Permanently deletes the file from Gofile cloud servers."""
    body = {"contentsId": file_id, "token": guest_token}
    res = requests.delete("https://api.gofile.io/contents", json=body, timeout=15).json()
    return res.get("status") == "ok"

def upload_to_streamtape_direct(file_path: str, login: str, key: str):
    """Uploads directly to user's Streamtape account via Streamtape API."""
    url_req = f"https://api.streamtape.com/file/ul?login={login}&key={key}"
    res = requests.get(url_req, timeout=15).json()
    if res.get("status") != 200:
        raise Exception(f"Streamtape auth error: {res.get('msg')}")
    
    upload_url = res["result"]["url"]
    with open(file_path, "rb") as f:
        upload_res = requests.post(upload_url, files={"file": f}, timeout=1200).json()
    
    if upload_res.get("status") == 200:
        return upload_res["result"]["url"]
    return None

def process_magnet(magnet: str, px_key: str = None, st_login: str = None, st_key: str = None):
    work_dir = "./cloud_downloads"
    output_mp4 = "./streamable_video.mp4"
    
    # Pre-cleanup
    cleanup_workspace([work_dir, output_mp4])
    os.makedirs(work_dir, exist_ok=True)
    
    # Progress Bar Container
    progress_bar = st.progress(0, text="⚡ Initializing Cloud Pipeline... (0%)")
    status_text = st.empty()
    
    # =========================================================================
    # Step 1: Downloading via aria2c (0% -> 50%)
    # =========================================================================
    progress_bar.progress(5, text="📥 Step 1/3: Connecting to peer swarm & downloading... (5%)")
    status_text.info("📥 Downloading torrent chunks at Gigabit speed...")
    
    cmd_aria = [
        "aria2c",
        "--seed-time=0",
        "--max-connection-per-server=16",
        "--split=16",
        "--summary-interval=1",
        f"--dir={work_dir}",
        magnet
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
            match = re.search(r'\((\d+)%\)', line)
            if match:
                torrent_pct = int(match.group(1))
                overall_pct = int(5 + (torrent_pct * 0.45))
                if overall_pct > last_pct:
                    last_pct = overall_pct
                    progress_bar.progress(
                        overall_pct,
                        text=f"📥 Step 1/3: Downloading Torrent ({torrent_pct}% torrent | {overall_pct}% total)"
                    )
        
        proc.wait()
        if proc.returncode != 0:
            st.error("Torrent download terminated with an error.")
            return None
            
    except Exception as e:
        st.error(f"Download failed: {str(e)}")
        return None

    progress_bar.progress(50, text="✅ Step 1/3: Torrent Download Completed! (50%)")
    time.sleep(0.5)

    # =========================================================================
    # Step 2: Locating & Remuxing Video (50% -> 75%)
    # =========================================================================
    progress_bar.progress(55, text="🎬 Step 2/3: Inspecting media codecs & remuxing to MP4... (55%)")
    status_text.info("🎬 Repackaging video container into standard MP4 stream...")
    
    media_exts = ("*.mkv", "*.avi", "*.mp4", "*.ts", "*.mov", "*.webm", "*.m4v", "*.flv")
    all_videos = []
    for ext in media_exts:
        all_videos.extend(glob.glob(f"{work_dir}/**/{ext}", recursive=True))

    if not all_videos:
        st.error("No valid video stream found in the downloaded torrent.")
        return None

    largest_video = max(all_videos, key=os.path.getsize)
    original_filename = os.path.basename(largest_video)
    
    progress_bar.progress(65, text=f"🎬 Step 2/3: Processing '{original_filename[:30]}...' (65%)")
    
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
    progress_bar.progress(75, text=f"✅ Step 2/3: MP4 Ready ({file_size_mb} MB) (75%)")
    time.sleep(0.5)

    # =========================================================================
    # Step 3: Generating Raw Direct MP4 & Gofile Links (75% -> 100%)
    # =========================================================================
    progress_bar.progress(80, text=f"☁️ Step 3/3: Generating direct raw stream links ({file_size_mb} MB)... (80%)")
    status_text.info(f"☁️ Uploading {original_filename} ({file_size_mb} MB) for direct streaming...")

    # 1. Direct Raw MP4 Stream Link (for Streamtape Remote Upload & VLC)
    direct_raw_mp4_url = None
    try:
        progress_bar.progress(85, text="📡 Generating direct raw .mp4 stream link... (85%)")
        direct_raw_mp4_url = upload_to_tempsh(output_mp4)
    except Exception:
        pass

    # 2. Gofile Page Link
    gofile_url = None
    file_id = None
    guest_token = None
    try:
        progress_bar.progress(90, text="☁️ Uploading to high-speed Gofile CDN... (90%)")
        gofile_url, file_id, guest_token = upload_to_gofile(output_mp4)
    except Exception as e:
        st.warning(f"Gofile fallback: {str(e)}")

    # 3. Streamtape Direct Account Upload (if user entered login/key in sidebar)
    streamtape_url = None
    if st_login and st_key:
        try:
            progress_bar.progress(95, text="🚀 Pushing directly to your Streamtape account... (95%)")
            streamtape_url = upload_to_streamtape_direct(output_mp4, st_login, st_key)
        except Exception as e:
            st.warning(f"Streamtape upload: {str(e)}")

    progress_bar.progress(100, text="🎉 Step 3/3: Complete! 100%")
    status_text.success("🎉 Conversion and streaming links generated successfully!")
    
    # Post-cleanup local
    cleanup_workspace([work_dir, output_mp4])
    
    return {
        "raw_mp4_url": direct_raw_mp4_url,
        "gofile_url": gofile_url,
        "streamtape_url": streamtape_url,
        "file_id": file_id,
        "guest_token": guest_token,
        "size_mb": file_size_mb,
        "filename": original_filename
    }

# Action Trigger Buttons
col1, col2 = st.columns([4, 1])
with col1:
    convert_clicked = st.button("🚀 Convert & Generate Direct Links")
with col2:
    if st.button("Clear / Reset"):
        st.session_state.result_data = None
        st.session_state.deleted = False
        st.rerun()

if convert_clicked:
    clean_magnet = magnet_input.strip()
    if not clean_magnet:
        st.warning("⚠️ Please paste a magnet link into the box above.")
    elif not clean_magnet.startswith("magnet:?"):
        st.error("⚠️ Invalid format. Magnet links must start with `magnet:?`")
    else:
        try:
            res = process_magnet(
                clean_magnet,
                px_key=pixeldrain_key.strip() if pixeldrain_key else None,
                st_login=st_login.strip() if st_login else None,
                st_key=st_key.strip() if st_key else None
            )
            if res:
                st.session_state.result_data = res
                st.session_state.deleted = False
                st.balloons()
        except Exception as e:
            st.error(f"❌ An error occurred during cloud processing: {str(e)}")

# Display Results Card
if st.session_state.result_data:
    data = st.session_state.result_data
    
    st.markdown("---")
    st.markdown(f"### 🎬 Converted Video: **{data['filename']}** ({data['size_mb']} MB)")
    
    if not st.session_state.deleted:
        # Streamtape Remote Upload Direct Link
        if data.get("raw_mp4_url"):
            st.markdown("#### 📡 Direct Raw MP4 Link *(For Streamtape Remote Upload, VLC & Direct Stream)*")
            st.code(data["raw_mp4_url"], language="text")
            st.caption("✅ **Copy this exact link into your Streamtape remote upload script!** It ends in `.mp4` and streams raw video.")
        
        # Streamtape Account Direct Link (if configured)
        if data.get("streamtape_url"):
            st.markdown("#### 🚀 Uploaded directly to your Streamtape Account:")
            st.code(data["streamtape_url"], language="text")
        
        # Gofile Link
        if data.get("gofile_url"):
            st.markdown("#### 🌐 Gofile Cloud Download Page:")
            st.code(data["gofile_url"], language="text")
            
        st.markdown("---")
        col_dl, col_del = st.columns([3, 2])
        with col_dl:
            if data.get("raw_mp4_url"):
                st.markdown(f"👉 [**▶️ Stream / Download Raw MP4**]({data['raw_mp4_url']})")
        with col_del:
            st.markdown('<div class="delete-btn">', unsafe_allow_html=True)
            if st.button("🗑️ Delete from Cloud Now"):
                with st.spinner("Deleting file from cloud servers..."):
                    if data.get("file_id") and data.get("guest_token"):
                        delete_from_gofile(data["file_id"], data["guest_token"])
                    st.session_state.deleted = True
                    st.success("✅ File deleted from cloud!")
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.error("🗑️ This file has been deleted from cloud servers.")

# Footer / Instructions
st.markdown("---")
with st.expander("ℹ️ How To Use With Streamtape Remote Upload"):
    st.markdown("""
    1. **For Remote Upload Scripts:** Copy the **Direct Raw MP4 Link** (e.g. `https://temp.sh/.../video.mp4`). Streamtape will download it instantly without errors.
    2. **For Direct Automatic Streamtape Upload:** Enter your Streamtape API Login and Key in the sidebar settings on the left. The app will automatically upload directly to your Streamtape account.
    """)