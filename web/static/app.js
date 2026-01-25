// CSFloat Bot Frontend JavaScript

// API базовый URL
const API_BASE = '';

// Утилиты
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => document.querySelectorAll(selector);

// Форматирование даты
function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleString();
}

// Форматирование цены
function formatPrice(cents) {
    return `$${(cents / 100).toFixed(2)}`;
}

// Toast notification system
const Toast = {
    container: null,
    defaultDuration: 4000,

    init() {
        this.container = document.getElementById('toast-container');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'toast-container';
            document.body.appendChild(this.container);
        }
    },

    getIcon(type) {
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-times-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };
        return icons[type] || icons.info;
    },

    show(message, type = 'info', duration = null) {
        if (!this.container) this.init();

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        toast.innerHTML = `
            <i class="toast-icon fas ${this.getIcon(type)}"></i>
            <span class="toast-content">${message}</span>
            <span class="toast-close">&times;</span>
        `;

        // Close on click
        toast.querySelector('.toast-close').addEventListener('click', (e) => {
            e.stopPropagation();
            this.dismiss(toast);
        });

        toast.addEventListener('click', () => this.dismiss(toast));

        this.container.appendChild(toast);

        // Auto dismiss
        const dismissTime = duration || this.defaultDuration;
        setTimeout(() => this.dismiss(toast), dismissTime);

        // Log to console
        console.log(`[${type.toUpperCase()}] ${message}`);

        return toast;
    },

    dismiss(toast) {
        if (!toast || toast.classList.contains('removing')) return;

        toast.classList.add('removing');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    },

    success(message, duration) {
        return this.show(message, 'success', duration);
    },

    error(message, duration) {
        return this.show(message, 'error', duration || 6000);
    },

    warning(message, duration) {
        return this.show(message, 'warning', duration);
    },

    info(message, duration) {
        return this.show(message, 'info', duration);
    }
};

// Показать уведомление (wrapper function for backward compatibility)
function showNotification(message, type = 'info') {
    Toast.show(message, type);
}

// Theme manager for dark/light mode
const Theme = {
    init() {
        // Check for saved theme preference or default to system preference
        const savedTheme = localStorage.getItem('theme');
        const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

        if (savedTheme === 'dark' || (!savedTheme && systemDark)) {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }

        // Listen for system theme changes
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            if (!localStorage.getItem('theme')) {
                this.setTheme(e.matches ? 'dark' : 'light', false);
            }
        });
    },

    toggle() {
        const isDark = document.documentElement.classList.contains('dark');
        this.setTheme(isDark ? 'light' : 'dark', true);
    },

    setTheme(theme, save = true) {
        if (theme === 'dark') {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }

        if (save) {
            localStorage.setItem('theme', theme);
        }
    },

    isDark() {
        return document.documentElement.classList.contains('dark');
    }
};

// WebSocket client for real-time updates
const WS = {
    socket: null,
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
    reconnectDelay: 2000,
    pingInterval: null,

    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const token = localStorage.getItem('access_token') || '';
        const wsUrl = `${protocol}//${window.location.host}/ws?token=${token}`;

        try {
            this.socket = new WebSocket(wsUrl);

            this.socket.onopen = () => {
                console.log('[WS] Connected');
                this.reconnectAttempts = 0;

                // Start ping interval
                this.pingInterval = setInterval(() => {
                    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
                        this.socket.send(JSON.stringify({ type: 'ping' }));
                    }
                }, 30000);
            };

            this.socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (e) {
                    console.error('[WS] Error parsing message:', e);
                }
            };

            this.socket.onclose = (event) => {
                console.log('[WS] Disconnected:', event.code, event.reason);
                this.cleanup();
                this.scheduleReconnect();
            };

            this.socket.onerror = (error) => {
                console.error('[WS] Error:', error);
            };

        } catch (error) {
            console.error('[WS] Connection error:', error);
            this.scheduleReconnect();
        }
    },

    cleanup() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    },

    scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * this.reconnectAttempts;
            console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            setTimeout(() => this.connect(), delay);
        } else {
            console.log('[WS] Max reconnection attempts reached');
        }
    },

    handleMessage(data) {
        console.log('[WS] Received:', data.type, data);

        switch (data.type) {
            case 'bot_status_changed':
                this.onBotStatusChanged(data.data);
                break;

            case 'account_status_changed':
                this.onAccountStatusChanged(data.data);
                break;

            case 'order_outbid':
                this.onOrderOutbid(data);
                break;

            case 'notification':
                this.onNotification(data);
                break;

            case 'pong':
                // Heartbeat response, ignore
                break;

            default:
                console.log('[WS] Unknown message type:', data.type);
        }
    },

    onBotStatusChanged(data) {
        // Update bot status display
        if (data) {
            $('#botStatus').textContent = data.is_running ? '🟢 Running' : '🔴 Stopped';
            if (data.check_interval) {
                $('#checkInterval').textContent = `${data.check_interval}s`;
            }
        }
    },

    onAccountStatusChanged(data) {
        // Reload accounts to show updated status
        loadAccounts();
    },

    onOrderOutbid(data) {
        // Show notification and reload data
        Toast.success(data.message || 'Order outbid!');
        loadOrders();
        loadHistory();
    },

    onNotification(data) {
        const level = data.data?.level || 'info';
        const message = data.message || 'Notification';
        Toast.show(message, level);
    },

    disconnect() {
        this.cleanup();
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
    }
};

