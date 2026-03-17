/**
 * PM Bot Dashboard JavaScript
 * Real-time dashboard for Copy Trading Bot
 */

// ===== CONFIGURATION =====
const CONFIG = {
    API_BASE_URL: '', // Relative to current host
    WS_PATH: '/socket.io/',
    REFRESH_INTERVAL: 5000, // 5 seconds for stats refresh
    MAX_TRADES_DISPLAY: 50,
    CHART_COLORS: {
        green: '#00d084',
        red: '#ff4757',
        blue: '#2e86de',
        yellow: '#ffa502',
        dark: '#141414',
        grid: '#2a2a2a'
    }
};

// ===== GLOBAL STATE =====
let socket = null;
let charts = {};
let trades = [];
let settings = {};
let refreshTimer = null;

// ===== INITIALIZATION =====
document.addEventListener('DOMContentLoaded', () => {
    initializeDashboard();
});

async function initializeDashboard() {
    console.log('🚀 Initializing PM Bot Dashboard...');
    
    // Initialize charts
    initializeCharts();
    
    // Load initial data
    await loadSettings();
    await loadStats();
    await loadTrades();
    
    // Setup WebSocket connection
    setupWebSocket();
    
    // Setup event listeners
    setupEventListeners();
    
    // Start auto-refresh
    startAutoRefresh();
    
    // Update timestamp
    updateLastRefresh();
    
    console.log('✅ Dashboard initialized');
}

// ===== CHARTS =====
function initializeCharts() {
    // Common chart options
    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: false
            }
        },
        scales: {
            x: {
                grid: {
                    color: CONFIG.CHART_COLORS.grid,
                    drawBorder: false
                },
                ticks: {
                    color: '#888888',
                    font: { size: 10 }
                }
            },
            y: {
                grid: {
                    color: CONFIG.CHART_COLORS.grid,
                    drawBorder: false
                },
                ticks: {
                    color: '#888888',
                    font: { size: 10 }
                }
            }
        }
    };

    // PnL Chart
    const pnlCtx = document.getElementById('pnlChart').getContext('2d');
    charts.pnl = new Chart(pnlCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'PnL',
                data: [],
                borderColor: CONFIG.CHART_COLORS.green,
                backgroundColor: 'rgba(0, 208, 132, 0.1)',
                fill: true,
                tension: 0.4,
                borderWidth: 2
            }]
        },
        options: {
            ...commonOptions,
            plugins: {
                ...commonOptions.plugins,
                tooltip: {
                    callbacks: {
                        label: (context) => `PnL: $${context.parsed.y.toFixed(2)}`
                    }
                }
            }
        }
    });

    // Volume Chart
    const volumeCtx = document.getElementById('volumeChart').getContext('2d');
    charts.volume = new Chart(volumeCtx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Buy Volume',
                    data: [],
                    backgroundColor: CONFIG.CHART_COLORS.green,
                    borderRadius: 4
                },
                {
                    label: 'Sell Volume',
                    data: [],
                    backgroundColor: CONFIG.CHART_COLORS.red,
                    borderRadius: 4
                }
            ]
        },
        options: {
            ...commonOptions,
            plugins: {
                ...commonOptions.plugins,
                legend: {
                    display: true,
                    labels: {
                        color: '#888888',
                        font: { size: 10 },
                        boxWidth: 12
                    }
                }
            }
        }
    });

    // Latency Chart
    const latencyCtx = document.getElementById('latencyChart').getContext('2d');
    charts.latency = new Chart(latencyCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Latency (ms)',
                data: [],
                borderColor: CONFIG.CHART_COLORS.blue,
                backgroundColor: 'rgba(46, 134, 222, 0.1)',
                fill: true,
                tension: 0.3,
                borderWidth: 2,
                pointRadius: 2
            }]
        },
        options: {
            ...commonOptions,
            scales: {
                ...commonOptions.scales,
                y: {
                    ...commonOptions.scales.y,
                    beginAtZero: true,
                    ticks: {
                        ...commonOptions.scales.y.ticks,
                        callback: (value) => `${value}ms`
                    }
                }
            },
            plugins: {
                ...commonOptions.plugins,
                tooltip: {
                    callbacks: {
                        label: (context) => `Latency: ${context.parsed.y.toFixed(0)}ms`
                    }
                }
            }
        }
    });
}

