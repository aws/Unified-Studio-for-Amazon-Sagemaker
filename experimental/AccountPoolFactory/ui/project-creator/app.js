import { CONFIG } from '../config.js';
import { Auth } from '../auth.js';

const api = (path, opts = {}) =>
  fetch(CONFIG.API_URL + path, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  }).then(r => r.json());

// ── DOM refs ──────────────────────────────────────────────────────────────────
const viewForm     = document.getElementById('view-form');
const viewProgress = document.getElementById('view-progress');
const form         = document.getElementById('create-form');
const nameInput    = document.getElementById('project-name');
const nameHint     = document.getElementById('name-hint');
const regionSel    = document.getElementById('project-region');
const regionHint   = document.getElementById('region-hint');
const ownerSearch  = document.getElementById('owner-search');
const ownerDropdown= document.getElementById('owner-dropdown');
const ownerIdInput = document.getElementById('owner-id');
const ownerTypeInput=document.getElementById('owner-type');
const ownerChip    = document.getElementById('owner-selected');
const profileSel   = document.getElementById('project-profile');
const submitBtn    = document.getElementById('submit-btn');

// Progress
const progressTitle   = document.getElementById('progress-title');
const progressSubtitle= document.getElementById('progress-subtitle');
const stepAccount     = document.getElementById('step-account');
const stepProject     = document.getElementById('step-project');
const stepEnvs        = document.getElementById('step-envs');
const stepAccountDetail=document.getElementById('step-account-detail');
const stepProjectDetail=document.getElementById('step-project-detail');
const stepEnvsDetail  = document.getElementById('step-envs-detail');
const envList         = document.getElementById('env-list');
const progressError   = document.getElementById('progress-error');
const successActions  = document.getElementById('success-actions');
const openSmusBtn     = document.getElementById('open-smus-btn');
const createAnotherBtn= document.getElementById('create-another-btn');

// ── Load profiles ─────────────────────────────────────────────────────────────
let profilesData = [];

async function loadProfiles() {
  try {
    const { profiles } = await api('/projects/profiles');
    profilesData = profiles;
    profileSel.innerHTML = '<option value="">Select a profile…</option>' +
      profiles.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
    profileSel.disabled = false;
    // Auto-select if only one profile
    if (profiles.length === 1) {
      profileSel.value = profiles[0].id;
      profileSel.dispatchEvent(new Event('change'));
    }
  } catch (e) {
    profileSel.innerHTML = '<option value="">Failed to load profiles</option>';
  }
  checkFormValid();
}

// When profile changes, update allowed regions
profileSel.addEventListener('change', () => {
  const profile = profilesData.find(p => p.id === profileSel.value);
  if (!profile || !profile.allowedRegions?.length) {
    regionSel.innerHTML = '<option value="">No regions available</option>';
    regionSel.disabled = true;
    regionHint.textContent = '';
  } else {
    regionSel.innerHTML = '<option value="">Select region…</option>' +
      profile.allowedRegions.map(r => `<option value="${r.value}">${r.label}</option>`).join('');
    regionSel.disabled = false;
    regionHint.textContent = `${profile.allowedRegions.length} region${profile.allowedRegions.length > 1 ? 's' : ''} available for this profile.`;
    // Auto-select if only one option
    if (profile.allowedRegions.length === 1) {
      regionSel.value = profile.allowedRegions[0].value;
    }
  }
  checkFormValid();
});

// ── Owner search ──────────────────────────────────────────────────────────────
let ownerSearchTimer;
let ownerSelected = false;

ownerSearch.addEventListener('input', () => {
  clearTimeout(ownerSearchTimer);
  const q = ownerSearch.value.trim();
  if (!q) { hideDropdown(); return; }
  ownerSearchTimer = setTimeout(() => fetchOwners(q), 250);
});

ownerSearch.addEventListener('keydown', e => {
  if (e.key === 'Escape') hideDropdown();
  if (e.key === 'ArrowDown') {
    const first = ownerDropdown.querySelector('[role=option]');
    if (first) first.focus();
  }
});

document.addEventListener('click', e => {
  if (!ownerSearch.contains(e.target) && !ownerDropdown.contains(e.target)) hideDropdown();
});

async function fetchOwners(q) {
  try {
    const { owners } = await api(`/projects/owners?search=${encodeURIComponent(q)}`);
    renderDropdown(owners);
  } catch { hideDropdown(); }
}

function renderDropdown(owners) {
  if (!owners.length) { hideDropdown(); return; }
  ownerDropdown.innerHTML = owners.map(o => `
    <div role="option" tabindex="0" class="owner-option" data-id="${o.id}" data-type="${o.type}" data-name="${o.name}">
      <span class="owner-badge ${o.type.toLowerCase()}">${o.type === 'GROUP' ? 'Group' : 'User'}</span>
      <span class="owner-name">${o.name}</span>
      ${o.email ? `<span class="owner-email">${o.email}</span>` : ''}
    </div>`).join('');
  ownerDropdown.hidden = false;
  ownerSearch.setAttribute('aria-expanded', 'true');

  ownerDropdown.querySelectorAll('[role=option]').forEach(el => {
    el.addEventListener('click', () => selectOwner(el));
    el.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') selectOwner(el);
      if (e.key === 'ArrowDown') el.nextElementSibling?.focus();
      if (e.key === 'ArrowUp') el.previousElementSibling?.focus() || ownerSearch.focus();
    });
  });
}

