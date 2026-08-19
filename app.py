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
    page_title="MagToMP - Magnet to Streamtape Direct",
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
    .streamtape-card {
        background-color: #131d31;
        border: 1px solid #312e81;
        border-radius: 16px;
        padding: 1.5rem;
        margin-top: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "result_data" not in st.session_state:
    st.session_state.result_data = None

# Retrieve Default Secrets or Environment Variables
default_login = ""
default_key = ""

try:
    if "STREAMTAPE_LOGIN" in st.secrets:
        default_login = st.secrets["STREAMTAPE_LOGIN"]
    if "STREAMTAPE_KEY" in st.secrets:
        default_key = st.secrets["STREAMTAPE_KEY"]
except Exception:
    pass

if not default_login:
    default_login = os.environ.get("STREAMTAPE_LOGIN", "")
if not default_key:
    default_key = os.environ.get("STREAMTAPE_KEY", "")

# Header Section
st.markdown("""
<div class="hero-container">
    <div class="hero-title">⚡ MagToMP ➔ Streamtape Cloud</div>
    <div class="hero-sub">Convert magnet links to MP4 and upload directly into your Streamtape account in the cloud.</div>
    <div class="badge-container">
        <span class="badge-st">🚀 Direct Streamtape Upload</span>
        <span class="badge">💻 Zero Local PC Bandwidth</span>
        <span class="badge">🎬 Fast MP4 Remuxing</span>
        <span class="badge">🆓 100% Free</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Sidebar Settings
with st.sidebar:
    st.header("⚡ Streamtape Account")
    st.caption("Your credentials are used to push videos directly to your Streamtape dashboard.")
    st_login = st.text_input("Streamtape API Login", value=default_login, type="default", placeholder="e.g. 1508538fc...")
    st_key = st.text_input("Streamtape API Key", value=default_key, type="password", placeholder="e.g. 9OpkRzZ...")
    
    if st_login and st_key:
        st.success("✅ Streamtape Account Connected!")
    else:
        st.info("💡 Enter your login & key above, or add them in Streamlit Secrets.")
        
    st.markdown("---")
    st.markdown("Created with ❤️ by **[webbusiness4](https://github.com/webbusiness4/magtomp)**")

# Input Section
magnet_input = st.text_area(
    "Paste Magnet Link",
    placeholder="magnet:?xt=urn:btih:d0c3a647d6928e469792036c05a18a99479e0809...",
    height=110,
    help="Paste a valid torrent magnet link to start the cloud transfer directly to Streamtape."
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

def upload_to_streamtape(file_path: str, login: str, key: str):
    """Directly uploads file to Streamtape via official REST API."""
    url_req = f"https://api.streamtape.com/file/ul?login={login}&key={key}"
    res = requests.get(url_req, timeout=15).json()
    if res.get("status") != 200:
        raise Exception(f"Streamtape API Error: {res.get('msg')}")
    
    upload_url = res["result"]["url"]
    with open(file_path, "rb") as f:
        upload_res = requests.post(upload_url, files={"file": f}, timeout=1800).json()
    
    if upload_res.get("status") == 200:
        video_url = upload_res["result"]["url"]
        return video_url
    else:
        raise Exception(f"Upload failed: {upload_res.get('msg')}")

def process_magnet_to_streamtape(magnet: str, login: str, key: str):
    work_dir = "./cloud_downloads"
    output_mp4 = "./streamable_video.mp4"
    
    cleanup_workspace([work_dir, output_mp4])
    os.makedirs(work_dir, exist_ok=True)
    
    progress_bar = st.progress(0, text="⚡ Initializing Cloud Engine... (0%)")
    status_text = st.empty()
    
    # =========================================================================
    # Step 1: Downloading via aria2c (0% -> 50%)
    # =========================================================================
    progress_bar.progress(5, text="📥 Step 1/3: Downloading torrent in cloud at Gigabit speed... (5%)")
    status_text.info("📥 Connecting to peer swarm...")
    
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
    # Step 2: Locating & Remuxing Video (50% -> 70%)
    # =========================================================================
    progress_bar.progress(55, text="🎬 Step 2/3: Repackaging video to standard MP4 stream... (55%)")
    status_text.info("🎬 Remuxing video container...")
    
    media_exts = ("*.mkv", "*.avi", "*.mp4", "*.ts", "*.mov", "*.webm", "*.m4v", "*.flv")
    all_videos = []
    for ext in media_exts:
        all_videos.extend(glob.glob(f"{work_dir}/**/{ext}", recursive=True))

    if not all_videos:
        st.error("No valid video stream found in the downloaded torrent.")
        return None

    largest_video = max(all_videos, key=os.path.getsize)
    original_filename = os.path.basename(largest_video)
    
    progress_bar.progress(62, text=f"🎬 Step 2/3: Remuxing '{original_filename[:30]}...' (62%)")
    
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
    progress_bar.progress(70, text=f"✅ Step 2/3: MP4 Ready ({file_size_mb} MB) (70%)")
    time.sleep(0.5)

    # =========================================================================
    # Step 3: Direct Upload to Streamtape (70% -> 100%)
    # =========================================================================
    progress_bar.progress(75, text=f"🚀 Step 3/3: Uploading {file_size_mb} MB directly to Streamtape... (75%)")
    status_text.info(f"🚀 Pushing {original_filename} directly to Streamtape API...")

    streamtape_url = None
    try:
        progress_bar.progress(85, text="🚀 Step 3/3: Transferring video stream to Streamtape... (85%)")
        streamtape_url = upload_to_streamtape(output_mp4, login, key)
    except Exception as e:
        st.error(f"Streamtape Upload failed: {str(e)}")
        return None

    progress_bar.progress(100, text="🎉 Step 3/3: Complete! 100%")
    status_text.success(f"🎉 Successfully uploaded to your Streamtape account!")
    
    cleanup_workspace([work_dir, output_mp4])
    
    return {
        "streamtape_url": streamtape_url,
        "size_mb": file_size_mb,
        "filename": original_filename
    }

# Action Trigger Buttons
col1, col2 = st.columns([4, 1])
with col1:
    convert_clicked = st.button("🚀 Convert & Push Directly to Streamtape")
with col2:
    if st.button("Clear / Reset"):
        st.session_state.result_data = None
        st.rerun()

if convert_clicked:
    clean_magnet = magnet_input.strip()
    clean_login = st_login.strip()
    clean_key = st_key.strip()
    
    if not clean_magnet:
        st.warning("⚠️ Please paste a magnet link into the box above.")
    elif not clean_magnet.startswith("magnet:?"):
        st.error("⚠️ Invalid format. Magnet links must start with `magnet:?`")
    elif not clean_login or not clean_key:
        st.error("⚠️ Please enter your Streamtape API Login and Key in the sidebar.")
    else:
        try:
            res = process_magnet_to_streamtape(clean_magnet, clean_login, clean_key)
            if res:
                st.session_state.result_data = res
                st.balloons()
        except Exception as e:
            st.error(f"❌ Error during processing: {str(e)}")

# Display Results Card
if st.session_state.result_data:
    data = st.session_state.result_data
    
    st.markdown("---")
    st.markdown(f"### 🎉 Streamtape Video Ready!")
    st.markdown(f"**File:** `{data['filename']}` | **Size:** `{data['size_mb']} MB`")
    
    st.markdown("#### 🔗 Your Streamtape Video Link:")
    st.code(data["streamtape_url"], language="text")
    
    st.markdown(f"👉 [**▶️ Open Video on Streamtape**]({data['streamtape_url']})")

# Footer / Instructions
st.markdown("---")
with st.expander("ℹ️ How It Works & Streamtape Integration"):
    st.markdown("""
    - **100% Direct & Cloud-Powered:** The cloud server downloads the torrent, converts it to MP4 with FFmpeg, and streams it directly to your Streamtape account over the official API.
    - **No Middlemen:** No 3rd-party temporary file hosts, no expiration links, and no remote download queue errors.
    - **Streamtape Secrets:** You can save your Login and Key permanently in your Streamlit Cloud **App Settings ➔ Secrets** so you never have to type them again!
    """)