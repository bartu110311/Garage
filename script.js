// =====================================================
// 1. DOM REFERANSLARI VE DURUM
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
// 0. AUTH KATMANI (Kalıcı Oturum - localStorage)
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
            text: 'ERR: Incorrect user or password.'
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
// 2. UYGULAMA İÇERİKLERİ (Güncellenmiş 8+ Kategori)
// =====================================================
const appConfigs = {
        'heart': {
        title: "Kalp Sağlığı İzleme",
        right: "Kalp Modülü: Nabız, tansiyon, HRV, SpO2 ve kan şekeri takibi.",
        left: `<div class="app-content-box">
            <h2>Kalp & Metabolizma</h2>
            <div class="data-card"><span>Nabız (Heart Rate)</span><strong data-metric="heart_rate"></strong></div>
            <div class="data-card"><span>Tansiyon (Sist./Diyast.)</span><strong data-metric="systolic_bp,diastolic_bp"></strong></div>
            <div class="data-card"><span>HRV (Değişkenlik)</span><strong data-metric="heart_rate_variability"></strong></div>
            <div class="data-card"><span>Oksijen (SpO2)</span><strong data-metric="spo2"></strong></div>
            <div class="data-card"><span>Kan Şekeri</span><strong data-metric="blood_glucose"></strong></div>
        </div>`
    },
    'bone': {
        title: "Kemik & Vücut Dengesi",
        right: "Kemik Modülü: Vücut kütlesi ve hidrasyon seviyeleri izleniyor.",
        left: `<div class="app-content-box">
            <h2>Kemik & Hidrasyon</h2>
            <div class="data-card"><span>Vücut Kütlesi</span><strong data-metric="body_mass"></strong></div>
            <div class="data-card"><span>Hidrasyon Seviyesi</span><strong data-metric="hydration_level"></strong></div>
        </div>`
    },
    'immunity': {
        title: "Bağışıklık & Solunum",
        right: "Bağışıklık Modülü: Solunum hızı ve genel direnç göstergeleri.",
        left: `<div class="app-content-box">
            <h2>Bağışıklık Durumu</h2>
            <div class="data-card"><span>Solunum Hızı</span><strong data-metric="respiratory_rate"></strong></div>
        </div>`
    },
    'stabilite': {
        title: "Fiziksel Sağlamlık",
        right: "Sağlamlık Modülü: Vücut kütlesi ve fiziksel aktivite endeksi.",
        left: `<div class="app-content-box">
            <h2>Sağlamlık Durumu</h2>
            <div class="data-card"><span>Vücut Kütlesi</span><strong data-metric="body_mass"></strong></div>
            <div class="data-card"><span>Fiziksel Aktivite</span><strong data-metric="physical_activity"></strong></div>
        </div>`
    },
    'sleep': {
        title: "Uyku Düzeni İzleme",
        right: "Uyku Analizi: Uyku süresi ve uyku kalitesi endeksi.",
        left: `<div class="app-content-box">
            <h2>Uyku Verileri</h2>
            <div class="data-card"><span>Uyku Süresi</span><strong data-metric="sleep_duration"></strong></div>
            <div class="data-card"><span>Uyku Kalitesi</span><strong data-metric="sleep_quality"></strong></div>
        </div>`
    },
    'psychology': {
        title: "Psikoloji & Stres Yönetimi",
        right: "Psikoloji Modülü: Astronot stres seviyesi ve zihinsel denge.",
        left: `<div class="app-content-box">
            <h2>Psikolojik Durum</h2>
            <div class="data-card"><span>Stres Seviyesi</span><strong data-metric="stress_level"></strong></div>
        </div>`
    },
    'environment': {
        title: "Kabin Ortam Koşulları",
        right: "Ortam Modülü: Kabin içi sıcaklık, basınç, gazlar ve yerçekimi durumu.",
        left: `<div class="app-content-box" style="gap: 8px;">
            <h2>Kabin Ortamı</h2>
            <div class="data-card"><span>Kabin Sıcaklığı</span><strong data-metric="cabin_temperature"></strong></div>
            <div class="data-card"><span>Kabin Basıncı</span><strong data-metric="cabin_pressure"></strong></div>
            <div class="data-card"><span>Nem Oranı</span><strong data-metric="cabin_humidity"></strong></div>
            <div class="data-card"><span>Oksijen (O2)</span><strong data-metric="cabin_oxygen"></strong></div>
            <div class="data-card"><span>Karbondioksit (CO2)</span><strong data-metric="cabin_co2"></strong></div>
            <div class="data-card"><span>Mikroyerçekimi</span><strong data-metric="microgravity_level"></strong></div>
            <div class="data-card"><span>Hava Kalitesi</span><strong data-metric="cabin_air_quality"></strong></div>
        </div>`
    },
    'space': {
        title: "Uzay & ISS Konum Verileri",
        right: "Uzay Modülü: ISS anlık koordinatları, irtifası ve yörünge hızı.",
        left: `<div class="app-content-box">
            <h2>ISS Yörünge Verileri</h2>
            <div class="data-card"><span>Enlem (Latitude)</span><strong data-metric="iss.latitude" data-unit="°" data-digits="2"></strong></div>
            <div class="data-card"><span>Boylam (Longitude)</span><strong data-metric="iss.longitude" data-unit="°" data-digits="2"></strong></div>
            <div class="data-card"><span>İrtifa (Altitude)</span><strong data-metric="iss.altitude_km" data-unit="km" data-digits="1"></strong></div>
            <div class="data-card"><span>Hız (Velocity)</span><strong data-metric="iss.velocity_km_h" data-unit="km/sa" data-digits="0"></strong></div>
            <div class="data-card"><span>Uzay Havası Durumu</span><strong data-metric="space.status"></strong></div>
            <div class="data-card"><span>Güneş Parçacık Olayları</span><strong data-metric="space.sep_events" data-format="count" data-unless="space.status=DISABLED_NO_API_KEY"></strong></div>
        </div>`
    },
    'active-radiation': {
        title: "Radyasyon & Uzay Havası",
        right: "Radyasyon Modülü: Doz oranı, kümülatif doz ve jeomanyetik fırtınalar.",
        left: `<div class="app-content-box">
            <h2>Radyasyon Dozimetresi</h2>
            <div class="data-card"><span>Doz Hızı</span><strong data-metric="rad.dose_rate_usv_h" data-unit="µSv/h" data-unless="rad.integration_status=NO_DOSE_INTEGRATED"></strong></div>
            <div class="data-card"><span>Kümülatif Doz</span><strong data-metric="rad.cumulative_dose_msv" data-unit="mSv" data-unless="rad.integration_status=NO_DOSE_INTEGRATED"></strong></div>
            <div class="data-card"><span>Veri Durumu</span><strong data-metric="rad.measurement_status"></strong></div>
        </div>`
    },
    'tiredness': {
        title: "Yorgunluk Takibi",
        right: "Yorgunluk Durumu: Uyku süresi ve dinlenme verileri.",
        left: `<div class="app-content-box"><h2>Yorgunluk</h2><div class="data-card"><span>Uyku Süresi</span><strong data-metric="sleep_duration"></strong></div></div>`
    },
    'immunity': {
        title: "Bağışıklık & Solunum",
        right: "Bağışıklık Modülü: Solunum hızı ve genel direnç göstergeleri.",
        left: `<div class="app-content-box">
            <h2>Bağışıklık Durumu</h2>
            <div class="data-card"><span>Solunum Hızı</span><strong id="immunity-resp-now">--</strong></div>
        </div>`
    },
    'diseases': {
        title: "Hastalıklar & Aktif Bulgular",
        right: "Hastalık Taraması: Sistem tarafından algılanan anlık tıbbi bulgular.",
        left: `<div class="app-content-box">
            <h2>Aktif Bulgular (Active Conditions)</h2>
            <div id="diseases-container" style="display: flex; flex-direction: column; gap: 10px; width: 100%; max-height: 260px; overflow-y: auto;">
                <div class="data-card"><span>Durum</span><strong>Veri bekleniyor...</strong></div>
            </div>
        </div>`
    },
    'cancer': {
        title: "Kanser Riski",
        right: "Bu sekme boş bırakılmıştır.",
        left: `<div class="app-content-box" style="text-align: center; justify-content: center; align-items: center;"><h2 style="border: none;">Boş</h2></div>`
    },
    'bacteria': {
        title: "Bakteriyel Flora",
        right: "Bakteriyel Flora: Mikrobiyom çeşitliliği stabil.",
        left: `<div class="app-content-box"><h2>Mikrobiyom</h2><div class="data-card"><span>Çeşitlilik Skoru</span><strong>94 / 100</strong></div></div>`
    },
    'standard-input': {
        title: "Günlük Veri Girişi",
        right: "Gündelik Veri Girdisi: Uyku, yorgunluk ve stres seviyenizi girin (v0.4.0).",
        left: `<div class="app-content-box">
            <h2>Günlük Veri Girişi</h2>
            <form class="app-form" onsubmit="submitDailyEntry(event)">
                <div class="form-group">
                    <label>Uyku Süresi (Saat, 0-24):</label>
                    <input type="number" id="daily-sleep-input" value="7.5" min="0" max="24" step="0.5">
                </div>
                <div class="form-group">
                    <label>Yorgunluk Seviyesi (0-10):</label>
                    <input type="number" id="daily-fatigue-input" min="0" max="10" value="4">
                </div>
                <div class="form-group">
                    <label>Stres Seviyesi (0-10):</label>
                    <input type="number" id="daily-stress-select" min="0" max="10" value="5">
                </div>
                <button type="submit" class="submit-btn">Verileri Sunucuya Gönder</button>
            </form>
        </div>`
    },
    'teammates': {
        title: "Takım Arkadaşları",
        right: "Ekip sağlık durumları.",
        left: `<div class="app-content-box"><h2>Ekip Durumu</h2><div class="data-card"><span>Astronot 1</span><strong id="teammate-1-status">--</strong></div><div class="data-card"><span>Astronot 2</span><strong id="teammate-2-status">--</strong></div><div class="data-card"><span>Astronot 3</span><strong id="teammate-3-status">--</strong></div></div>`
    },
    'learn': { title: "Acil Eğitim", right: "", left: "" },
    'standard-procedure': { title: "Prosedürler", right: "", left: "" },
    'emergency': { title: "Acil Durum", right: "", left: "" },
    'settings': {
        title: "Ayarlar",
        right: "Oturum ve Ayarlar",
        left: `<div class="app-content-box">
            <h2>Ayarlar & Oturum</h2>
            <input type="file" id="photo-input" accept="image/*" hidden>
            <button id="photo-pick" type="button" class="submit-btn">Fotoğraf Seç</button>
            <button id="photo-clear" type="button" class="submit-btn">Fotoğrafı Sıfırla</button>
            <hr style="border: 0; border-top: 1px solid rgba(231, 225, 88, 0.3); margin: 5px 0;">
            <button id="logout-btn" type="button" class="submit-btn" style="background-color: var(--fourth); color: #fff;">Oturumu Kapat (Çıkış)</button>
        </div>`
    }
};

