/**
 * YouTube Downloader - Frontend JavaScript
 * FIXED: Proper format selection with actual formats from video
 */

// DOM Elements
const elements = {
    urlInput: document.getElementById('urlInput'),
    pasteBtn: document.getElementById('pasteBtn'),
    clearBtn: document.getElementById('clearBtn'),
    fetchBtn: document.getElementById('fetchBtn'),
    dropZone: document.getElementById('dropZone'),
    errorMessage: document.getElementById('errorMessage'),
    errorText: document.getElementById('errorText'),
    loading: document.getElementById('loading'),
    videoInfo: document.getElementById('videoInfo'),
    formatSection: document.getElementById('formatSection'),
    progressSection: document.getElementById('progressSection'),
    completeSection: document.getElementById('completeSection'),
    themeToggle: document.getElementById('themeToggle'),
    themeIcon: document.getElementById('themeIcon'),
    toastContainer: document.getElementById('toastContainer'),
};

// State
let state = {
    currentUrl: '',
    videoData: null,
    selectedVideoFormat: null,  // Stores {format_id, height, resolution, filesize_str}
    selectedAudioFormat: null,  // Stores {format_id, abr, abr_str, filesize_str}
    formatType: 'video',
    isDownloading: false,
    downloadId: null,
};

const API_BASE = '';

// ============== Theme ==============
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const newTheme = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
    elements.themeIcon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
}

// ============== Toast ==============
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icons = { success: 'fa-check-circle', error: 'fa-exclamation-circle', info: 'fa-info-circle' };
    toast.innerHTML = `<i class="fas ${icons[type]}"></i><span>${message}</span>`;
    elements.toastContainer.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ============== Validation ==============
function isValidYouTubeUrl(url) {
    const patterns = [
        /^(https?:\/\/)?(www\.)?youtube\.com\/watch\?v=[\w-]+/,
        /^(https?:\/\/)?(www\.)?youtube\.com\/shorts\/[\w-]+/,
        /^(https?:\/\/)?(www\.)?youtu\.be\/[\w-]+/,
        /^(https?:\/\/)?(m\.)?youtube\.com\/watch\?v=[\w-]+/,
    ];
    return patterns.some(p => p.test(url));
}

// ============== Error & Loading ==============
function showError(message) {
    elements.errorText.textContent = message;
    elements.errorMessage.classList.add('visible');
}

function hideError() {
    elements.errorMessage.classList.remove('visible');
}

function showLoading() {
    elements.loading.classList.add('visible');
    elements.fetchBtn.disabled = true;
}

function hideLoading() {
    elements.loading.classList.remove('visible');
    elements.fetchBtn.disabled = false;
}

// ============== Sections ==============
function hideAllSections() {
    elements.videoInfo.classList.remove('visible');
    elements.formatSection.classList.remove('visible');
    elements.progressSection.classList.remove('visible');
    elements.completeSection.classList.remove('visible');
}

function showVideoAndFormats() {
    elements.videoInfo.classList.add('visible');
    elements.formatSection.classList.add('visible');
    elements.progressSection.classList.remove('visible');
    elements.completeSection.classList.remove('visible');
}

// ============== Formatting ==============
function formatNumber(num) {
    if (!num) return '0';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
}

function formatSpeed(bps) {
    if (!bps) return '-- MB/s';
    const mbps = bps / (1024 * 1024);
    return mbps.toFixed(1) + ' MB/s';
}

function formatEta(seconds) {
    if (!seconds || seconds < 0) return '-- remaining';
    if (seconds < 60) return `${Math.round(seconds)}s remaining`;
    const min = Math.floor(seconds / 60);
    const sec = Math.round(seconds % 60);
    return `${min}m ${sec}s remaining`;
}