// ===== WEBSOCKET =====
function setupWebSocket() {
    console.log('🔌 Connecting to WebSocket...');
    
    socket = io(CONFIG.API_BASE_URL, {
        path: CONFIG.WS_PATH,
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000
    });

    socket.on('connect', () => {
        console.log('✅ WebSocket connected');
        updateConnectionStatus('connected');
        showToast('Connected', 'Real-time updates enabled', 'success');
    });

    socket.on('disconnect', () => {
        console.log('❌ WebSocket disconnected');
        updateConnectionStatus('disconnected');
    });

    socket.on('connect_error', (error) => {
        console.error('WebSocket error:', error);
        updateConnectionStatus('error');
    });

    // Trade events
    socket.on('new_trade', (trade) => {
        console.log('📊 New trade received:', trade);
        addTradeToTable(trade);
        updateStatsFromTrade(trade);
    });

    socket.on('trade_update', (trade) => {
        console.log('🔄 Trade update:', trade);
        updateTradeInTable(trade);
    });

    // Status events
    socket.on('bot_status', (status) => {
        console.log('🤖 Bot status:', status);
        updateBotStatus(status);
    });

    socket.on('settings_updated', (newSettings) => {
        console.log('⚙️ Settings updated:', newSettings);
        settings = { ...settings, ...newSettings };
        populateSettingsForm();
        showToast('Settings Updated', 'Configuration synchronized', 'info');
    });
}

function updateConnectionStatus(status) {
    const el = document.getElementById('connection-status');
    const icon = el.querySelector('i');
    const text = el.querySelector('span');
    
    el.className = '';
    
    switch (status) {
        case 'connected':
            el.classList.add('connection-online');
            icon.className = 'fas fa-wifi text-sm';
            text.textContent = 'Connected';
            break;
        case 'disconnected':
            el.classList.add('connection-offline');
            icon.className = 'fas fa-wifi-slash text-sm';
            text.textContent = 'Disconnected';
            break;
        case 'connecting':
            el.classList.add('connection-connecting');
            icon.className = 'fas fa-spinner fa-spin text-sm';
            text.textContent = 'Connecting...';
            break;
        default:
            el.classList.add('connection-offline');
            icon.className = 'fas fa-exclamation-circle text-sm';
            text.textContent = 'Error';
    }
}

// ===== API CALLS =====
async function apiCall(endpoint, options = {}) {
    const url = `${CONFIG.API_BASE_URL}/api${endpoint}`;
    
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json'
            },
            ...options
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error(`API Error (${endpoint}):`, error);
        throw error;
    }
}

async function loadSettings() {
    try {
        const data = await apiCall('/settings');
        settings = data;
        populateSettingsForm();
    } catch (error) {
        showToast('Error', 'Failed to load settings', 'error');
        console.error(error);
    }
}

