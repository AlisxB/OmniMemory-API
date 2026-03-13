// ─── State ──────────────────────────────────────────────────────────────────
let ACCESS_TOKEN = null;
let tenantsData = [];
let sessionChart = null, tenantChart = null;

// ─── Init ───────────────────────────────────────────────────────────────────
window.onload = () => {
    const t = localStorage.getItem('omni_token');
    if (t) { ACCESS_TOKEN = t; showApp(); }
    document.getElementById('login-pass').addEventListener('keydown', e => { if (e.key === 'Enter') doLogin(); });
};

// ─── Auth ────────────────────────────────────────────────────────────────────
async function doLogin() {
    const user = document.getElementById('login-user').value;
    const pass = document.getElementById('login-pass').value;
    const btn = document.getElementById('login-btn');
    const err = document.getElementById('login-error');
    err.textContent = '';
    btn.disabled = true; btn.textContent = 'Entrando...';
    try {
        const fd = new FormData(); fd.append('username', user); fd.append('password', pass);
        const r = await fetch('/admin/auth/login', { method: 'POST', body: fd });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || 'Credenciais inválidas');
        ACCESS_TOKEN = d.access_token;
        localStorage.setItem('omni_token', ACCESS_TOKEN);
        showApp();
    } catch (e) {
        err.textContent = '❌ ' + e.message;
    } finally {
        btn.disabled = false; btn.textContent = 'Entrar';
    }
}

function logout() {
    localStorage.removeItem('omni_token');
    ACCESS_TOKEN = null;
    document.getElementById('app').classList.remove('visible');
    document.getElementById('login-screen').style.display = 'flex';
    document.getElementById('login-pass').value = '';
}

function showApp() {
    document.getElementById('login-screen').style.display = 'none';
    document.getElementById('app').classList.add('visible');
    refreshAll();
}

// ─── API helpers ─────────────────────────────────────────────────────────────
async function api(path, opts = {}) {
    const headers = { 'Authorization': 'Bearer ' + ACCESS_TOKEN, 'Content-Type': 'application/json', ...(opts.headers || {}) };
    const r = await fetch(path, { ...opts, headers });
    if (r.status === 401) { logout(); throw new Error('Sessão expirada'); }
    const d = await r.json();
    if (!r.ok) throw new Error(d.data?.detail || d.detail || 'Erro na API');
    return d.data !== undefined ? d.data : d;
}

// ─── Navigation ──────────────────────────────────────────────────────────────
function switchSection(name) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.getElementById('section-' + name)?.classList.add('active');
    document.getElementById('nav-' + name)?.classList.add('active');
    const titles = { overview: 'Overview', tenants: 'Gerenciar Tenants', 'create-tenant': 'Novo Tenant', analytics: 'Analytics' };
    document.getElementById('topbar-title').textContent = titles[name] || name;
    if (name === 'tenants') renderTenants();
    if (name === 'analytics') populateSelectTenant();
}

// ─── Refresh All ─────────────────────────────────────────────────────────────
async function refreshAll() {
    await Promise.all([checkHealth(), loadStats(), loadTenants()]);
}

// ─── Health ──────────────────────────────────────────────────────────────────
async function checkHealth() {
    try {
        const r = await fetch('/health');
        const d = await r.json();
        const status = d.data?.status || 'unknown';
        const dot = document.getElementById('health-dot');
        const lbl = document.getElementById('health-label');
        dot.className = 'health-dot' + (status === 'healthy' ? '' : status === 'degraded' ? ' warn' : ' err');
        lbl.textContent = status === 'healthy' ? 'Sistema saudável' : status === 'degraded' ? 'Sistema degradado' : 'Erro';
    } catch { document.getElementById('health-dot').className = 'health-dot err'; }
}

// ─── Load Tenants ─────────────────────────────────────────────────────────────
async function loadTenants() {
    try {
        tenantsData = await api('/admin/api/tenants');
        renderTenants();
        renderOverviewTable();
        updateStatsFromTenants();
        renderCharts();
        renderAlerts();
    } catch (e) { toast('Erro ao carregar tenants: ' + e.message, 'error'); }
}