// ============== Fetch Video Info ==============
async function fetchVideoInfo(url) {
    hideError();
    showLoading();
    hideAllSections();
    
    try {
        const response = await fetch(`${API_BASE}/api/info`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url }),
        });
        
        const data = await response.json();
        
        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Failed to fetch video info');
        }
        
        state.videoData = data;
        state.currentUrl = url;
        
        displayVideoInfo(data.info);
        displayFormats(data.formats);
        showVideoAndFormats();
        showToast('Video info loaded!', 'success');
        
    } catch (error) {
        showError(error.message);
        showToast(error.message, 'error');
    } finally {
        hideLoading();
    }
}

// ============== Display Video Info ==============
function displayVideoInfo(info) {
    document.getElementById('thumbnail').src = info.thumbnail || '';
    document.getElementById('duration').textContent = info.duration_str || '';
    document.getElementById('videoTitle').textContent = info.title || 'Unknown';
    document.getElementById('channelName').textContent = info.channel || 'Unknown';
    document.getElementById('viewCount').textContent = formatNumber(info.view_count) + ' views';
}

// ============== Display Formats ==============
function displayFormats(formats) {
    const videoGrid = document.getElementById('videoFormatGrid');
    const audioGrid = document.getElementById('audioFormatGrid');
    
    videoGrid.innerHTML = '';
    audioGrid.innerHTML = '';
    
    // VIDEO FORMATS - Show actual available formats with real sizes
    if (formats.video && formats.video.length > 0) {
        formats.video.forEach((fmt, index) => {
            const card = document.createElement('div');
            card.className = 'format-card';
            card.dataset.type = 'video';
            card.dataset.formatId = fmt.format_id;
            card.dataset.height = fmt.height;
            
            const hasAudioIcon = fmt.has_audio ? '<i class="fas fa-volume-up" title="Has audio"></i>' : '<i class="fas fa-volume-mute" title="No audio (will merge)"></i>';
            
            card.innerHTML = `
                <div class="format-quality">${fmt.resolution}</div>
                <div class="format-ext">${fmt.ext.toUpperCase()} ${hasAudioIcon}</div>
                <div class="format-size">${fmt.filesize_str || 'Size varies'}</div>
            `;
            
            card.addEventListener('click', () => selectVideoFormat(fmt, card));
            videoGrid.appendChild(card);
            
            // Select first format by default
            if (index === 0) {
                selectVideoFormat(fmt, card);
            }
        });
    } else {
        videoGrid.innerHTML = '<p class="no-formats">No video formats available</p>';
    }
    
    // Add video download button
    const existingVideoBtn = document.getElementById('videoDownloadBtn');
    if (existingVideoBtn) existingVideoBtn.remove();
    
    const videoDownloadBtn = document.createElement('button');
    videoDownloadBtn.className = 'download-format-btn';
    videoDownloadBtn.id = 'videoDownloadBtn';
    videoDownloadBtn.innerHTML = '<i class="fas fa-download"></i> Download Video';
    videoDownloadBtn.addEventListener('click', () => startDownload('video'));
    videoGrid.parentElement.appendChild(videoDownloadBtn);
    
    // AUDIO FORMATS - Show actual available formats with real sizes
    if (formats.audio && formats.audio.length > 0) {
        formats.audio.forEach((fmt, index) => {
            const card = document.createElement('div');
            card.className = 'format-card';
            card.dataset.type = 'audio';
            card.dataset.formatId = fmt.format_id;
            card.dataset.abr = fmt.abr;
            
            card.innerHTML = `
                <div class="format-quality">${fmt.abr_str}</div>
                <div class="format-ext">${fmt.ext.toUpperCase()}</div>
                <div class="format-size">${fmt.filesize_str || 'Size varies'}</div>
            `;
            
            card.addEventListener('click', () => selectAudioFormat(fmt, card));
            audioGrid.appendChild(card);
            
            // Select first format by default
            if (index === 0) {
                selectAudioFormat(fmt, card);
            }
        });
    } else {
        audioGrid.innerHTML = '<p class="no-formats">No audio formats available</p>';
    }
    
    // Add audio download button
    const existingAudioBtn = document.getElementById('audioDownloadBtn');
    if (existingAudioBtn) existingAudioBtn.remove();
    
    const audioDownloadBtn = document.createElement('button');
    audioDownloadBtn.className = 'download-format-btn';
    audioDownloadBtn.id = 'audioDownloadBtn';
    audioDownloadBtn.innerHTML = '<i class="fas fa-download"></i> Download Audio';
    audioDownloadBtn.addEventListener('click', () => startDownload('audio'));
    audioGrid.parentElement.appendChild(audioDownloadBtn);
}

