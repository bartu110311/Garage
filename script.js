// =====================================================
// 1. DOM REFERENCES AND STATE
// =====================================================
const hexagonBtn      = document.getElementById('hexagon-btn');
const cancelMenuBtn   = document.getElementById('cancel-menu-btn');
const menu            = document.getElementById('menu');
const ringGroups      = document.querySelectorAll('.ring-group');
const arcs            = document.querySelectorAll('.arc-ring');
const panelTitle      = document.getElementById('panel-title');
const panelDesc       = document.getElementById('panel-desc');
const leftSection     = document.getElementById('left-section');
const notifStack      = document.getElementById('notif-stack');

let isDetailView = false;
let hexagonClickInDetail = 0;
let lastData = null;
let currentAstronaut = 'user1';

// =====================================================
// 0. AUTH LAYER (Persistent Session - localStorage)
// =====================================================
const AUTH_KEY      = 'astro-session';
const AUTH_USER_KEY = 'astro-user';

const USERS = {
    user1: '111111',
    user2: '222222',
    user3: '333333'
};

function isAuth() {
    try { return localStorage.getItem(AUTH_KEY) === 'ok'; }
    catch { return false; }
}

function showLogin() {
    document.body.classList.add('locked');
    const loginScreen = document.getElementById('login-screen');
    if (loginScreen) loginScreen.hidden = false;
    const loginUser = document.getElementById('login-user');
    if (loginUser) loginUser.focus();
}

function hideLogin() {
    const loginScreen = document.getElementById('login-screen');
    if (loginScreen) loginScreen.hidden = true;
    document.body.classList.remove('locked');
}

function requireAuth() {
    if (!isAuth()) { showLogin(); return false; }
    return true;
}

function attemptLogin() {
    const userEl = document.getElementById('login-user');
    const passEl = document.getElementById('login-pass');
    if (!userEl || !passEl) return;

    const user = userEl.value;
    const pass = passEl.value;

    if (USERS[user] === pass) {
        try {
            localStorage.setItem(AUTH_KEY, 'ok');
            localStorage.setItem(AUTH_USER_KEY, user);
        } catch {}
        currentAstronaut = user;
        hideLogin();
        resetToHome();
        startPolling();
        setTimeout(layoutMenu, 50);
    } else {
        notify({
            id: 'login-fail',
            level: 'mid',
            text: 'ERR: Incorrect user or passcode.'
        });
        passEl.value = '';
        passEl.focus();
    }
}

let pollTimer = null;
function startPolling() {
    if (pollTimer) return;
    fetchDashboardData();
    fetchCrew();
    pollTimer = setInterval(fetchDashboardData, POLL_INTERVAL_MS);
}
function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