// ─── Load Stats ───────────────────────────────────────────────────────────────
async function loadStats() {
    try {
        const d = await api('/admin/api/stats');
        document.getElementById('stat-tenants').textContent = d.total_tenants ?? '—';
        document.getElementById('stat-users').textContent = d.total_users ?? '—';
        document.getElementById('stat-messages').textContent = d.total_messages ?? '—';
    } catch { }
}

function updateStatsFromTenants() {
    const expired = tenantsData.filter(t => t.api_key_info?.needs_rotation).length;
    document.getElementById('stat-keys-expired').textContent = expired;
}

// ─── Alerts ───────────────────────────────────────────────────────────────────
function renderAlerts() {
    const container = document.getElementById('alerts-container');
    container.innerHTML = '';
    const expiring = tenantsData.filter(t => t.api_key_info?.needs_rotation);
    if (expiring.length > 0) {
        const div = document.createElement('div');
        div.className = 'alert alert-warn';
        div.innerHTML = `⚠️ <strong>${expiring.length} tenant${expiring.length > 1 ? 's' : ''}</strong> com API Key sem rotação há mais de 90 dias: <strong>${expiring.map(t => t.id).join(', ')}</strong>`;
        container.appendChild(div);
    }
}

// ─── Render Tables ────────────────────────────────────────────────────────────
function renderOverviewTable() {
    const tbody = document.getElementById('overview-tbody');
    tbody.innerHTML = '';
    tenantsData.slice(0, 5).forEach(t => {
        const row = document.createElement('tr');
        row.innerHTML = `
      <td><span class="monospace">${t.id}</span></td>
      <td>${t.name}</td>
      <td>${statusBadge(t.is_active)}</td>
      <td>${keyAgeBadge(t.api_key_info)}</td>
      <td>${t.usage?.requests ?? 0} req</td>`;
        tbody.appendChild(row);
    });
    if (!tenantsData.length) tbody.innerHTML = '<tr class="empty-row"><td colspan="5">Nenhum tenant encontrado</td></tr>';
}

function renderTenants(filter = '') {
    const tbody = document.getElementById('tenants-tbody');
    tbody.innerHTML = '';
    const list = filter
        ? tenantsData.filter(t => t.id.includes(filter.toLowerCase()) || t.name.toLowerCase().includes(filter.toLowerCase()))
        : tenantsData;

    if (!list.length) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="6">Nenhum tenant encontrado</td></tr>';
        return;
    }
    list.forEach(t => {
        const row = document.createElement('tr');
        const expires = t.subscription_expires_at ? new Date(t.subscription_expires_at).toLocaleDateString('pt-BR') : '—';
        const whCount = t.webhooks?.length || 0;
        const whUrl = whCount > 0 ? `<div style="font-size:10px;color:var(--muted);max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${whCount > 1 ? `🔔 ${whCount} webhooks` : t.webhooks[0].url}</div>` : '';
        row.innerHTML = `
      <td>
        <div style="font-weight:600;font-size:13px">${t.name}</div>
        <div class="monospace">${t.id}</div>
      </td>
      <td>${statusBadge(t.is_active)}</td>
      <td>${keyAgeBadge(t.api_key_info)}</td>
      <td style="color:var(--muted);font-size:12px">${expires}</td>
      <td style="font-size:12px">
        <div title="Uso de hoje (baseado em cache)">📅 ${t.usage?.requests ?? 0} req / ${fmtNum(t.usage?.tokens ?? 0)} tokens</div>
        <div title="Uso total acumulado no banco" style="color:var(--muted); font-size:11px">📊 ${t.total_usage?.requests ?? 0} req / ${fmtNum(t.total_usage?.tokens ?? 0)} tokens</div>
        ${whUrl}
      </td>
      <td>
        <div class="flex-gap">
          <button class="btn btn-warn btn-sm btn-icon" onclick="confirmRotateKey('${t.id}')" title="Rotacionar API Key">🔑</button>
          <button class="btn btn-ghost btn-sm btn-icon" onclick="openWebhookModal('${t.id}', ${t.webhook_configured})" title="Configurar Webhook" style="color:${t.webhook_configured ? 'var(--success)' : 'var(--muted)'}">🔔</button>
          <button class="btn btn-ghost btn-sm btn-icon" onclick="toggleTenant('${t.id}',${t.is_active})" title="${t.is_active ? 'Desativar' : 'Ativar'}">${t.is_active ? '⏸' : '▶️'}</button>
          <button class="btn btn-danger btn-sm btn-icon" onclick="confirmDeleteTenant('${t.id}')" title="Deletar">🗑</button>
        </div>
      </td>`;
        tbody.appendChild(row);
    });
}