// =====================================================
// 3. RADYAL MENÜ YERLEŞİMİ
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
// 4. FOTOĞRAF ÇERÇEVESİ VE AYARLAR
// =====================================================
const PHOTO_KEY = 'family-photo';
const photoKey = () => `${PHOTO_KEY}-${currentAstronaut}`;  // hemen altına ekle

const DEFAULT_PHOTO = 'data:image/svg+xml;utf8,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400"><rect width="100%" height="100%" fill="#00273d"/>' +
    '<text x="50%" y="50%" fill="#e7e158" font-family="sans-serif" font-size="26" text-anchor="middle">' +
    'Ayarlar menüsünden fotoğraf ekleyin</text></svg>'
);

function currentPhoto() {
    try { return localStorage.getItem(PHOTO_KEY) || DEFAULT_PHOTO; }
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
                localStorage.setItem(PHOTO_KEY, c.toDataURL('image/jpeg', 0.85));
                pick.textContent = 'Fotoğraf kaydedildi ✓';
            } catch { 
                pick.textContent = 'Kaydedilemedi'; 
            }
        };
        img.src = URL.createObjectURL(file);
    };

    if (clear) {
        clear.onclick = () => {
            try { localStorage.removeItem(PHOTO_KEY); } catch {}
            clear.textContent = 'Varsayılana dönüldü ✓';
        };
    }
}