// =====================================================
// 2. APPLICATION CONTENTS
// =====================================================
const appConfigs = {
    'heart': {
        title: "Heart Health Monitoring",
        right: "Cardio Module: Tracking heart rate, blood pressure, HRV, SpO2, and blood glucose.",
        left: `<div class="app-content-box">
            <h2>Cardio & Metabolism</h2>
            <div class="data-card"><span>Heart Rate</span><strong data-metric="heart_rate"></strong></div>
            <div class="data-card"><span>Blood Pressure (Sys/Dia)</span><strong data-metric="systolic_bp,diastolic_bp"></strong></div>
            <div class="data-card"><span>HRV (Variability)</span><strong data-metric="heart_rate_variability"></strong></div>
            <div class="data-card"><span>Oxygen (SpO2)</span><strong data-metric="spo2"></strong></div>
            <div class="data-card"><span>Blood Glucose</span><strong data-metric="blood_glucose"></strong></div>
        </div>`
    },
    'bone': {
        title: "Bone & Body Balance",
        right: "Skeletal Module: Monitoring body mass and hydration levels.",
        left: `<div class="app-content-box">
            <h2>Bone & Hydration</h2>
            <div class="data-card"><span>Body Mass</span><strong data-metric="body_mass"></strong></div>
            <div class="data-card"><span>Hydration Level</span><strong data-metric="hydration_level"></strong></div>
        </div>`
    },
    'immunity': {
        title: "Immunity & Respiration",
        right: "Immunity Module: Respiratory rate and general resilience indicators.",
        left: `<div class="app-content-box">
            <h2>Immunity Status</h2>
            <div class="data-card"><span>Respiratory Rate</span><strong data-metric="respiratory_rate"></strong></div>
        </div>`
    },
    'stability': {
        title: "Physical Stability",
        right: "Stability Module: Body mass and physical activity index.",
        left: `<div class="app-content-box">
            <h2>Stability Status</h2>
            <div class="data-card"><span>Body Mass</span><strong data-metric="body_mass"></strong></div>
            <div class="data-card"><span>Physical Activity</span><strong data-metric="physical_activity"></strong></div>
        </div>`
    },
    'sleep': {
        title: "Sleep Pattern Monitoring",
        right: "Sleep Analysis: Sleep duration and sleep quality index.",
        left: `<div class="app-content-box">
            <h2>Sleep Data</h2>
            <div class="data-card"><span>Sleep Duration</span><strong data-metric="sleep_duration"></strong></div>
            <div class="data-card"><span>Sleep Quality</span><strong data-metric="sleep_quality"></strong></div>
        </div>`
    },
    'psychology': {
        title: "Psychology & Stress Management",
        right: "Psychology Module: Astronaut stress level and mental balance.",
        left: `<div class="app-content-box">
            <h2>Psychological State</h2>
            <div class="data-card"><span>Stress Level</span><strong data-metric="stress_level"></strong></div>
        </div>`
    },
    'environment': {
        title: "Cabin Environment Conditions",
        right: "Environment Module: Cabin temperature, pressure, gases, and microgravity status.",
        left: `<div class="app-content-box" style="gap: 8px;">
            <h2>Cabin Environment</h2>
            <div class="data-card"><span>Cabin Temperature</span><strong data-metric="cabin_temperature"></strong></div>
            <div class="data-card"><span>Cabin Pressure</span><strong data-metric="cabin_pressure"></strong></div>
            <div class="data-card"><span>Humidity</span><strong data-metric="cabin_humidity"></strong></div>
            <div class="data-card"><span>Oxygen (O2)</span><strong data-metric="cabin_oxygen"></strong></div>
            <div class="data-card"><span>Carbon Dioxide (CO2)</span><strong data-metric="cabin_co2"></strong></div>
            <div class="data-card"><span>Microgravity</span><strong data-metric="microgravity_level"></strong></div>
            <div class="data-card"><span>Air Quality</span><strong data-metric="cabin_air_quality"></strong></div>
        </div>`
    },
    'space': {
        title: "Space & ISS Telemetry",
        right: "Space Module: Real-time ISS coordinates, altitude, and orbital velocity.",
        left: `<div class="app-content-box">
            <h2>ISS Orbital Data</h2>
            <div class="data-card"><span>Latitude</span><strong data-metric="iss.latitude" data-unit="°" data-digits="2"></strong></div>
            <div class="data-card"><span>Longitude</span><strong data-metric="iss.longitude" data-unit="°" data-digits="2"></strong></div>
            <div class="data-card"><span>Altitude</span><strong data-metric="iss.altitude_km" data-unit="km" data-digits="1"></strong></div>
            <div class="data-card"><span>Velocity</span><strong data-metric="iss.velocity_km_h" data-unit="km/h" data-digits="0"></strong></div>
            <div class="data-card"><span>Space Weather Status</span><strong data-metric="space.status"></strong></div>
            <div class="data-card"><span>Solar Particle Events</span><strong data-metric="space.sep_events" data-format="count" data-unless="space.status=DISABLED_NO_API_KEY"></strong></div>
        </div>`
    },
    'active-radiation': {
        title: "Radiation & Space Weather",
        right: "Radiation Module: Dose rate, cumulative dose, and geomagnetic storms.",
        left: `<div class="app-content-box">
            <h2>Radiation Dosimeter</h2>
            <div class="data-card"><span>Dose Rate</span><strong data-metric="rad.dose_rate_usv_h" data-unit="µSv/h" data-unless="rad.integration_status=NO_DOSE_INTEGRATED"></strong></div>
            <div class="data-card"><span>Cumulative Dose</span><strong data-metric="rad.cumulative_dose_msv" data-unit="mSv" data-unless="rad.integration_status=NO_DOSE_INTEGRATED"></strong></div>
            <div class="data-card"><span>Measurement Status</span><strong data-metric="rad.measurement_status"></strong></div>
        </div>`
    },
    'tiredness': {
        title: "Fatigue Tracking",
        right: "Fatigue Status: Sleep duration and rest metrics.",
        left: `<div class="app-content-box"><h2>Fatigue</h2><div class="data-card"><span>Sleep Duration</span><strong data-metric="sleep_duration"></strong></div></div>`
    },
    'diseases': {
        title: "Conditions & Active Findings",
        right: "Condition Scan: Real-time medical findings detected by the system.",
        left: `<div class="app-content-box">
            <h2>Active Conditions</h2>
            <div id="diseases-container" style="display: flex; flex-direction: column; gap: 10px; width: 100%; max-height: 260px; overflow-y: auto;">
                <div class="data-card"><span>Status</span><strong>Waiting for data...</strong></div>
            </div>
        </div>`
    },
    'cancer': {
        title: "Cancer Risk",
        right: "This tab is intentionally left blank.",
        left: `<div class="app-content-box" style="text-align: center; justify-content: center; align-items: center;"><h2 style="border: none;">Empty</h2></div>`
    },
    'bacteria': {
        title: "Bacterial Flora",
        right: "Bacterial Flora: Microbiome diversity is stable.",
        left: `<div class="app-content-box"><h2>Microbiome</h2><div class="data-card"><span>Diversity Score</span><strong>94 / 100</strong></div></div>`
    },
    'standard-input': {
        title: "Daily Data Entry",
        right: "Daily Entry: Log your sleep, fatigue, and stress levels (v0.4.0).",
        left: `<div class="app-content-box">
            <h2>Daily Data Entry</h2>
            <form class="app-form" onsubmit="submitDailyEntry(event)">
                <div class="form-group">
                    <label>Sleep Duration (Hours, 0-24):</label>
                    <input type="number" id="daily-sleep-input" value="7.5" min="0" max="24" step="0.5">
                </div>
                <div class="form-group">
                    <label>Fatigue Level (0-10):</label>
                    <input type="number" id="daily-fatigue-input" min="0" max="10" value="4">
                </div>
                <div class="form-group">
                    <label>Stress Level (0-10):</label>
                    <input type="number" id="daily-stress-select" min="0" max="10" value="5">
                </div>
                <button type="submit" class="submit-btn">Submit Data to Server</button>
            </form>
        </div>`
    },
    'teammates': {
        title: "Crewmates",
        right: "Crew health statuses.",
        left: `<div class="app-content-box">
            <h2>Crew Status</h2>
            <div class="data-card"><span>Astronaut 1</span><strong id="teammate-1-status">--</strong></div>
            <div class="data-card"><span>Astronaut 2</span><strong id="teammate-2-status">--</strong></div>
            <div class="data-card"><span>Astronaut 3</span><strong id="teammate-3-status">--</strong></div>
        </div>`
    },
    'actions': { title: "Actions", right: "", left: "" },
    'learn': { title: "Quick Learn", right: "", left: "" },
    'standard-procedure': { title: "Procedures", right: "", left: "" },
    'emergency': { title: "Emergency", right: "", left: "" },
    'settings': {
        title: "Settings",
        right: "Session and Preferences",
        left: `<div class="app-content-box">
            <h2>Settings & Session</h2>
            <input type="file" id="photo-input" accept="image/*" hidden>
            <button id="photo-pick" type="button" class="submit-btn">Choose Photo</button>
            <button id="photo-clear" type="button" class="submit-btn">Reset Photo</button>
            <hr style="border: 0; border-top: 1px solid rgba(231, 225, 88, 0.3); margin: 5px 0;">
            <button id="logout-btn" type="button" class="submit-btn" style="background-color: var(--fourth); color: #fff;">Log Out</button>
        </div>`
    }
};

