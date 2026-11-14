// =====================================================
// 1. DOM REFERANSLARI VE DURUM
// =====================================================
const hexagonBtn = document.getElementById('hexagon-btn');
const cancelMenuBtn = document.getElementById('cancel-menu-btn');
const menu = document.getElementById('menu');
const ringGroups = document.querySelectorAll('.ring-group');
const arcs = document.querySelectorAll('.arc-ring');
const panelTitle = document.getElementById('panel-title');
const panelDesc = document.getElementById('panel-desc');
const leftSection = document.getElementById('left-section');
const notifStack = document.getElementById('notif-stack');

let isDetailView = false;
let hexagonClickInDetail = 0;
let lastData = null;               // API'den gelen son dashboard verisi

// =====================================================
// 2. UYGULAMA İÇERİKLERİ (sol ve sağ panel)
// =====================================================
const appConfigs = {
    'heart': {
        title: "Kalp Sağlığı İzleme",
        right: "Kalp Modülü: Anlık EKG ritimleri normal sınırlarda seyrediyor. Ventriküler kasılma düzenli, aritmi riski saptanmadı.",
        left: `<div class="app-content-box"><h2>Kalp Metrikleri</h2><div class="data-card"><span>Anlık Nabız</span><strong id="heart-rate-now">--</strong></div><div class="data-card"><span>EKG Durumu</span><strong>Normal Sinüs</strong></div><div class="data-card"><span>Aritmi Riski</span><strong>%0 (Düşük)</strong></div></div>`
    },
    'bone': {
        title: "Kemik Yoğunluğu Analizi",
        right: "Kemik Yoğunluğu: Yerçekimsiz ortam nedeniyle aylık %1.2 kalsiyum kaybı gözlemleniyor. Direnç egzersizlerinin artırılması önerilir.",
        left: `<div class="app-content-box"><h2>Kemik Durumu</h2><div class="data-card"><span>Kalsiyum Seviyesi</span><strong>9.2 mg/dL</strong></div><div class="data-card"><span>Yoğunluk Kaybı</span><strong>-%1.2 / Ay</strong></div><div class="data-card"><span>Direnç Skoru</span><strong>78 / 100</strong></div></div>`
    },
    'sleep': {
        title: "Uyku Düzeni İzleme",
        right: "Uyku Analizi: Son 24 saatte toplam 6.5 saat uyku alındı. REM evresi normal değerlerin altında, hafif yorgunluk sinyali veriyor.",
        left: `<div class="app-content-box"><h2>Uyku Verileri</h2><div class="data-card"><span>Son Uyku Süresi</span><strong>6.5 Saat</strong></div><div class="data-card"><span>REM Evresi</span><strong>%18 (Düşük)</strong></div><div class="data-card"><span>Uyku Kalitesi</span><strong>Orta</strong></div></div>`
    },
    'cancer': {
        title: "Kanser & Radyasyon Riski",
        right: "Kanser Riski & Radyasyon: Kümülatif kozmik radyasyon dozu 145 mSv seviyesinde. Koruyucu kalkan katmanı optimize edildi.",
        left: `<div class="app-content-box"><h2>Kozmik Risk</h2><div class="data-card"><span>Toplam Doz</span><strong>145 mSv</strong></div><div class="data-card"><span>Kalkan Durumu</span><strong>Aktif (%99)</strong></div><div class="data-card"><span>Hücresel Risk</span><strong>Güvenli Aralık</strong></div></div>`
    },
    'stabilite': {
        title: "Psikolojik Sağlamlık",
        right: "Psikolojik Sağlamlık: Stres endeksi dengeli. Ekip içi uyum skoru 88/100 olarak ölçüldü.",
        left: `<div class="app-content-box"><h2>Psikoloji</h2><div class="data-card"><span>Stres Endeksi</span><strong>1.4 / 5</strong></div><div class="data-card"><span>Moral Skoru</span><strong>88 / 100</strong></div><div class="data-card"><span>Motivasyon</span><strong>Yüksek</strong></div></div>`
    },
    'actions': {
        title: "Davranışsal Tepki Analizi",
        right: "Davranışsal Tepki: Refleks testleri ve karar verme süresi (210ms) optimal seviyede.",
        left: `<div class="app-content-box"><h2>Davranış & Refleks</h2><div class="data-card"><span>Tepki Süresi</span><strong>210 ms</strong></div><div class="data-card"><span>Karar Doğruluğu</span><strong>%96</strong></div><div class="data-card"><span>Bilişsel Yük</span><strong>Normal</strong></div></div>`
    },
    'tiredness': {
        title: "Yorgunluk Takibi",
        right: "Yorgunluk Durumu: Mental yorgunluk düşük düzeyde, fiziksel kas yorgunluğu 3/10 oranında raporlandı.",
        left: `<div class="app-content-box"><h2>Yorgunluk Seviyesi</h2><div class="data-card"><span>Mental Yorgunluk</span><strong>Düşük</strong></div><div class="data-card"><span>Fiziksel Yorgunluk</span><strong>3 / 10</strong></div><div class="data-card"><span>Dinlenme İhtiyacı</span><strong>Gerekli Değil</strong></div></div>`
    },
    'bacteria': {
        title: "Bakteriyel Flora",
        right: "Bakteriyel Flora: Cilt ve sindirim sistemi mikrobiyom çeşitliliği stabil, patojenik risk bulunmuyor.",
        left: `<div class="app-content-box"><h2>Mikrobiyom</h2><div class="data-card"><span>Çeşitlilik Skoru</span><strong>94 / 100</strong></div><div class="data-card"><span>Patojen Riski</span><strong>Sıfır</strong></div><div class="data-card"><span>Cilt Florası</span><strong>Stabil</strong></div></div>`
    },
    'immunity': {
        title: "Bağışıklık Sistemi",
        right: "Bağışıklık Sistemi: Lökosit ve antikor seviyeleri bağışıklık sisteminin normal çalıştığını gösteriyor.",
        left: `<div class="app-content-box"><h2>Bağışıklık Durumu</h2><div class="data-card"><span>Lökosit Sayısı</span><strong>6.8 k/uL</strong></div><div class="data-card"><span>Antikor Seviyesi</span><strong>Normal</strong></div><div class="data-card"><span>Enfeksiyon</span><strong>Yok</strong></div></div>`
    },
    'diseases': {
        title: "Diseases",
        right: "Hastalık Tarama: Aktif enfeksiyon bulgusu yok. Vücut sıcaklığı 36.6 °C stabil.",
        left: `<div class="app-content-box"><h2>Hastalık Taraması</h2><div class="data-card"><span>Vücut Sıcaklığı</span><strong>36.6 °C</strong></div><div class="data-card"><span>Solunum Yolu</span><strong>Temiz</strong></div><div class="data-card"><span>Genel Durum</span><strong>Sağlıklı</strong></div></div>`
    },
    'active-radiation': {
        title: "Radiation Risk",
        right: "Aktif Radyasyon Riski: Dış sensörlerden gelen anlık akı 0.45 mSv/h. Güvenli bölgedesiniz.",
        left: `<div class="app-content-box"><h2>Radyasyon Akışı</h2><div class="data-card"><span>Anlık Akı</span><strong>0.45 mSv/h</strong></div><div class="data-card"><span>İç Ortam</span><strong>Güvenli</strong></div><div class="data-card"><span>Alarm Durumu</span><strong>Pasif</strong></div></div>`
    },
    'activities': {
        title: "Activities",
        right: "Aktivite Programı: Bugün için planlanan 45 dakikalık koşu bandı ve direnç egzersizi başarıyla tamamlandı.",
        left: `<div class="app-content-box"><h2>Günlük Aktivite</h2><div class="data-card"><span>Koşu Bandı</span><strong>45 Dk (Tamamlandı)</strong></div><div class="data-card"><span>Direnç Egzersizi</span><strong>30 Dk (Tamamlandı)</strong></div><div class="data-card"><span>Harcanan Kalori</span><strong>520 kcal</strong></div></div>`
    },
    'sport-rate': {
        title: "Sports and Condition",
        right: "Spor Oranı: Haftalık egzersiz hedefi tamamlama oranı %95. Kondisyon kaybı önlendi.",
        left: `<div class="app-content-box"><h2>Haftalık Spor Hedefi</h2><div class="data-card"><span>Tamamlama Oranı</span><strong>%95</strong></div><div class="data-card"><span>Kondisyon Durumu</span><strong>Mükemmel</strong></div><div class="data-card"><span>Kas Kütlesi Korunumu</span><strong>%99</strong></div></div>`
    },
    'standart-input': {
        title: "Daily Data In",
        right: "Gündelik Veri Girdisi: Klavyeden uyku süresi, yorgunluk ve stres seviyenizi girerek günlük sağlık kaydınızı güncelleyin.",
        left: `<div class="app-content-box"><h2>Günlük Veri Girişi</h2><form class="app-form" onsubmit="event.preventDefault(); alert('Veriler SQLite veritabanına kaydedildi!');"><div class="form-group"><label>Uyku Süresi (Saat):</label><input type="number" value="7" min="0" max="24" step="0.5"></div><div class="form-group"><label>Yorgunluk (1-10):</label><input type="number" min="1" max="10" value="3"></div><div class="form-group"><label>Stres Seviyesi:</label><select><option>Düşük</option><option selected>Normal</option><option>Yüksek</option></select></div><button type="submit" class="submit-btn">Verileri Kaydet</button></form></div>`
    },
    'teammates': {
        title: "Teammates",
        right: "Takım Arkadaşları: Tüm ekip üyelerinin hayati bulguları ve sağlık durumları anlık olarak stabil.",
        left: `<div class="app-content-box"><h2>Ekip Durumu</h2><div class="data-card"><span>Komutan (A. Yılmaz)</span><strong>Stabil (74 BPM)</strong></div><div class="data-card"><span>Pilot (Z. Kaya)</span><strong>Stabil (68 BPM)</strong></div><div class="data-card"><span>Uzman (M. Demir)</span><strong>Stabil (70 BPM)</strong></div></div>`
    },
    'learn': {
        title: "Emergency Learning",
        right: "Acil Durum Eğitimi: Basınç düşüşü ve oksijen maskesi prosedürleri ile ilgili interaktif simülasyon modülü aktif.",
        left: `<div class="app-content-box"><h2>Eğitim Modülleri</h2><div class="data-card"><span>Basınç Düşüşü</span><strong>Tamamlandı</strong></div><div class="data-card"><span>Oksijen Maskesi</span><strong>Tamamlandı</strong></div><div class="data-card"><span>Yangın Prosedürü</span><strong>İnceleniyor</strong></div></div>`
    },
    'standart-procedure': {
        title: "Standard Procedures",
        right: "Standart Prosedürler: Günlük bakım ve sistem kontrol listesi eksiksiz tamamlandı.",
        left: `<div class="app-content-box"><h2>Kontrol Listesi</h2><div class="data-card"><span>Kabin Filtreleri</span><strong>Kontrol Edildi</strong></div><div class="data-card"><span>Su Geri Dönüşüm</span><strong>Normal (%98)</strong></div><div class="data-card"><span>İletişim Anteni</span><strong>Aktif</strong></div></div>`
    },
    'emergency': {
        title: "Emergency Procedures",
        right: "Acil Durum Prosedürleri: Tahliye rotaları ve kritik kriz senaryo planları güncel ve devrede.",
        left: `<div class="app-content-box"><h2>Kriz Planları</h2><div class="data-card"><span>Tahliye Rotası</span><strong>Açık</strong></div><div class="data-card"><span>Güvenli Sığınak</span><strong>Hazır</strong></div><div class="data-card"><span>Acil Ekipman</span><strong>Eksiksiz</strong></div></div>`
    },
    'settings': {
        title: "Settings",
        right: "Ayarlar: Ana ekranda görünecek aile fotoğrafını değiştirebilirsiniz. Fotoğraf yalnızca bu cihazda saklanır, sunucuya gönderilmez.",
        left: `<div class="app-content-box"><h2>Aile Fotoğrafı</h2><input type="file" id="photo-input" accept="image/*" hidden><button id="photo-folder" type="button" class="submit-btn">Klasör</button><button id="photo-pick" type="button" class="submit-btn">Fotoğraf seç</button><button id="photo-clear" type="button" class="submit-btn">Varsayılana dön</button></div>`    }
};

