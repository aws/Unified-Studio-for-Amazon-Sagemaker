import { CONFIG } from '../config.js';
import { Auth } from '../auth.js';

// ── API helper ────────────────────────────────────────────────────────────────
const api = (path, opts = {}) => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
  return fetch(CONFIG.API_URL + path, {
    ...opts,
    signal: controller.signal,
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  }).then(r => {
    clearTimeout(timeout);
    if (!r.ok) throw new Error(`HTTP ${r.status} ${r.statusText}`);
    return r.json();
  }).catch(err => {
    clearTimeout(timeout);
    if (err.name === 'AbortError') throw new Error('Request timed out — credentials may be expired');
    throw err;
  });
};

// ── DOM refs ──────────────────────────────────────────────────────────────────
const navLinks      = document.querySelectorAll('.nav-link');
const views         = { dashboard: document.getElementById('view-dashboard'),
                        accounts:  document.getElementById('view-accounts'),
                        config:    document.getElementById('view-config') };
const poolCards     = document.getElementById('pool-cards');
const lastReconciled  = document.getElementById('last-reconciled');
const dashRefreshed   = document.getElementById('dashboard-refreshed');
const acctRefreshed   = document.getElementById('accounts-refreshed');
const btnReconcile    = document.getElementById('btn-reconcile-dry');
const btnReplenish    = document.getElementById('btn-replenish');
const btnRefreshDash  = document.getElementById('btn-refresh-dashboard');
const btnRefreshAccts = document.getElementById('btn-refresh-accounts');
const autoRefreshToggle   = document.getElementById('auto-refresh-toggle');
const autoRefreshInterval = document.getElementById('auto-refresh-interval');
const accountsTbody = document.getElementById('accounts-tbody');
const accountsEmpty = document.getElementById('accounts-empty');
const accountsCount  = document.getElementById('accounts-count');
const filterPool    = document.getElementById('filter-pool');
const filterState   = document.getElementById('filter-state');
const filterAccount = document.getElementById('filter-account');
const filterProject = document.getElementById('filter-project');
const detailPanel   = document.getElementById('detail-panel');
const panelTitle    = document.getElementById('panel-title');
const panelBody     = document.getElementById('panel-body');
const panelActions  = document.getElementById('panel-actions');
const panelClose    = document.getElementById('panel-close');
const opsDrawer     = document.getElementById('ops-drawer');
const opsToggle     = document.getElementById('ops-log-toggle');
const opsClose      = document.getElementById('ops-close');
const opsEntries    = document.getElementById('ops-entries');
const opsCount      = document.getElementById('ops-count');
const toast         = document.getElementById('toast');
const confirmDialog = document.getElementById('confirm-dialog');
const confirmTitle  = document.getElementById('confirm-title');
const confirmMsg    = document.getElementById('confirm-msg');
const confirmOk     = document.getElementById('confirm-ok');
const confirmCancel = document.getElementById('confirm-cancel');

// ── Navigation ────────────────────────────────────────────────────────────────
let currentView = 'dashboard';

navLinks.forEach(link => {
  link.addEventListener('click', e => {
    e.preventDefault();
    switchView(link.dataset.view);
  });
});