// =====================================================
// 3. RADIAL MENU LAYOUT
// =====================================================
function layoutMenu() {
    const W = innerWidth, H = innerHeight;
    const M = 16, HEX = 161;
    const all = [...document.querySelectorAll('.app-btn')];
    if (all.length === 0) return;
    const maxW = Math.max(...all.map(b => b.offsetWidth));
    const maxH = Math.max(...all.map(b => b.offsetHeight));
    const gap = maxW + 24;
    const r0 = HEX + gap / 2;
    const hw = maxW / 2 + M, hh = maxH / 2 + M;

    ringGroups.forEach((group, i) => {
        const R = r0 + i * gap;
        let lo = Math.asin(hh / R);
        if ((W - hw) / R < 1) lo = Math.max(lo, Math.acos((W - hw) / R));
        let hi = Math.acos(hw / R);
        if ((H - hh) / R < 1) hi = Math.min(hi, Math.asin((H - hh) / R));
        hi = Math.max(hi, lo);

        const btns = group.querySelectorAll('.app-btn');
        btns.forEach((btn, j) => {
            const a = btns.length === 1 ? (lo + hi) / 2 : lo + (hi - lo) * j / (btns.length - 1);
            btn.style.left = `${R * Math.cos(a)}px`;
            btn.style.top  = `${R * Math.sin(a)}px`;
        });
        if (arcs[i]) {
            arcs[i].style.setProperty('--in',  `${R - gap / 2}px`);
            arcs[i].style.setProperty('--out', `${R + gap / 2}px`);
        }
    });
}
layoutMenu();
document.fonts.ready.then(layoutMenu);
addEventListener('resize', layoutMenu);

