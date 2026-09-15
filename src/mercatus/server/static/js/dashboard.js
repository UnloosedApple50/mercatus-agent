/**
 * Mercatus Agent Dashboard — Single Page Application
 * Real-time WebSocket communication, charts, and interactive UI.
 */

(function () {
    'use strict';

    // === State ===
    const state = {
        currentPage: 'dashboard',
        sessionId: null,
        ws: null,
        wsConnected: false,
        reconnectAttempts: 0,
        maxReconnectAttempts: 10,
        isProcessing: false,
        theme: localStorage.getItem('mercatus_theme') || 'dark',
        lang: localStorage.getItem('mercatus_lang') || 'en',
        metrics: {
            cpuHistory: [],
            memoryHistory: [],
            networkRxHistory: [],
            networkTxHistory: [],
            throughputHistory: [],
            maxDataPoints: 60,
        },
        charts: {},
    };

    // === DOM Elements ===
    const elements = {
        sidebar: document.getElementById('sidebar'),
        menuToggle: document.getElementById('menu-toggle'),
        pageTitle: document.getElementById('page-title'),
        wsStatusDot: document.getElementById('ws-status-dot'),
        wsStatusText: document.getElementById('ws-status-text'),
        uptimeDisplay: document.getElementById('uptime-display'),
        notificationBadge: document.getElementById('notification-badge'),
        notificationsBtn: document.getElementById('notifications-btn'),
        refreshBtn: document.getElementById('refresh-btn'),
        navItems: document.querySelectorAll('.nav-item'),
        pages: document.querySelectorAll('.page'),
        modalOverlay: document.getElementById('modal-overlay'),
        modalTitle: document.getElementById('modal-title'),
        modalBody: document.getElementById('modal-body'),
        modalFooter: document.getElementById('modal-footer'),
        modalClose: document.getElementById('modal-close'),
        themeToggle: document.getElementById('theme-toggle'),
        themeIcon: document.getElementById('theme-icon'),
        themeLabel: document.getElementById('theme-label'),
        langSelect: document.getElementById('lang-select'),
        agentStatus: document.getElementById('agent-status'),
        modelName: document.getElementById('model-name'),
    };

    // === Theme Management ===
    function initTheme() {
        applyTheme(state.theme);
    }

    function applyTheme(theme) {
        state.theme = theme;
        localStorage.setItem('mercatus_theme', theme);

        if (theme === 'dark') {
            document.documentElement.removeAttribute('data-theme');
            elements.themeIcon.textContent = '🌙';
            elements.themeLabel.textContent = 'Dark';
        } else {
            document.documentElement.setAttribute('data-theme', 'light');
            elements.themeIcon.textContent = '☀️';
            elements.themeLabel.textContent = 'Light';
        }
    }

    function toggleTheme() {
        applyTheme(state.theme === 'dark' ? 'light' : 'dark');
    }

    // === Language Management ===
    function initLanguage() {
        if (elements.langSelect) {
            elements.langSelect.value = state.lang;
            elements.langSelect.addEventListener('change', (e) => {
                setLanguage(e.target.value);
            });
        }
        applyLanguage(state.lang);
    }

    function setLanguage(lang) {
        state.lang = lang;
        localStorage.setItem('mercatus_lang', lang);

        // Use i18n.js if available
        if (typeof window.setLanguage === 'function') {
            window.setLanguage(lang);
        } else {
            applyLanguage(lang);
        }

        // Update page title
        updatePageTitle();
    }

    function applyLanguage(lang) {
        // Apply data-i18n translations
        document.querySelectorAll('[data-i18n]').forEach((el) => {
            const key = el.getAttribute('data-i18n');
            if (typeof window.t === 'function') {
                el.textContent = window.t(key, el.textContent);
            }
        });

        // Apply placeholder translations
        document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
            const key = el.getAttribute('data-i18n-placeholder');
            if (typeof window.t === 'function') {
                el.setAttribute('placeholder', window.t(key, el.getAttribute('placeholder')));
            }
        });

        // Set RTL for Arabic
        if (lang === 'ar') {
            document.documentElement.setAttribute('dir', 'rtl');
        } else {
            document.documentElement.setAttribute('dir', 'ltr');
        }
    }

    function t(key, fallback) {
        if (typeof window.t === 'function') {
            return window.t(key, fallback);
        }
        return fallback || key;
    }

    // === Navigation ===
    const pageTitles = {
        dashboard: 'Dashboard',
        chat: 'Chat',
        memory: 'Memory',
        decisions: 'Decisions',
        knowledge: 'Knowledge',
        brainmap: 'Brain Map',
        analytics: 'Analytics',
        integrations: 'Integrations',
        training: 'Training',
        logs: 'Logs',
        security: 'Security',
        settings: 'Settings',
    };

    function navigateTo(pageName) {
        // Update nav items
        elements.navItems.forEach(item => {
            item.classList.toggle('active', item.dataset.page === pageName);
        });

        // Update pages
        elements.pages.forEach(page => {
            page.classList.toggle('active', page.id === `page-${pageName}`);
        });

        updatePageTitle();
        state.currentPage = pageName;

        // Load page data
        loadPageData(pageName);

        // Close mobile sidebar
        if (elements.sidebar) {
            elements.sidebar.classList.remove('open');
        }
    }

    function updatePageTitle() {
        const title = pageTitles[state.currentPage] || 'Mercatus';
        elements.pageTitle.textContent = title;
    }

    function loadPageData(pageName) {
        switch (pageName) {
            case 'dashboard':
                fetchDashboardData();
                break;
            case 'chat':
                break;
            case 'memory':
                fetchMemoryData();
                break;
            case 'decisions':
                fetchDecisionsData();
                break;
            case 'knowledge':
                fetchKnowledgeData();
                break;
            case 'integrations':
                fetchIntegrationsData();
                break;
            case 'training':
                fetchTrainingData();
                break;
            case 'analytics':
                fetchAnalyticsData();
                break;
            case 'logs':
                fetchLogsData();
                break;
            case 'security':
                fetchSecurityData();
                break;
            case 'brainmap':
                if (window.BrainMap && window.BrainMap.init) {
                    window.BrainMap.init();
                }
                break;
            case 'settings':
                fetchSettingsData();
                break;
        }
    }

    // === WebSocket Connection ===
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        try {
            state.ws = new WebSocket(wsUrl);

            state.ws.onopen = () => {
                state.wsConnected = true;
                state.reconnectAttempts = 0;
                updateConnectionStatus('connected');
            };

            state.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    handleWebSocketMessage(data);
                } catch (e) {
                    console.error('Failed to parse WS message:', e);
                }
            };

            state.ws.onclose = () => {
                state.wsConnected = false;
                updateConnectionStatus('disconnected');
                if (state.reconnectAttempts < state.maxReconnectAttempts) {
                    state.reconnectAttempts++;
                    const delay = Math.min(1000 * Math.pow(1.5, state.reconnectAttempts), 15000);
                    setTimeout(connectWebSocket, delay);
                }
            };

            state.ws.onerror = () => {
                state.wsConnected = false;
                updateConnectionStatus('error');
            };
        } catch (e) {
            console.error('Failed to create WebSocket:', e);
            updateConnectionStatus('error');
        }
    }

    function handleWebSocketMessage(data) {
        switch (data.type) {
            case 'connected':
                break;
            case 'response':
                hideTyping();
                displayChatResponse(data.payload);
                state.isProcessing = false;
                updateSendButton();
                break;
            case 'processing':
                break;
            case 'pong':
                break;
            case 'health':
                updateHealth(data.payload);
                break;
            case 'metrics':
                updateThroughputMetrics(data.payload);
                break;
            case 'system_metrics':
                updateDashboardMetrics(data.payload);
                break;
            case 'realtime_metrics':
                updateRealtimeMetrics(data.payload);
                break;
            case 'notification':
                handleNotification(data.payload);
                break;
            case 'error':
                hideTyping();
                displayChatError(data.payload.message);
                state.isProcessing = false;
                updateSendButton();
                break;
            default:
                break;
        }
    }

    function sendWSMessage(type, payload) {
        if (state.wsConnected && state.ws.readyState === WebSocket.OPEN) {
            state.ws.send(JSON.stringify({ type, payload }));
        }
    }

    function updateConnectionStatus(status) {
        elements.wsStatusDot.className = 'status-dot ' + status;
        const texts = {
            connected: 'Connected',
            disconnected: 'Disconnected',
            error: 'Error',
        };
        elements.wsStatusText.textContent = texts[status] || 'Connecting...';
    }

    // === Dashboard Data ===
    async function fetchDashboardData() {
        try {
            const sysResponse = await fetch('/api/v1/system/metrics');
            if (sysResponse.ok) {
                const sysData = await sysResponse.json();
                updateDashboardMetrics(sysData);
            }

            const metricsResponse = await fetch('/api/v1/metrics/throughput');
            if (metricsResponse.ok) {
                const metricsData = await metricsResponse.json();
                updateThroughputMetrics(metricsData);
            }

            const healthResponse = await fetch('/api/v1/health');
            if (healthResponse.ok) {
                const healthData = await healthResponse.json();
                updateQuickStats(healthData);
            }
        } catch (e) {
            console.error('Failed to fetch dashboard data:', e);
        }
    }

    function updateDashboardMetrics(data) {
        if (data.cpu) {
            const cpu = data.cpu.overall_percent || 0;
            document.getElementById('cpu-percent').textContent = `${Math.round(cpu)}%`;
            document.getElementById('cpu-cores').textContent = `${data.cpu.core_count || '--'} cores`;
            const cpuProgress = document.getElementById('cpu-progress');
            cpuProgress.style.width = `${cpu}%`;
            cpuProgress.className = 'progress-fill' + (cpu > 80 ? ' danger' : cpu > 60 ? ' warning' : '');
            state.metrics.cpuHistory.push(cpu);
            if (state.metrics.cpuHistory.length > state.metrics.maxDataPoints) {
                state.metrics.cpuHistory.shift();
            }
        }

        if (data.ram) {
            const ram = data.ram.percent_used || 0;
            document.getElementById('ram-percent').textContent = `${Math.round(ram)}%`;
            document.getElementById('ram-detail').textContent =
                `${data.ram.used_human || '--'} / ${data.ram.total_human || '--'}`;
            const ramProgress = document.getElementById('ram-progress');
            ramProgress.style.width = `${ram}%`;
            ramProgress.className = 'progress-fill' + (ram > 85 ? ' danger' : ram > 70 ? ' warning' : '');
            state.metrics.memoryHistory.push(ram);
            if (state.metrics.memoryHistory.length > state.metrics.maxDataPoints) {
                state.metrics.memoryHistory.shift();
            }
        }

        if (data.disks && data.disks.length > 0) {
            const disk = data.disks[0];
            const pct = disk.percent_used || 0;
            document.getElementById('disk-percent').textContent = `${Math.round(pct)}%`;
            document.getElementById('disk-detail').textContent =
                `${disk.used_human} / ${disk.total_human}`;
            const diskProgress = document.getElementById('disk-progress');
            diskProgress.style.width = `${pct}%`;
            diskProgress.className = 'progress-fill' + (pct > 90 ? ' danger' : pct > 75 ? ' warning' : '');
        }

        if (data.network) {
            document.getElementById('net-throughput').textContent =
                `${formatBytes(data.network.bytes_received + data.network.bytes_sent)}/s`;
            document.getElementById('net-detail').textContent =
                `↓ ${data.network.bytes_received_human} ↑ ${data.network.bytes_sent_human}`;
        }

        if (data.uptime_human) {
            elements.uptimeDisplay.textContent = data.uptime_human;
        }
    }

    function updateThroughputMetrics(data) {
        document.getElementById('tps-value').textContent = `${data.rolling_avg_tps || 0} tok/s`;
        document.getElementById('total-tokens').textContent = `${data.total_tokens || 0} total`;
        document.getElementById('avg-latency').textContent = `${data.avg_latency_ms || 0} ms avg`;
    }

    function updateQuickStats(data) {
        document.getElementById('stat-memories').textContent = data.memory_count || '--';
        document.getElementById('stat-sessions').textContent = '--';
    }

    function updateRealtimeMetrics(data) {
        if (data.cpu_percent !== undefined) {
            state.metrics.cpuHistory.push(data.cpu_percent);
            if (state.metrics.cpuHistory.length > state.metrics.maxDataPoints) {
                state.metrics.cpuHistory.shift();
            }
        }
        if (data.memory_percent !== undefined) {
            state.metrics.memoryHistory.push(data.memory_percent);
            if (state.metrics.memoryHistory.length > state.metrics.maxDataPoints) {
                state.metrics.memoryHistory.shift();
            }
        }
    }

    function updateHealth(data) {
        if (data.llm_connected !== undefined) {
            elements.agentStatus.textContent = data.llm_connected ? '● Ready' : '● Fallback';
            elements.agentStatus.className = data.llm_connected ? 'status-badge text-success' : 'status-badge text-warning';
        }
    }

    // === Analytics ===
    async function fetchAnalyticsData() {
        try {
            const convResponse = await fetch('/api/v1/analytics/conversations');
            if (convResponse.ok) {
                const data = await convResponse.json();
                document.getElementById('total-conversations').textContent = data.total || 0;
            }

            const memResponse = await fetch('/api/v1/analytics/memory');
            if (memResponse.ok) {
                const data = await memResponse.json();
                document.getElementById('total-memories-analytics').textContent = data.total || 0;
            }

            const tokenResponse = await fetch('/api/v1/analytics/tokens');
            if (tokenResponse.ok) {
                const data = await tokenResponse.json();
                document.getElementById('avg-confidence').textContent =
                    data.avg_confidence ? `${(data.avg_confidence * 100).toFixed(0)}%` : '--';
            }
        } catch (e) {
            console.error('Failed to fetch analytics:', e);
        }
    }

    // === Logs ===
    async function fetchLogsData() {
        const container = document.getElementById('logs-container');
        container.innerHTML = '<div class="loading-spinner">Loading logs...</div>';

        try {
            const response = await fetch('/api/v1/logs');
            if (response.ok) {
                const logs = await response.json();
                if (logs.length === 0) {
                    container.innerHTML = '<div class="text-muted">No logs available.</div>';
                    return;
                }
                container.innerHTML = logs.map(log =>
                    `<div class="log-entry">
                        <span class="text-muted">${log.timestamp}</span>
                        <span class="text-${log.level === 'error' ? 'error' : log.level === 'warning' ? 'warning' : 'success'}">[${log.level.toUpperCase()}]</span>
                        ${escapeHtml(log.message)}
                    </div>`
                ).join('');
            }
        } catch (e) {
            container.innerHTML = `<div class="text-error">Error loading logs: ${e.message}</div>`;
        }
    }

    // === Security ===
    async function fetchSecurityData() {
        try {
            const bruteForceResponse = await fetch('/api/v1/security/audit?type=brute_force');
            if (bruteForceResponse.ok) {
                const data = await bruteForceResponse.json();
                document.getElementById('bf-locked-count').textContent = data.locked || 0;
                document.getElementById('bf-attempts').textContent = data.tracked || 0;
            }

            const ipResponse = await fetch('/api/v1/security/audit?type=ip_blocking');
            if (ipResponse.ok) {
                const data = await ipResponse.json();
                document.getElementById('blocked-ips').textContent = data.blocked || 0;
                document.getElementById('total-violations').textContent = data.violations || 0;
            }

            const auditResponse = await fetch('/api/v1/security/audit?limit=20');
            if (auditResponse.ok) {
                const entries = await auditResponse.json();
                const container = document.getElementById('audit-log-container');
                if (entries.length === 0) {
                    container.innerHTML = '<div class="text-muted">No audit entries.</div>';
                } else {
                    container.innerHTML = entries.map(entry =>
                        `<div class="audit-entry">
                            <span class="text-muted">${entry.created_at}</span>
                            <strong>${entry.action}</strong>
                            ${entry.ip_address ? `from ${entry.ip_address}` : ''}
                        </div>`
                    ).join('');
                }
            }

            const sessionsResponse = await fetch('/api/v1/security/sessions');
            if (sessionsResponse.ok) {
                const sessions = await sessionsResponse.json();
                const container = document.getElementById('sessions-container');
                if (sessions.length === 0) {
                    container.innerHTML = '<div class="text-muted">No active sessions.</div>';
                } else {
                    container.innerHTML = sessions.map(session =>
                        `<div class="session-entry">
                            <span class="text-muted">${session.ip_address}</span>
                            <span>${session.session_id?.substring(0, 16)}...</span>
                        </div>`
                    ).join('');
                }
            }
        } catch (e) {
            console.error('Failed to fetch security data:', e);
        }
    }

    // === Memory Page ===
    async function fetchMemoryData() {
        const container = document.getElementById('memory-list');
        container.innerHTML = '<div class="loading-spinner">Loading memories...</div>';

        try {
            const typeFilter = document.getElementById('memory-type-filter')?.value || 'all';
            const moduleFilter = document.getElementById('memory-module-filter')?.value || 'all';
            const search = document.getElementById('memory-search')?.value || '';

            let memories = [];

            if (typeFilter === 'all' || typeFilter === 'episodic') {
                let url = '/api/v1/memory/episodic?limit=50';
                if (moduleFilter !== 'all') url += `&module=${moduleFilter}`;
                const resp = await fetch(url);
                if (resp.ok) {
                    const data = await resp.json();
                    memories = memories.concat(data.map(m => ({ ...m, type: 'episodic' })));
                }
            }

            if (typeFilter === 'all' || typeFilter === 'semantic') {
                let url = '/api/v1/memory/semantic?limit=50';
                if (moduleFilter !== 'all') url += `&module=${moduleFilter}`;
                const resp = await fetch(url);
                if (resp.ok) {
                    const data = await resp.json();
                    memories = memories.concat(data.map(m => ({ ...m, type: 'semantic' })));
                }
            }

            if (search) {
                const searchLower = search.toLowerCase();
                memories = memories.filter(m =>
                    (m.query && m.query.toLowerCase().includes(searchLower)) ||
                    (m.response && m.response.toLowerCase().includes(searchLower)) ||
                    (m.key && m.key.toLowerCase().includes(searchLower)) ||
                    (m.value && m.value.toLowerCase().includes(searchLower))
                );
            }

            renderMemoryList(memories);
        } catch (e) {
            container.innerHTML = `<div class="loading-spinner">Error loading memories: ${e.message}</div>`;
        }
    }

    function renderMemoryList(memories) {
        const container = document.getElementById('memory-list');
        if (memories.length === 0) {
            container.innerHTML = '<div class="loading-spinner">No memories found.</div>';
            return;
        }

        container.innerHTML = memories.map(m => `
            <div class="memory-item">
                <div class="memory-item-header">
                    <span class="memory-type-badge">${m.type}</span>
                    <span class="text-muted">${m.module || 'general'}</span>
                </div>
                <div class="memory-item-content">
                    ${m.type === 'episodic'
                        ? `<strong>Q:</strong> ${escapeHtml(m.query?.substring(0, 100) || '')}...<br>
                           <strong>A:</strong> ${escapeHtml(m.response?.substring(0, 150) || '')}...`
                        : `<strong>${escapeHtml(m.key || '')}:</strong> ${escapeHtml(m.value?.substring(0, 200) || '')}`
                    }
                </div>
            </div>
        `).join('');
    }

    // === Decisions Page ===
    async function fetchDecisionsData() {
        const container = document.getElementById('decisions-list');
        container.innerHTML = '<div class="loading-spinner">Loading decisions...</div>';

        try {
            const resp = await fetch('/api/v1/decisions');
            if (resp.ok) {
                const decisions = await resp.json();
                renderDecisionsList(decisions);
            } else {
                container.innerHTML = '<div class="loading-spinner">No decisions recorded yet.</div>';
            }
        } catch (e) {
            container.innerHTML = `<div class="loading-spinner">Error: ${e.message}</div>`;
        }
    }

    function renderDecisionsList(decisions) {
        const container = document.getElementById('decisions-list');
        if (decisions.length === 0) {
            container.innerHTML = '<div class="loading-spinner">No decisions found.</div>';
            return;
        }

        container.innerHTML = decisions.map(d => `
            <div class="decision-item">
                <div class="decision-item-header">
                    <span class="decision-module-badge">${d.module || 'general'}</span>
                    <span class="text-muted">${d.selected_option || 'pending'}</span>
                </div>
                <div class="decision-item-content">
                    <strong>Context:</strong> ${escapeHtml(d.context?.substring(0, 150) || '')}...<br>
                    <strong>Confidence:</strong> ${Math.round((d.confidence || 0) * 100)}%
                </div>
            </div>
        `).join('');
    }

    // === Knowledge Page ===
    async function fetchKnowledgeData() {
        const container = document.getElementById('knowledge-grid');
        container.innerHTML = '<div class="loading-spinner">Loading knowledge...</div>';

        try {
            const resp = await fetch('/api/v1/memory/semantic?limit=100');
            if (resp.ok) {
                const knowledge = await resp.json();
                renderKnowledgeGrid(knowledge);
            }
        } catch (e) {
            container.innerHTML = `<div class="loading-spinner">Error: ${e.message}</div>`;
        }
    }

    function renderKnowledgeGrid(knowledge) {
        const container = document.getElementById('knowledge-grid');
        if (knowledge.length === 0) {
            container.innerHTML = '<div class="loading-spinner">No knowledge entries found.</div>';
            return;
        }

        container.innerHTML = knowledge.map(k => `
            <div class="knowledge-card">
                <div class="knowledge-card-header">
                    <span class="knowledge-card-category">${k.category}</span>
                    <span class="text-muted">${k.module}</span>
                </div>
                <div class="knowledge-card-key">${escapeHtml(k.key)}</div>
                <div class="knowledge-card-value">${escapeHtml(k.value?.substring(0, 200) || '')}</div>
            </div>
        `).join('');
    }

    // === Integrations Page ===
    async function fetchIntegrationsData() {
        try {
            const resp = await fetch('/api/v1/integrations/webhooks');
            if (resp.ok) {
                const webhooks = await resp.json();
                renderWebhooksList(webhooks);
            }
        } catch (e) {
            console.error('Failed to load integrations:', e);
        }
    }

    function renderWebhooksList(webhooks) {
        const container = document.getElementById('webhooks-list');
        if (webhooks.length === 0) {
            container.innerHTML = '<div class="text-muted">No webhooks registered.</div>';
            return;
        }

        container.innerHTML = webhooks.map(w => `
            <div class="memory-item">
                <div class="memory-item-header">
                    <span class="memory-type-badge">${w.id}</span>
                    <span class="text-muted">${w.active ? 'Active' : 'Inactive'}</span>
                </div>
                <div class="memory-item-content">
                    <strong>URL:</strong> ${escapeHtml(w.url)}<br>
                    <strong>Events:</strong> ${w.events?.join(', ') || 'None'}
                </div>
            </div>
        `).join('');
    }

    // === Training Page ===
    async function fetchTrainingData() {
        try {
            const resp = await fetch('/api/v1/training/stats');
            if (resp.ok) {
                const stats = await resp.json();
                document.getElementById('total-feedback').textContent = stats.total_feedback || 0;
                document.getElementById('avg-rating').textContent = stats.avg_rating || '0.0';
                document.getElementById('corrections-count').textContent = stats.corrections || 0;
            }
        } catch (e) {
            console.error('Failed to load training stats:', e);
        }
    }

    // === Settings Page ===
    async function fetchSettingsData() {
        try {
            const resp = await fetch('/api/v1/settings');
            if (resp.ok) {
                const settings = await resp.json();
                if (settings.llm_base_url) document.getElementById('setting-llm-url').value = settings.llm_base_url;
                if (settings.llm_model) document.getElementById('setting-llm-model').value = settings.llm_model;
            }
        } catch (e) {
            console.log('Settings endpoint not available');
        }
    }

    // === Chat Functions ===
    function initChat() {
        const chatInput = document.getElementById('chat-input');
        const sendBtn = document.getElementById('send-btn');
        const chatModule = document.getElementById('chat-module');
        const newChatBtn = document.getElementById('new-chat-btn');

        if (chatInput) {
            chatInput.addEventListener('input', function() {
                document.getElementById('input-count').textContent = `${this.value.length}/10000`;
                this.style.height = 'auto';
                this.style.height = Math.min(this.scrollHeight, 120) + 'px';
            });

            chatInput.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendChatMessage();
                }
            });
        }

        if (sendBtn) sendBtn.addEventListener('click', sendChatMessage);
        if (newChatBtn) newChatBtn.addEventListener('click', clearChat);
    }

    function sendChatMessage() {
        const input = document.getElementById('chat-input');
        const module = document.getElementById('chat-module').value;
        const message = input.value.trim();

        if (!message || state.isProcessing) return;

        displayUserMessage(message);
        input.value = '';
        input.style.height = 'auto';
        document.getElementById('input-count').textContent = '0/10000';
        state.isProcessing = true;
        updateSendButton();

        if (state.wsConnected) {
            sendWSMessage('chat', { message, module, session_id: state.sessionId });
        } else {
            sendChatRest(message, module);
        }

        showTyping();
    }

    async function sendChatRest(message, module) {
        try {
            const response = await fetch('/api/v1/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, module, session_id: state.sessionId }),
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            hideTyping();
            displayChatResponse(data);
        } catch (error) {
            hideTyping();
            displayChatError(error.message);
        } finally {
            state.isProcessing = false;
            updateSendButton();
        }
    }

    function displayUserMessage(text) {
        const container = document.getElementById('chat-messages');
        const div = document.createElement('div');
        div.className = 'message user';
        div.innerHTML = `
            <div class="message-avatar">👤</div>
            <div class="message-content">${escapeHtml(text)}</div>
        `;
        container.appendChild(div);
        scrollChatToBottom();
    }

    function displayChatResponse(data) {
        const container = document.getElementById('chat-messages');
        const div = document.createElement('div');
        div.className = 'message assistant';

        const conf = Math.round((data.confidence || 0) * 100);
        const confColor = conf > 70 ? 'var(--success)' : conf > 40 ? 'var(--warning)' : 'var(--error)';
        const confBg = conf > 70 ? 'var(--success-bg)' : conf > 40 ? 'var(--warning-bg)' : 'var(--error-bg)';

        div.innerHTML = `
            <div class="message-avatar">✦</div>
            <div class="message-content">
                ${formatMessage(data.response || '')}
                <div class="message-meta">
                    <span class="confidence-badge" style="background: ${confBg}; color: ${confColor}">
                        ${conf}% confidence
                    </span>
                    ${data.fallback ? '<span class="fallback-badge">Rule-based</span>' : ''}
                </div>
            </div>
        `;
        container.appendChild(div);

        if (data.session_id) state.sessionId = data.sessionId;
        scrollChatToBottom();
    }

    function displayChatError(message) {
        const container = document.getElementById('chat-messages');
        const div = document.createElement('div');
        div.className = 'message assistant';
        div.innerHTML = `
            <div class="message-avatar">⚠</div>
            <div class="message-content" style="border-color: var(--error);">
                <p style="color: var(--error);">${escapeHtml(message)}</p>
            </div>
        `;
        container.appendChild(div);
        scrollChatToBottom();
    }

    function showTyping() {
        const container = document.getElementById('chat-messages');
        const div = document.createElement('div');
        div.className = 'message assistant';
        div.id = 'typing-indicator';
        div.innerHTML = `
            <div class="message-avatar">✦</div>
            <div class="message-content">
                <div class="typing-indicator">
                    <span></span><span></span><span></span>
                </div>
            </div>
        `;
        container.appendChild(div);
        scrollChatToBottom();
    }

    function hideTyping() {
        const el = document.getElementById('typing-indicator');
        if (el) el.remove();
    }

    function scrollChatToBottom() {
        const container = document.getElementById('chat-messages');
        if (container) container.scrollTop = container.scrollHeight;
    }

    function clearChat() {
        const container = document.getElementById('chat-messages');
        container.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">✦</div>
                <h2 data-i18n="chat.welcome">Welcome to Mercatus</h2>
                <p>Ask about sales strategies, trading analysis, or general advisory.</p>
            </div>
        `;
        state.sessionId = null;
    }

    function updateSendButton() {
        const btn = document.getElementById('send-btn');
        if (btn) btn.disabled = state.isProcessing;
    }

    // === Utility Functions ===
    function formatBytes(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatMessage(text) {
        let html = escapeHtml(text);
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\n/g, '<br>');
        return html;
    }

    function handleNotification(data) {
        const badge = elements.notificationBadge;
        const currentCount = parseInt(badge.textContent) || 0;
        badge.textContent = currentCount + 1;
        badge.style.display = 'flex';
    }

    function showModal(title, body, footer) {
        elements.modalTitle.textContent = title;
        elements.modalBody.innerHTML = body;
        elements.modalFooter.innerHTML = footer || '';
        elements.modalOverlay.style.display = 'flex';
    }

    function hideModal() {
        elements.modalOverlay.style.display = 'none';
    }

    // === Event Listeners ===
    function setupEventListeners() {
        // Navigation
        elements.navItems.forEach(item => {
            item.addEventListener('click', () => navigateTo(item.dataset.page));
        });

        // Theme toggle
        if (elements.themeToggle) {
            elements.themeToggle.addEventListener('click', toggleTheme);
        }

        // Menu toggle
        if (elements.menuToggle) {
            elements.menuToggle.addEventListener('click', () => {
                elements.sidebar.classList.toggle('open');
            });
        }

        // Refresh button
        if (elements.refreshBtn) {
            elements.refreshBtn.addEventListener('click', () => {
                loadPageData(state.currentPage);
            });
        }

        // Modal close
        if (elements.modalClose) elements.modalClose.addEventListener('click', hideModal);
        if (elements.modalOverlay) {
            elements.modalOverlay.addEventListener('click', (e) => {
                if (e.target === elements.modalOverlay) hideModal();
            });
        }

        // Memory filters
        document.getElementById('memory-type-filter')?.addEventListener('change', fetchMemoryData);
        document.getElementById('memory-module-filter')?.addEventListener('change', fetchMemoryData);
        document.getElementById('memory-search')?.addEventListener('input', debounce(fetchMemoryData, 300));
        document.getElementById('refresh-memories')?.addEventListener('click', fetchMemoryData);

        // Integrations
        document.getElementById('register-webhook-btn')?.addEventListener('click', registerWebhook);
        document.getElementById('generate-key-btn')?.addEventListener('click', generateApiKey);
        document.getElementById('export-obsidian-btn')?.addEventListener('click', exportObsidian);
        document.getElementById('sync-obsidian-btn')?.addEventListener('click', syncObsidian);

        // Training
        document.getElementById('adapt-btn')?.addEventListener('click', runAdaptation);

        // Settings
        document.getElementById('test-llm-btn')?.addEventListener('click', testLlmConnection);
        document.getElementById('vacuum-db-btn')?.addEventListener('click', vacuumDatabase);
        document.getElementById('backup-btn')?.addEventListener('click', createBackup);
        document.getElementById('restore-btn')?.addEventListener('click', restoreBackup);

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') hideModal();
            if (e.ctrlKey && e.key === 'k') {
                e.preventDefault();
                document.getElementById('global-search')?.focus();
            }
        });
    }

    async function registerWebhook() {
        const url = document.getElementById('webhook-url')?.value;
        const eventsSelect = document.getElementById('webhook-events');
        const events = eventsSelect ? Array.from(eventsSelect.selectedOptions).map(o => o.value) : [];

        if (!url) {
            showModal('Error', '<p>Please enter a webhook URL.</p>');
            return;
        }

        try {
            const resp = await fetch('/api/v1/integrations/webhooks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, events }),
            });

            if (resp.ok) {
                showModal('Success', '<p>Webhook registered successfully!</p>');
                fetchIntegrationsData();
            } else {
                const err = await resp.json();
                showModal('Error', `<p>${err.detail || 'Failed to register webhook'}</p>`);
            }
        } catch (e) {
            showModal('Error', `<p>${e.message}</p>`);
        }
    }

    async function generateApiKey() {
        const name = document.getElementById('api-key-name')?.value;
        const scopesSelect = document.getElementById('api-key-scopes');
        const scopes = scopesSelect ? Array.from(scopesSelect.selectedOptions).map(o => o.value) : [];

        if (!name) {
            showModal('Error', '<p>Please enter a key name.</p>');
            return;
        }

        try {
            const resp = await fetch('/api/v1/integrations/api-keys', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, scopes }),
            });

            if (resp.ok) {
                const data = await resp.json();
                showModal('API Key Generated',
                    `<p>Your API key (copy it now, it won't be shown again):</p>
                     <code style="display:block;padding:12px;background:var(--bg-input);border-radius:8px;margin:12px 0;word-break:break-all;">${data.key}</code>`,
                    '<button class="btn btn-primary" onclick="hideModal()">Done</button>'
                );
            } else {
                const err = await resp.json();
                showModal('Error', `<p>${err.detail || 'Failed to generate key'}</p>`);
            }
        } catch (e) {
            showModal('Error', `<p>${e.message}</p>`);
        }
    }

    async function exportObsidian() {
        const statusContainer = document.getElementById('obsidian-status');
        statusContainer.innerHTML = '<div class="loading-spinner">Generating vault...</div>';

        try {
            const resp = await fetch('/api/v1/obsidian/export');
            if (resp.ok) {
                const blob = await resp.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'mercatus-vault.zip';
                a.click();
                window.URL.revokeObjectURL(url);
                statusContainer.innerHTML = '<div class="text-success">Vault exported successfully!</div>';
            } else {
                statusContainer.innerHTML = '<div class="text-error">Failed to export vault.</div>';
            }
        } catch (e) {
            statusContainer.innerHTML = `<div class="text-error">Error: ${e.message}</div>`;
        }
    }

    async function syncObsidian() {
        const statusContainer = document.getElementById('obsidian-status');
        statusContainer.innerHTML = '<div class="loading-spinner">Syncing vault...</div>';

        try {
            const resp = await fetch('/api/v1/obsidian/sync', { method: 'POST' });
            if (resp.ok) {
                const data = await resp.json();
                statusContainer.innerHTML = `<div class="text-success">Synced! ${data.total_notes} notes generated.</div>`;
            } else {
                statusContainer.innerHTML = '<div class="text-error">Failed to sync vault.</div>';
            }
        } catch (e) {
            statusContainer.innerHTML = `<div class="text-error">Error: ${e.message}</div>`;
        }
    }

    async function runAdaptation() {
        try {
            const resp = await fetch('/api/v1/training/adapt', { method: 'POST' });
            if (resp.ok) {
                const data = await resp.json();
                document.getElementById('adaptation-results').innerHTML =
                    `<pre>${JSON.stringify(data, null, 2)}</pre>`;
            }
        } catch (e) {
            console.error('Adaptation failed:', e);
        }
    }

    async function testLlmConnection() {
        const btn = document.getElementById('test-llm-btn');
        if (btn) {
            btn.textContent = 'Testing...';
            btn.disabled = true;
        }

        try {
            const resp = await fetch('/api/v1/health');
            if (resp.ok) {
                const data = await resp.json();
                showModal('LLM Status',
                    `<p>Status: <strong>${data.status}</strong></p>
                     <p>LLM Connected: <strong>${data.llm_connected ? 'Yes' : 'No'}</strong></p>`
                );
            }
        } catch (e) {
            showModal('Error', `<p>Connection test failed: ${e.message}</p>`);
        } finally {
            if (btn) {
                btn.textContent = 'Test Connection';
                btn.disabled = false;
            }
        }
    }

    async function vacuumDatabase() {
        try {
            const resp = await fetch('/api/v1/database/vacuum', { method: 'POST' });
            if (resp.ok) {
                showModal('Success', '<p>Database vacuumed successfully.</p>');
            } else {
                showModal('Error', '<p>Failed to vacuum database.</p>');
            }
        } catch (e) {
            showModal('Error', `<p>${e.message}</p>`);
        }
    }

    async function createBackup() {
        try {
            const resp = await fetch('/api/v1/backup/create', { method: 'POST' });
            if (resp.ok) {
                const data = await resp.json();
                showModal('Backup Created', `<p>Backup created: ${data.path}</p>`);
            } else {
                showModal('Error', '<p>Failed to create backup.</p>');
            }
        } catch (e) {
            showModal('Error', `<p>${e.message}</p>`);
        }
    }

    async function restoreBackup() {
        showModal('Restore Backup',
            '<p>Enter backup path to restore from:</p><input type="text" id="restore-path" placeholder="/path/to/backup.db">',
            '<button class="btn btn-danger" onclick="confirmRestore()">Restore</button>'
        );
    }

    function debounce(fn, delay) {
        let timeout;
        return function (...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => fn.apply(this, args), delay);
        };
    }

    // === Initialization ===
    function init() {
        initTheme();
        initLanguage();
        setupEventListeners();
        connectWebSocket();
        initChat();
        fetchDashboardData();

        // Periodic refresh
        setInterval(() => {
            if (state.currentPage === 'dashboard') fetchDashboardData();
        }, 5000);
    }

    // Start
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