function selectVideoFormat(fmt, cardElement) {
    // Remove selected from all video cards
    document.querySelectorAll('.format-card[data-type="video"]').forEach(c => {
        c.classList.remove('selected');
    });
    
    cardElement.classList.add('selected');
    state.selectedVideoFormat = fmt;
    
    console.log('Selected video format:', fmt);
}

function selectAudioFormat(fmt, cardElement) {
    // Remove selected from all audio cards
    document.querySelectorAll('.format-card[data-type="audio"]').forEach(c => {
        c.classList.remove('selected');
    });
    
    cardElement.classList.add('selected');
    state.selectedAudioFormat = fmt;
    
    console.log('Selected audio format:', fmt);
}

// ============== Tab Switching ==============
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        document.querySelectorAll('.format-content').forEach(c => c.classList.remove('active'));
        document.getElementById(`${tab}Formats`).classList.add('active');
        
        state.formatType = tab;
    });
});

// ============== Start Download ==============
async function startDownload(type) {
    if (state.isDownloading) {
        showToast('Download already in progress', 'info');
        return;
    }
    
    let selectedFormat;
    let quality;
    
    if (type === 'video') {
        selectedFormat = state.selectedVideoFormat;
        if (!selectedFormat) {
            showToast('Please select a video quality', 'error');
            return;
        }
        quality = String(selectedFormat.height);  // Send height as quality
    } else {
        selectedFormat = state.selectedAudioFormat;
        if (!selectedFormat) {
            showToast('Please select an audio quality', 'error');
            return;
        }
        quality = selectedFormat.format_id;  // Send format_id for audio
    }
    
    console.log(`Starting ${type} download:`, selectedFormat);
    console.log(`Quality parameter: ${quality}`);
    
    state.isDownloading = true;
    state.formatType = type;
    
    elements.formatSection.classList.remove('visible');
    elements.progressSection.classList.add('visible');
    
    updateProgress(0, 'Starting download...', `Expected size: ${selectedFormat.filesize_str || 'Unknown'}`);
    
    try {
        const response = await fetch(`${API_BASE}/api/download`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: state.currentUrl,
                format_type: type,
                quality: quality,
            }),
        });
        
        const data = await response.json();
        
        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Download failed');
        }
        
        state.downloadId = data.download_id;
        pollProgress(data.download_id, data.download_url, data.filename, data.filesize);
        
    } catch (error) {
        state.isDownloading = false;
        showError(error.message);
        showToast(error.message, 'error');
        showVideoAndFormats();
    }
}