// =====================================================
// 3. RADYAL MENÜ YERLEŞİMİ
// =====================================================
function layoutMenu() {
    const W = innerWidth, H = innerHeight;
    const M = 16, HEX = 161;                       // kenar boşluğu, altıgen yasak bölgesi
    const all = [...document.querySelectorAll('.app-btn')];
    const maxW = Math.max(...all.map(b => b.offsetWidth));
    const maxH = Math.max(...all.map(b => b.offsetHeight));
    const gap = maxW + 24;                         // halkalar arası mesafe
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
            btn.style.top = `${R * Math.sin(a)}px`;
        });
        arcs[i].style.setProperty('--in', `${R - gap / 2}px`);
        arcs[i].style.setProperty('--out', `${R + gap / 2}px`);
    });
}
layoutMenu();
document.fonts.ready.then(layoutMenu);             // font yüklenince boyutlar değişir
addEventListener('resize', layoutMenu);

// =====================================================
// 4. FOTOĞRAF ÇERÇEVESİ
// =====================================================
const PHOTO_KEY = 'family-photo';                  // çok kullanıcılı olursa kullanıcı id'sini ekle
const DEFAULT_PHOTO = 'data:image/svg+xml;utf8,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400"><rect width="100%" height="100%" fill="#00273d"/>' +
    '<text x="50%" y="50%" fill="#9be758" font-family="sans-serif" font-size="26" text-anchor="middle">' +
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

