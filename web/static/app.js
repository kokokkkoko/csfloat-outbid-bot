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

// Показать уведомление
function showNotification(message, type = 'info') {
    // Простая реализация - можно улучшить
    const color = type === 'success' ? 'green' : type === 'error' ? 'red' : 'blue';
    console.log(`[${type.toUpperCase()}] ${message}`);
    alert(message);
}

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
    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

async function saveSettings() {
    try {
        const settings = {
            check_interval: parseInt($('#settingInterval').value),
            outbid_step: parseFloat($('#settingStep').value),
            max_outbids: parseInt($('#settingMaxOutbids').value)
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
            tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-4 text-center text-gray-500">No accounts yet. Add one to get started!</td></tr>';
            return;
        }

        accounts.forEach(account => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="font-medium">${account.name}</span>
                    ${account.is_active ? '' : '<span class="ml-2 text-xs text-red-500">(Inactive)</span>'}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${account.api_key}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${account.proxy || 'None'}</td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="status-${account.status}">
                        ${account.status === 'online' ? '🟢' : account.status === 'error' ? '🔴' : '⚪'}
                        ${account.status}
                    </span>
                    ${account.error_message ? `<br><span class="text-xs text-red-500">${account.error_message}</span>` : ''}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${formatDate(account.last_check)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm">
                    <button onclick="testAccount(${account.id})" class="text-blue-600 hover:text-blue-800 mr-2">
                        <i class="fas fa-check"></i>
                    </button>
                    <button onclick="toggleAccount(${account.id}, ${!account.is_active})" class="text-yellow-600 hover:text-yellow-800 mr-2">
                        <i class="fas fa-${account.is_active ? 'pause' : 'play'}"></i>
                    </button>
                    <button onclick="deleteAccount(${account.id})" class="text-red-600 hover:text-red-800">
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
            tbody.innerHTML = '<tr><td colspan="7" class="px-6 py-4 text-center text-gray-500">No active orders</td></tr>';
            return;
        }

        orders.forEach(order => {
            const floatRange = order.order_type === 'advanced'
                ? `${order.float_min?.toFixed(4)} - ${order.float_max?.toFixed(4)}`
                : '-';

            const maxPrice = order.max_price_cents
                ? formatPrice(order.max_price_cents)
                : 'None';

            const row = document.createElement('tr');
            row.innerHTML = `
                <td class="px-6 py-4">
                    <div class="text-sm font-medium text-gray-900">${order.market_hash_name}</div>
                    <div class="text-xs text-gray-500">ID: ${order.order_id}</div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">${formatPrice(order.price_cents)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm">
                    <span class="px-2 py-1 rounded ${order.order_type === 'advanced' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'}">
                        ${order.order_type}
                    </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${floatRange}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm">
                    <span class="${order.outbid_count > 5 ? 'text-red-600 font-bold' : 'text-gray-900'}">
                        ${order.outbid_count}
                    </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${maxPrice}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm">
                    <button onclick="deleteOrder('${order.order_id}')" class="text-red-600 hover:text-red-800">
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
            tbody.innerHTML = '<tr><td colspan="5" class="px-6 py-4 text-center text-gray-500">No outbid history yet</td></tr>';
            return;
        }

        history.forEach(h => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${formatDate(h.timestamp)}</td>
                <td class="px-6 py-4 text-sm text-gray-900">${h.market_hash_name}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${formatPrice(h.old_price_cents)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-green-600">${formatPrice(h.new_price_cents)}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-red-600">${formatPrice(h.competitor_price_cents)}</td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading history:', error);
    }
}

// === Event Listeners ===

document.addEventListener('DOMContentLoaded', () => {
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