// === Bot Control ===

async function startBot() {
    try {
        const response = await fetch(`${API_BASE}/api/bot/start`, { method: 'POST' });
        const data = await response.json();

        if (response.ok) {
            showNotification('Bot started successfully!', 'success');
            await loadBotStatus();
        } else {
            showNotification(`Error: ${data.detail}`, 'error');
        }
    } catch (error) {
        showNotification(`Error starting bot: ${error.message}`, 'error');
    }
}

async function stopBot() {
    try {
        const response = await fetch(`${API_BASE}/api/bot/stop`, { method: 'POST' });
        const data = await response.json();

        if (response.ok) {
            showNotification('Bot stopped successfully!', 'success');
            await loadBotStatus();
        } else {
            showNotification(`Error: ${data.detail}`, 'error');
        }
    } catch (error) {
        showNotification(`Error stopping bot: ${error.message}`, 'error');
    }
}

async function loadBotStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/bot/status`);
        const data = await response.json();

        $('#botStatus').textContent = data.is_running ? '🟢 Running' : '🔴 Stopped';
        $('#checkInterval').textContent = `${data.check_interval}s`;
        $('#outbidStep').textContent = `$${data.outbid_step}`;
        $('#maxOutbids').textContent = data.max_outbids;
    } catch (error) {
        console.error('Error loading bot status:', error);
        $('#botStatus').textContent = '⚠️ Error';
    }
}

// === Settings ===

async function loadSettings() {
    try {
        const response = await fetch(`${API_BASE}/api/settings`);
        const data = await response.json();

        $('#settingInterval').value = data.check_interval;
        $('#settingStep').value = data.outbid_step;
        $('#settingMaxOutbids').value = data.max_outbids;
        $('#settingMultiplier').value = data.max_outbid_multiplier;
        $('#settingPremium').value = data.max_outbid_premium;
    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

async function saveSettings() {
    try {
        const settings = {
            check_interval: parseInt($('#settingInterval').value),
            outbid_step: parseFloat($('#settingStep').value),
            max_outbids: parseInt($('#settingMaxOutbids').value),
            max_outbid_multiplier: parseFloat($('#settingMultiplier').value),
            max_outbid_premium: parseFloat($('#settingPremium').value)
        };

        const response = await fetch(`${API_BASE}/api/settings`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });

        if (response.ok) {
            showNotification('Settings saved successfully!', 'success');
            await loadBotStatus();
        } else {
            const data = await response.json();
            showNotification(`Error: ${data.detail}`, 'error');
        }
    } catch (error) {
        showNotification(`Error saving settings: ${error.message}`, 'error');
    }
}

// === Accounts ===

async function loadAccounts() {
    try {
        const response = await fetch(`${API_BASE}/api/accounts`);
        const accounts = await response.json();

        const tbody = $('#accountsTable');
        tbody.innerHTML = '';

        if (accounts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-4 text-center text-gray-500 dark:text-gray-400">No accounts yet. Add one to get started!</td></tr>';
            return;
        }

        accounts.forEach(account => {
            const row = document.createElement('tr');
            row.className = 'dark:bg-gray-800';
            row.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="font-medium dark:text-white">${account.name}</span>
                    ${account.is_active ? '' : '<span class="ml-2 text-xs text-red-500">(Inactive)</span>'}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">${account.api_key}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">${account.proxy || 'None'}</td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="status-${account.status}">
                        ${account.status === 'online' ? '🟢' : account.status === 'error' ? '🔴' : '⚪'}
                        ${account.status}
                    </span>
                    ${account.error_message ? `<br><span class="text-xs text-red-500">${account.error_message}</span>` : ''}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">${formatDate(account.last_check)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm">
                    <button onclick="testAccount(${account.id})" class="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 mr-2">
                        <i class="fas fa-check"></i>
                    </button>
                    <button onclick="toggleAccount(${account.id}, ${!account.is_active})" class="text-yellow-600 hover:text-yellow-800 dark:text-yellow-400 dark:hover:text-yellow-300 mr-2">
                        <i class="fas fa-${account.is_active ? 'pause' : 'play'}"></i>
                    </button>
                    <button onclick="deleteAccount(${account.id})" class="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading accounts:', error);
    }
}

async function addAccount() {
    const name = $('#newAccountName').value.trim();
    const api_key = $('#newAccountKey').value.trim();
    const proxy = $('#newAccountProxy').value.trim() || null;

    if (!name || !api_key) {
        showNotification('Please fill in name and API key', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/accounts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, api_key, proxy })
        });

        if (response.ok) {
            showNotification('Account added successfully!', 'success');
            $('#addAccountModal').classList.add('hidden');
            $('#newAccountName').value = '';
            $('#newAccountKey').value = '';
            $('#newAccountProxy').value = '';
            await loadAccounts();
        } else {
            const data = await response.json();
            showNotification(`Error: ${data.detail}`, 'error');
        }
    } catch (error) {
        showNotification(`Error adding account: ${error.message}`, 'error');
    }
}

async function deleteAccount(accountId) {
    if (!confirm('Are you sure you want to delete this account?')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/accounts/${accountId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showNotification('Account deleted successfully!', 'success');
            await loadAccounts();
        } else {
            const data = await response.json();
            showNotification(`Error: ${data.detail}`, 'error');
        }
    } catch (error) {
        showNotification(`Error deleting account: ${error.message}`, 'error');
    }
}

async function toggleAccount(accountId, isActive) {
    try {
        const response = await fetch(`${API_BASE}/api/accounts/${accountId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_active: isActive })
        });

        if (response.ok) {
            showNotification(`Account ${isActive ? 'activated' : 'deactivated'}!`, 'success');
            await loadAccounts();
        } else {
            const data = await response.json();
            showNotification(`Error: ${data.detail}`, 'error');
        }
    } catch (error) {
        showNotification(`Error toggling account: ${error.message}`, 'error');
    }
}