// Ayarlar ekranı her açıldığında butonlar yeniden oluştuğu için burada bağlanır
let photoDir = null;   // seçilen proje klasörü

// Klasör tutamacını sayfa yenilense de hatırlamak için küçük IndexedDB yardımcısı
const idb = {
    open: () => new Promise((res, rej) => {
        const r = indexedDB.open('photo-store', 1);
        r.onupgradeneeded = () => r.result.createObjectStore('kv');
        r.onsuccess = () => res(r.result);
        r.onerror = () => rej(r.error);
    }),
    async get(k) {
        const db = await this.open();
        return new Promise((res, rej) => {
            const q = db.transaction('kv').objectStore('kv').get(k);
            q.onsuccess = () => res(q.result);
            q.onerror = () => rej(q.error);
        });
    },
    async set(k, v) {
        const db = await this.open();
        return new Promise((res, rej) => {
            const t = db.transaction('kv', 'readwrite');
            t.objectStore('kv').put(v, k);
            t.oncomplete = res;
            t.onerror = () => rej(t.error);
        });
    }
};

// 'unsupported' | 'none' | 'prompt' | 'granted'
async function photoDirState() {
    if (!window.showDirectoryPicker) return 'unsupported';
    photoDir ??= await idb.get('photo-dir').catch(() => null);
    if (!photoDir) return 'none';
    return photoDir.queryPermission({ mode: 'readwrite' });
}

