"""
YouTube Video/Audio Downloader - Flask Application
FIXED: Proper format selection with correct file sizes
"""
import os
import re
import json
import uuid
import random
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from flask import (
    Flask, render_template, request, jsonify, 
    Response, send_file, abort
)
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import yt_dlp

from config import config
from ffmpeg_handler import setup_ffmpeg, FFmpegHandler

# Initialize Flask app
app = Flask(__name__)

# Load configuration
env = os.environ.get('FLASK_ENV', 'development')
app.config.from_object(config.get(env, config['default']))

# Initialize extensions
CORS(app)
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=app.config.get('RATELIMIT_STORAGE_URL', 'memory://')
)

# Global variables
download_progress = {}
ffmpeg_location = None
video_formats_cache = {}  # Cache format info per video

# Ensure directories exist
os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['FFMPEG_FOLDER'], exist_ok=True)


def init_ffmpeg():
    """Initialize FFmpeg on startup"""
    global ffmpeg_location
    print("=" * 50)
    print("Initializing FFmpeg...")
    print("=" * 50)
    
    try:
        ffmpeg_location = setup_ffmpeg(app.config['FFMPEG_FOLDER'])
        if ffmpeg_location:
            print(f"✓ FFmpeg ready at: {ffmpeg_location}")
        else:
            handler = FFmpegHandler(app.config['FFMPEG_FOLDER'])
            if handler.check_system_ffmpeg():
                print("✓ Using system FFmpeg")
            else:
                print("⚠ FFmpeg not available - audio conversion limited")
    except Exception as e:
        print(f"✗ FFmpeg init error: {e}")


init_ffmpeg()


def get_random_user_agent():
    return random.choice(app.config.get('USER_AGENTS', [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    ]))


def validate_youtube_url(url):
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
    if bytes_size is None or bytes_size == 0:
        return None
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"


def format_duration(seconds):
    if not seconds:
        return 'Unknown'
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def get_yt_dlp_opts():
    """Get yt-dlp options with bypass settings"""
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
    download_folder = Path(app.config['DOWNLOAD_FOLDER'])
    current_time = time.time()
    
    for file_path in download_folder.glob('*'):
        if file_path.is_file() and file_path.name != '.gitkeep':
            try:
                if current_time - file_path.stat().st_mtime > 300:
                    file_path.unlink()
            except:
                pass


class ProgressHook:
    def __init__(self, download_id):
        self.download_id = download_id
        self.last_update = 0
    
    def __call__(self, d):
        if time.time() - self.last_update < 0.3:
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


# ============== ROUTES ==============

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/health')
def health_check():
    handler = FFmpegHandler(app.config['FFMPEG_FOLDER'])
    return jsonify({
        'status': 'healthy',
        'ffmpeg_available': handler.is_installed() or handler.check_system_ffmpeg(),
        'yt_dlp_version': yt_dlp.version.__version__,
    })