async function testAccount(accountId) {
    try {
        const response = await fetch(`${API_BASE}/api/accounts/${accountId}/test`, {
            method: 'POST'
        });
        const data = await response.json();

        if (data.status === 'success') {
            showNotification('Connection test successful!', 'success');
        } else {
            showNotification(`Connection test failed: ${data.message}`, 'error');
        }

        await loadAccounts();
    } catch (error) {
        showNotification(`Error testing account: ${error.message}`, 'error');
    }
}

// === Orders ===

async function syncAndLoadOrders() {
    try {
        // Получаем все аккаунты
        const accountsResponse = await fetch(`${API_BASE}/api/accounts`);
        const accounts = await accountsResponse.json();

        // Синхронизируем ордера для каждого аккаунта
        for (const account of accounts) {
            if (account.status === 'online') {
                try {
                    await fetch(`${API_BASE}/api/accounts/${account.id}/sync-orders`, {
                        method: 'POST'
                    });
                } catch (error) {
                    console.error(`Failed to sync orders for ${account.name}:`, error);
                }
            }
        }

        // Загружаем обновленные ордера
        await loadOrders();
        showNotification('Orders synced successfully', 'success');
    } catch (error) {
        showNotification(`Error syncing orders: ${error.message}`, 'error');
    }
}