async function loadStats() {
    try {
        const data = await apiCall('/stats');
        updateStatsDisplay(data);
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

async function loadTrades() {
    try {
        const data = await apiCall('/trades');
        trades = data.trades || [];
        renderTradesTable();
        updateCharts();
    } catch (error) {
        console.error('Failed to load trades:', error);
    }
}

async function saveSettings(newSettings) {
    try {
        const data = await apiCall('/settings', {
            method: 'POST',
            body: JSON.stringify(newSettings)
        });
        
        settings = { ...settings, ...data };
        showToast('Success', 'Settings saved successfully', 'success');
        return true;
    } catch (error) {
        showToast('Error', 'Failed to save settings', 'error');
        return false;
    }
}

// ===== UI UPDATES =====
function populateSettingsForm() {
    document.getElementById('setting-max-amount').value = settings.max_trade_amount || '';
    document.getElementById('setting-percentage').value = settings.trade_percentage || '';
    document.getElementById('setting-max-trades').value = settings.max_trades_per_hour || '';
    document.getElementById('setting-poll-interval').value = settings.poll_interval_seconds || '';
    document.getElementById('setting-target-wallet').value = settings.target_wallet || '';
}

function updateStatsDisplay(stats) {
    document.getElementById('stat-total-trades').textContent = stats.total_trades || 0;
    document.getElementById('stat-executed').textContent = stats.executed || 0;
    document.getElementById('stat-failed').textContent = stats.failed || 0;
    document.getElementById('stat-volume').textContent = formatCurrency(stats.total_volume || 0);
    document.getElementById('stat-latency').textContent = formatLatency(stats.avg_latency_ms || 0);
    document.getElementById('stat-pnl').textContent = formatPnL(stats.pnl || 0);
    
    // Update PnL color
    const pnlEl = document.getElementById('stat-pnl');
    pnlEl.className = 'stat-value ' + (stats.pnl >= 0 ? 'pnl-positive' : 'pnl-negative');
}

function updateBotStatus(status) {
    const el = document.getElementById('bot-status');
    const dot = el.querySelector('.status-dot');
    
    el.className = 'status-badge';
    
    switch (status) {
        case 'running':
            el.classList.add('status-running');
            el.innerHTML = '<span class="status-dot"></span>Running';
            break;
        case 'stopped':
            el.classList.add('status-stopped');
            el.innerHTML = '<span class="status-dot"></span>Stopped';
            break;
        case 'paused':
            el.classList.add('status-paused');
            el.innerHTML = '<span class="status-dot"></span>Paused';
            break;
        default:
            el.classList.add('status-running');
            el.innerHTML = '<span class="status-dot"></span>Running';
    }
}

// ===== TRADE TABLE =====
function renderTradesTable() {
    const tbody = document.getElementById('trade-table-body');
    const emptyState = document.getElementById('empty-state');
    
    if (trades.length === 0) {
        tbody.innerHTML = '';
        emptyState.style.display = 'block';
        return;
    }
    
    emptyState.style.display = 'none';
    tbody.innerHTML = trades.map(trade => createTradeRow(trade)).join('');
    
    // Update trade count
    document.getElementById('trade-count').textContent = `${trades.length} trades`;
}

function createTradeRow(trade) {
    const sideClass = trade.side === 'BUY' ? 'side-buy' : 'side-sell';
    const statusClass = `status-${trade.status || 'pending'}`;
    const latencyClass = getLatencyClass(trade.latency_ms);
    const latencyText = formatLatency(trade.latency_ms);
    
    return `
        <tr data-trade-id="${trade.id}" class="${trade.isNew ? 'trade-new' : ''}">
            <td>${formatTime(trade.timestamp)}</td>
            <td>
                <div class="font-medium">${escapeHtml(trade.market || 'Unknown')}</div>
                ${trade.condition ? `<div class="text-xs text-pm-muted">${escapeHtml(trade.condition)}</div>` : ''}
            </td>
            <td class="${sideClass}">${trade.side}</td>
            <td>${formatNumber(trade.size)}</td>
            <td>$${formatNumber(trade.price)}</td>
            <td>
                <span class="latency-bar ${latencyClass}">
                    <span class="latency-dot"></span>
                    ${latencyText}
                </span>
            </td>
            <td class="${statusClass}">
                <i class="fas fa-${getStatusIcon(trade.status)}"></i>
                ${trade.status || 'Pending'}
            </td>
        </tr>
    `;
}

function addTradeToTable(trade) {
    trade.isNew = true;
    trades.unshift(trade);
    
    // Keep only max trades
    if (trades.length > CONFIG.MAX_TRADES_DISPLAY) {
        trades = trades.slice(0, CONFIG.MAX_TRADES_DISPLAY);
    }
    
    renderTradesTable();
    
    // Remove animation class after animation completes
    setTimeout(() => {
        const row = document.querySelector(`[data-trade-id="${trade.id}"]`);
        if (row) row.classList.remove('trade-new');
    }, 500);
    
    // Update charts
    updateCharts();
}

function updateTradeInTable(trade) {
    const index = trades.findIndex(t => t.id === trade.id);
    if (index !== -1) {
        trades[index] = { ...trades[index], ...trade };
        renderTradesTable();
    }
}

function updateStatsFromTrade(trade) {
    // Increment total
    const totalEl = document.getElementById('stat-total-trades');
    totalEl.textContent = parseInt(totalEl.textContent) + 1;
    
    // Update executed/failed
    if (trade.status === 'success') {
        const executedEl = document.getElementById('stat-executed');
        executedEl.textContent = parseInt(executedEl.textContent) + 1;
    } else if (trade.status === 'failed') {
        const failedEl = document.getElementById('stat-failed');
        failedEl.textContent = parseInt(failedEl.textContent) + 1;
    }
    
    // Update volume
    if (trade.size && trade.price) {
        const volumeEl = document.getElementById('stat-volume');
        const currentVolume = parseFloat(volumeEl.textContent.replace(/[^0-9.-]+/g, '')) || 0;
        const tradeVolume = trade.size * trade.price;
        volumeEl.textContent = formatCurrency(currentVolume + tradeVolume);
    }
}

// ===== CHARTS UPDATE =====
function updateCharts() {
    // Prepare data (last 20 trades)
    const recentTrades = trades.slice(0, 20).reverse();
    const labels = recentTrades.map(t => formatTimeShort(t.timestamp));
    
    // Update PnL chart
    const pnlData = recentTrades.map(t => t.pnl || 0);
    charts.pnl.data.labels = labels;
    charts.pnl.data.datasets[0].data = pnlData;
    charts.pnl.update('none');
    
    // Update Volume chart
    const buyVolume = recentTrades.map(t => t.side === 'BUY' ? (t.size || 0) : 0);
    const sellVolume = recentTrades.map(t => t.side === 'SELL' ? (t.size || 0) : 0);
    charts.volume.data.labels = labels;
    charts.volume.data.datasets[0].data = buyVolume;
    charts.volume.data.datasets[1].data = sellVolume;
    charts.volume.update('none');
    
    // Update Latency chart
    const latencyData = recentTrades.map(t => t.latency_ms || 0);
    charts.latency.data.labels = labels;
    charts.latency.data.datasets[0].data = latencyData;
    charts.latency.update('none');
}

// ===== EVENT LISTENERS =====
function setupEventListeners() {
    // Settings form
    document.getElementById('settings-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const newSettings = {
            max_trade_amount: parseFloat(document.getElementById('setting-max-amount').value) || 0,
            trade_percentage: parseFloat(document.getElementById('setting-percentage').value) || 0,
            max_trades_per_hour: parseInt(document.getElementById('setting-max-trades').value) || 0,
            poll_interval_seconds: parseInt(document.getElementById('setting-poll-interval').value) || 5
        };
        
        await saveSettings(newSettings);
    });
    
    // Reset button
    document.getElementById('btn-reset').addEventListener('click', () => {
        populateSettingsForm();
        showToast('Reset', 'Settings restored', 'info');
    });
}

