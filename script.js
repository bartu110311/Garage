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
            text: 'Hatalı giriş: kullanıcı veya parola yanlış'
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
// 2. UYGULAMA İÇERİKLERİ (Güncellenmiş Modüller)
// =====================================================
const appConfigs = {
    'heart': {
        title: "Kalp Sağlığı İzleme",
        right: "Kalp Modülü: Anlık nabız, oksijen satürasyonu, tansiyon ve solunum hızı takibi.",
        left: `<div class="app-content-box">
            <h2>Kalp & Dolaşım</h2>
            <div class="data-card"><span>Anlık Nabız</span><strong id="heart-rate-now">--</strong></div>
            <div class="data-card"><span>Oksijen Satürasyonu</span><strong id="oxygen-sat-now">--</strong></div>
            <div class="data-card"><span>Tansiyon (Sist./Diyast.)</span><strong id="blood-pressure-now">--</strong></div>
            <div class="data-card"><span>Solunum Hızı</span><strong id="respiratory-now">--</strong></div>
        </div>`
    },
    'bone': {
        title: "Kemik Yoğunluğu Analizi",
        right: "Kemik Yoğunluğu: Yerçekimsiz ortam kalsiyum seviyeleri ve kemik mineral yoğunluğu.",
        left: `<div class="app-content-box">
            <h2>Kemik Durumu</h2>
            <div class="data-card"><span>Kalsiyum Seviyesi</span><strong id="bone-calcium-now">--</strong></div>
            <div class="data-card"><span>Kemik Yoğunluğu</span><strong id="bone-density-now">--</strong></div>
        </div>`
    },
    'environment': {
        title: "Ortam Koşulları",
        right: "Ortam Modülü: Kabin içi basınç, sıcaklık, CO2 ve nem seviyeleri izleniyor.",
        left: `<div class="app-content-box">
            <h2>Kabin Ortamı</h2>
            <div class="data-card"><span>Kabin Basıncı</span><strong id="env-pressure-now">--</strong></div>
            <div class="data-card"><span>Kabin Sıcaklığı</span><strong id="env-temp-now">--</strong></div>
            <div class="data-card"><span>Karbondioksit (CO2)</span><strong id="env-co2-now">--</strong></div>
            <div class="data-card"><span>Nem Oranı</span><strong id="env-humidity-now">--</strong></div>
        </div>`
    },
    'space': {
        title: "Uzay & ISS Konum / Hava Durumu",
        right: "Uzay Modülü: ISS yörünge simülasyonu, Dünya mesafesi ve uzay havası bağlamı.",
        left: `<div class="app-content-box">
            <h2>Uzay & ISS Simülasyonu</h2>
            <div class="data-card"><span>Dünya - ISS Mesafesi</span><strong id="iss-distance-now">--</strong></div>
            <div class="data-card"><span>ISS Konum (Enl/Boy/Yük)</span><strong id="iss-coords-now">--</strong></div>
            <div class="data-card"><span>Uzay Havası</span><strong id="space-weather-now">--</strong></div>
            <div style="background: rgba(0,0,0,0.3); border-radius: 12px; padding: 12px; text-align: center; border: 1px dashed var(--second);">
                <p style="font-size: 0.9rem; color: var(--second); margin-bottom: 5px; font-weight: bold;">[ 3D Yörünge Simülasyonu ]</p>
                <div id="iss-3d-visual" style="font-size: 1.05rem; color: #fff;">ISS Dünya Yörüngesinde Aktif 🛰️</div>
            </div>
        </div>`
    },
    'active-radiation': {
        title: "Radyasyon Riski",
        right: "Aktif Radyasyon Riski: Anlık akı, doz hızı ve kümülatif doz ölçümleri.",
        left: `<div class="app-content-box">
            <h2>Radyasyon Dozimetresi</h2>
            <div class="data-card"><span>Anlık Akı (Current Flux)</span><strong id="radiation-flux-now">--</strong></div>
            <div class="data-card"><span>Doz Hızı (Dose Rate)</span><strong id="radiation-dose-rate">--</strong></div>
            <div class="data-card"><span>Kümülatif Doz</span><strong id="radiation-cum-dose">--</strong></div>
        </div>`
    },
    'cancer': {
        title: "Kanser Riski",
        right: "Kanser Risk Modülü: Bu modül boş bırakılmıştır.",
        left: `<div class="app-content-box" style="text-align: center; justify-content: center; align-items: center;">
            <h2 style="border: none;">Boş</h2>
            <p style="color: rgba(255,255,255,0.6); font-size: 1.1rem;">Bu sekme şu anda boş durumdadır.</p>
        </div>`
    },
    'tiredness': {
        title: "Yorgunluk Takibi",
        right: "Yorgunluk Durumu: Uyku süresi ve dinlenme verileri.",
        left: `<div class="app-content-box">
            <h2>Yorgunluk & Uyku</h2>
            <div class="data-card"><span>Uyku Süresi</span><strong id="tiredness-sleep-now">--</strong></div>
            <div class="data-card"><span>Fiziksel Yorgunluk</span><strong>3 / 10</strong></div>
            <div class="data-card"><span>Mental Durum</span><strong>Stabil</strong></div>
        </div>`
    },
    'diseases': {
        title: "Hastalıklar & Aktif Bulgular",
        right: "Hastalık Taraması: Sistem tarafından algılanan anlık tıbbi bulgular ve uyarılar.",
        left: `<div class="app-content-box">
            <h2>Aktif Tıbbi Bulgular</h2>
            <div id="diseases-container" style="display: flex; flex-direction: column; gap: 10px; width: 100%; max-height: 250px; overflow-y: auto;">
                <div class="data-card"><span>Tarama Durumu</span><strong>Aktif Bulgu Bekleniyor...</strong></div>
            </div>
        </div>`
    },
    'sleep': {
        title: "Uyku Düzeni İzleme",
        right: "Uyku Analizi: Son 24 saatteki uyku verileri.",
        left: `<div class="app-content-box"><h2>Uyku Verileri</h2><div class="data-card"><span>Son Uyku</span><strong id="sleep-duration-now">--</strong></div><div class="data-card"><span>REM Evresi</span><strong>%18 (Düşük)</strong></div><div class="data-card"><span>Uyku Kalitesi</span><strong>Orta</strong></div></div>`
    },
    'stabilite': {
        title: "Psikolojik Sağlamlık",
        right: "Psikolojik Sağlamlık: Stres endeksi dengeli.",
        left: `<div class="app-content-box"><h2>Psikoloji</h2><div class="data-card"><span>Stres Endeksi</span><strong>1.4 / 5</strong></div><div class="data-card"><span>Moral Skoru</span><strong>88 / 100</strong></div><div class="data-card"><span>Motivasyon</span><strong>Yüksek</strong></div></div>`
    },
    'actions': {
        title: "Davranışsal Tepki Analizi",
        right: "Davranışsal Tepki: Refleks testleri optimal seviyede.",
        left: `<div class="app-content-box"><h2>Davranış & Refleks</h2><div class="data-card"><span>Tepki Süresi</span><strong>210 ms</strong></div><div class="data-card"><span>Karar Doğruluğu</span><strong>%96</strong></div><div class="data-card"><span>Bilişsel Yük</span><strong>Normal</strong></div></div>`
    },
    'bacteria': {
        title: "Bakteriyel Flora",
        right: "Bakteriyel Flora: Mikrobiyom çeşitliliği stabil.",
        left: `<div class="app-content-box"><h2>Mikrobiyom</h2><div class="data-card"><span>Çeşitlilik Skoru</span><strong>94 / 100</strong></div><div class="data-card"><span>Patojen Riski</span><strong>Sıfır</strong></div><div class="data-card"><span>Cilt Florası</span><strong>Stabil</strong></div></div>`
    },
    'immunity': {
        title: "Bağışıklık Sistemi",
        right: "Bağışıklık Sistemi: Lökosit ve antikor seviyeleri normal.",
        left: `<div class="app-content-box"><h2>Bağışıklık Durumu</h2><div class="data-card"><span>Lökosit Sayısı</span><strong>6.8 k/uL</strong></div><div class="data-card"><span>Antikor Seviyesi</span><strong>Normal</strong></div><div class="data-card"><span>Enfeksiyon</span><strong>Yok</strong></div></div>`
    },
    'standart-input': {
        title: "Günlük Veri Girişi",
        right: "Gündelik Veri Girdisi: Uyku, yorgunluk ve stres seviyenizi girin.",
        left: `<div class="app-content-box"><h2>Günlük Veri Girişi</h2><form class="app-form" onsubmit="event.preventDefault(); alert('Veriler kaydedildi!');"><div class="form-group"><label>Uyku Süresi (Saat):</label><input type="number" value="7" min="0" max="24" step="0.5"></div><div class="form-group"><label>Yorgunluk (1-10):</label><input type="number" min="1" max="10" value="3"></div><div class="form-group"><label>Stres Seviyesi:</label><select><option>Düşük</option><option selected>Normal</option><option>Yüksek</option></select></div><button type="submit" class="submit-btn">Verileri Kaydet</button></form></div>`
    },
    'teammates': {
        title: "Takım Arkadaşları",
        right: "Takım Arkadaşları: Ekip sağlık durumları.",
        left: `<div class="app-content-box"><h2>Ekip Durumu</h2><div class="data-card"><span>Astronot 1</span><strong id="teammate-1-status">--</strong></div><div class="data-card"><span>Astronot 2</span><strong id="teammate-2-status">--</strong></div><div class="data-card"><span>Astronot 3</span><strong id="teammate-3-status">--</strong></div></div>`
    },
    'learn': {
        title: "Acil Durum Eğitimi",
        right: "Acil Durum Eğitimi: Basınç düşüşü ve oksijen maskesi prosedürleri.",
        left: `<div class="app-content-box"><h2>Eğitim Modülleri</h2><div class="data-card"><span>Basınç Düşüşü</span><strong>Tamamlandı</strong></div><div class="data-card"><span>Oksijen Maskesi</span><strong>Tamamlandı</strong></div><div class="data-card"><span>Yangın Prosedürü</span><strong>İnceleniyor</strong></div></div>`
    },
    'standart-procedure': {
        title: "Standart Prosedürler",
        right: "Standart Prosedürler: Günlük bakım ve sistem kontrolü.",
        left: `<div class="app-content-box"><h2>Kontrol Listesi</h2><div class="data-card"><strong>https://ntrs.nasa.gov/api/citations/20210013869/downloads/20210013869.pdf?attachment=true#4#19#4</strong></div><div class="data-card"><span>Su Geri Dönüşüm</span><strong>Normal (%98)</strong></div><div class="data-card"><span>İletişim Anteni</span><strong>Aktif</strong></div></div>`
    },
    'emergency': {
        title: "Acil Durum Prosedürleri",
        right: "Acil Durum Prosedürleri: Tahliye rotaları ve kriz planları.",
        left: `<div class="app-content-box"><h2>Kriz Planları</h2><div class="data-card"><span>Tahliye Rotası</span><strong>Açık</strong></div><div class="data-card"><span>Güvenli Sığınak</span><strong>Hazır</strong></div><div class="data-card"><span>Acil Ekipman</span><strong>Eksiksiz</strong></div></div>`
    },
    'settings': {
        title: "Ayarlar",
        right: "Ayarlar: Ana ekranda görünecek aile fotoğrafını değiştirebilir veya mevcut oturumu sonlandırabilirsiniz.",
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
                pick.textContent = 'Kaydedilemedi (Boyut çok büyük)'; 
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

function readMeasurement(measurement, defaultUnit = '') {
    if (measurement == null) return null;
    
    if (typeof measurement === 'object') {
        if (measurement.value == null) return null;
        const quality = measurement.quality ?? 'UNKNOWN';
        
        if (quality === 'INVALID' || quality === 'MISSING' || quality === 'UNKNOWN') {
            return null;
        }
        
        return {
            value: measurement.value,
            unit: measurement.unit ?? defaultUnit,
            stale: quality === 'STALE',
            measuredAt: measurement.measured_at
        };
    }
    
    return { value: measurement, unit: defaultUnit, stale: false };
}

function getTelemetryValue(data, targetAstronaut, category, key) {
    if (!data) return null;

    let targetTelemetry = null;

    if (data.telemetry) {
        targetTelemetry = data.telemetry;
    } else if (data.crew && targetAstronaut) {
        const astronautObj = data.crew.find(c => c.astronaut_id === targetAstronaut);
        if (astronautObj && astronautObj.telemetry) {
            targetTelemetry = astronautObj.telemetry;
        }
    }

    if (!targetTelemetry) return null;

    let targetGroup = null;

    switch (category) {
        case 'physiological':
            targetGroup = targetTelemetry.physiological_data;
            break;
        case 'environmental':
            targetGroup = targetTelemetry.environmental_data;
            break;
        case 'radiation':
            targetGroup = targetTelemetry.radiation_dosimetry_data;
            break;
        case 'iss':
            targetGroup = targetTelemetry.iss_position_data;
            break;
        case 'space_weather':
            targetGroup = targetTelemetry.space_weather_data;
            break;
        default:
            return null;
    }

    if (!targetGroup || targetGroup[key] == null) return null;

    const defaultUnits = {
        heart_rate: 'bpm',
        blood_glucose: 'mg/dL',
        body_temperature: '°C',
        oxygen_saturation: '%',
        respiratory_rate: 'rpm',
        blood_pressure_systolic: 'mmHg',
        blood_pressure_diastolic: 'mmHg',
        cabin_pressure: 'kPa',
        cabin_temperature: '°C',
        carbon_dioxide_level: 'mmHg',
        humidity: '%',
        current_flux: 'mSv/h',
        dose_rate: 'mSv/h',
        cumulative_dose: 'mSv',
        calcium_level: 'mg/dL',
        bone_density: 'g/cm²',
        sleep_duration: 'saat'
    };

    return readMeasurement(targetGroup[key], defaultUnits[key] || '');
}

function formatTelemetryDisplay(metricObj, fallbackText = '--') {
    if (!metricObj) return fallbackText;
    const text = `${metricObj.value} ${metricObj.unit}`.trim();
    return metricObj.stale ? `${text} (eski)` : text;
}

function updateUIWithTelemetry(data) {
    lastData = data;
    clearNotify('conn');
    document.body.setAttribute('data-system-status', data.overall_status);

    renderActiveConditions(data.active_conditions ?? [], data.overall_status);

    if (data.data_quality && data.data_quality.status !== 'GOOD') {
        notify({
            id: 'dq', level: 'low',
            text: `Veri kalitesi: ${(data.data_quality.warnings ?? []).join(', ') || data.data_quality.status}`
        });
    } else {
        clearNotify('dq');
    }

    updateLiveFields(data);
    updateHomePanel();
}

// ------------------------------------------------     
// CANLI ALANLARI GÜNCELLEME
// ------------------------------------------------     
function updateLiveFields(data) {
    if (!data) return;

    // 1. Kalp Modülü Metrikleri
    const hrEl = document.getElementById('heart-rate-now');
    if (hrEl) {
        const hr = getTelemetryValue(data, currentAstronaut, 'physiological', 'heart_rate') 
                   ?? extractHeartRateFromConditions(data);
        hrEl.textContent = formatTelemetryDisplay(hr, '--');
    }

    const o2El = document.getElementById('oxygen-sat-now');
    if (o2El) {
        const o2 = getTelemetryValue(data, currentAstronaut, 'physiological', 'oxygen_saturation');
        o2El.textContent = formatTelemetryDisplay(o2, '--');
    }

    const bpEl = document.getElementById('blood-pressure-now');
    if (bpEl) {
        const sys = getTelemetryValue(data, currentAstronaut, 'physiological', 'blood_pressure_systolic');
        const dia = getTelemetryValue(data, currentAstronaut, 'physiological', 'blood_pressure_diastolic');
        if (sys && dia) {
            bpEl.textContent = `${sys.value}/${dia.value} mmHg`;
        } else {
            bpEl.textContent = '--';
        }
    }

    const respEl = document.getElementById('respiratory-now');
    if (respEl) {
        const resp = getTelemetryValue(data, currentAstronaut, 'physiological', 'respiratory_rate');
        respEl.textContent = formatTelemetryDisplay(resp, '--');
    }

    // 2. Kemik Modülü Metrikleri
    const calciumEl = document.getElementById('bone-calcium-now');
    if (calciumEl) {
        const calcium = getTelemetryValue(data, currentAstronaut, 'physiological', 'calcium_level');
        calciumEl.textContent = formatTelemetryDisplay(calcium, '--');
    }

    const densityEl = document.getElementById('bone-density-now');
    if (densityEl) {
        const density = getTelemetryValue(data, currentAstronaut, 'physiological', 'bone_density');
        densityEl.textContent = formatTelemetryDisplay(density, '--');
    }

    // 3. Ortam Modülü
    const pressEl = document.getElementById('env-pressure-now');
    if (pressEl) {
        const p = getTelemetryValue(data, currentAstronaut, 'environmental', 'cabin_pressure');
        pressEl.textContent = formatTelemetryDisplay(p, '--');
    }

    const tempEl = document.getElementById('env-temp-now');
    if (tempEl) {
        const t = getTelemetryValue(data, currentAstronaut, 'environmental', 'cabin_temperature');
        tempEl.textContent = formatTelemetryDisplay(t, '--');
    }

    const co2El = document.getElementById('env-co2-now');
    if (co2El) {
        const co2 = getTelemetryValue(data, currentAstronaut, 'environmental', 'carbon_dioxide_level');
        co2El.textContent = formatTelemetryDisplay(co2, '--');
    }

    const humEl = document.getElementById('env-humidity-now');
    if (humEl) {
        const h = getTelemetryValue(data, currentAstronaut, 'environmental', 'humidity');
        humEl.textContent = formatTelemetryDisplay(h, '--');
    }

    // 4. Uzay Modülü & ISS Simülasyonu
    const distEl = document.getElementById('iss-distance-now');
    if (distEl) {
        const altObj = getTelemetryValue(data, currentAstronaut, 'iss', 'iss_altitude');
        if (altObj && altObj.value != null) {
            const earthRadius = 6371;
            const totalDist = (earthRadius + altObj.value).toFixed(1);
            distEl.textContent = `${totalDist} km`;
        } else {
            distEl.textContent = '~6771.0 km (Simüle)';
        }
    }

    const coordsEl = document.getElementById('iss-coords-now');
    if (coordsEl) {
        const lat = getTelemetryValue(data, currentAstronaut, 'iss', 'iss_latitude');
        const lon = getTelemetryValue(data, currentAstronaut, 'iss', 'iss_longitude');
        if (lat && lon) {
            coordsEl.textContent = `${lat.value}°, ${lon.value}°`;
        } else {
            coordsEl.textContent = '27.5°, 45.2° (Aktif)';
        }
    }

    const swEl = document.getElementById('space-weather-now');
    if (swEl) {
        const sw = getTelemetryValue(data, currentAstronaut, 'space_weather', 'solar_wind_speed') 
                   ?? { value: 'Normal / Stabil', unit: '' };
        swEl.textContent = formatTelemetryDisplay(sw, 'Normal');
    }

    // 5. Radyasyon Modülü (current_flux, dose_rate, cumulative_dose)
    const fluxEl = document.getElementById('radiation-flux-now');
    if (fluxEl) {
        const flux = getTelemetryValue(data, currentAstronaut, 'radiation', 'current_flux');
        fluxEl.textContent = formatTelemetryDisplay(flux, '--');
    }

    const doseRateEl = document.getElementById('radiation-dose-rate');
    if (doseRateEl) {
        const dr = getTelemetryValue(data, currentAstronaut, 'radiation', 'dose_rate');
        doseRateEl.textContent = formatTelemetryDisplay(dr, '--');
    }

    const cumDoseEl = document.getElementById('radiation-cum-dose');
    if (cumDoseEl) {
        const cd = getTelemetryValue(data, currentAstronaut, 'radiation', 'cumulative_dose');
        cumDoseEl.textContent = formatTelemetryDisplay(cd, '--');
    }

    // 6. Yorgunluk Modülü (sleep_duration eklendi)
    const tiredSleepEl = document.getElementById('tiredness-sleep-now');
    if (tiredSleepEl) {
        const sleep = getTelemetryValue(data, currentAstronaut, 'physiological', 'sleep_duration');
        tiredSleepEl.textContent = formatTelemetryDisplay(sleep, '--');
    }

    // 7. Hastalıklar / Aktif Bulgular Modülü
    const diseaseContainer = document.getElementById('diseases-container');
    if (diseaseContainer) {
        const conds = data.active_conditions ?? [];
        if (conds.length > 0) {
            diseaseContainer.innerHTML = conds.map(c => `
                <div class="data-card" style="flex-direction: column; align-items: flex-start; gap: 4px;">
                    <div style="display: flex; justify-content: space-width; width: 100%; justify-content: space-between;">
                        <span style="color: var(--second);">[ ${c.status} ] ${c.title}</span>
                        <strong>${c.observed_value ?? ''} ${c.unit ?? ''}</strong>
                    </div>
                    <span style="font-size: 0.85rem; opacity: 0.8;">ID: ${c.id}</span>
                </div>
            `).join('');
        } else {
            diseaseContainer.innerHTML = `<div class="data-card"><span>Tarama Durumu</span><strong>Aktif bulgu / hastalık yok.</strong></div>`;
        }
    }
}

function extractHeartRateFromConditions(data) {
    const c = data?.active_conditions?.find(x =>
        x.id === 'tachycardia' ||
        x.id === 'bradycardia' ||
        (Array.isArray(x.related_measurements) && x.related_measurements.includes('heart_rate'))
    );
    return c ? { value: c.observed_value, unit: c.unit ?? 'bpm', stale: false } : null;
}

function showConnectionErrorState() {
    notify({ id: 'conn', level: 'mid', text: 'Sunucu bağlantısı yok, veriler güncel değil' });
}

// =====================================================
// 8. AKTİF BULGULAR VE ÇOKLU BİLDİRİM YÖNETİMİ
// =====================================================
const STATUS_TO_LEVEL = { CAUTION: 'low', WARNING: 'mid', CRITICAL: 'high' };
const CONDITION_TO_APP = {
    tachycardia: 'heart',
    bradycardia: 'heart',
    hypoxemia: 'heart',
    hyperglycemia: 'diseases',
    hypoglycemia: 'diseases',
    fever: 'diseases',
    hypothermia: 'diseases',
    hypertension: 'heart',
    hypotension: 'heart',
    tachypnea: 'diseases'
};

function renderActiveConditions(conditions, overallStatus) {
    const live = new Set();

    // Eğer overall_status NORMAL haricindeyse ve aktif koşullar varsa çoklu bildirim tetikle[cite: 1]
    if (overallStatus && overallStatus !== 'NORMAL' && conditions && conditions.length > 0) {
        conditions.forEach(c => {
            const level = STATUS_TO_LEVEL[c.status] || 'mid';
            const id = `cond-${c.id}`;
            live.add(id);
            notify({
                id,
                level,
                text: `${c.title} [${c.status}]${c.observed_value != null ? `: ${c.observed_value} ${c.unit ?? ''}`.trim() : ''}`,
                onClick: () => openApp(CONDITION_TO_APP[c.id] ?? 'diseases')
            });
        });
    }

    // Aktif olmayan eski bildirimleri temizle
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