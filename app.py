"""
YouTube Video/Audio Downloader - Flask Application
Production-ready for Render deployment
"""
import os
import re
import uuid
import random
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

from flask import (
    Flask, render_template, request, jsonify,
    send_file, abort
)
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import yt_dlp

from config import config
from ffmpeg_handler import setup_ffmpeg, FFmpegHandler

# ==================== APP SETUP ====================

app = Flask(__name__)

# Load config
env = os.environ.get('FLASK_ENV', 'development')
app.config.from_object(config.get(env, config['default']))

# Extensions
CORS(app)
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=app.config.get('RATELIMIT_STORAGE_URL', 'memory://')
)

# Global state
download_progress = {}
ffmpeg_location = None

# Create directories
os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['FFMPEG_FOLDER'], exist_ok=True)


# ==================== INITIALIZATION ====================

def init_ffmpeg():
    """Initialize FFmpeg"""
    global ffmpeg_location
    print("=" * 50)
    print("Initializing FFmpeg...")
    
    try:
        ffmpeg_location = setup_ffmpeg(app.config['FFMPEG_FOLDER'])
        
        if ffmpeg_location:
            print(f"✓ FFmpeg at: {ffmpeg_location}")
        else:
            handler = FFmpegHandler(app.config['FFMPEG_FOLDER'])
            if handler.check_system_ffmpeg():
                print("✓ Using system FFmpeg")
            else:
                print("⚠ FFmpeg not available - audio features limited")
    except Exception as e:
        print(f"✗ FFmpeg error: {e}")
    
    print("=" * 50)


# Initialize on startup
init_ffmpeg()


# ==================== HELPERS ====================

def get_random_user_agent():
    """Get random user agent"""
    agents = app.config.get('USER_AGENTS', [])
    if agents:
        return random.choice(agents)
    return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'


def validate_youtube_url(url):
    """Validate YouTube URL"""
    if not url:
        return False, "URL is required"
    
    patterns = [
        r'(https?://)?(www\.)?youtube\.com/watch\?v=[\w-]+',
        r'(https?://)?(www\.)?youtube\.com/shorts/[\w-]+',
        r'(https?://)?(www\.)?youtu\.be/[\w-]+',
        r'(https?://)?(m\.)?youtube\.com/watch\?v=[\w-]+',
    ]
    
    for pattern in patterns:
        if re.match(pattern, url, re.IGNORECASE):
            return True, None
    
    return False, "Please enter a valid YouTube URL"


def format_filesize(bytes_size):
    """Format bytes to readable size"""
    if not bytes_size:
        return None
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"


def format_duration(seconds):
    """Format seconds to readable duration"""
    if not seconds:
        return 'Unknown'
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def get_yt_dlp_opts():
    """Get yt-dlp options with anti-block settings"""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'http_headers': {
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
            }
        },
        'socket_timeout': 30,
        'retries': 5,
        'nocheckcertificate': True,
        'geo_bypass': True,
    }
    
    if ffmpeg_location:
        opts['ffmpeg_location'] = ffmpeg_location
    
    return opts


def cleanup_old_files():
    """Remove old download files"""
    folder = Path(app.config['DOWNLOAD_FOLDER'])
    now = time.time()
    
    for f in folder.glob('*'):
        if f.is_file() and f.name != '.gitkeep':
            try:
                if now - f.stat().st_mtime > 300:
                    f.unlink()
            except Exception:
                pass


class ProgressHook:
    """Track download progress"""
    
    def __init__(self, download_id):
        self.download_id = download_id
        self.last_update = 0
    
    def __call__(self, d):
        if time.time() - self.last_update < 0.5:
            return
        self.last_update = time.time()
        
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            progress = (downloaded / total * 100) if total > 0 else 0
            
            download_progress[self.download_id] = {
                'status': 'downloading',
                'progress': round(progress, 1),
                'speed': d.get('speed', 0),
                'eta': d.get('eta', 0),
            }
        
        elif d['status'] == 'finished':
            download_progress[self.download_id] = {
                'status': 'processing',
                'progress': 100,
            }


# ==================== ROUTES ====================

@app.route('/')
def index():
    """Serve main page"""
    return render_template('index.html')


@app.route('/api/health')
def health():
    """Health check endpoint"""
    handler = FFmpegHandler(app.config['FFMPEG_FOLDER'])
    has_ffmpeg = handler.is_installed() or handler.check_system_ffmpeg()
    
    return jsonify({
        'status': 'healthy',
        'ffmpeg': has_ffmpeg,
        'version': yt_dlp.version.__version__,
        'time': datetime.utcnow().isoformat()
    })