function switchView(name) {
  currentView = name;
  navLinks.forEach(l => l.classList.toggle('active', l.dataset.view === name));
  Object.entries(views).forEach(([k, el]) => el.hidden = k !== name);
  closePanel();
  if (name === 'dashboard') loadDashboard();
  if (name === 'accounts') loadAccounts();
  if (name === 'config') loadConfig();
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
async function loadDashboard() {
  poolCards.innerHTML = '<div class="loading">Loading…</div>';
  try {
    const { pools, lastReconciled: lr } = await api('/pool/summary');
    lastReconciled.textContent = lr ? `Last reconciled: ${fmtTime(lr)}` : '';
    dashRefreshed.textContent = `Refreshed ${fmtTime(new Date().toISOString())}`;
    poolCards.innerHTML = pools.map(renderPoolCard).join('');
    // Populate pool filter
    filterPool.innerHTML = '<option value="">All pools</option>' +
      pools.map(p => `<option value="${p.poolName}">${p.poolName}</option>`).join('');
  } catch {
    poolCards.innerHTML = '<div class="error-inline">Failed to load pool summary.</div>';
  }
}

function renderPoolCard(pool) {
  const c = pool.counts;
  const total = Object.values(c).reduce((a, b) => a + b, 0);
  const available = c.AVAILABLE || 0;
  const pct = total ? Math.round((available / total) * 100) : 0;
  const hasFailed = (c.FAILED || 0) > 0;
  return `
  <article class="pool-card ${hasFailed ? 'has-failed' : ''}">
    <header>
      <strong><span class="pool-label">Pool:</span> ${pool.poolName}</strong>
      ${hasFailed ? '<span class="badge-failed">⚠ Failed accounts</span>' : ''}
    </header>
    <div class="capacity-bar-wrap">
      <div class="capacity-bar">
        <div class="capacity-fill" style="width:${pct}%"></div>
      </div>
      <span class="capacity-label">${available} / ${total} available</span>
    </div>
    <div class="state-counts">
      ${renderCount('AVAILABLE', c.AVAILABLE)}
      ${renderCount('ASSIGNED', c.ASSIGNED)}
      ${renderCount('SETTING_UP', c.SETTING_UP)}
      ${renderCount('CLEANING', c.CLEANING)}
      ${renderCount('FAILED', c.FAILED)}
      ${renderCount('ORPHANED', c.ORPHANED)}
    </div>
    <footer>
      <button class="outline small" onclick="replenishPool('${pool.poolName}')">Replenish</button>
      <button class="outline secondary small" onclick="switchToAccounts('${pool.poolName}')">View accounts</button>
    </footer>
  </article>`;
}

function renderCount(state, n) {
  if (!n) return '';
  return `<span class="state-chip state-${state.toLowerCase()} clickable-chip"
    onclick="drillToState('${state}')"
    title="View ${state.replace('_',' ')} accounts">${state.replace('_', ' ')}: ${n}</span>`;
}

window.replenishPool = async (poolName) => {
  const confirmed = await confirm(`Trigger replenishment for pool "${poolName}"?`, 'Force Replenish');
  if (!confirmed) return;
  try {
    const res = await api('/pool/replenish', { method: 'POST', body: { poolName } });
    logOp('Replenish', poolName, res.message || 'Triggered');
    showToast(res.message || 'Replenishment triggered');
  } catch { showToast('Failed to trigger replenishment', true); }
};

window.switchToAccounts = (poolName) => {
  switchView('accounts');
  filterPool.value = poolName;
  loadAccounts();
};

window.drillToState = (state) => {
  if (filterState) filterState.value = state;
  switchView('accounts');
};

btnReplenish.addEventListener('click', () => replenishPool(''));
btnReconcile.addEventListener('click', async () => {
  try {
    const res = await api('/pool/reconcile', { method: 'POST', body: { dryRun: true } });
    logOp('Reconcile (dry run)', 'all', JSON.stringify(res.summary));
    showToast(`Dry run: ${res.summary.healthy} healthy, ${res.summary.markedFailed} issues`);
  } catch { showToast('Reconcile failed', true); }
});

// ── Accounts table ────────────────────────────────────────────────────────────
let accountsDebounce;

function scheduleLoad() {
  clearTimeout(accountsDebounce);
  accountsDebounce = setTimeout(loadAccounts, 350);
}

async function loadAccounts() {
  const params = new URLSearchParams();
  const account = filterAccount?.value.trim();
  const pool    = filterPool?.value;
  const state   = filterState?.value;
  const project = filterProject?.value.trim();

  if (account) params.set('search', account);
  else if (project) params.set('search', project);
  if (pool)    params.set('poolName', pool);
  if (state)   params.set('state', state);

  accountsTbody.innerHTML = '<tr><td colspan="5" class="loading">Loading…</td></tr>';
  accountsEmpty.hidden = true;
  try {
    const { accounts, total } = await api('/pool/accounts?' + params);
    if (acctRefreshed) acctRefreshed.textContent = `${total} accounts · ${fmtTime(new Date().toISOString())}`;
    renderAccountsTable(accounts);
  } catch {
    accountsTbody.innerHTML = '<tr><td colspan="5" class="error-inline">Failed to load accounts.</td></tr>';
  }
}

function renderAccountsTable(accounts) {
  if (!accounts.length) {
    accountsTbody.innerHTML = '';
    accountsEmpty.hidden = false;
    return;
  }
  accountsEmpty.hidden = true;
  accountsTbody.innerHTML = accounts.map(a => {
    const smusLink = (a.state === 'ASSIGNED' && a.projectId && CONFIG.portalUrl)
      ? `<a href="${CONFIG.portalUrl}/projects/${a.projectId}" target="_blank" class="smus-link" title="Open in SMUS">↗</a>`
      : '';
    return `
    <tr class="account-row" data-id="${a.accountId}" tabindex="0">
      <td><code>${a.accountId}</code><br><span class="account-name-sub">${a.accountName}</span></td>
      <td>${a.poolName}</td>
      <td><span class="state-badge state-${a.state.toLowerCase()}">${a.state.replace('_', ' ')}</span></td>
      <td>${a.projectId ? `<code class="project-id">${a.projectId}</code> ${smusLink}` : '<span class="muted">—</span>'}</td>
      <td class="muted">${fmtDate(a.createdDate)}</td>
    </tr>`;
  }).join('');

  accountsTbody.querySelectorAll('.account-row').forEach(row => {
    row.addEventListener('click', () => openPanel(row.dataset.id));
    row.addEventListener('keydown', e => { if (e.key === 'Enter') openPanel(row.dataset.id); });
  });
}

// Debounced text filters, immediate select filters
[filterAccount, filterProject].forEach(el => el?.addEventListener('input', scheduleLoad));
[filterPool, filterState].forEach(el => el?.addEventListener('change', loadAccounts));

// ── Detail panel ──────────────────────────────────────────────────────────────
async function openPanel(accountId) {
  detailPanel.hidden = false;
  panelTitle.textContent = accountId;
  panelBody.innerHTML = '<div class="loading">Loading…</div>';
  panelActions.innerHTML = '';
  try {
    const [acc, ssResp] = await Promise.all([
      api(`/pool/accounts/${accountId}`),
      api(`/pool/accounts/${accountId}/stacksets`).catch(() => ({ stacksets: [] }))
    ]);
    renderPanel(acc, ssResp.stacksets || []);
  } catch {
    panelBody.innerHTML = '<div class="error-inline">Failed to load account details.</div>';
  }
}

function renderPanel(acc, stacksets = []) {
  const fields = [
    ['Account ID', `<code>${acc.accountId}</code>`],
    ['Pool', acc.poolName || '—'],
    ['State', `<span class="state-badge state-${(acc.state||'').toLowerCase()}">${(acc.state||'').replace('_', ' ')}</span>`],
    ['Account Name', acc.accountName || '—'],
    ['Email', acc.accountEmail || '—'],
    ['Project ID', acc.projectId ? `<code>${acc.projectId}</code>` : '—'],
    ['Created', fmtDate(acc.createdDate)],
    ['Setup Complete', acc.setupCompleteDate ? fmtDate(acc.setupCompleteDate) : '—'],
    ['Assigned', acc.assignedDate ? fmtDate(acc.assignedDate) : '—'],
    ['Retry Count', acc.retryCount ?? 0],
    ['Error', acc.errorMessage || '—'],
    ['Reconciliation Note', acc.reconciliationNote || '—'],
  ];

  const ssHtml = stacksets.length ? `
    <div class="stacksets-section">
      <strong>StackSet Instances</strong>
      <table class="ss-table">
        <thead><tr><th>StackSet</th><th>Status</th></tr></thead>
        <tbody>${stacksets.map(s => {
          const cls = s.status === 'CURRENT' ? 'ss-ok'
                    : s.status === 'OUTDATED' ? 'ss-warn'
                    : s.status === 'NOT_FOUND' ? 'ss-missing'
                    : 'ss-unknown';
          const tip = s.statusReason ? ` title="${s.statusReason.replace(/"/g,"'")}"` : '';
          return `<tr>
            <td><code class="ss-name">${s.name}</code></td>
            <td><span class="ss-badge ${cls}"${tip}>${s.status}</span></td>
          </tr>`;
        }).join('')}</tbody>
      </table>
    </div>` : '';

  panelBody.innerHTML = `
    <dl class="detail-list">
      ${fields.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}
    </dl>
    ${ssHtml}`;

  const actions = [];
  if (acc.state === 'FAILED') {
    actions.push(`<button class="small" onclick="recycleAccount('${acc.accountId}')">Trigger Recycler</button>`);
    actions.push(`<button class="small secondary outline" onclick="removeAccount('${acc.accountId}')">Remove from Pool</button>`);
  }
  actions.push(`<button class="small secondary outline" onclick="copyId('${acc.accountId}')">Copy Account ID</button>`);
  panelActions.innerHTML = actions.join('');
}

panelClose.addEventListener('click', closePanel);
function closePanel() { detailPanel.hidden = true; }

// ── Panel resize ──────────────────────────────────────────────────────────────
const panelResize = document.getElementById('panel-resize');
let resizing = false, resizeStartX = 0, resizeStartW = 0;
panelResize.addEventListener('mousedown', e => {
  resizing = true;
  resizeStartX = e.clientX;
  resizeStartW = detailPanel.offsetWidth;
  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';
});
document.addEventListener('mousemove', e => {
  if (!resizing) return;
  const delta = resizeStartX - e.clientX;
  const newW = Math.max(260, Math.min(700, resizeStartW + delta));
  detailPanel.style.width = newW + 'px';
});
document.addEventListener('mouseup', () => {
  resizing = false;
  document.body.style.cursor = '';
  document.body.style.userSelect = '';
});

window.recycleAccount = async (id) => {
  const ok = await confirm(`Trigger recycler for account ${id}?`, 'Recycle Account');
  if (!ok) return;
  try {
    const res = await api(`/pool/accounts/${id}/recycle`, { method: 'POST' });
    logOp('Recycle', id, res.message || 'Triggered');
    showToast(`Recycler triggered for ${id}`);
    openPanel(id);
  } catch { showToast('Failed to trigger recycler', true); }
};

window.removeAccount = async (id) => {
  const ok = await confirm(`Remove account ${id} from the pool? This cannot be undone.`, 'Remove Account');
  if (!ok) return;
  try {
    await api(`/pool/accounts/${id}`, { method: 'DELETE' });
    logOp('Remove', id, 'Removed from pool');
    showToast(`Account ${id} removed`);
    closePanel();
    if (currentView === 'accounts') loadAccounts();
    if (currentView === 'dashboard') loadDashboard();
  } catch { showToast('Failed to remove account', true); }
};

window.copyId = (id) => {
  navigator.clipboard.writeText(id).then(() => showToast('Copied!'));
};

// ── Operations log ────────────────────────────────────────────────────────────
const OPS_KEY = 'apf-ops-log';
function loadOps() { try { return JSON.parse(localStorage.getItem(OPS_KEY) || '[]'); } catch { return []; } }
function saveOps(ops) { localStorage.setItem(OPS_KEY, JSON.stringify(ops.slice(0, 50))); }

function logOp(action, target, result) {
  const ops = loadOps();
  ops.unshift({ action, target, result, time: new Date().toISOString() });
  saveOps(ops);
  renderOpsLog();
}

function renderOpsLog() {
  const ops = loadOps();
  opsCount.textContent = ops.length;
  opsCount.hidden = ops.length === 0;
  opsEntries.innerHTML = ops.length
    ? ops.map(o => `
        <div class="ops-entry">
          <div class="ops-meta"><strong>${o.action}</strong> · ${o.target} <span class="muted">${fmtTime(o.time)}</span></div>
          <div class="ops-result">${o.result}</div>
        </div>`).join('')
    : '<div class="empty-state">No operations yet.</div>';
}

opsToggle.addEventListener('click', () => {
  opsDrawer.hidden = !opsDrawer.hidden;
  if (!opsDrawer.hidden) renderOpsLog();
});
opsClose.addEventListener('click', () => { opsDrawer.hidden = true; });

// ── Toast ─────────────────────────────────────────────────────────────────────
let toastTimer;
function showToast(msg, isError = false) {
  toast.textContent = msg;
  toast.className = `toast ${isError ? 'toast-error' : 'toast-ok'}`;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 3500);
}

// ── Confirm dialog ────────────────────────────────────────────────────────────
function confirm(msg, title = 'Confirm') {
  return new Promise(resolve => {
    confirmTitle.textContent = title;
    confirmMsg.textContent = msg;
    confirmDialog.showModal();
    const ok = () => { confirmDialog.close(); resolve(true); cleanup(); };
    const cancel = () => { confirmDialog.close(); resolve(false); cleanup(); };
    const cleanup = () => {
      confirmOk.removeEventListener('click', ok);
      confirmCancel.removeEventListener('click', cancel);
    };
    confirmOk.addEventListener('click', ok);
    confirmCancel.addEventListener('click', cancel);
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}
function fmtTime(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

// ── Configuration ─────────────────────────────────────────────────────────────
const configPanels = document.getElementById('config-panels');

async function loadConfig() {
  configPanels.innerHTML = '<div class="loading">Loading…</div>';
  try {
    const { pools } = await api('/pool/config');
    configPanels.innerHTML = pools.map(renderConfigPanel).join('');
    configPanels.querySelectorAll('.config-form').forEach(form => {
      form.addEventListener('submit', saveConfig);
    });
  } catch {
    configPanels.innerHTML = '<div class="error-inline">Failed to load configuration.</div>';
  }
}

function renderConfigPanel(pool) {
  return `
  <article class="config-card">
    <header><strong>${pool.poolName}</strong></header>
    <form class="config-form" data-pool="${pool.poolName}" novalidate>
      <div class="config-grid">
        <label>
          Minimum Pool Size
          <input type="number" name="minSize" value="${pool.minSize}" min="1" max="50" required>
          <small>Replenishment triggers when available accounts drop below this.</small>
        </label>
        <label>
          Target Pool Size
          <input type="number" name="targetSize" value="${pool.targetSize}" min="1" max="100" required>
          <small>Pool is replenished up to this size.</small>
        </label>
        <label>
          Max Concurrent Setups
          <input type="number" name="maxConcurrentSetups" value="${pool.maxConcurrentSetups}" min="1" max="20" required>
          <small>Limits parallel account provisioning to avoid API throttling.</small>
        </label>
        <label>
          Reclaim Strategy
          <select name="reclaimStrategy">
            <option value="DELETE" ${pool.reclaimStrategy === 'DELETE' ? 'selected' : ''}>DELETE — remove from pool after project deletion</option>
            <option value="REUSE" ${pool.reclaimStrategy === 'REUSE' ? 'selected' : ''}>REUSE — clean and return to pool</option>
          </select>
          <small>DELETE is simpler; REUSE saves account quota and speeds replenishment.</small>
        </label>
      </div>
      <div class="config-actions">
        <button type="submit" class="small">Save to SSM</button>
        <span class="save-status" id="save-status-${pool.poolName}"></span>
      </div>
    </form>
  </article>`;
}

async function saveConfig(e) {
  e.preventDefault();
  const form = e.target;
  const poolName = form.dataset.pool;
  const statusEl = document.getElementById(`save-status-${poolName}`);
  const submitBtn = form.querySelector('[type=submit]');

  const payload = {
    minSize: parseInt(form.minSize.value),
    targetSize: parseInt(form.targetSize.value),
    maxConcurrentSetups: parseInt(form.maxConcurrentSetups.value),
    reclaimStrategy: form.reclaimStrategy.value,
  };

  // Basic validation
  if (payload.minSize >= payload.targetSize) {
    statusEl.textContent = 'Target size must be greater than minimum size.';
    statusEl.className = 'save-status error';
    return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = 'Saving…';
  statusEl.textContent = '';

  try {
    const res = await api(`/pool/config/${poolName}`, { method: 'PUT', body: payload });
    statusEl.textContent = '✓ Saved';
    statusEl.className = 'save-status ok';
    logOp('Config saved', poolName, JSON.stringify(payload));
    showToast(`Configuration for '${poolName}' saved to SSM`);
    setTimeout(() => { statusEl.textContent = ''; }, 4000);
  } catch {
    statusEl.textContent = 'Save failed';
    statusEl.className = 'save-status error';
    showToast('Failed to save configuration', true);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Save to SSM';
  }
}

// ── Refresh buttons ───────────────────────────────────────────────────────────
btnRefreshDash?.addEventListener('click', () => loadDashboard());
btnRefreshAccts?.addEventListener('click', () => loadAccounts());

// ── Auto-refresh ──────────────────────────────────────────────────────────────
let autoRefreshTimer = null;

function startAutoRefresh() {
  stopAutoRefresh();
  const secs = parseInt(autoRefreshInterval?.value || '30') * 1000;
  autoRefreshTimer = setInterval(() => {
    if (currentView === 'dashboard') loadDashboard();
    if (currentView === 'accounts') loadAccounts();
  }, secs);
}

function stopAutoRefresh() {
  if (autoRefreshTimer) { clearInterval(autoRefreshTimer); autoRefreshTimer = null; }
}

autoRefreshToggle?.addEventListener('change', () => {
  if (autoRefreshToggle.checked) startAutoRefresh();
  else stopAutoRefresh();
});

autoRefreshInterval?.addEventListener('change', () => {
  if (autoRefreshToggle?.checked) startAutoRefresh();
});

// ── Credential health check ───────────────────────────────────────────────────
const credBanner = document.getElementById('cred-banner');
function checkCredentials() {
  if (CONFIG.MOCK) return;
  fetch(CONFIG.API_URL + '/health')
    .then(r => r.json())
    .then(h => { credBanner.hidden = h.ok; })
    .catch(() => { /* network error — don't show banner, server may be restarting */ });
}
setTimeout(checkCredentials, 2000); // delay so page loads first
setInterval(checkCredentials, 60000);

// ── Init ──────────────────────────────────────────────────────────────────────
loadDashboard();
renderOpsLog();
