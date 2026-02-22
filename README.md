# 🎬 YouTube Video & Audio Downloader

A production-ready web application for downloading YouTube videos and audio in various formats and qualities.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.3-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## ✨ Features

- 📹 **Video Downloads**: MP4 format in 360p, 480p, 720p, 1080p, 1440p, 4K
- 🎵 **Audio Downloads**: MP3 (128/256/320 kbps), M4A, WAV
- 🌓 **Dark/Light Theme**: Toggle between themes
- 📱 **Responsive Design**: Works on desktop and mobile
- ⚡ **Fast Processing**: Efficient download and conversion
- 🔒 **Secure**: Input validation, rate limiting, no data storage
- 🚀 **Production Ready**: Deployable on Render, Heroku, Docker

## 🖥️ Demo

![Screenshot](https://via.placeholder.com/800x400?text=YouTube+Downloader+Demo)

## 🚀 Quick Start

### Local Development

```bash
# Clone the repository
git clone https://github.com/yourusername/youtube-downloader.git
cd youtube-downloader

# Run the build script (sets up everything)
chmod +x build.sh
./build.sh

# Start the development server
python app.py