// =====================================================
// 4. PHOTO FRAME AND SETTINGS
// =====================================================
const PHOTO_KEY = 'family-photo';
const photoKey = () => `${PHOTO_KEY}-${currentAstronaut}`;

const DEFAULT_PHOTO = 'data:image/svg+xml;utf8,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400"><rect width="100%" height="100%" fill="#00273d"/>' +
    '<text x="50%" y="50%" fill="#e7e158" font-family="sans-serif" font-size="26" text-anchor="middle">' +
    'Add a photo from the Settings menu</text></svg>'
);

function currentPhoto() {
    try { return localStorage.getItem(photoKey()) || localStorage.getItem(PHOTO_KEY) || DEFAULT_PHOTO; }
    catch { return DEFAULT_PHOTO; }
}

function showPhoto(url) {
    const img = document.querySelector('.photo-frame img');
    if (img) img.src = url;
}

function bindPhotoControls() {
    const pick      = document.getElementById('photo-pick');
    const input     = document.getElementById('photo-input');
    const clear     = document.getElementById('photo-clear');
    const logoutBtn = document.getElementById('logout-btn');

    if (logoutBtn) {
        logoutBtn.onclick = () => {
            try {
                localStorage.removeItem(AUTH_KEY);
                localStorage.removeItem(AUTH_USER_KEY);
            } catch {}
            window.location.reload();
        };
    }

    if (!pick || !input) return;

    pick.onclick = () => input.click();
    input.onchange = (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const img = new Image();
        img.onload = () => {
            const s = Math.min(1, 900 / Math.max(img.width, img.height));
            const c = document.createElement('canvas');
            c.width = img.width * s; c.height = img.height * s;
            c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
            URL.revokeObjectURL(img.src);
            try {
                localStorage.setItem(photoKey(), c.toDataURL('image/jpeg', 0.85));
                pick.textContent = 'Photo saved ✓';
            } catch {
                pick.textContent = 'Failed to save';
            }
        };
        img.src = URL.createObjectURL(file);
    };

    if (clear) {
        clear.onclick = () => {
            try {
                localStorage.removeItem(photoKey());
                localStorage.removeItem(PHOTO_KEY);
            } catch {}
            clear.textContent = 'Reset to default ✓';
        };
    }
}