async function bindPhotoControls() {
    const folderBtn = document.getElementById('photo-folder');
    const pick = document.getElementById('photo-pick');
    const input = document.getElementById('photo-input');
    const clear = document.getElementById('photo-clear');
    if (!folderBtn || !pick || !input) return;

    async function refresh() {
        const st = await photoDirState();
        folderBtn.textContent = {
            unsupported: 'Bu tarayıcı klasöre yazamaz (yerel yedek)',
            none: 'Proje klasörünü seç (bir kez)',
            prompt: 'Klasör iznini ver',
            granted: 'Klasör hazır ✓'
        }[st];
        folderBtn.disabled = st === 'unsupported' || st === 'granted';
        pick.disabled = !(st === 'granted' || st === 'unsupported');
    }

    folderBtn.onclick = async () => {
        try {
            if (!photoDir) {
                const dir = await showDirectoryPicker({ mode: 'readwrite' });
                await dir.getFileHandle('index.html');          // doğru klasör mü?
                photoDir = dir;
                await idb.set('photo-dir', dir);
            } else {
                await photoDir.requestPermission({ mode: 'readwrite' });
            }
        } catch (err) {
            folderBtn.textContent = err.name === 'NotFoundError'
                ? 'index.html yok: projenin ana klasörünü seç' : 'İptal edildi';
            return;
        }
        refresh();
    };

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
            c.toBlob(async (blob) => {
                try {
                    if (await photoDirState() === 'granted') {
                        const fh = await photoDir.getFileHandle(PHOTO_FILE, { create: true });
                        const w = await fh.createWritable();
                        await w.write(blob);
                        await w.close();                          // aynı isimle üzerine yazar
                        pick.textContent = 'Klasöre kaydedildi ✓';
                    } else {
                        localStorage.setItem(PHOTO_KEY, c.toDataURL('image/jpeg', 0.85));
                        pick.textContent = 'Sadece bu tarayıcıda kaydedildi';
                    }
                } catch { pick.textContent = 'Kaydedilemedi'; }
            }, 'image/jpeg', 0.85);
        };
        img.src = URL.createObjectURL(file);
    };

    if (clear) clear.onclick = async () => {
        try { localStorage.removeItem(PHOTO_KEY); } catch {}
        try { if (await photoDirState() === 'granted') await photoDir.removeEntry(PHOTO_FILE); } catch {}
        clear.textContent = 'Varsayılana dönüldü ✓';
    };

    refresh();
}

