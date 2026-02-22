"""
FFmpeg Handler - Manages FFmpeg binary for audio/video processing
"""
import os
import sys
import stat
import subprocess
import platform
import shutil
from pathlib import Path


class FFmpegHandler:
    """Handles FFmpeg detection and setup"""
    
    def __init__(self, ffmpeg_folder=None):
        if ffmpeg_folder:
            self.ffmpeg_folder = Path(ffmpeg_folder)
        else:
            self.ffmpeg_folder = Path(__file__).parent / 'static' / 'ffmpeg'
        
        self.ffmpeg_folder.mkdir(parents=True, exist_ok=True)
        self.system = sys.platform
        
        if self.system == 'win32':
            self.ffmpeg_path = self.ffmpeg_folder / 'ffmpeg.exe'
            self.ffprobe_path = self.ffmpeg_folder / 'ffprobe.exe'
        else:
            self.ffmpeg_path = self.ffmpeg_folder / 'ffmpeg'
            self.ffprobe_path = self.ffmpeg_folder / 'ffprobe'
    
    def is_installed(self):
        """Check if FFmpeg is in our folder"""
        if self.ffmpeg_path.exists():
            try:
                return os.access(str(self.ffmpeg_path), os.X_OK)
            except:
                return False
        return False
    
    def check_system_ffmpeg(self):
        """Check if FFmpeg is available in system PATH"""
        try:
            # Try to find ffmpeg in PATH
            ffmpeg_path = shutil.which('ffmpeg')
            if ffmpeg_path:
                result = subprocess.run(
                    ['ffmpeg', '-version'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                return result.returncode == 0
        except Exception:
            pass
        return False
    
    def get_ffmpeg_location(self):
        """Get FFmpeg location for yt-dlp"""
        # First check our folder
        if self.is_installed():
            return str(self.ffmpeg_folder)
        
        # Then check system
        if self.check_system_ffmpeg():
            return None  # yt-dlp will find it automatically
        
        return None
    
    def verify_installation(self):
        """Verify FFmpeg works"""
        if not self.is_installed():
            return False
        
        try:
            result = subprocess.run(
                [str(self.ffmpeg_path), '-version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def download_ffmpeg(self):
        """Download FFmpeg static binary for Linux"""
        if self.system != 'linux':
            print(f"Auto-download only available for Linux, not {self.system}")
            return False
        
        try:
            import requests
            import tarfile
            import lzma
            
            url = 'https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz'
            print(f"Downloading FFmpeg from {url}...")
            
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()
            
            archive_path = self.ffmpeg_folder / 'ffmpeg.tar.xz'
            
            with open(archive_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print("Extracting FFmpeg...")
            
            with lzma.open(archive_path) as xz:
                with tarfile.open(fileobj=xz) as tar:
                    for member in tar.getmembers():
                        if member.name.endswith('/ffmpeg'):
                            f = tar.extractfile(member)
                            if f:
                                with open(self.ffmpeg_path, 'wb') as out:
                                    out.write(f.read())
                        elif member.name.endswith('/ffprobe'):
                            f = tar.extractfile(member)
                            if f:
                                with open(self.ffprobe_path, 'wb') as out:
                                    out.write(f.read())
            
            # Make executable
            self.ffmpeg_path.chmod(self.ffmpeg_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            self.ffprobe_path.chmod(self.ffprobe_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            
            # Cleanup
            archive_path.unlink()
            
            print("FFmpeg installed successfully!")
            return True
            
        except Exception as e:
            print(f"FFmpeg download error: {e}")
            return False


def setup_ffmpeg(ffmpeg_folder=None):
    """Setup FFmpeg and return location"""
    handler = FFmpegHandler(ffmpeg_folder)
    
    # Check if already installed in our folder
    if handler.is_installed() and handler.verify_installation():
        print(f"FFmpeg ready at: {handler.ffmpeg_path}")
        return str(handler.ffmpeg_folder)
    
    # Check system FFmpeg
    if handler.check_system_ffmpeg():
        print("Using system FFmpeg")
        return None
    
    # Try to download (Linux only)
    if handler.download_ffmpeg():
        return str(handler.ffmpeg_folder)
    
    print("WARNING: FFmpeg not available - some features may be limited")
    return None


def get_ffmpeg_location():
    """Get FFmpeg path for other modules"""
    handler = FFmpegHandler()
    return handler.get_ffmpeg_location()