async function loadOrders() {
    try {
        const response = await fetch(`${API_BASE}/api/orders?active_only=true`);
        const orders = await response.json();

        const tbody = $('#ordersTable');
        tbody.innerHTML = '';

        if (orders.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="px-6 py-4 text-center text-gray-500 dark:text-gray-400">No active orders</td></tr>';
            return;
        }

        orders.forEach(order => {
            const floatRange = order.order_type === 'advanced'
                ? `${order.float_min?.toFixed(4)} - ${order.float_max?.toFixed(4)}`
                : '-';

            const maxPrice = order.max_price_cents
                ? formatPrice(order.max_price_cents)
                : 'None';

            // Construct Steam CDN icon URL
            const iconHtml = order.icon_url
                ? `<img src="https://community.akamai.steamstatic.com/economy/image/${order.icon_url}"
                       class="w-12 h-12 rounded object-cover flex-shrink-0"
                       onerror="this.style.display='none'"
                       loading="lazy">`
                : `<div class="w-12 h-12 rounded bg-gray-200 dark:bg-gray-600 flex items-center justify-center flex-shrink-0">
                       <i class="fas fa-image text-gray-400 dark:text-gray-500"></i>
                   </div>`;

            const row = document.createElement('tr');
            row.className = 'dark:bg-gray-800';
            row.innerHTML = `
                <td class="px-6 py-4">
                    <div class="flex items-center gap-3">
                        ${iconHtml}
                        <div class="min-w-0">
                            <div class="text-sm font-medium text-gray-900 dark:text-white truncate max-w-xs" title="${order.market_hash_name}">${order.market_hash_name}</div>
                            <div class="text-xs text-gray-500 dark:text-gray-400">ID: ${order.order_id}</div>
                        </div>
                    </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium dark:text-white">${formatPrice(order.price_cents)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm">
                    <span class="px-2 py-1 rounded ${order.order_type === 'advanced' ? 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200' : 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'}">
                        ${order.order_type}
                    </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">${floatRange}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm">
                    <span class="${order.outbid_count > 5 ? 'text-red-600 font-bold' : 'text-gray-900 dark:text-white'}">
                        ${order.outbid_count}
                    </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">${maxPrice}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm">
                    <button onclick="deleteOrder('${order.order_id}')" class="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300">
                        <i class="fas fa-times"></i> Cancel
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading orders:', error);
    }
}

async function deleteOrder(orderId) {
    if (!confirm('Are you sure you want to cancel this order?')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/orders/${orderId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showNotification('Order cancelled successfully!', 'success');
            await loadOrders();
        } else {
            const data = await response.json();
            showNotification(`Error: ${data.detail}`, 'error');
        }
    } catch (error) {
        showNotification(`Error cancelling order: ${error.message}`, 'error');
    }
}

// === History ===

async function loadHistory() {
    try {
        const response = await fetch(`${API_BASE}/api/history?limit=50`);
        const history = await response.json();

        const tbody = $('#historyTable');
        tbody.innerHTML = '';

        if (history.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="px-6 py-4 text-center text-gray-500 dark:text-gray-400">No outbid history yet</td></tr>';
            return;
        }

        history.forEach(h => {
            const row = document.createElement('tr');
            row.className = 'dark:bg-gray-800';
            row.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">${formatDate(h.timestamp)}</td>
                <td class="px-6 py-4 text-sm text-gray-900 dark:text-white">${h.market_hash_name}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">${formatPrice(h.old_price_cents)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-green-600 dark:text-green-400">${formatPrice(h.new_price_cents)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-red-600 dark:text-red-400">${formatPrice(h.competitor_price_cents)}</td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading history:', error);
    }
}

// === User/Auth Functions ===

async function checkCurrentUser() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        return null;
    }

    try {
        const response = await fetch(`${API_BASE}/api/auth/me`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
            // Token invalid, clear storage
            localStorage.removeItem('access_token');
            localStorage.removeItem('user');
            return null;
        }

        return await response.json();
    } catch (error) {
        console.error('Error checking user:', error);
        return null;
    }
}

function updateUserUI(user) {
    const userInfo = $('#userInfo');
    const adminLink = $('#adminLink');
    const logoutBtn = $('#logoutBtn');

    if (user) {
        if (userInfo) userInfo.textContent = user.username;
        if (adminLink && user.is_admin) adminLink.classList.remove('hidden');
        if (logoutBtn) {
            logoutBtn.classList.remove('hidden');
            logoutBtn.addEventListener('click', logout);
        }
    }
}

function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    window.location.href = '/login';
}

// === Event Listeners ===

document.addEventListener('DOMContentLoaded', async () => {
    // Initialize toast notifications
    Toast.init();

    // Initialize theme
    Theme.init();

    // Theme toggle
    const themeToggle = $('#themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', () => Theme.toggle());
    }

    // Check current user and update UI
    const user = await checkCurrentUser();
    updateUserUI(user);

    // Initialize WebSocket for real-time updates
    WS.connect();

    // Bot control
    $('#startBot').addEventListener('click', startBot);
    $('#stopBot').addEventListener('click', stopBot);

    // Settings
    $('#saveSettings').addEventListener('click', saveSettings);

    // Accounts
    $('#addAccountBtn').addEventListener('click', () => {
        $('#addAccountModal').classList.remove('hidden');
    });
    $('#saveAccount').addEventListener('click', addAccount);
    $('#cancelAccount').addEventListener('click', () => {
        $('#addAccountModal').classList.add('hidden');
    });

    // Orders
    $('#refreshOrders').addEventListener('click', syncAndLoadOrders);

    // Initial load
    loadBotStatus();
    loadSettings();
    loadAccounts();
    loadOrders();
    loadHistory();

    // Auto-refresh every 10 seconds
    setInterval(() => {
        loadBotStatus();
        loadAccounts();
        loadOrders();
        loadHistory();
    }, 10000);
});