@app.route('/api/info', methods=['POST'])
@limiter.limit("30 per minute")
def get_video_info():
    """Get video information with ACTUAL available formats"""
    data = request.get_json()
    url = data.get('url', '').strip()
    
    is_valid, error = validate_youtube_url(url)
    if not is_valid:
        return jsonify({'success': False, 'error': error}), 400
    
    try:
        ydl_opts = get_yt_dlp_opts()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        
        if not info:
            return jsonify({'success': False, 'error': 'Could not extract video info'}), 400
        
        video_id = info.get('id', '')
        formats = info.get('formats', [])
        
        # Separate and organize formats
        video_formats = []
        audio_formats = []
        
        # Track best format per resolution
        best_video_by_height = {}
        best_audio_by_bitrate = {}
        
        for f in formats:
            format_id = f.get('format_id', '')
            ext = f.get('ext', '')
            filesize = f.get('filesize') or f.get('filesize_approx', 0)
            vcodec = f.get('vcodec', 'none')
            acodec = f.get('acodec', 'none')
            
            # VIDEO FORMATS
            if vcodec != 'none':
                height = f.get('height', 0)
                if height and height >= 144:
                    # Key for grouping: height
                    key = height
                    
                    # Check if this is better than existing
                    existing = best_video_by_height.get(key)
                    
                    # Prefer formats with audio, then by filesize
                    has_audio = acodec != 'none'
                    current_score = (has_audio, filesize or 0)
                    
                    if existing is None or current_score > (existing.get('has_audio', False), existing.get('filesize', 0)):
                        best_video_by_height[key] = {
                            'format_id': format_id,
                            'height': height,
                            'resolution': f"{height}p",
                            'ext': ext,
                            'filesize': filesize,
                            'filesize_str': format_filesize(filesize),
                            'has_audio': has_audio,
                            'vcodec': vcodec.split('.')[0] if vcodec else '',
                            'acodec': acodec.split('.')[0] if acodec != 'none' else '',
                            'fps': f.get('fps', 30),
                            'tbr': f.get('tbr', 0),  # Total bitrate
                        }
            
            # AUDIO FORMATS (no video)
            elif acodec != 'none' and vcodec == 'none':
                abr = f.get('abr', 0)
                if abr and abr >= 48:
                    # Round to nearest standard bitrate
                    standard_bitrates = [64, 96, 128, 160, 192, 256, 320]
                    rounded_abr = min(standard_bitrates, key=lambda x: abs(x - abr))
                    
                    key = (ext, rounded_abr)
                    existing = best_audio_by_bitrate.get(key)
                    
                    if existing is None or (filesize or 0) > existing.get('filesize', 0):
                        best_audio_by_bitrate[key] = {
                            'format_id': format_id,
                            'ext': ext,
                            'abr': abr,
                            'abr_rounded': rounded_abr,
                            'abr_str': f"{rounded_abr} kbps",
                            'filesize': filesize,
                            'filesize_str': format_filesize(filesize),
                            'acodec': acodec.split('.')[0] if acodec else '',
                        }
        
        # Convert to sorted lists
        video_formats = sorted(
            best_video_by_height.values(),
            key=lambda x: x['height'],
            reverse=True
        )
        
        audio_formats = sorted(
            best_audio_by_bitrate.values(),
            key=lambda x: x['abr'],
            reverse=True
        )
        
        # Store format mappings in cache for download
        format_map = {
            'video': {str(f['height']): f['format_id'] for f in video_formats},
            'audio': {f['format_id']: f for f in audio_formats}
        }
        video_formats_cache[video_id] = {
            'format_map': format_map,
            'all_formats': {f['format_id']: f for f in formats},
            'video_list': video_formats,
            'audio_list': audio_formats,
        }
        
        print(f"\n{'='*50}")
        print(f"Video: {info.get('title')}")
        print(f"Available video formats: {[f['resolution'] for f in video_formats]}")
        print(f"Available audio formats: {[f['abr_str'] for f in audio_formats]}")
        print(f"{'='*50}\n")
        
        return jsonify({
            'success': True,
            'info': {
                'id': video_id,
                'title': info.get('title'),
                'thumbnail': info.get('thumbnail'),
                'duration': info.get('duration'),
                'duration_str': format_duration(info.get('duration')),
                'channel': info.get('channel') or info.get('uploader'),
                'view_count': info.get('view_count'),
            },
            'formats': {
                'video': video_formats,
                'audio': audio_formats,
            }
        })
    
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if 'Private video' in error_msg:
            return jsonify({'success': False, 'error': 'This video is private'}), 400
        elif 'age-restricted' in error_msg.lower():
            return jsonify({'success': False, 'error': 'Age-restricted video'}), 400
        return jsonify({'success': False, 'error': 'Could not fetch video info'}), 400
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'An error occurred'}), 500