// ===== AUTO REFRESH =====
function startAutoRefresh() {
    refreshTimer = setInterval(() => {
        loadStats();
        updateLastRefresh();
    }, CONFIG.REFRESH_INTERVAL);
}

function stopAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
}

function updateLastRefresh() {
    const now = new Date();
    document.getElementById('last-update').textContent = now.toLocaleTimeString();
}

// ===== UTILITY FUNCTIONS =====
function formatCurrency(value) {
    return '$' + parseFloat(value).toLocaleString('en-US', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2
    });
}

function formatPnL(value) {
    const prefix = value >= 0 ? '+' : '';
    return prefix + formatCurrency(value);
}

function formatNumber(value) {
    if (!value) return '0';
    return parseFloat(value).toLocaleString('en-US', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 4
    });
}

function formatLatency(ms) {
    if (!ms) return '0ms';
    if (ms < 1000) return `${Math.round(ms)}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
}

function getLatencyClass(ms) {
    if (!ms) return 'latency-good';
    if (ms < 2000) return 'latency-good';
    if (ms < 10000) return 'latency-warning';
    return 'latency-bad';
}

function formatTime(timestamp) {
    if (!timestamp) return '-';
    const date = new Date(timestamp);
    return date.toLocaleTimeString('de-DE', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

function formatTimeShort(timestamp) {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString('de-DE', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

function getStatusIcon(status) {
    switch (status) {
        case 'success': return 'check-circle';
        case 'failed': return 'times-circle';
        case 'pending': return 'clock';
        default: return 'question-circle';
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ===== TOAST NOTIFICATIONS =====
function showToast(title, message, type = 'info') {
    const container = document.getElementById('toast-container');
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <div class="toast-title">${escapeHtml(title)}</div>
        <div class="toast-message">${escapeHtml(message)}</div>
    `;
    
    container.appendChild(toast);
    
    // Remove after 4 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ===== WINDOW EVENTS =====
window.addEventListener('beforeunload', () => {
    stopAutoRefresh();
    if (socket) {
        socket.disconnect();
    }
});

window.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        stopAutoRefresh();
    } else {
        startAutoRefresh();
        loadStats();
    }
});