function filterTenants() {
    renderTenants(document.getElementById('search-tenant').value);
}

// ─── Charts ───────────────────────────────────────────────────────────────────
function renderCharts() {
    // Sessions donut (fake data — real data would come from per-tenant analytics)
    const sessCtx = document.getElementById('chart-sessions').getContext('2d');
    if (sessionChart) sessionChart.destroy();
    sessionChart = new Chart(sessCtx, {
        type: 'doughnut',
        data: {
            labels: ['Ativas', 'Expiradas', 'Fechadas'],
            datasets: [{
                data: [tenantsData.length * 3, tenantsData.length * 8, tenantsData.length * 5],
                backgroundColor: ['rgba(99,102,241,.8)', 'rgba(245,158,11,.8)', 'rgba(100,116,139,.6)'],
                borderWidth: 0
            }]
        },
        options: { plugins: { legend: { labels: { color: '#94a3b8', font: { size: 12 } } } }, cutout: '65%' }
    });

    // Tenants bar chart
    const tCtx = document.getElementById('chart-tenants').getContext('2d');
    if (tenantChart) tenantChart.destroy();
    const top = tenantsData.slice(0, 6);
    tenantChart = new Chart(tCtx, {
        type: 'bar',
        data: {
            labels: top.map(t => t.id),
            datasets: [{
                label: 'Requests hoje', data: top.map(t => t.usage?.requests || 0),
                backgroundColor: 'rgba(99,102,241,.7)', borderRadius: 6
            }]
        },
        options: {
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,.05)' } },
                y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,.05)' } }
            }
        }
    });
}

// ─── Tenant Actions ───────────────────────────────────────────────────────────
function confirmRotateKey(tenantId) {
    showModal({
        title: '🔑 Rotacionar API Key',
        body: `Deseja gerar uma nova API Key para <strong>${tenantId}</strong>? A chave atual será <strong>imediatamente invalidada</strong>.`,
        confirmText: 'Rotacionar', confirmClass: 'btn-warn',
        onConfirm: () => rotateKey(tenantId)
    });
}

async function rotateKey(tenantId) {
    try {
        const data = await api(`/admin/api/tenants/${tenantId}/rotate-key`, {
            method: 'POST',
            headers: { 'X-Super-Admin-Key': await askSuperAdminKey() }
        });
        showApiKeyModal(data.api_key, 'API Key Rotacionada com Sucesso');
        await loadTenants();
    } catch (e) { toast('Erro: ' + e.message, 'error'); }
}

async function toggleTenant(tenantId, currentActive) {
    try {
        await api(`/admin/api/tenants/${tenantId}`, {
            method: 'PATCH',
            body: JSON.stringify({ is_active: !currentActive })
        });
        toast(`Tenant ${!currentActive ? 'ativado' : 'desativado'} com sucesso`, 'success');
        await loadTenants();
    } catch (e) { toast('Erro: ' + e.message, 'error'); }
}

function confirmDeleteTenant(tenantId) {
    showModal({
        title: '🗑 Deletar Tenant',
        body: `Esta ação é <strong>irreversível</strong>. Todos os dados de <strong>${tenantId}</strong> (usuários, sessões, mensagens, memórias) serão removidos permanentemente.`,
        confirmText: 'Deletar', confirmClass: 'btn-danger',
        onConfirm: () => deleteTenant(tenantId)
    });
}

async function deleteTenant(tenantId) {
    try {
        const superKey = await askSuperAdminKey();
        await api(`/admin/api/tenants/${tenantId}`, {
            method: 'DELETE',
            headers: { 'X-Super-Admin-Key': superKey }
        });
        toast(`Tenant ${tenantId} removido`, 'warn');
        await loadTenants();
    } catch (e) { toast('Erro: ' + e.message, 'error'); }
}

