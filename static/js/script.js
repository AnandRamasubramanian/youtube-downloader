/**
 * YouTube Downloader - Frontend JavaScript
 * Handles UI interactions and API calls
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
    selectedVideoFormat: null,
    selectedAudioFormat: null,
    formatType: 'video',
    isDownloading: false,
    downloadId: null,
};

const API_BASE = '';

// ==================== THEME ====================

function initTheme() {
    const saved = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
    updateThemeIcon(saved);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    updateThemeIcon(next);
}

function updateThemeIcon(theme) {
    elements.themeIcon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
}

// ==================== TOAST ====================

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        info: 'fa-info-circle'
    };
    toast.innerHTML = `<i class="fas ${icons[type]}"></i><span>${message}</span>`;
    elements.toastContainer.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ==================== VALIDATION ====================

function isValidYouTubeUrl(url) {
    const patterns = [
        /^(https?:\/\/)?(www\.)?youtube\.com\/watch\?v=[\w-]+/,
        /^(https?:\/\/)?(www\.)?youtube\.com\/shorts\/[\w-]+/,
        /^(https?:\/\/)?(www\.)?youtu\.be\/[\w-]+/,
        /^(https?:\/\/)?(m\.)?youtube\.com\/watch\?v=[\w-]+/,
    ];
    return patterns.some(p => p.test(url));
}

// ==================== UI HELPERS ====================

function showError(msg) {
    elements.errorText.textContent = msg;
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

// ==================== FORMATTING ====================

function formatNumber(num) {
    if (!num) return '0';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
}

function formatSpeed(bps) {
    if (!bps) return '-- MB/s';
    return (bps / (1024 * 1024)).toFixed(1) + ' MB/s';
}

function formatEta(sec) {
    if (!sec || sec < 0) return '-- remaining';
    if (sec < 60) return `${Math.round(sec)}s remaining`;
    return `${Math.floor(sec / 60)}m ${Math.round(sec % 60)}s remaining`;
}

// ==================== FETCH VIDEO INFO ====================

async function fetchVideoInfo(url) {
    hideError();
    showLoading();
    hideAllSections();
    
    try {
        const res = await fetch(`${API_BASE}/api/info`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url }),
        });
        
        const data = await res.json();
        
        if (!res.ok || !data.success) {
            throw new Error(data.error || 'Failed to fetch video info');
        }
        
        state.videoData = data;
        state.currentUrl = url;
        
        displayVideoInfo(data.info);
        displayFormats(data.formats);
        showVideoAndFormats();
        showToast('Video info loaded!', 'success');
    } catch (err) {
        showError(err.message);
        showToast(err.message, 'error');
    } finally {
        hideLoading();
    }
}

// ==================== DISPLAY VIDEO INFO ====================

function displayVideoInfo(info) {
    document.getElementById('thumbnail').src = info.thumbnail || '';
    document.getElementById('duration').textContent = info.duration_str || '';
    document.getElementById('videoTitle').textContent = info.title || 'Unknown';
    document.getElementById('channelName').textContent = info.channel || 'Unknown';
    document.getElementById('viewCount').textContent = formatNumber(info.view_count) + ' views';
}

// ==================== DISPLAY FORMATS ====================

function displayFormats(formats) {
    const videoGrid = document.getElementById('videoFormatGrid');
    const audioGrid = document.getElementById('audioFormatGrid');
    
    videoGrid.innerHTML = '';
    audioGrid.innerHTML = '';
    
    // Video formats
    if (formats.video && formats.video.length > 0) {
        formats.video.forEach((fmt, i) => {
            const card = document.createElement('div');
            card.className = 'format-card';
            card.dataset.type = 'video';
            card.dataset.formatId = fmt.format_id;
            card.dataset.height = fmt.height;
            
            const audioIcon = fmt.has_audio 
                ? '<i class="fas fa-volume-up" title="Has audio"></i>' 
                : '<i class="fas fa-volume-mute" title="Video only"></i>';
            
            card.innerHTML = `
                <div class="format-quality">${fmt.resolution}</div>
                <div class="format-ext">${fmt.ext.toUpperCase()} ${audioIcon}</div>
                <div class="format-size">${fmt.filesize_str || 'Size varies'}</div>
            `;
            
            card.addEventListener('click', () => selectVideoFormat(fmt, card));
            videoGrid.appendChild(card);
            
            if (i === 0) selectVideoFormat(fmt, card);
        });
    } else {
        videoGrid.innerHTML = '<p class="no-formats">No video formats available</p>';
    }
    
    // Video download button
    const oldVideoBtn = document.getElementById('videoDownloadBtn');
    if (oldVideoBtn) oldVideoBtn.remove();
    
    const videoBtn = document.createElement('button');
    videoBtn.className = 'download-format-btn';
    videoBtn.id = 'videoDownloadBtn';
    videoBtn.innerHTML = '<i class="fas fa-download"></i> Download Video';
    videoBtn.addEventListener('click', () => startDownload('video'));
    videoGrid.parentElement.appendChild(videoBtn);
    
    // Audio formats
    if (formats.audio && formats.audio.length > 0) {
        formats.audio.forEach((fmt, i) => {
            const card = document.createElement('div');
            card.className = 'format-card';
            card.dataset.type = 'audio';
            card.dataset.formatId = fmt.format_id;
            
            card.innerHTML = `
                <div class="format-quality">${fmt.abr_str}</div>
                <div class="format-ext">${fmt.ext.toUpperCase()}</div>
                <div class="format-size">${fmt.filesize_str || 'Size varies'}</div>
            `;
            
            card.addEventListener('click', () => selectAudioFormat(fmt, card));
            audioGrid.appendChild(card);
            
            if (i === 0) selectAudioFormat(fmt, card);
        });
    } else {
        audioGrid.innerHTML = '<p class="no-formats">No audio formats available</p>';
    }
    
    // Audio download button
    const oldAudioBtn = document.getElementById('audioDownloadBtn');
    if (oldAudioBtn) oldAudioBtn.remove();
    
    const audioBtn = document.createElement('button');
    audioBtn.className = 'download-format-btn';
    audioBtn.id = 'audioDownloadBtn';
    audioBtn.innerHTML = '<i class="fas fa-download"></i> Download Audio';
    audioBtn.addEventListener('click', () => startDownload('audio'));
    audioGrid.parentElement.appendChild(audioBtn);
}

function selectVideoFormat(fmt, card) {
    document.querySelectorAll('.format-card[data-type="video"]').forEach(c => {
        c.classList.remove('selected');
    });
    card.classList.add('selected');
    state.selectedVideoFormat = fmt;
}

function selectAudioFormat(fmt, card) {
    document.querySelectorAll('.format-card[data-type="audio"]').forEach(c => {
        c.classList.remove('selected');
    });
    card.classList.add('selected');
    state.selectedAudioFormat = fmt;
}

// ==================== TAB SWITCHING ====================

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

// ==================== DOWNLOAD ====================

async function startDownload(type) {
    if (state.isDownloading) {
        showToast('Download in progress', 'info');
        return;
    }
    
    let fmt, quality;
    
    if (type === 'video') {
        fmt = state.selectedVideoFormat;
        if (!fmt) {
            showToast('Select a video quality', 'error');
            return;
        }
        quality = String(fmt.height);
    } else {
        fmt = state.selectedAudioFormat;
        if (!fmt) {
            showToast('Select an audio quality', 'error');
            return;
        }
        quality = fmt.format_id;
    }
    
    state.isDownloading = true;
    state.formatType = type;
    
    elements.formatSection.classList.remove('visible');
    elements.progressSection.classList.add('visible');
    
    updateProgress(0, 'Starting download...', `Expected: ${fmt.filesize_str || 'Unknown size'}`);
    
    try {
        const res = await fetch(`${API_BASE}/api/download`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: state.currentUrl,
                format_type: type,
                quality: quality,
            }),
        });
        
        const data = await res.json();
        
        if (!res.ok || !data.success) {
            throw new Error(data.error || 'Download failed');
        }
        
        state.downloadId = data.download_id;
        pollProgress(data.download_id, data.download_url, data.filename, data.filesize);
    } catch (err) {
        state.isDownloading = false;
        showError(err.message);
        showToast(err.message, 'error');
        showVideoAndFormats();
    }
}

// ==================== PROGRESS POLLING ====================

function pollProgress(downloadId, downloadUrl, filename, filesize) {
    const poll = setInterval(async () => {
        try {
            const res = await fetch(`${API_BASE}/api/progress/${downloadId}`);
            const data = await res.json();
            
            if (data.status === 'downloading') {
                updateProgress(
                    data.progress || 0,
                    'Downloading...',
                    `${formatSpeed(data.speed)} | ${formatEta(data.eta)}`
                );
            } else if (data.status === 'processing') {
                updateProgress(100, 'Processing...', 'Almost done!');
            } else if (data.status === 'completed') {
                clearInterval(poll);
                state.isDownloading = false;
                showComplete(
                    data.download_url || downloadUrl,
                    data.filename || filename,
                    data.filesize || filesize
                );
            } else if (data.status === 'error') {
                clearInterval(poll);
                state.isDownloading = false;
                showError(data.message || 'Download failed');
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

// ==================== UPDATE UI ====================

function updateProgress(percent, status, info = '') {
    document.getElementById('progressFill').style.width = `${percent}%`;
    document.getElementById('progressPercentage').textContent = `${Math.round(percent)}%`;
    document.getElementById('progressTitle').textContent = status;
    document.getElementById('progressSpeed').textContent = info;
    document.getElementById('progressEta').textContent = '';
}

function showComplete(url, filename, filesize) {
    elements.progressSection.classList.remove('visible');
    elements.completeSection.classList.add('visible');
    
    const name = filename || 'Download ready';
    const size = filesize ? ` (${filesize})` : '';
    
    document.getElementById('completedFilename').textContent = name + size;
    
    const link = document.getElementById('downloadLink');
    link.href = url;
    link.download = filename || '';
    
    showToast('Download complete!', 'success');
}

// ==================== EVENT LISTENERS ====================

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
    } catch (e) {
        showToast('Could not paste', 'error');
    }
});

elements.clearBtn.addEventListener('click', () => {
    elements.urlInput.value = '';
    elements.clearBtn.classList.remove('visible');
    hideError();
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

// ==================== INITIALIZE ====================

initTheme();