// Handle online/offline
window.addEventListener('online', () => {
    showToast('Online', 'Connection restored', 'success');
    if (!socket?.connected) {
        socket?.connect();
    }
});

window.addEventListener('offline', () => {
    showToast('Offline', 'Connection lost', 'error');
    updateConnectionStatus('disconnected');
});

// ===== BOT STATE (PLAY/PAUSE) =====
let botState = { state: 'paused', is_running: false };

async function loadBotState() {
    try {
        const response = await fetch('/api/bot/state');
        if (response.ok) {
            botState = await response.json();
            updatePlayPauseButton();
        }
    } catch (error) {
        console.error('Failed to load bot state:', error);
    }
}

async function toggleBotState() {
    try {
        const response = await fetch('/api/bot/state', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        
        if (response.ok) {
            botState = await response.json();
            updatePlayPauseButton();
            showToast(
                botState.is_running ? 'Bot Started' : 'Bot Paused',
                botState.is_running ? 'Copy trading is now active' : 'Copy trading is paused',
                botState.is_running ? 'success' : 'info'
            );
        }
    } catch (error) {
        console.error('Failed to toggle bot state:', error);
        showToast('Error', 'Failed to toggle bot state', 'error');
    }
}

function updatePlayPauseButton() {
    const btn = document.getElementById('btn-play-pause');
    const icon = document.getElementById('play-pause-icon');
    const text = document.getElementById('play-pause-text');
    
    if (botState.is_running) {
        btn.className = 'flex items-center space-x-2 px-4 py-2 rounded-lg font-semibold transition-all duration-200 running';
        btn.style.background = '#00d084';
        icon.className = 'fas fa-pause';
        text.textContent = 'Running';
    } else {
        btn.className = 'flex items-center space-x-2 px-4 py-2 rounded-lg font-semibold transition-all duration-200 paused';
        btn.style.background = '#ff4757';
        icon.className = 'fas fa-play';
        text.textContent = 'Paused';
    }
}

// ===== PROFILE MANAGEMENT =====
let profiles = [];

async function loadProfiles() {
    try {
        const response = await fetch('/api/profiles');
        if (response.ok) {
            profiles = await response.json();
            updateProfileSelect();
        }
    } catch (error) {
        console.error('Failed to load profiles:', error);
    }
}

function updateProfileSelect() {
    const select = document.getElementById('profile-select');
    select.innerHTML = '<option value="">Select Profile...</option>';
    
    profiles.forEach(profile => {
        const option = document.createElement('option');
        option.value = profile.id;
        option.textContent = `@${profile.username}`;
        if (profile.is_active) {
            option.textContent += ' (Active)';
            option.selected = true;
        }
        select.appendChild(option);
    });
}

async function activateProfile(profileId) {
    if (!profileId) return;
    
    try {
        const response = await fetch(`/api/profiles/${profileId}/activate`, {
            method: 'PUT'
        });
        
        if (response.ok) {
            const profile = await response.json();
            showToast('Profile Activated', `@${profile.username} is now the target`, 'success');
            await loadProfiles(); // Reload to update UI
        } else {
            const error = await response.json();
            showToast('Error', error.error || 'Failed to activate profile', 'error');
        }
    } catch (error) {
        console.error('Failed to activate profile:', error);
        showToast('Error', 'Failed to activate profile', 'error');
    }
}

async function addProfile(username, profileUrl) {
    try {
        const response = await fetch('/api/profiles', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username: username,
                profile_url: profileUrl
            })
        });
        
        if (response.ok) {
            const profile = await response.json();
            showToast('Profile Added', `@${profile.username} added successfully`, 'success');
            await loadProfiles();
            return true;
        } else {
            const error = await response.json();
            showToast('Error', error.error || 'Failed to add profile', 'error');
            return false;
        }
    } catch (error) {
        console.error('Failed to add profile:', error);
        showToast('Error', 'Failed to add profile', 'error');
        return false;
    }
}

