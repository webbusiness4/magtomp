import streamlit as st
import subprocess
import os
import glob
import shutil
import requests
import time

# Page Configuration
st.set_page_config(
    page_title="MagToMP - Magnet to Direct MP4",
    page_icon="??",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS for Premium UI
st.markdown("""
<style>
    /* Global Styles */
    .stApp {
        background-color: #0b0f19;
        color: #f1f5f9;
    }
    
    /* Header & Branding */
    .hero-container {
        text-align: center;
        padding: 2rem 0 1rem 0;
    }
    .hero-title {
        font-size: 2.6rem;
        font-weight: 800;
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .hero-sub {
        color: #94a3b8;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    
    /* Badge styling */
    .badge-container {
        display: flex;
        justify-content: center;
        gap: 0.75rem;
        margin-bottom: 1.5rem;
        flex-wrap: wrap;
    }
    .badge {
        background-color: #1e293b;
        color: #38bdf8;
        padding: 0.35rem 0.85rem;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid #334155;
    }

    /* Result Card */
    .result-card {
        background-color: #131d31;
        border: 1px solid #1e293b;
        border-radius: 16px;
        padding: 1.5rem;
        margin-top: 1.5rem;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
    }
    
    /* Primary Button */
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
    <div class="hero-title">? MagToMP Cloud Converter</div>
    <div class="hero-sub">Transform torrent magnet links into direct, high-speed MP4 streaming & download links in the cloud.</div>
    <div class="badge-container">
        <span class="badge">?? 100% Cloud-Powered</span>
        <span class="badge">?? Zero Local PC Bandwidth</span>
        <span class="badge">?? Direct In-Browser Playback</span>
        <span class="badge">?? Free & Instant</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Input Section
with st.container():
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

def process_magnet(magnet: str):
    work_dir = "./cloud_downloads"
    output_mp4 = "./streamable_video.mp4"
    
    # Pre-cleanup
    cleanup_workspace([work_dir, output_mp4])
    os.makedirs(work_dir, exist_ok=True)
    
    with st.status("? Initializing Cloud Pipeline...", expanded=True) as status:
        # Step 1: Downloading via aria2c
        status.update(label="?? Step 1/3: Downloading torrent in cloud...", state="running")
        st.write("Connecting to peer swarm and downloading media chunks...")
        
        cmd_aria = [
            "aria2c",
            "--seed-time=0",
            "--max-connection-per-server=16",
            "--split=16",
            "--summary-interval=5",
            f"--dir={work_dir}",
            magnet
        ]
        
        try:
            res_aria = subprocess.run(cmd_aria, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            st.error(f"Download failed: {e.stderr or e.stdout}")
            return None, None, None

        # Step 2: Locating and Remuxing Video
        status.update(label="?? Step 2/3: Remuxing/converting to MP4 container...", state="running")
        st.write("Inspecting media codecs and building standard MP4 stream...")
        
        media_exts = ("*.mkv", "*.avi", "*.mp4", "*.ts", "*.mov", "*.webm", "*.m4v", "*.flv")
        all_videos = []
        for ext in media_exts:
            all_videos.extend(glob.glob(f"{work_dir}/**/{ext}", recursive=True))

        if not all_videos:
            st.error("No valid video stream found in the downloaded torrent.")
            return None, None, None

        largest_video = max(all_videos, key=os.path.getsize)
        original_filename = os.path.basename(largest_video)
        
        # Remux using FFmpeg fast stream-copy
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
        st.write(f"? Video ready: **{original_filename}** ({file_size_mb} MB)")

        # Step 3: Generating Direct MP4 Link
        status.update(label=f"?? Step 3/3: Generating direct link ({file_size_mb} MB)...", state="running")
        st.write("Uploading stream to high-speed media CDN for direct playback...")

        direct_stream_url = None
        direct_download_url = None
        
        with open(output_mp4, "rb") as f:
            upload_res = requests.post("https://pixeldrain.com/api/file", files={"file": f})
            if upload_res.status_code == 201:
                file_id = upload_res.json().get("id")
                direct_stream_url = f"https://pixeldrain.com/api/file/{file_id}"
                direct_download_url = f"https://pixeldrain.com/api/file/{file_id}?download"
                status.update(label="?? Conversion & Upload Complete!", state="complete", expanded=False)
            else:
                st.error(f"Direct link generation failed: {upload_res.text}")
                return None, None, None

        # Post-cleanup
        cleanup_workspace([work_dir, output_mp4])
        return direct_stream_url, direct_download_url, file_size_mb

# Action Trigger
col1, col2 = st.columns([4, 1])
with col1:
    convert_clicked = st.button("?? Convert & Generate Direct MP4 Link")
with col2:
    if st.button("Clear"):
        st.rerun()

if convert_clicked:
    clean_magnet = magnet_input.strip()
    if not clean_magnet:
        st.warning("?? Please paste a magnet link into the box above.")
    elif not clean_magnet.startswith("magnet:?"):
        st.error("?? Invalid format. Magnet links must start with `magnet:?`")
    else:
        try:
            stream_url, download_url, size_mb = process_magnet(clean_magnet)
            if stream_url:
                st.balloons()
                st.success("? Success! Your direct MP4 link is ready.")
                
                # Result Card
                st.markdown("### ?? Direct Playable MP4 Link")
                st.code(stream_url, language="text")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown(f"[?? **Download MP4 File** ({size_mb} MB)]({download_url})")
                with col_b:
                    st.caption("?? Works in VLC, Browser, and any external media player.")
                
                # In-Browser Video Player
                st.markdown("### ?? Instant Cloud Stream")
                st.video(stream_url)
                
        except Exception as e:
            st.error(f"? An error occurred during cloud processing: {str(e)}")

# Footer / Instructions
st.markdown("---")
with st.expander("?? How It Works & FAQ"):
    st.markdown("""
    - **How does it download so fast?** The conversion runs on high-speed cloud servers with Gigabit bandwidth.
    - **Is anything stored on my computer?** No. The entire process (downloading, remuxing, uploading) happens completely in the cloud.
    - **Where can I use the link?** You can paste the direct link into VLC Media Player (`Media -> Open Network Stream`), use it in web players, or download the raw `.mp4` file directly.
    """)