// =====================================================
// 5. EKRAN GEÇİŞLERİ
// =====================================================
function openApp(appId) {
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
    const PHOTO_FILE = 'family_photo.jpg';

    function loadPhoto() {
        const img = document.querySelector('.photo-frame img');
        if (!img) return;
        img.onerror = () => { img.onerror = null; img.src = currentPhoto(); };   // dosya yoksa yerel yedek/varsayılan
        img.src = `${PHOTO_FILE}?v=${Date.now()}`;                               // önbelleği atla
    }
}

const STATUS_TR = { NORMAL: 'NORMAL', CAUTION: 'DİKKAT', WARNING: 'UYARI', CRITICAL: 'KRİTİK' };

// Ana ekranda sağ panelde genel durum + aktif bulgular
function updateHomePanel() {
    if (isDetailView) return;
    if (!lastData) {
        panelTitle.textContent = 'Bağlanıyor…';
        panelDesc.textContent = 'Veri bekleniyor.';
        return;
    }
    panelTitle.textContent = `Genel Durum: ${STATUS_TR[lastData.overall_status] ?? '—'}`;
    const c = lastData.active_conditions ?? [];
    panelDesc.textContent = c.length ? c.map(x => x.title).join(' · ') : 'Aktif bulgu yok.';
}

// Sağ üst iptal butonu: menüyü kapat
cancelMenuBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    menu.setAttribute('inert', '');
    hexagonClickInDetail = 0;
});

// Sol üst altıgen: menüyü aç/kapat, detaydayken ikinci tıklamada ana ekrana dön
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

// Menü butonları (tek bir dinleyici)
document.querySelectorAll('.app-btn:not(.empty)').forEach(b =>
    b.addEventListener('click', () => openApp(b.id))
);