@app.route('/api/info', methods=['POST'])
@limiter.limit("30 per minute")
def get_video_info():
    """Get video information and available formats"""
    data = request.get_json()
    url = data.get('url', '').strip()
    
    valid, error = validate_youtube_url(url)
    if not valid:
        return jsonify({'success': False, 'error': error}), 400
    
    try:
        opts = get_yt_dlp_opts()
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        
        if not info:
            return jsonify({'success': False, 'error': 'Could not get video info'}), 400
        
        # Process formats
        formats = info.get('formats', [])
        video_formats = {}
        audio_formats = {}
        
        for f in formats:
            fmt_id = f.get('format_id', '')
            ext = f.get('ext', '')
            filesize = f.get('filesize') or f.get('filesize_approx', 0)
            vcodec = f.get('vcodec', 'none')
            acodec = f.get('acodec', 'none')
            
            # Video formats
            if vcodec != 'none':
                height = f.get('height', 0)
                if height and height >= 144:
                    has_audio = acodec != 'none'
                    current = video_formats.get(height)
                    
                    # Prefer formats with audio, then by bitrate
                    score = (has_audio, f.get('tbr', 0) or 0, filesize)
                    if not current or score > current['score']:
                        video_formats[height] = {
                            'format_id': fmt_id,
                            'height': height,
                            'resolution': f"{height}p",
                            'ext': ext,
                            'filesize': filesize,
                            'filesize_str': format_filesize(filesize),
                            'has_audio': has_audio,
                            'score': score,
                        }
            
            # Audio formats
            elif acodec != 'none' and vcodec == 'none':
                abr = f.get('abr', 0)
                if abr and abr >= 48:
                    key = f"{ext}_{int(abr)}"
                    if key not in audio_formats:
                        audio_formats[key] = {
                            'format_id': fmt_id,
                            'ext': ext,
                            'abr': abr,
                            'abr_str': f"{int(abr)} kbps",
                            'filesize': filesize,
                            'filesize_str': format_filesize(filesize),
                        }
        
        # Convert to sorted lists
        video_list = sorted(
            [v for v in video_formats.values()],
            key=lambda x: x['height'],
            reverse=True
        )
        
        audio_list = sorted(
            audio_formats.values(),
            key=lambda x: x['abr'],
            reverse=True
        )
        
        # Remove score from output
        for v in video_list:
            del v['score']
        
        return jsonify({
            'success': True,
            'info': {
                'id': info.get('id'),
                'title': info.get('title'),
                'thumbnail': info.get('thumbnail'),
                'duration': info.get('duration'),
                'duration_str': format_duration(info.get('duration')),
                'channel': info.get('channel') or info.get('uploader'),
                'view_count': info.get('view_count'),
            },
            'formats': {
                'video': video_list[:8],
                'audio': audio_list[:5],
            }
        })
    
    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if 'Private video' in msg:
            return jsonify({'success': False, 'error': 'This video is private'}), 400
        if 'age-restricted' in msg.lower():
            return jsonify({'success': False, 'error': 'Age-restricted video'}), 400
        return jsonify({'success': False, 'error': 'Could not fetch video info'}), 400
    
    except Exception as e:
        print(f"Info error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'An error occurred'}), 500


@app.route('/api/download', methods=['POST'])
@limiter.limit("10 per minute")
def download():
    """Download video or audio"""
    data = request.get_json()
    url = data.get('url', '').strip()
    format_type = data.get('format_type', 'video')
    quality = data.get('quality', '')
    
    print(f"\n{'='*50}")
    print(f"Download: {format_type} / {quality}")
    print(f"URL: {url}")
    print(f"{'='*50}")
    
    valid, error = validate_youtube_url(url)
    if not valid:
        return jsonify({'success': False, 'error': error}), 400
    
    download_id = str(uuid.uuid4())[:8]
    
    output_template = os.path.join(
        app.config['DOWNLOAD_FOLDER'],
        f'{download_id}_%(title)s.%(ext)s'
    )
    
    opts = get_yt_dlp_opts()
    opts.update({
        'outtmpl': output_template,
        'progress_hooks': [ProgressHook(download_id)],
        'quiet': False,
    })
    
    try:
        # Get video info first
        with yt_dlp.YoutubeDL(get_yt_dlp_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
        
        title = info.get('title', 'video')
        formats = info.get('formats', [])
        format_lookup = {f['format_id']: f for f in formats}
        
        # Select format
        if format_type == 'audio':
            # Audio: quality is format_id
            if quality in format_lookup:
                opts['format'] = quality
            else:
                opts['format'] = 'bestaudio/best'
            
            # Check if conversion needed
            fmt = format_lookup.get(quality, {})
            has_ffmpeg = ffmpeg_location or FFmpegHandler(app.config['FFMPEG_FOLDER']).check_system_ffmpeg()
            
            if has_ffmpeg and fmt.get('ext') not in ['mp3']:
                abr = fmt.get('abr', 192)
                opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': str(int(abr)),
                }]
        
        else:
            # Video: quality is height
            target_height = int(quality) if quality.isdigit() else 720
            
            # Find best matching format
            best_format = None
            best_audio = None
            
            for f in formats:
                h = f.get('height', 0)
                if h == target_height and f.get('vcodec') != 'none':
                    has_audio = f.get('acodec') != 'none'
                    tbr = f.get('tbr', 0) or 0
                    
                    if not best_format:
                        best_format = f
                    else:
                        # Prefer with audio, then higher bitrate
                        current_score = (has_audio, tbr)
                        best_score = (best_format.get('acodec') != 'none', best_format.get('tbr', 0) or 0)
                        if current_score > best_score:
                            best_format = f
                
                # Find best audio for merging
                if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    if not best_audio or (f.get('abr', 0) or 0) > (best_audio.get('abr', 0) or 0):
                        best_audio = f
            
            if best_format:
                fmt_id = best_format['format_id']
                
                if best_format.get('acodec') != 'none':
                    # Has audio already
                    opts['format'] = fmt_id
                elif best_audio:
                    # Need to merge with audio
                    opts['format'] = f"{fmt_id}+{best_audio['format_id']}"
                else:
                    opts['format'] = fmt_id
                
                print(f"Selected format: {opts['format']}")
            else:
                opts['format'] = f"best[height<={target_height}]/best"
            
            opts['merge_output_format'] = 'mp4'
        
        # Initialize progress
        download_progress[download_id] = {
            'status': 'starting',
            'progress': 0,
            'title': title,
        }
        
        # Download
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        
        # Find file
        folder = Path(app.config['DOWNLOAD_FOLDER'])
        files = list(folder.glob(f'{download_id}_*'))
        
        if not files:
            return jsonify({'success': False, 'error': 'File not found after download'}), 500
        
        downloaded_file = files[0]
        filesize = format_filesize(downloaded_file.stat().st_size)
        
        download_progress[download_id] = {
            'status': 'completed',
            'progress': 100,
            'filename': downloaded_file.name,
            'filesize': filesize,
            'download_url': f'/api/file/{download_id}'
        }
        
        print(f"✓ Success: {downloaded_file.name} ({filesize})")
        
        return jsonify({
            'success': True,
            'download_id': download_id,
            'filename': downloaded_file.name,
            'filesize': filesize,
            'download_url': f'/api/file/{download_id}'
        })
    
    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        print(f"✗ Error: {msg}")
        download_progress[download_id] = {'status': 'error', 'message': msg}
        
        if '403' in msg:
            return jsonify({'success': False, 'error': 'YouTube blocked this request. Try again or different quality.'}), 400
        return jsonify({'success': False, 'error': 'Download failed. Try different quality.'}), 400
    
    except Exception as e:
        print(f"✗ Error: {e}")
        traceback.print_exc()
        download_progress[download_id] = {'status': 'error'}
        return jsonify({'success': False, 'error': 'Download failed'}), 500