function selectOwner(el) {
  ownerIdInput.value = el.dataset.id;
  ownerTypeInput.value = el.dataset.type;
  ownerSearch.value = '';
  ownerSearch.setAttribute('aria-expanded', 'false');
  ownerDropdown.hidden = true;
  ownerSelected = true;

  const typeLabel = el.dataset.type === 'GROUP' ? 'Group' : 'User';
  ownerChip.innerHTML = `
    <span class="owner-badge ${el.dataset.type.toLowerCase()}">${typeLabel}</span>
    <span>${el.dataset.name}</span>
    <button type="button" class="chip-remove" aria-label="Remove owner">×</button>`;
  ownerChip.hidden = false;
  ownerChip.querySelector('.chip-remove').addEventListener('click', clearOwner);
  checkFormValid();
}

function clearOwner() {
  ownerIdInput.value = '';
  ownerTypeInput.value = '';
  ownerSelected = false;
  ownerChip.hidden = true;
  ownerSearch.value = '';
  checkFormValid();
}

function hideDropdown() {
  ownerDropdown.hidden = true;
  ownerSearch.setAttribute('aria-expanded', 'false');
}

// ── Form validation ───────────────────────────────────────────────────────────
function checkFormValid() {
  const valid = nameInput.value.trim() &&
                regionSel.value &&
                ownerSelected &&
                profileSel.value;
  submitBtn.disabled = !valid;
}

[nameInput, regionSel].forEach(el => el.addEventListener('change', checkFormValid));
[nameInput, regionSel].forEach(el => el.addEventListener('input', checkFormValid));

nameInput.addEventListener('input', () => {
  const v = nameInput.value.trim();
  const valid = /^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$/.test(v) || v.length < 2;
  nameHint.textContent = v && !valid ? 'Use lowercase letters, numbers, and hyphens only.' : '';
  nameHint.className = v && !valid ? 'hint error' : 'hint';
});

// ── Form submit ───────────────────────────────────────────────────────────────
form.addEventListener('submit', async e => {
  e.preventDefault();
  const payload = {
    name: nameInput.value.trim(),
    region: regionSel.value,
    ownerId: ownerIdInput.value,
    ownerType: ownerTypeInput.value,
    profileId: profileSel.value,
  };
  showProgress();
  await runCreation(payload);
});

function showProgress() {
  viewForm.hidden = true;
  viewProgress.hidden = false;
  setStep(stepAccount, 'active');
  setStep(stepProject, 'pending');
  setStep(stepEnvs, 'pending');
  envList.hidden = true;
  progressError.hidden = true;
  successActions.hidden = true;
}

async function runCreation(payload) {
  let projectId, portalUrl;
  try {
    // Step 1: create (server resolves account internally)
    setStep(stepAccount, 'active');
    stepAccountDetail.textContent = 'Selecting an available account from the pool…';
    const res = await api('/projects', { method: 'POST', body: payload });
    if (res.error) throw new Error(res.error);
    projectId = res.projectId;
    portalUrl = res.portalUrl;
    setStep(stepAccount, 'done');
    stepAccountDetail.textContent = `Account assigned: ${res.resolvedAccountId || 'pending'}`;

    // Step 2: project created
    setStep(stepProject, 'active');
    stepProjectDetail.textContent = `Project ID: ${projectId}`;
    await sleep(800);
    setStep(stepProject, 'done');

    // Step 3: poll environments
    setStep(stepEnvs, 'active');
    await pollStatus(projectId, portalUrl);
  } catch (err) {
    showError(err.message || 'An unexpected error occurred.');
  }
}

async function pollStatus(projectId, portalUrl) {
  const maxAttempts = 40;
  for (let i = 0; i < maxAttempts; i++) {
    await sleep(3000);
    try {
      const status = await api(`/projects/${projectId}/status`);
      renderEnvList(status.environments || []);
      envList.hidden = false;

      if (status.overallDeploymentStatus === 'COMPLETED') {
        setStep(stepEnvs, 'done');
        stepEnvsDetail.textContent = 'All environments active.';
        showSuccess(projectId, portalUrl);
        return;
      }
      if (status.overallDeploymentStatus === 'FAILED_DEPLOYMENT' ||
          status.overallDeploymentStatus === 'FAILED_VALIDATION') {
        throw new Error(`Deployment failed: ${status.overallDeploymentStatus}`);
      }
    } catch (err) {
      if (err.message.startsWith('Deployment failed')) throw err;
      // transient fetch error — keep polling
    }
  }
  throw new Error('Timed out waiting for environments to deploy.');
}

function renderEnvList(envs) {
  envList.innerHTML = envs.map(e => `
    <div class="env-row">
      <span class="env-name">${e.name}</span>
      <span class="status-badge status-${e.status.toLowerCase()}">${e.status}</span>
    </div>`).join('');
}

function showSuccess(projectId, portalUrl) {
  progressTitle.textContent = 'Project ready';
  progressSubtitle.textContent = `Project ${projectId} is live.`;
  openSmusBtn.href = `${portalUrl}/projects/${projectId}`;
  successActions.hidden = false;
}

function showError(msg) {
  progressError.textContent = msg;
  progressError.hidden = false;
  setStep(stepEnvs, 'error');
}

createAnotherBtn.addEventListener('click', () => {
  viewProgress.hidden = true;
  viewForm.hidden = false;
  form.reset();
  clearOwner();
  checkFormValid();
  setStep(stepAccount, 'pending');
  setStep(stepProject, 'pending');
  setStep(stepEnvs, 'pending');
});

// ── Helpers ───────────────────────────────────────────────────────────────────
function setStep(el, state) {
  el.querySelector('.step-icon').dataset.state = state;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ── Init ──────────────────────────────────────────────────────────────────────
loadProfiles();