// ===== MODAL HANDLING =====
function setupModalListeners() {
    const modal = document.getElementById('profile-modal');
    const btnAdd = document.getElementById('btn-add-profile');
    const btnClose = document.getElementById('btn-close-modal');
    const btnCancel = document.getElementById('btn-cancel-profile');
    const form = document.getElementById('profile-form');
    
    // Open modal
    btnAdd.addEventListener('click', () => {
        modal.classList.remove('hidden');
        document.getElementById('profile-username').focus();
    });
    
    // Close modal
    const closeModal = () => modal.classList.add('hidden');
    btnClose.addEventListener('click', closeModal);
    btnCancel.addEventListener('click', closeModal);
    
    // Close on overlay click
    modal.querySelector('.modal-overlay').addEventListener('click', closeModal);
    
    // Submit form
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('profile-username').value.trim();
        const url = document.getElementById('profile-url').value.trim();
        
        if (await addProfile(username, url)) {
            form.reset();
            closeModal();
        }
    });
}

// ===== EXTENDED SETUP =====
// Store original setupEventListeners reference
const originalSetupListeners = setupEventListeners;

setupEventListeners = function() {
    // Call original
    originalSetupListeners();
    
    // Setup Play/Pause button
    document.getElementById('btn-play-pause').addEventListener('click', toggleBotState);
    
    // Setup Profile selector
    document.getElementById('profile-select').addEventListener('change', (e) => {
        activateProfile(e.target.value);
    });
    
    // Setup Modal
    setupModalListeners();
};

// Extend initializeDashboard
const originalInit = initializeDashboard;

initializeDashboard = async function() {
    await originalInit();
    
    // Load bot state
    await loadBotState();
    
    // Load profiles
    await loadProfiles();
};

// Extend WebSocket handlers
const originalSocketHandlers = setupWebSocket;

setupWebSocket = function() {
    originalSocketHandlers();
    
    if (!socket) return;
    
    // Bot state updates
    socket.on('bot_state_update', (data) => {
        botState = data;
        updatePlayPauseButton();
    });
    
    // Profile updates
    socket.on('profile_added', () => {
        loadProfiles();
    });
    
    socket.on('profile_activated', (data) => {
        showToast('Profile Changed', `@${data.username} is now active`, 'info');
        loadProfiles();
    });
    
    socket.on('profile_deleted', () => {
        loadProfiles();
    });
};