@app.route('/api/progress/<download_id>')
def get_progress(download_id):
    """Get download progress"""
    progress = download_progress.get(download_id, {'status': 'unknown'})
    return jsonify(progress)


@app.route('/api/file/<download_id>')
def serve_file(download_id):
    """Serve downloaded file"""
    folder = Path(app.config['DOWNLOAD_FOLDER'])
    files = list(folder.glob(f'{download_id}_*'))
    
    if not files:
        abort(404)
    
    file_path = files[0]
    original_name = file_path.name[len(f'{download_id}_'):]
    
    # Schedule cleanup
    def cleanup():
        time.sleep(120)
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception:
            pass
    
    threading.Thread(target=cleanup, daemon=True).start()
    
    return send_file(file_path, as_attachment=True, download_name=original_name)


# ==================== ERROR HANDLERS ====================

@app.errorhandler(429)
def rate_limit_error(e):
    return jsonify({'success': False, 'error': 'Rate limit exceeded. Please wait.'}), 429


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Not found'}), 404
    return render_template('index.html')


@app.errorhandler(500)
def server_error(e):
    return jsonify({'success': False, 'error': 'Server error'}), 500


# ==================== BACKGROUND TASKS ====================

def periodic_cleanup():
    """Clean up old files periodically"""
    while True:
        time.sleep(300)
        cleanup_old_files()


cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
cleanup_thread.start()


# ==================== MAIN ====================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    print("\n" + "=" * 50)
    print("YouTube Downloader Starting")
    print(f"yt-dlp: {yt_dlp.version.__version__}")
    print(f"FFmpeg: {ffmpeg_location or 'System/None'}")
    print(f"Port: {port}")
    print("=" * 50 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