// ============== Poll Progress ==============
function pollProgress(downloadId, downloadUrl, filename, filesize) {
    const poll = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/api/progress/${downloadId}`);
            const progress = await response.json();
            
            if (progress.status === 'downloading') {
                updateProgress(
                    progress.progress || 0,
                    'Downloading...',
                    `Speed: ${formatSpeed(progress.speed)} | ${formatEta(progress.eta)}`
                );
            } else if (progress.status === 'processing') {
                updateProgress(100, 'Processing file...', 'Almost done!');
            } else if (progress.status === 'completed') {
                clearInterval(poll);
                state.isDownloading = false;
                showDownloadComplete(
                    progress.download_url || downloadUrl,
                    progress.filename || filename,
                    progress.filesize || filesize
                );
            } else if (progress.status === 'error') {
                clearInterval(poll);
                state.isDownloading = false;
                showError(progress.message || 'Download failed');
                showToast('Download failed', 'error');
                showVideoAndFormats();
            }
        } catch (e) {
            console.error('Poll error:', e);
        }
    }, 1000);
    
    // Timeout after 10 minutes
    setTimeout(() => {
        clearInterval(poll);
        if (state.isDownloading) {
            state.isDownloading = false;
            showError('Download timed out');
            showVideoAndFormats();
        }
    }, 600000);
}

// ============== Update Progress ==============
function updateProgress(percent, status, info = '') {
    document.getElementById('progressFill').style.width = `${percent}%`;
    document.getElementById('progressPercentage').textContent = `${Math.round(percent)}%`;
    document.getElementById('progressTitle').textContent = status;
    
    const speedEl = document.getElementById('progressSpeed');
    const etaEl = document.getElementById('progressEta');
    
    if (info) {
        speedEl.textContent = info;
        etaEl.textContent = '';
    }
}

// ============== Download Complete ==============
function showDownloadComplete(downloadUrl, filename, filesize) {
    elements.progressSection.classList.remove('visible');
    elements.completeSection.classList.add('visible');
    
    const displayName = filename || 'Download ready';
    const displaySize = filesize ? ` (${filesize})` : '';
    
    document.getElementById('completedFilename').textContent = displayName + displaySize;
    
    const downloadLink = document.getElementById('downloadLink');
    downloadLink.href = downloadUrl;
    downloadLink.download = filename || '';
    
    showToast('Download complete!', 'success');
}

// ============== Event Listeners ==============
elements.themeToggle.addEventListener('click', toggleTheme);

elements.urlInput.addEventListener('input', () => {
    const hasValue = elements.urlInput.value.trim().length > 0;
    elements.clearBtn.classList.toggle('visible', hasValue);
    hideError();
});

elements.urlInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') handleFetch();
});

elements.pasteBtn.addEventListener('click', async () => {
    try {
        const text = await navigator.clipboard.readText();
        elements.urlInput.value = text;
        elements.clearBtn.classList.add('visible');
        showToast('URL pasted', 'info');
    } catch (error) {
        showToast('Could not access clipboard', 'error');
    }
});

elements.clearBtn.addEventListener('click', () => {
    elements.urlInput.value = '';
    elements.clearBtn.classList.remove('visible');
    hideError();
    hideAllSections();
    state.currentUrl = '';
    state.videoData = null;
    state.selectedVideoFormat = null;
    state.selectedAudioFormat = null;
});

elements.fetchBtn.addEventListener('click', handleFetch);

function handleFetch() {
    const url = elements.urlInput.value.trim();
    
    if (!url) {
        showError('Please enter a YouTube URL');
        return;
    }
    
    if (!isValidYouTubeUrl(url)) {
        showError('Please enter a valid YouTube URL');
        return;
    }
    
    fetchVideoInfo(url);
}

// Drop zone
elements.dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    elements.dropZone.classList.add('drag-over');
});

elements.dropZone.addEventListener('dragleave', () => {
    elements.dropZone.classList.remove('drag-over');
});

elements.dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    elements.dropZone.classList.remove('drag-over');
    const text = e.dataTransfer.getData('text');
    if (text && isValidYouTubeUrl(text)) {
        elements.urlInput.value = text;
        elements.clearBtn.classList.add('visible');
        fetchVideoInfo(text);
    } else {
        showToast('Please drop a valid YouTube URL', 'error');
    }
});

elements.dropZone.addEventListener('click', () => elements.urlInput.focus());

// New download button
document.getElementById('newDownloadBtn').addEventListener('click', () => {
    elements.urlInput.value = '';
    elements.clearBtn.classList.remove('visible');
    hideAllSections();
    state = {
        currentUrl: '',
        videoData: null,
        selectedVideoFormat: null,
        selectedAudioFormat: null,
        formatType: 'video',
        isDownloading: false,
        downloadId: null,
    };
    elements.urlInput.focus();
});

// Initialize
initTheme();