// ─── Webhook Modal ────────────────────────────────────────────────────────────
let _webhookTenantId = null;

function openWebhookModal(tenantId, isConfigured) {
    _webhookTenantId = tenantId;
    const tenant = tenantsData.find(t => t.id === tenantId);

    document.getElementById('wh-tenant-label').textContent = tenantId;
    document.getElementById('wh-url').value = tenant?.webhooks?.[0]?.url || '';

    const container = document.getElementById('wh-list-container');
    container.innerHTML = '';

    if (tenant?.webhooks?.length > 0) {
        tenant.webhooks.forEach(w => {
            const div = document.createElement('div');
            div.style.padding = '8px';
            div.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
            div.style.display = 'flex';
            div.style.flexDirection = 'column';
            div.style.gap = '4px';
            div.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center">
                    <span style="font-size:12px; font-weight:600; color:var(--text)">${w.url}</span>
                    <span class="badge ${w.is_active ? 'badge-success' : 'badge-muted'}" style="font-size:10px">${w.is_active ? 'Ativo' : 'Inativo'}</span>
                </div>
                <div style="font-size:10px; color:var(--muted); cursor:pointer" onclick="copyToClipboard('${w.secret}', this)">
                    Secret: <span class="monospace">${w.secret}</span> 📋
                </div>
            `;
            container.appendChild(div);
        });
    } else {
        container.innerHTML = '<div style="text-align:center; color:var(--muted); font-size:12px; padding:20px">Nenhum webhook configurado.</div>';
    }

    document.getElementById('wh-status').textContent = isConfigured
        ? `✅ ${tenant?.webhooks?.length || 0} webhook(s) configurado(s)`
        : '⚪ Nenhum webhook configurado ainda';
    document.getElementById('wh-status').style.color = isConfigured ? 'var(--success)' : 'var(--muted)';

    // Buscar valor atual do buffer
    document.getElementById('wh-buffer').value = tenant?.settings?.buffer_window_seconds || 0;

    document.getElementById('wh-error').textContent = '';
    document.getElementById('wh-modal').style.display = 'flex';
}

function closeWebhookModal() {
    document.getElementById('wh-modal').style.display = 'none';
    _webhookTenantId = null;
}

async function saveWebhook() {
    const url = document.getElementById('wh-url').value.trim();
    const buffer = parseInt(document.getElementById('wh-buffer').value) || 0;
    if (!url) { document.getElementById('wh-error').textContent = 'URL é obrigatória.'; return; }
    if (!url.startsWith('http')) { document.getElementById('wh-error').textContent = 'URL deve começar com http:// ou https://'; return; }
    const btn = document.getElementById('wh-save-btn');
    btn.disabled = true; btn.textContent = 'Salvando...';
    try {
        // 1. Sincronizar URL do Webhook
        await api(`/admin/api/tenants/${_webhookTenantId}/webhooks/sync`, {
            method: 'POST',
            body: JSON.stringify({ url })
        });

        // 2. Sincronizar Buffer Window
        await api(`/admin/api/tenants/${_webhookTenantId}`, {
            method: 'PATCH',
            body: JSON.stringify({
                settings: { buffer_window_seconds: buffer }
            })
        });

        toast(`Configurações salvas para ${_webhookTenantId}`, 'success');
        closeWebhookModal();
        await loadTenants();
    } catch (e) {
        document.getElementById('wh-error').textContent = 'Erro: ' + e.message;
    } finally {
        btn.disabled = false; btn.textContent = '💾 Salvar Webhook';
    }
}

async function createTenant() {
    const id = document.getElementById('ct-id').value.trim();
    const name = document.getElementById('ct-name').value.trim();
    const rpm = parseInt(document.getElementById('ct-rpm').value) || 60;
    const tokens = parseInt(document.getElementById('ct-tokens').value) || 100000;
    const ttl = parseInt(document.getElementById('ct-ttl').value) || 30;
    const buffer = parseInt(document.getElementById('ct-buffer').value) || 0;
    const expires = document.getElementById('ct-expires').value;
    if (!id || !name) { toast('ID e Nome são obrigatórios', 'warn'); return; }
    const btn = document.getElementById('ct-btn'); btn.disabled = true; btn.textContent = 'Criando...';
    try {
        const data = await api('/admin/api/tenants', {
            method: 'POST',
            body: JSON.stringify({
                id, name,
                subscription_expires_at: expires ? expires + 'T00:00:00Z' : null,
                settings: {
                    rate_limit_rpm: rpm,
                    daily_token_limit: tokens,
                    session_ttl_minutes: ttl,
                    buffer_window_seconds: buffer
                }
            })
        });
        showApiKeyModal(data.api_key, 'Tenant Criado com Sucesso!');
        ['ct-id', 'ct-name'].forEach(f => document.getElementById(f).value = '');
        await loadTenants();
        switchSection('tenants');
    } catch (e) { toast('Erro: ' + e.message, 'error'); }
    finally { btn.disabled = false; btn.textContent = '🚀 Criar Tenant'; }
}

// ─── Analytics ────────────────────────────────────────────────────────────────
function populateSelectTenant() {
    const sel = document.getElementById('analytics-tenant-select');
    sel.innerHTML = '<option value="">Selecionar tenant...</option>';
    tenantsData.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.id; opt.textContent = `${t.name} (${t.id})`;
        sel.appendChild(opt);
    });
}

async function loadTenantAnalytics() {
    const tid = document.getElementById('analytics-tenant-select').value;
    if (!tid) { document.getElementById('analytics-content').style.display = 'none'; return; }
    try {
        const d = await api(`/v1/tenants/${tid}/analytics`, {
            headers: { 'Authorization': 'Bearer ' + ACCESS_TOKEN }
        });
        document.getElementById('analytics-content').style.display = 'block';
        const stats = document.getElementById('analytics-stats');
        const s = d.summary || {};
        stats.innerHTML = `
      <div class="stat-card"><div class="stat-icon">📁</div><div class="stat-label">Sessões</div><div class="stat-value">${s.total_sessions ?? 0}</div></div>
      <div class="stat-card"><div class="stat-icon">👥</div><div class="stat-label">Usuários</div><div class="stat-value">${s.total_users ?? 0}</div></div>
      <div class="stat-card"><div class="stat-icon">💬</div><div class="stat-label">Mensagens</div><div class="stat-value">${s.total_messages ?? 0}</div></div>
      <div class="stat-card"><div class="stat-icon">🔢</div><div class="stat-label">Tokens Hoje</div><div class="stat-value">${fmtNum(d.today?.tokens ?? 0)}</div></div>
    `;
        renderAnalyticsCharts(d);
    } catch (e) { toast('Erro ao carregar analytics: ' + e.message, 'error'); }
}

let analyticsSessionChart, analyticsUsageChart;
function renderAnalyticsCharts(d) {
    const statuses = d.session_status || {};
    const sessCtx2 = document.getElementById('chart-analytics-sessions').getContext('2d');
    if (analyticsSessionChart) analyticsSessionChart.destroy();
    analyticsSessionChart = new Chart(sessCtx2, {
        type: 'doughnut',
        data: {
            labels: Object.keys(statuses),
            datasets: [{
                data: Object.values(statuses),
                backgroundColor: ['rgba(16,185,129,.8)', 'rgba(239,68,68,.8)', 'rgba(245,158,11,.8)', 'rgba(99,102,241,.8)'],
                borderWidth: 0
            }]
        },
        options: { plugins: { legend: { labels: { color: '#94a3b8', font: { size: 12 } } } }, cutout: '60%' }
    });

    const usage = d.today || {};
    const uCtx = document.getElementById('chart-analytics-usage').getContext('2d');
    if (analyticsUsageChart) analyticsUsageChart.destroy();
    analyticsUsageChart = new Chart(uCtx, {
        type: 'bar',
        data: {
            labels: ['Requests', 'Tokens (÷100)'],
            datasets: [{
                data: [usage.requests || 0, Math.round((usage.tokens || 0) / 100)],
                backgroundColor: ['rgba(6,182,212,.7)', 'rgba(139,92,246,.7)'],
                borderRadius: 8
            }]
        },
        options: {
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,.05)' } },
                y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,.05)' } }
            }
        }
    });
}

// ─── UI Helpers ───────────────────────────────────────────────────────────────
function statusBadge(active) {
    return active
        ? '<span class="badge badge-success">● Ativo</span>'
        : '<span class="badge badge-muted">● Inativo</span>';
}

function keyAgeBadge(info) {
    if (!info) return '<span class="badge badge-muted">—</span>';
    const suffix = info.suffix ? `…${info.suffix}` : '';
    const age = info.age_days;
    if (info.needs_rotation) return `<span class="badge badge-danger key-age-badge">⚠ ${age}d ${suffix}</span>`;
    if (age !== null && age > 60) return `<span class="badge badge-warn key-age-badge">⏱ ${age}d ${suffix}</span>`;
    if (age !== null) return `<span class="badge badge-success key-age-badge">✓ ${age}d ${suffix}</span>`;
    return `<span class="badge badge-muted">${suffix || '—'}</span>`;
}

function fmtNum(n) {
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
    return n;
}

// ─── Modal ─────────────────────────────────────────────────────────────────
function showModal({ title, body, confirmText = 'Confirmar', confirmClass = 'btn-primary', onConfirm }) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
    <div class="modal-box">
      <h3>${title}</h3>
      <p>${body}</p>
      <div class="modal-actions">
        <button class="btn btn-ghost" onclick="this.closest('.modal-overlay').remove()">Cancelar</button>
        <button class="btn ${confirmClass}" id="modal-confirm-btn">${confirmText}</button>
      </div>
    </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('#modal-confirm-btn').onclick = () => { overlay.remove(); onConfirm(); };
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
}

function showApiKeyModal(apiKey, title) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
    <div class="modal-box">
      <h3>🔑 ${title}</h3>
      <p>Salve esta API Key em local seguro. <strong>Ela não será exibida novamente.</strong></p>
      <div class="api-key-box" onclick="copyToClipboard('${apiKey}',this)" title="Clique para copiar">${apiKey}</div>
      <div class="api-key-note">⚠️ Configure no seu orquestrador (n8n, etc.) como X-API-Key header.</div>
      <div class="modal-actions" style="margin-top:20px">
        <button class="btn btn-ghost" onclick="copyToClipboard('${apiKey}',this)">📋 Copiar</button>
        <button class="btn btn-primary" onclick="this.closest('.modal-overlay').remove()">Entendido ✓</button>
      </div>
    </div>`;
    document.body.appendChild(overlay);
}

function askSuperAdminKey() {
    return new Promise(resolve => {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
      <div class="modal-box">
        <h3>🔐 Super Admin Key</h3>
        <p>Esta operação requer a <strong>Super Admin Key</strong>.</p>
        <div class="form-field">
          <label>X-Super-Admin-Key</label>
          <input type="password" id="sak-input" placeholder="••••••••">
        </div>
        <div class="modal-actions" style="margin-top:16px">
          <button class="btn btn-ghost" onclick="this.closest('.modal-overlay').remove()">Cancelar</button>
          <button class="btn btn-primary" id="sak-btn">Confirmar</button>
        </div>
      </div>`;
        document.body.appendChild(overlay);
        overlay.querySelector('#sak-btn').onclick = () => {
            const val = overlay.querySelector('#sak-input').value;
            overlay.remove(); resolve(val);
        };
        overlay.querySelector('#sak-input').addEventListener('keydown', e => {
            if (e.key === 'Enter') { const val = overlay.querySelector('#sak-input').value; overlay.remove(); resolve(val); }
        });
    });
}

// ─── Toast ───────────────────────────────────────────────────────────────────
function toast(msg, type = 'info') {
    const icons = { success: '✅', error: '❌', warn: '⚠️', info: 'ℹ️' };
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.innerHTML = `<span class="toast-icon">${icons[type]}</span> <span>${msg}</span>`;
    container.appendChild(el);
    setTimeout(() => { el.classList.add('removing'); setTimeout(() => el.remove(), 300); }, 4000);
}

function copyToClipboard(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
        const orig = btn.textContent;
        btn.textContent = '✅ Copiado!';
        setTimeout(() => { btn.textContent = orig; }, 2000);
    });
    toast('Copiado para a área de transferência', 'success');
}