// =====================================================
// 5. VIEW TRANSITIONS
// =====================================================
function openApp(appId) {
    if (!requireAuth()) return;
    const config = appConfigs[appId];
    if (!config) return;
    panelTitle.textContent = config.title;
    panelDesc.textContent = config.right;
    leftSection.innerHTML = config.left;
    isDetailView = true;
    hexagonClickInDetail = 0;
    menu.setAttribute('inert', '');
    bindPhotoControls();
    if (lastData) updateLiveFields(lastData);
}

function resetToHome() {
    leftSection.innerHTML = `
        <div class="photo-frame" id="initial-photo">
            <img alt="Family photo">
        </div>
    `;
    showPhoto(currentPhoto());
    isDetailView = false;
    hexagonClickInDetail = 0;
    menu.setAttribute('inert', '');
    updateHomePanel();
}

const STATUS_LABEL = { NORMAL: 'NORMAL', CAUTION: 'CAUTION', WARNING: 'WARNING', CRITICAL: 'CRITICAL' };

function updateHomePanel() {
    if (isDetailView) return;
    if (!lastData) {
        panelTitle.textContent = 'Connecting…';
        panelDesc.textContent = 'Waiting for data.';
        return;
    }
    panelTitle.textContent = `Overall Status: ${STATUS_LABEL[lastData.overall_status] ?? '—'}`;
    const c = lastData.active_conditions ?? [];
    panelDesc.textContent = c.length
        ? c.map(x => x.title).join(' · ')
        : `${currentAstronaut} — No active findings.`;
}

cancelMenuBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    menu.setAttribute('inert', '');
    hexagonClickInDetail = 0;
});

hexagonBtn.addEventListener('click', () => {
    if (isDetailView) {
        hexagonClickInDetail++;
        if (hexagonClickInDetail === 2) {
            resetToHome();
            return;
        }
    }
    if (menu.hasAttribute('inert')) menu.removeAttribute('inert');
    else menu.setAttribute('inert', '');
});

document.querySelectorAll('.app-btn:not(.empty)').forEach(b =>
    b.addEventListener('click', () => openApp(b.id))
);

// =====================================================
// 6. MULTI-NOTIFICATION SYSTEM
// =====================================================
const LEVELS = {
    low:  { rank: 1, icon: 'ℹ', label: 'LOW ALERT',      sticky: false, color: '#e7e158' },
    mid:  { rank: 2, icon: '▲', label: 'MODERATE ALERT', sticky: false, color: '#feb367' },
    high: { rank: 3, icon: '⚠', label: 'CRITICAL ALERT', sticky: true,  color: '#ff5f66' }
};
const notifs    = new Map();
const dismissed = new Map();

function notify({ id, level, text, onClick }) {
    const cfg = LEVELS[level];
    if (!cfg) return;
    if ((dismissed.get(id) ?? 0) >= cfg.rank) return;
    let n = notifs.get(id);
    if (!n) {
        const el = document.createElement('button');
        el.type = 'button';
        el.className = 'notif';
        n = { el };
        el.addEventListener('click', () => {
            n.onClick?.();
            if (!LEVELS[n.level].sticky) {
                dismissed.set(id, LEVELS[n.level].rank);
                removeNotif(id);
            }
        });
        notifs.set(id, n);
        notifStack.appendChild(el);
    }
    n.level = level;
    n.onClick = onClick;
    n.el.dataset.level = level;
    n.el.setAttribute('role', level === 'high' ? 'alert' : 'status');
    n.el.style.order = -cfg.rank;
    n.el.replaceChildren();
    const tag = Object.assign(document.createElement('span'), { className: 'tag', textContent: `${cfg.icon} ${cfg.label}` });
    const msg = Object.assign(document.createElement('span'), { textContent: text });
    n.el.append(tag, msg);
    updateHexColor();
}