// =====================================================
// 6. BİLDİRİM SİSTEMİ
// =====================================================
const LEVELS = {
    low:  { rank: 1, icon: 'ℹ', label: 'BASİT UYARI',     sticky: false, color: '#e7e158' },
    mid:  { rank: 2, icon: '▲', label: 'RİSKLİ UYARI',    sticky: false, color: '#feb367' },
    high: { rank: 3, icon: '⚠', label: 'TEHLİKELİ UYARI', sticky: true,  color: '#ff5f66' }
};
const notifs = new Map();      // id -> { el, level, onClick }
const dismissed = new Map();   // id -> kapatılan seviyenin rank'ı

function notify({ id, level, text, onClick }) {
    const cfg = LEVELS[level];
    if (!cfg) return;
    if ((dismissed.get(id) ?? 0) >= cfg.rank) return;   // kapatıldı, şiddet artmadıkça tekrar gösterme
    let n = notifs.get(id);
    if (!n) {
        const el = document.createElement('button');
        el.type = 'button';
        el.className = 'notif';
        n = { el };
        el.addEventListener('click', () => {
            n.onClick?.();                                // özel işlem
            if (!LEVELS[n.level].sticky) {                // yüksek seviye kalır
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
    n.el.style.order = -cfg.rank;                         // yüksek öncelik üstte
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

function clearNotify(id) {          // sistem durumu normale döndü
    dismissed.delete(id);
    removeNotif(id);
}

function updateHexColor() {
    const top = [...notifs.values()].sort((a, b) => LEVELS[b.level].rank - LEVELS[a.level].rank)[0];
    if (top) document.documentElement.style.setProperty('--hex-color', LEVELS[top.level].color);
    else document.documentElement.style.removeProperty('--hex-color');
}

// =====================================================
// 7. API KATMANI (gerçek ve sahte veri)
// =====================================================
const API_BASE_URL = "http://127.0.0.1:8000";      // backend'de CORS açık olmalı
const POLL_INTERVAL_MS = 2000;                     // 2 saniyede bir sorgula
const USE_MOCK = true;                             // API hazır olunca false yap

const MOCK = {
    normal:   { hr: 72,  conds: [] },
    caution:  { hr: 105, conds: [{ id: 'tachycardia', status: 'CAUTION',  title: 'Elevated heart rate',  observed_value: 105, unit: 'bpm' }] },
    warning:  { hr: 125, conds: [{ id: 'tachycardia', status: 'WARNING',  title: 'Elevated heart rate',  observed_value: 125, unit: 'bpm' }] },
    critical: { hr: 96,  conds: [{ id: 'hypoxemia',   status: 'CRITICAL', title: 'Low blood oxygen',     observed_value: 68,  unit: '%' }] },
    multi:    { hr: 125, conds: [
        { id: 'tachycardia',   status: 'WARNING',  title: 'Elevated heart rate',    observed_value: 125, unit: 'bpm' },
        { id: 'hyperglycemia', status: 'CAUTION',  title: 'Elevated blood glucose', observed_value: 185, unit: 'mg/dL' },
        { id: 'hypoxemia',     status: 'CRITICAL', title: 'Low blood oxygen',       observed_value: 68,  unit: '%' }
    ] }
};
let scenario = 'normal';

function mockDashboard() {
    const { hr, conds } = MOCK[scenario];
    const order = { NORMAL: 0, CAUTION: 1, WARNING: 2, CRITICAL: 3 };
    const overall = conds.reduce((m, c) => order[c.status] > order[m] ? c.status : m, 'NORMAL');
    return {
        api_version: 'v1',
        generated_at: new Date().toISOString(),
        overall_status: overall,
        active_conditions: conds,
        physiological_data: { heart_rate: { value: hr, unit: 'bpm', quality: 'VALID' } },
        data_quality: { status: 'GOOD', warnings: [] }
    };
}

async function getJson(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`Sunucu hatası: ${r.status}`);
    return r.json();
}

async function fetchDashboardData() {
    try {
        const data = USE_MOCK ? mockDashboard() : await getJson(`${API_BASE_URL}/api/v1/dashboard`);
        updateUIWithTelemetry(data);
    } catch (error) {
        console.warn("Telemetri bağlantısı kurulamadı:", error.message);
        showConnectionErrorState();
    }
}

function updateUIWithTelemetry(data) {
    lastData = data;
    clearNotify('conn');
    document.body.setAttribute('data-system-status', data.overall_status);

    renderActiveConditions(data.active_conditions ?? []);

    // Veri kalitesi sağlık bulgularından ayrı gösterilir
    if (data.data_quality && data.data_quality.status !== 'GOOD') {
        notify({ id: 'dq', level: 'low', text: `Veri kalitesi uyarısı: ${(data.data_quality.warnings ?? []).join(', ') || data.data_quality.status}` });
    } else {
        clearNotify('dq');
    }

    updateLiveFields(data);
    updateHomePanel();
}

// Hem düz sayı hem {value, unit, quality} biçimini okur; eksik/geçersiz veri null döner
function readMeasurement(m, defaultUnit = '') {
    if (m == null) return null;
    if (typeof m === 'object') {
        if (m.value == null || (m.quality && m.quality !== 'VALID')) return null;
        return { value: m.value, unit: m.unit ?? defaultUnit };
    }
    return { value: m, unit: defaultUnit };
}

// Açık olan ekrandaki canlı alanları günceller (element yoksa sessizce geçer)
function updateLiveFields(data) {
    const hrEl = document.getElementById('heart-rate-now');
    if (hrEl) {
        const hr = readMeasurement(data.physiological_data?.heart_rate, 'bpm') ?? extractHeartRateFromConditions(data);
        hrEl.textContent = hr ? `${hr.value} ${hr.unit}`.trim() : '--';
    }
}

function extractHeartRateFromConditions(data) {
    const c = data?.active_conditions?.find(x => x.id === 'tachycardia' || x.related_measurements?.includes('heart_rate'));
    return c ? { value: c.observed_value, unit: c.unit ?? 'bpm' } : null;
}

function showConnectionErrorState() {
    notify({ id: 'conn', level: 'mid', text: 'Sunucu bağlantısı yok, veriler güncel değil' });
}

// =====================================================
// 8. BULGULAR → BİLDİRİMLER
// =====================================================
const STATUS_TO_LEVEL = { CAUTION: 'low', WARNING: 'mid', CRITICAL: 'high' };
const CONDITION_TO_APP = {
    tachycardia: 'heart',
    hypoxemia: 'heart',           // geçici eşleme
    hyperglycemia: 'diseases'     // geçici eşleme
};

function renderActiveConditions(conditions) {
    const live = new Set();
    conditions.forEach(c => {
        const level = STATUS_TO_LEVEL[c.status];
        if (!level) return;
        const id = `cond-${c.id}`;
        live.add(id);
        notify({
            id, level,
            text: `${c.title}${c.observed_value != null ? `: ${c.observed_value} ${c.unit ?? ''}` : ''}`,
            onClick: () => openApp(CONDITION_TO_APP[c.id])
        });
    });
    // Artık aktif olmayan bulguların bildirimlerini kaldır
    [...notifs.keys()].filter(k => k.startsWith('cond-') && !live.has(k)).forEach(clearNotify);
}

// =====================================================
// 9. DEMO PANELİ (sadece USE_MOCK açıkken) VE BAŞLATMA
// =====================================================
if (USE_MOCK) {
    const bar = document.createElement('div');
    bar.style.cssText = 'position:fixed;bottom:8px;right:8px;z-index:1200;display:flex;gap:6px;opacity:.85';
    Object.keys(MOCK).forEach(name => {
        const b = document.createElement('button');
        b.type = 'button';
        b.textContent = name;
        b.style.cssText = 'padding:6px 10px;border-radius:8px;border:0;font:600 13px sans-serif;cursor:pointer';
        b.onclick = () => { scenario = name; fetchDashboardData(); };
        bar.appendChild(b);
    });
    document.body.appendChild(bar);
}

resetToHome();                                   // kayıtlı fotoğrafı ve ana paneli yükle
fetchDashboardData();                            // ilk çağrı
setInterval(fetchDashboardData, POLL_INTERVAL_MS);