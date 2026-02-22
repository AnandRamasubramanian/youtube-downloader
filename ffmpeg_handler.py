"""
FFmpeg binary handler - Downloads and manages FFmpeg static binary
"""
import os
import sys
import stat
import subprocess
import platform
from pathlib import Path

class FFmpegHandler:
    """Handles FFmpeg binary download and setup"""
    
    def __init__(self, ffmpeg_folder=None):
        if ffmpeg_folder:
            self.ffmpeg_folder = Path(ffmpeg_folder)
        else:
            self.ffmpeg_folder = Path(__file__).parent / 'static' / 'ffmpeg'
        
        self.ffmpeg_folder.mkdir(parents=True, exist_ok=True)
        self.system = self._detect_system()
        self.ffmpeg_path = self._get_ffmpeg_path()
        self.ffprobe_path = self._get_ffprobe_path()
    
    def _detect_system(self):
        """Detect the operating system"""
        system = sys.platform
        if system.startswith('linux'):
            machine = platform.machine().lower()
            if 'arm' in machine or 'aarch64' in machine:
                return 'linux_arm'
            return 'linux'
        elif system == 'darwin':
            return 'darwin'
        elif system == 'win32':
            return 'win32'
        return 'linux'
    
    def _get_ffmpeg_path(self):
        """Get the FFmpeg binary path"""
        if self.system == 'win32':
            return self.ffmpeg_folder / 'ffmpeg.exe'
        return self.ffmpeg_folder / 'ffmpeg'
    
    def _get_ffprobe_path(self):
        """Get the FFprobe binary path"""
        if self.system == 'win32':
            return self.ffmpeg_folder / 'ffprobe.exe'
        return self.ffmpeg_folder / 'ffprobe'
    
    def is_installed(self):
        """Check if FFmpeg is already installed in our folder"""
        return self.ffmpeg_path.exists() and os.access(str(self.ffmpeg_path), os.X_OK)
    
    def get_ffmpeg_location(self):
        """Get the FFmpeg binary location for yt-dlp"""
        if self.is_installed():
            return str(self.ffmpeg_folder)
        return None
    
    def check_system_ffmpeg(self):
        """Check if FFmpeg is available in system PATH"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            pass
        return False
    
    def download_ffmpeg(self):
        """Download FFmpeg using Python requests"""
        import requests
        import tarfile
        import lzma
        
        print(f"Downloading FFmpeg for {self.system}...")
        
        urls = {
            'linux': 'https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz',
            'linux_arm': 'https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz',
        }
        
        url = urls.get(self.system)
        if not url:
            print(f"No automatic download available for {self.system}")
            return False
        
        try:
            # Download
            print(f"Downloading from {url}...")
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()
            
            archive_path = self.ffmpeg_folder / 'ffmpeg.tar.xz'
            
            with open(archive_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print("Extracting FFmpeg...")
            
            # Extract
            with lzma.open(archive_path) as xz:
                with tarfile.open(fileobj=xz) as tar:
                    for member in tar.getmembers():
                        if member.name.endswith('/ffmpeg') or member.name == 'ffmpeg':
                            f = tar.extractfile(member)
                            if f:
                                with open(self.ffmpeg_path, 'wb') as target:
                                    target.write(f.read())
                        elif member.name.endswith('/ffprobe') or member.name == 'ffprobe':
                            f = tar.extractfile(member)
                            if f:
                                with open(self.ffprobe_path, 'wb') as target:
                                    target.write(f.read())
            
            # Make executable
            self.ffmpeg_path.chmod(self.ffmpeg_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            self.ffprobe_path.chmod(self.ffprobe_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            
            # Cleanup
            archive_path.unlink()
            
            print("FFmpeg installed successfully!")
            return True
            
        except Exception as e:
            print(f"Error downloading FFmpeg: {e}")
            return False
    
    def verify_installation(self):
        """Verify FFmpeg installation by running a test command"""
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
        except Exception as e:
            print(f"FFmpeg verification failed: {e}")
            return False


def setup_ffmpeg(ffmpeg_folder=None):
    """Setup FFmpeg - download if not present"""
    handler = FFmpegHandler(ffmpeg_folder)
    
    # Check if already installed in our folder
    if handler.is_installed() and handler.verify_installation():
        print(f"FFmpeg ready at: {handler.ffmpeg_path}")
        return str(handler.ffmpeg_folder)
    
    # Check system FFmpeg
    if handler.check_system_ffmpeg():
        print("Using system FFmpeg")
        return None  # yt-dlp will find it automatically
    
    # Download FFmpeg
    if handler.download_ffmpeg():
        return str(handler.ffmpeg_folder)
    
    print("WARNING: FFmpeg not available - audio conversion will be limited")
    return None


def get_ffmpeg_path():
    """Get FFmpeg path for use in other modules"""
    handler = FFmpegHandler()
    
    if handler.is_installed():
        return str(handler.ffmpeg_folder)
    
    if handler.check_system_ffmpeg():
        return None  # System FFmpeg
    
    return None


if __name__ == '__main__':
    location = setup_ffmpeg()
    print(f"FFmpeg location: {location}")