function removeNotif(id) {
    notifs.get(id)?.el.remove();
    notifs.delete(id);
    updateHexColor();
}

function clearNotify(id) {
    dismissed.delete(id);
    removeNotif(id);
}

function updateHexColor() {
    const top = [...notifs.values()].sort((a, b) => LEVELS[b.level].rank - LEVELS[a.level].rank)[0];
    if (top) document.documentElement.style.setProperty('--hex-color', LEVELS[top.level].color);
    else document.documentElement.style.removeProperty('--hex-color');
}

// =====================================================
// 7. API LAYER AND CENTRAL DATA MANAGEMENT — v0.4.0
// =====================================================
const API_BASE_URL = "http://127.0.0.1:8080";
const POLL_INTERVAL_MS = 2000;

async function getJson(url, options) {
    const r = await fetch(url, options);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
}

async function fetchDashboardData() {
    if (!isAuth()) return;
    try {
        const url = `${API_BASE_URL}/api/v1/astronauts/${currentAstronaut}/dashboard`;
        const data = await getJson(url);
        updateUIWithTelemetry(data);
    } catch (error) {
        console.warn(`Failed to fetch dashboard (${currentAstronaut}):`, error.message);
        showConnectionErrorState();
    }
}

async function fetchCrew() {
    if (!isAuth()) return;
    try {
        const data = await getJson(`${API_BASE_URL}/api/v1/crew`);
        if (data?.crew) {
            data.crew.forEach((c, idx) => {
                const el = document.getElementById(`teammate-${idx + 1}-status`);
                if (el) el.textContent = `${STATUS_LABEL[c.overall_status] ?? c.overall_status}`;
            });
        }
    } catch (e) {}
}

function updateUIWithTelemetry(data) {
    lastData = data;
    clearNotify('conn');
    document.body.setAttribute('data-system-status', data.overall_status);

    renderActiveConditions(data.active_conditions ?? [], data.overall_status);
    updateLiveFields(data);
    updateHomePanel();
}

// =====================================================
// TELEMETRY PARSER: nested JSON -> flat index -> data-metric
// =====================================================
const GROUP_PREFIX = {
    physiological_data: '',            // heart_rate, spo2, ...
    environmental_data: '',            // cabin_co2, cabin_pressure, ...
    iss_position_data: 'iss.',         // iss.altitude_km, iss.latitude, ...
    space_weather_data: 'space.',      // space.status, space.sep_events, ...
    radiation_dosimetry_data: 'rad.'   // rad.cumulative_dose_msv, rad.integration_status, ...
};
const UNIT_LABEL = { 'breaths/min': 'breaths/min', 'h': 'h', 'index': 'index', 'simulation_index': 'sim. index' };
const Q_ORDER = ['MISSING', 'INVALID', 'STALE', 'UNKNOWN', 'VALID']; // worst to best

// Flattens all fields under data.telemetry into a single dictionary
function buildMetricIndex(data) {
    const index = {};
    for (const [group, fields] of Object.entries(data?.telemetry ?? {})) {
        if (!fields || typeof fields !== 'object') continue;
        const prefix = GROUP_PREFIX[group] ?? `${group}.`;
        for (const [key, raw] of Object.entries(fields)) index[prefix + key] = raw;
    }
    return index;
}

const isMeasurement = v => v && typeof v === 'object' && !Array.isArray(v) && 'value' in v;

