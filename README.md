# ⚡ MagToMP - Magnet to Direct MP4 Cloud Downloader

A high-performance cloud web application built with **Streamlit** that takes any torrent magnet link, downloads it in the cloud via `aria2c`, remuxes it to standard `.mp4` container with `ffmpeg`, and produces a **direct playable & downloadable `.mp4` link** without touching your local computer storage or network bandwidth.

---

## 🌟 Key Features

- **🚀 100% Cloud Execution:** Torrents are fetched, converted, and uploaded entirely on remote cloud servers.
- **📊 Real-Time Percentage Tracking:** Live progress bar displaying download %, remuxing %, and cloud upload %.
- **🎬 Direct Playable Links:** Outputs clean high-speed URLs that stream directly in browsers, VLC, or external media players.
- **🗑️ Manual Cloud Deletion:** Integrated `Delete from Cloud Now` button to permanently destroy uploaded files at any time.
- **🆓 Zero-Cost Deployment:** 100% free hosting on Streamlit Community Cloud with no server setup required.

---

## 🚀 1-Click Deployment to Streamlit Cloud

1. Go to **[share.streamlit.io](https://share.streamlit.io/)** and log in with your GitHub account.
2. Click **"New app"** (or **"Create app"**).
3. Set:
   - **Repository:** `webbusiness4/magtomp`
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. Click **"Deploy!"**.

Streamlit Cloud will read `packages.txt`, automatically install `aria2` and `ffmpeg`, and launch your web app at `https://magtomp.streamlit.app` (or your custom subdomain).

---

## 💻 Running Locally

### 1. Prerequisites
- Python 3.9+
- `aria2` and `ffmpeg` installed on your system path.

### 2. Installation & Run
```bash
git clone https://github.com/webbusiness4/magtomp.git
cd magtomp
pip install -r requirements.txt
streamlit run app.py
```