@app.route('/api/download', methods=['POST'])
@limiter.limit("10 per minute")
def download_video():
    """Download video or audio with EXACT format selection"""
    data = request.get_json()
    url = data.get('url', '').strip()
    format_type = data.get('format_type', 'video')
    quality = data.get('quality', '')  # This will be format_id or height
    
    print(f"\n{'='*50}")
    print(f"DOWNLOAD REQUEST")
    print(f"Type: {format_type}")
    print(f"Quality: {quality}")
    print(f"URL: {url}")
    print(f"{'='*50}")
    
    is_valid, error = validate_youtube_url(url)
    if not is_valid:
        return jsonify({'success': False, 'error': error}), 400
    
    download_id = str(uuid.uuid4())[:8]
    
    output_template = os.path.join(
        app.config['DOWNLOAD_FOLDER'],
        f'{download_id}_%(title)s.%(ext)s'
    )
    
    ydl_opts = get_yt_dlp_opts()
    ydl_opts.update({
        'outtmpl': output_template,
        'progress_hooks': [ProgressHook(download_id)],
        'quiet': False,
    })
    
    try:
        # First, get fresh format info
        with yt_dlp.YoutubeDL(get_yt_dlp_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
        
        video_id = info.get('id', '')
        title = info.get('title', 'video')
        formats = info.get('formats', [])
        
        # Build format lookup
        format_lookup = {f['format_id']: f for f in formats}
        
        # DETERMINE THE EXACT FORMAT TO DOWNLOAD
        if format_type == 'audio':
            # Quality is format_id for audio
            selected_format_id = quality
            
            # Verify it exists
            if selected_format_id not in format_lookup:
                # Try to find best matching audio
                audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
                if audio_formats:
                    selected_format_id = audio_formats[0]['format_id']
                else:
                    selected_format_id = 'bestaudio'
            
            format_string = selected_format_id
            
            # Check if we need to convert
            selected_fmt = format_lookup.get(selected_format_id, {})
            selected_ext = selected_fmt.get('ext', 'm4a')
            
            print(f"Audio format selected: {selected_format_id}")
            print(f"Audio ext: {selected_ext}")
            print(f"Audio bitrate: {selected_fmt.get('abr', 'unknown')} kbps")
            
            ydl_opts['format'] = format_string
            
            # Convert to mp3 if requested and we have FFmpeg
            convert_ext = data.get('convert_to', None)
            if convert_ext == 'mp3':
                has_ffmpeg = ffmpeg_location or FFmpegHandler(app.config['FFMPEG_FOLDER']).check_system_ffmpeg()
                if has_ffmpeg:
                    # Get target bitrate from the selected format
                    target_bitrate = str(int(selected_fmt.get('abr', 192)))
                    ydl_opts['postprocessors'] = [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': target_bitrate,
                    }]
                    print(f"Will convert to MP3 at {target_bitrate}kbps")
        
        else:  # Video
            # Quality is height (e.g., "720", "1080", "2160")
            target_height = int(quality) if quality.isdigit() else 720
            
            print(f"Looking for video with height: {target_height}p")
            
            # Find EXACT format with this height
            # Priority: has audio > higher bitrate > mp4
            matching_formats = []
            
            for f in formats:
                height = f.get('height', 0)
                if height == target_height and f.get('vcodec') != 'none':
                    has_audio = f.get('acodec') != 'none'
                    tbr = f.get('tbr', 0) or 0
                    is_mp4 = f.get('ext') == 'mp4'
                    filesize = f.get('filesize') or f.get('filesize_approx', 0) or 0
                    
                    matching_formats.append({
                        'format_id': f['format_id'],
                        'has_audio': has_audio,
                        'tbr': tbr,
                        'is_mp4': is_mp4,
                        'filesize': filesize,
                        'ext': f.get('ext'),
                        'acodec': f.get('acodec'),
                    })
            
            if matching_formats:
                # Sort: has_audio DESC, tbr DESC, is_mp4 DESC
                matching_formats.sort(
                    key=lambda x: (x['has_audio'], x['tbr'], x['is_mp4'], x['filesize']),
                    reverse=True
                )
                
                best_match = matching_formats[0]
                selected_format_id = best_match['format_id']
                
                print(f"Found exact match: {selected_format_id}")
                print(f"  Has audio: {best_match['has_audio']}")
                print(f"  Bitrate: {best_match['tbr']} kbps")
                print(f"  Filesize: {format_filesize(best_match['filesize'])}")
                
                # If video has no audio, we need to merge with audio
                if best_match['has_audio']:
                    format_string = selected_format_id
                else:
                    # Find best audio to merge
                    audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
                    if audio_formats:
                        # Sort by bitrate
                        audio_formats.sort(key=lambda x: x.get('abr', 0), reverse=True)
                        best_audio = audio_formats[0]['format_id']
                        format_string = f"{selected_format_id}+{best_audio}"
                        print(f"Will merge with audio: {best_audio}")
                    else:
                        format_string = selected_format_id
            else:
                # No exact match, use yt-dlp format selection
                format_string = f"best[height<={target_height}]/best"
                print(f"No exact match, using: {format_string}")
            
            ydl_opts['format'] = format_string
            ydl_opts['merge_output_format'] = 'mp4'
        
        print(f"\nFinal format string: {ydl_opts['format']}")
        
        # Initialize progress
        download_progress[download_id] = {
            'status': 'starting',
            'progress': 0,
            'title': title,
        }
        
        # DOWNLOAD
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Find downloaded file
        download_folder = Path(app.config['DOWNLOAD_FOLDER'])
        files = list(download_folder.glob(f'{download_id}_*'))
        
        if not files:
            return jsonify({'success': False, 'error': 'Download failed - file not found'}), 500
        
        downloaded_file = files[0]
        file_size = downloaded_file.stat().st_size
        
        print(f"\n✓ Download complete!")
        print(f"  File: {downloaded_file.name}")
        print(f"  Size: {format_filesize(file_size)}")
        
        download_progress[download_id] = {
            'status': 'completed',
            'progress': 100,
            'filename': downloaded_file.name,
            'filesize': format_filesize(file_size),
            'download_url': f'/api/file/{download_id}'
        }
        
        return jsonify({
            'success': True,
            'download_id': download_id,
            'filename': downloaded_file.name,
            'filesize': format_filesize(file_size),
            'download_url': f'/api/file/{download_id}'
        })
    
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        print(f"✗ Download error: {error_msg}")
        
        download_progress[download_id] = {'status': 'error', 'message': error_msg}
        
        if '403' in error_msg:
            return jsonify({
                'success': False,
                'error': 'YouTube blocked this request. Try again or select a different quality.'
            }), 400
        
        return jsonify({'success': False, 'error': 'Download failed. Try a different quality.'}), 400
    
    except Exception as e:
        traceback.print_exc()
        download_progress[download_id] = {'status': 'error'}
        return jsonify({'success': False, 'error': 'Download failed'}), 500