function fmtNum(v, digits) {
    if (typeof v !== 'number') return String(v);
    if (digits != null) return v.toFixed(digits);
    if (v !== 0 && Math.abs(v) < 1) return Number(v.toPrecision(3)).toString();
    return (Math.round(v * 10) / 10).toString();
}

// Normalizes a raw field into { ok, value, unit, quality }
function readField(raw, { digits, unit, format } = {}) {
    const d = digits != null ? Number(digits) : undefined;
    if (raw == null) return { ok: false, quality: 'MISSING' };
    if (Array.isArray(raw)) return { ok: true, value: format === 'count' ? String(raw.length) : raw.join(', '), unit: unit ?? '' };
    if (isMeasurement(raw)) {
        const q = raw.quality ?? 'UNKNOWN';
        if (raw.value == null || q === 'MISSING' || q === 'INVALID') return { ok: false, quality: q };
        const u = raw.unit === 'unknown' ? '' : (UNIT_LABEL[raw.unit] ?? raw.unit ?? '');
        return { ok: true, value: fmtNum(raw.value, d), unit: u, quality: q };
    }
    if (typeof raw === 'number') return { ok: true, value: fmtNum(raw, d), unit: unit ?? '' };
    return { ok: true, value: String(raw), unit: unit ?? '' };
}

// Populates all [data-metric] elements inside root
function bindMetrics(root, data) {
    const index = buildMetricIndex(data);
    root.querySelectorAll('[data-metric]').forEach(el => {
        const setText = (text, quality) => {
            el.textContent = text;
            if (quality) { el.dataset.quality = quality; el.title = `Measurement quality: ${quality}`; }
            else { delete el.dataset.quality; el.removeAttribute('title'); }
        };

        // data-unless="key=value": treat as unavailable if condition matches (e.g. hide "0 mSv" on dosimeter error)
        const unless = el.dataset.unless;
        if (unless) {
            const [k, v] = unless.split('=');
            if (String(index[k]) === v) return setText('--');
        }

        const opts = { digits: el.dataset.digits, unit: el.dataset.unit, format: el.dataset.format };
        const parts = el.dataset.metric.split(',').map(k => readField(index[k.trim()], opts)); // "systolic_bp,diastolic_bp" -> 113.6/72.9
        const qs = parts.map(p => p.quality).filter(Boolean);
        const worst = Q_ORDER.find(q => qs.includes(q));

        if (!parts.every(p => p.ok)) return setText('--', worst);
        setText(`${parts.map(p => p.value).join('/')} ${parts[0].unit}`.trim(), worst);
    });
}

const esc = s => String(s ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));

function updateLiveFields(data) {
    if (!data) return;
    bindMetrics(leftSection, data);

    // Conditions / Active Findings Module
    const diseaseContainer = document.getElementById('diseases-container');
    if (diseaseContainer) {
        const conds = data.active_conditions ?? [];
        if (conds.length > 0) {
            diseaseContainer.innerHTML = conds.map(c => {
                // Check if observed_value is an object (e.g., { systolic, diastolic } for blood pressure)
                let obsValStr = '';
                if (c.observed_value != null) {
                    if (typeof c.observed_value === 'object') {
                        const vals = Object.values(c.observed_value);
                        obsValStr = vals.length === 2 ? `${vals[0]} / ${vals[1]}` : JSON.stringify(c.observed_value);
                    } else {
                        obsValStr = c.observed_value;
                    }
                }

                return `
                <div class="data-card" style="flex-direction: column; align-items: flex-start; gap: 4px;">
                    <div style="display: flex; width: 100%; justify-content: space-between;">
                        <span style="color: var(--second);">[ ${esc(c.status)} ] ${esc(c.title)}</span>
                        <strong>${esc(obsValStr)} ${esc(c.unit ?? '')}</strong>
                    </div>
                    <span style="font-size: 0.85rem; opacity: 0.85;">${esc(c.context_note ?? c.description ?? c.id)}</span>
                </div>`;
            }).join('');
        } else {
            diseaseContainer.innerHTML = `<div class="data-card"><span>Scan Status</span><strong>No active conditions or findings.</strong></div>`;
        }
    }
}