// =====================================================
// 5. EKRAN GEÇİŞLERİ
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
            <img alt="Aile fotoğrafı">
        </div>
    `;
    showPhoto(currentPhoto());
    isDetailView = false;
    hexagonClickInDetail = 0;
    menu.setAttribute('inert', '');
    updateHomePanel();
}

const STATUS_TR = { NORMAL: 'NORMAL', CAUTION: 'DİKKAT', WARNING: 'UYARI', CRITICAL: 'KRİTİK' };

function updateHomePanel() {
    if (isDetailView) return;
    if (!lastData) {
        panelTitle.textContent = 'Bağlanıyor…';
        panelDesc.textContent = 'Veri bekleniyor.';
        return;
    }
    panelTitle.textContent = `Genel Durum: ${STATUS_TR[lastData.overall_status] ?? '—'}`;
    const c = lastData.active_conditions ?? [];
    panelDesc.textContent = c.length
        ? c.map(x => x.title).join(' · ')
        : `${currentAstronaut} — Aktif bulgu yok.`;
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
// 6. ÇOKLU BİLDİRİM SİSTEMİ
// =====================================================
const LEVELS = {
    low:  { rank: 1, icon: 'ℹ', label: 'BASİT UYARI',     sticky: false, color: '#e7e158' },
    mid:  { rank: 2, icon: '▲', label: 'RİSKLİ UYARI',    sticky: false, color: '#feb367' },
    high: { rank: 3, icon: '⚠', label: 'TEHLİKELİ UYARI', sticky: true,  color: '#ff5f66' }
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
// 7. API KATMANI VE MERKEZİ VERİ YÖNETİMİ — v0.3.0
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
        console.warn(`Dashboard alınamadı (${currentAstronaut}):`, error.message);
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
                if (el) el.textContent = `${STATUS_TR[c.overall_status] ?? c.overall_status}`;
            });
        }
    } catch (e) {}
}
// =====================================================
// TELEMETRİ OKUMA YAPISI: iç içe JSON → düz anahtar listesi → data-metric
// =====================================================
const GROUP_PREFIX = {
    physiological_data: '',            // heart_rate, spo2, ...
    environmental_data: '',            // cabin_co2, cabin_pressure, ...
    iss_position_data: 'iss.',         // iss.altitude_km, iss.latitude, ...
    space_weather_data: 'space.',      // space.status, space.sep_events, ...
    radiation_dosimetry_data: 'rad.'   // rad.cumulative_dose_msv, rad.integration_status, ...
};
const UNIT_TR = { 'breaths/min': 'nefes/dk', 'h': 'saat', 'index': 'indeks', 'simulation_index': 'sim. indeks' };
const Q_ORDER = ['MISSING', 'INVALID', 'STALE', 'UNKNOWN', 'VALID'];   // en kötüden en iyiye

// data.telemetry içindeki her alanı tek bir düz sözlüğe çevirir
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

// Ham bir alanı { ok, value, unit, quality } biçimine çevirir
function readField(raw, { digits, unit, format } = {}) {
    const d = digits != null ? Number(digits) : undefined;
    if (raw == null) return { ok: false, quality: 'MISSING' };
    if (Array.isArray(raw)) return { ok: true, value: format === 'count' ? String(raw.length) : raw.join(', '), unit: unit ?? '' };
    if (isMeasurement(raw)) {
        const q = raw.quality ?? 'UNKNOWN';
        if (raw.value == null || q === 'MISSING' || q === 'INVALID') return { ok: false, quality: q };
        const u = raw.unit === 'unknown' ? '' : (UNIT_TR[raw.unit] ?? raw.unit ?? '');
        return { ok: true, value: fmtNum(raw.value, d), unit: u, quality: q };
    }
    if (typeof raw === 'number') return { ok: true, value: fmtNum(raw, d), unit: unit ?? '' };
    return { ok: true, value: String(raw), unit: unit ?? '' };
}

// root içindeki tüm [data-metric] elemanlarını doldurur
function bindMetrics(root, data) {
    const index = buildMetricIndex(data);
    root.querySelectorAll('[data-metric]').forEach(el => {
        const setText = (text, quality) => {
            el.textContent = text;
            if (quality) { el.dataset.quality = quality; el.title = `Ölçüm kalitesi: ${quality}`; }
            else { delete el.dataset.quality; el.removeAttribute('title'); }
        };

        // data-unless="anahtar=değer": o durumdaysa veri yok say (ör. dozimetre hatası varken "0 mSv" gösterme)
        const unless = el.dataset.unless;
        if (unless) {
            const [k, v] = unless.split('=');
            if (String(index[k]) === v) return setText('--');
        }

        const opts = { digits: el.dataset.digits, unit: el.dataset.unit, format: el.dataset.format };
        const parts = el.dataset.metric.split(',').map(k => readField(index[k.trim()], opts));   // "systolic_bp,diastolic_bp" → 113.6/72.9
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

    // Hastalıklar / aktif bulgular listesi
    const box = document.getElementById('diseases-container');
    if (box) {
        const conds = data.active_conditions ?? [];
        box.innerHTML = conds.length ? conds.map(c => `
            <div class="data-card" style="flex-direction:column;align-items:flex-start;gap:4px;">
                <div style="display:flex;justify-content:space-between;width:100%;">
                    <span style="color:var(--second);">[ ${esc(c.status)} ] ${esc(c.title)}</span>
                    <strong>${esc(c.observed_value)} ${esc(c.unit)}</strong>
                </div>
                <span style="font-size:.85rem;opacity:.8;">${esc(c.context_note ?? c.id)}</span>
            </div>`).join('')
            : `<div class="data-card"><span>Tarama Durumu</span><strong>Aktif bulgu yok.</strong></div>`;
    }
}

function showConnectionErrorState() {
    notify({ id: 'conn', level: 'mid', text: 'Sunucu bağlantısı yok, veriler güncel değil' });
}

// =====================================================
// 8. AKTİF BULGULAR VE ÇOKLU BİLDİRİM YÖNETİMİ
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
            notify({
                id, level,
                text: `${c.title} [${c.status}]${c.observed_value != null ? `: ${c.observed_value} ${c.unit ?? ''}`.trim() : ''}`,
                onClick: () => openApp(CONDITION_TO_APP[c.id] ?? 'diseases')
            });
        });
    }
    [...notifs.keys()].filter(k => k.startsWith('cond-') && !live.has(k)).forEach(clearNotify);
}

// =====================================================
// 9. BAŞLATMA VE EVENT BINDING
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
// 10. Günlük Gönderi POST
// =====================================================
async function submitDailyEntry(event) {
    event.preventDefault();

    // Form alanlarından değerleri alıyoruz
    const sleepInput = document.getElementById('daily-sleep-input');
    const fatigueInput = document.getElementById('daily-fatigue-input');
    const stressSelect = document.getElementById('daily-stress-select');

    if (!sleepInput || !fatigueInput || !stressSelect) return;

    const payload = {
        astronaut_id: currentAstronaut,
        sleep_hours: parseFloat(sleepInput.value),
        fatigue_level: parseInt(fatigueInput.value),
        stress_level: parseInt(stressSelect.value) // 0-10 arası bir değer veya indeks
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
            throw new Error(`HTTP ${response.status}: Veri gönderilemedi.`);
        }

        const result = await response.json();
        notify({
            id: 'daily-success',
            level: 'low',
            text: 'Günlük veriler başarıyla kaydedildi ✓'
        });
        console.log('Daily entry success:', result);
    } catch (error) {
        console.error('Daily entry error:', error);
        notify({
            id: 'daily-fail',
            level: 'mid',
            text: 'Hata: Günlük veriler sunucuya gönderilemedi.'
        });
    }
}