@app.route('/api/progress/<download_id>')
def get_progress(download_id):
    progress = download_progress.get(download_id, {'status': 'unknown'})
    return jsonify(progress)


@app.route('/api/file/<download_id>')
def serve_file(download_id):
    download_folder = Path(app.config['DOWNLOAD_FOLDER'])
    files = list(download_folder.glob(f'{download_id}_*'))
    
    if not files:
        abort(404)
    
    file_path = files[0]
    original_name = file_path.name[len(f'{download_id}_'):]
    
    def cleanup():
        time.sleep(120)
        try:
            if file_path.exists():
                file_path.unlink()
        except:
            pass
    
    threading.Thread(target=cleanup, daemon=True).start()
    
    return send_file(file_path, as_attachment=True, download_name=original_name)


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'success': False, 'error': 'Rate limit exceeded'}), 429


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Not found'}), 404
    return render_template('index.html')


def periodic_cleanup():
    while True:
        time.sleep(300)
        cleanup_old_files()

threading.Thread(target=periodic_cleanup, daemon=True).start()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    print("\n" + "=" * 50)
    print("YouTube Downloader")
    print(f"yt-dlp: {yt_dlp.version.__version__}")
    print(f"FFmpeg: {ffmpeg_location or 'System'}")
    print(f"Port: {port}")
    print("=" * 50 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=debug)