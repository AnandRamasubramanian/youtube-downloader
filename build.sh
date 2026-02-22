#!/bin/bash
# Build script for YouTube Downloader
# Handles FFmpeg setup and dependency installation

set -e

echo "=========================================="
echo "YouTube Downloader - Build Script"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check Python version
print_status "Checking Python version..."
python3 --version || python --version

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    print_status "Creating virtual environment..."
    python3 -m venv venv || python -m venv venv
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
print_status "Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
print_status "Creating directories..."
mkdir -p static/ffmpeg
mkdir -p downloads
mkdir -p templates
mkdir -p static/css
mkdir -p static/js

# Download FFmpeg if not present
FFMPEG_PATH="static/ffmpeg/ffmpeg"
if [ ! -f "$FFMPEG_PATH" ]; then
    print_status "FFmpeg not found. Downloading..."
    
    # Detect OS
    OS=$(uname -s)
    ARCH=$(uname -m)
    
    case "$OS" in
        Linux*)
            if [ "$ARCH" = "x86_64" ]; then
                FFMPEG_URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
            elif [ "$ARCH" = "aarch64" ]; then
                FFMPEG_URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz"
            fi
            ;;
        Darwin*)
            print_warning "Please install FFmpeg manually on macOS: brew install ffmpeg"
            ;;
        MINGW*|CYGWIN*)
            print_warning "Please download FFmpeg manually for Windows"
            ;;
    esac
    
    if [ ! -z "$FFMPEG_URL" ]; then
        print_status "Downloading from: $FFMPEG_URL"
        wget -q "$FFMPEG_URL" -O /tmp/ffmpeg.tar.xz
        
        print_status "Extracting FFmpeg..."
        tar -xf /tmp/ffmpeg.tar.xz -C /tmp
        
        # Find and copy binaries
        cp /tmp/ffmpeg-*-static/ffmpeg static/ffmpeg/
        cp /tmp/ffmpeg-*-static/ffprobe static/ffmpeg/
        
        # Make executable
        chmod +x static/ffmpeg/ffmpeg
        chmod +x static/ffmpeg/ffprobe
        
        # Cleanup
        rm -rf /tmp/ffmpeg*
        
        print_status "FFmpeg installed successfully!"
    fi
else
    print_status "FFmpeg already installed."
fi

# Verify FFmpeg
if [ -f "$FFMPEG_PATH" ]; then
    print_status "FFmpeg version:"
    ./static/ffmpeg/ffmpeg -version | head -1
fi

# Create .gitkeep files
touch static/ffmpeg/.gitkeep
touch downloads/.gitkeep

# Run tests if pytest is available
if pip list | grep -q pytest; then
    print_status "Running tests..."
    pytest -v || print_warning "Tests failed or not found"
fi

print_status "=========================================="
print_status "Build complete!"
print_status "=========================================="
print_status ""
print_status "To run the application:"
print_status "  Development: python app.py"
print_status "  Production:  gunicorn app:app"
print_status ""