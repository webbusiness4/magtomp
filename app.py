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
</style>
""", unsafe_allow_html=True)

# Header Section
st.markdown("""
<div class="hero-container">
    <div class="hero-title">⚡ MagToMP Cloud Converter</div>
    <div class="hero-sub">Convert torrent magnet links to direct MP4 streaming & download links in the cloud.</div>
    <div class="badge-container">
        <span class="badge">🚀 100% Cloud-Powered</span>
        <span class="badge">💻 Zero Local PC Bandwidth</span>
        <span class="badge">🍿 Direct High-Speed Link</span>
        <span class="badge">🆓 Free & Instant</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Optional Settings in Sidebar
with st.sidebar:
    st.header("⚙️ Optional Settings")
    st.caption("No accounts or keys required by default! Default cloud upload is 100% free & anonymous.")
    pixeldrain_key = st.text_input("Pixeldrain API Key (Optional)", type="password", help="If you have a Pixeldrain account key, enter it here.")
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

def upload_to_gofile(file_path: str):
    """Uploads file to Gofile (Free, No Auth Required, Ultra-fast)."""
    server_res = requests.get("https://api.gofile.io/servers", timeout=15).json()
    if server_res.get("status") != "ok" or not server_res.get("data", {}).get("servers"):
        raise Exception("Gofile servers unavailable.")
    
    server_name = server_res["data"]["servers"][0]["name"]
    upload_url = f"https://{server_name}.gofile.io/contents/uploadfile"
    
    with open(file_path, "rb") as f:
        res = requests.post(upload_url, files={"file": f}, timeout=600).json()
        
    if res.get("status") == "ok":
        download_page = res["data"]["downloadPage"]
        return download_page
    else:
        raise Exception(f"Gofile upload error: {res}")

def upload_to_pixeldrain(file_path: str, api_key: str = None):
    """Uploads file to Pixeldrain."""
    auth = ("", api_key) if api_key else None
    with open(file_path, "rb") as f:
        res = requests.post("https://pixeldrain.com/api/file", files={"file": f}, auth=auth, timeout=600)
        if res.status_code == 201:
            file_id = res.json().get("id")
            return f"https://pixeldrain.com/api/file/{file_id}"
        else:
            raise Exception(res.text)

def process_magnet(magnet: str, px_key: str = None):
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
            # Parse percentage like (45%) from aria2c output
            match = re.search(r'\((\d+)%\)', line)
            if match:
                torrent_pct = int(match.group(1))
                # Scale torrent download 0-100% into overall pipeline 5% - 50%
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
            return None, None
            
    except Exception as e:
        st.error(f"Download failed: {str(e)}")
        return None, None

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
        return None, None

    largest_video = max(all_videos, key=os.path.getsize)
    original_filename = os.path.basename(largest_video)
    
    progress_bar.progress(65, text=f"🎬 Step 2/3: Processing '{original_filename[:30]}...' (65%)")
    
    # Remux using FFmpeg stream-copy
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
    # Step 3: Uploading for Direct Link (75% -> 100%)
    # =========================================================================
    progress_bar.progress(80, text=f"☁️ Step 3/3: Uploading {file_size_mb} MB to high-speed cloud CDN... (80%)")
    status_text.info(f"☁️ Generating direct stream link for {original_filename} ({file_size_mb} MB)...")

    final_url = None
    
    if px_key:
        try:
            progress_bar.progress(88, text="☁️ Step 3/3: Uploading to Pixeldrain... (88%)")
            final_url = upload_to_pixeldrain(output_mp4, px_key)
        except Exception as e:
            st.warning(f"Pixeldrain error ({str(e)}), falling back to Gofile...")
    
    if not final_url:
        try:
            progress_bar.progress(90, text="☁️ Step 3/3: Uploading to Gofile CDN... (90%)")
            final_url = upload_to_gofile(output_mp4)
        except Exception as e:
            st.error(f"Upload failed: {str(e)}")
            return None, None

    progress_bar.progress(100, text="🎉 Step 3/3: Complete! 100%")
    status_text.success("🎉 Conversion & upload finished successfully!")
    
    # Post-cleanup
    cleanup_workspace([work_dir, output_mp4])
    return final_url, file_size_mb

# Action Trigger
col1, col2 = st.columns([4, 1])
with col1:
    convert_clicked = st.button("🚀 Convert & Generate Direct Link")
with col2:
    if st.button("Clear"):
        st.rerun()

if convert_clicked:
    clean_magnet = magnet_input.strip()
    if not clean_magnet:
        st.warning("⚠️ Please paste a magnet link into the box above.")
    elif not clean_magnet.startswith("magnet:?"):
        st.error("⚠️ Invalid format. Magnet links must start with `magnet:?`")
    else:
        try:
            download_url, size_mb = process_magnet(clean_magnet, pixeldrain_key.strip() if pixeldrain_key else None)
            if download_url:
                st.balloons()
                
                # Result Card
                st.markdown("### 🎬 Direct Video Link")
                st.code(download_url, language="text")
                
                st.markdown(f"👉 [**Click Here to Open / Download Video** ({size_mb} MB)]({download_url})")
                st.info("💡 You can open the link above to stream online or download directly at maximum internet speed.")
                
        except Exception as e:
            st.error(f"❌ An error occurred during cloud processing: {str(e)}")

# Footer / Instructions
st.markdown("---")
with st.expander("ℹ️ How It Works & FAQ"):
    st.markdown("""
    - **How does it download so fast?** The conversion runs on high-speed cloud servers with Gigabit bandwidth.
    - **Is anything stored on my computer?** No. The entire process (downloading, remuxing, uploading) happens completely in the cloud.
    - **Where can I use the link?** You can paste the link into VLC Media Player, stream in browser, or download directly.
    """)