function showConnectionErrorState() {
    notify({ id: 'conn', level: 'mid', text: 'Server disconnected; data may be outdated.' });
}

// =====================================================
// 8. ACTIVE FINDINGS AND MULTI-ALERT MANAGEMENT
// =====================================================
const STATUS_TO_LEVEL = { CAUTION: 'low', WARNING: 'mid', CRITICAL: 'high' };
const CONDITION_TO_APP = {
    HYPERGLYCEMIA: 'diseases',
    tachycardia: 'heart', bradycardia: 'heart', hypoxemia: 'heart',
    hyperglycemia: 'diseases', hypoglycemia: 'diseases', fever: 'diseases',
    hypothermia: 'diseases', hypertension: 'heart', hypotension: 'heart', tachypnea: 'diseases'
};

function renderActiveConditions(conditions, overallStatus) {
    const live = new Set();
    if (overallStatus && overallStatus !== 'NORMAL' && conditions && conditions.length > 0) {
        conditions.forEach(c => {
            const level = STATUS_TO_LEVEL[c.status] || 'mid';
            const id = `cond-${c.id}`;
            live.add(id);

            // Check if observed_value is an object (e.g., { systolic, diastolic }) or a primitive
            let valStr = '';
            if (c.observed_value != null) {
                if (typeof c.observed_value === 'object') {
                    const keys = Object.values(c.observed_value);
                    if (keys.length === 2) {
                        valStr = `: ${keys[0]} / ${keys[1]} ${c.unit ?? ''}`;
                    } else {
                        valStr = `: ${JSON.stringify(c.observed_value)}`;
                    }
                } else {
                    valStr = `: ${c.observed_value} ${c.unit ?? ''}`;
                }
            }

            notify({
                id, level,
                text: `${c.title} [${c.status}]${valStr}`.trim(),
                onClick: () => openApp(CONDITION_TO_APP[c.id] ?? 'diseases')
            });
        });
    }
    [...notifs.keys()].filter(k => k.startsWith('cond-') && !live.has(k)).forEach(clearNotify);
}

// =====================================================
// 9. INITIALIZATION AND EVENT BINDING
// =====================================================
document.getElementById('login-btn').addEventListener('click', attemptLogin);
document.getElementById('login-pass').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') attemptLogin();
});

if (isAuth()) {
    currentAstronaut = localStorage.getItem(AUTH_USER_KEY) || 'user1';
    hideLogin();
    resetToHome();
    startPolling();
    setTimeout(layoutMenu, 50);
} else {
    showLogin();
}

// =====================================================
// 10. DAILY ENTRY POST
// =====================================================
async function submitDailyEntry(event) {
    event.preventDefault();

    const sleepInput = document.getElementById('daily-sleep-input');
    const fatigueInput = document.getElementById('daily-fatigue-input');
    const stressSelect = document.getElementById('daily-stress-select');

    if (!sleepInput || !fatigueInput || !stressSelect) return;

    const payload = {
        astronaut_id: currentAstronaut,
        sleep_hours: parseFloat(sleepInput.value),
        fatigue_level: parseInt(fatigueInput.value),
        stress_level: parseInt(stressSelect.value)
    };

    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/daily-entry`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: Failed to submit daily entry.`);
        }

        const result = await response.json();
        notify({
            id: 'daily-success',
            level: 'low',
            text: 'Daily entry saved successfully ✓'
        });
        console.log('Daily entry success:', result);
    } catch (error) {
        console.error('Daily entry error:', error);
        notify({
            id: 'daily-fail',
            level: 'mid',
            text: 'Error: Could not submit daily entry to server.'
        });
    }
}