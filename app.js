// Leaflet (bản đồ) được nạp động (lazy-load) khi người dùng bấm tab "Bản đồ" lần đầu —
  // xem hàm loadMapLibraries() bên dưới. Người chỉ dùng Danh sách sẽ không tải phần này,
  // tiết kiệm ~150KB JS/CSS + tránh gọi mạng không cần thiết trên kết nối yếu.

  let ALL = [];

  // Cổng miễn trừ trách nhiệm: chỉ mở nội dung chính sau khi người dùng xác nhận.
  const DISCLAIMER_STORAGE_KEY = 'strokeLocatorDisclaimerAccepted:v1';
  const disclaimerGate = document.getElementById('disclaimerGate');
  const acceptDisclaimer = document.getElementById('acceptDisclaimer');
  const appHeader = document.getElementById('appHeader');
  const mainContent = document.getElementById('mainContent');
  const emergencySos = document.getElementById('emergencySos');
  const disclaimerTitle = document.getElementById('disclaimerTitle');
  const disclaimerContentVi = document.getElementById('disclaimerContentVi');
  const disclaimerContentEn = document.getElementById('disclaimerContentEn');
  const disclaimerLanguageButtons = [...document.querySelectorAll('[data-disclaimer-language]')];
  const disclaimerLanguageKey = 'strokeLocatorDisclaimerLanguage:v1';

  function setDisclaimerLanguage(language) {
    const isEnglish = language === 'en';
    disclaimerContentVi.hidden = isEnglish;
    disclaimerContentEn.hidden = !isEnglish;
    disclaimerTitle.textContent = isEnglish
      ? 'DISCLAIMER & PRIVACY NOTICE'
      : 'TUYÊN BỐ MIỄN TRỪ TRÁCH NHIỆM & QUYỀN RIÊNG TƯ';
    acceptDisclaimer.textContent = isEnglish ? 'I have read and agree' : 'Tôi đã hiểu và đồng ý';
    disclaimerLanguageButtons.forEach(button => {
      const active = button.dataset.disclaimerLanguage === language;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    try { localStorage.setItem(disclaimerLanguageKey, language); } catch (err) { /* private mode */ }
  }

  function openMainContent() {
    disclaimerGate.hidden = true;
    appHeader.hidden = false;
    mainContent.hidden = false;
    emergencySos.hidden = false;
    document.body.classList.remove('disclaimer-open');
    try { localStorage.setItem(DISCLAIMER_STORAGE_KEY, '1'); } catch (err) { /* private mode */ }
  }

  document.body.classList.add('disclaimer-open');
  let disclaimerAccepted = false;
  try { disclaimerAccepted = localStorage.getItem(DISCLAIMER_STORAGE_KEY) === '1'; } catch (err) { /* private mode */ }
  if (disclaimerAccepted) openMainContent();
  acceptDisclaimer.addEventListener('click', openMainContent);
  disclaimerLanguageButtons.forEach(button => {
    button.addEventListener('click', () => setDisclaimerLanguage(button.dataset.disclaimerLanguage));
  });
  let preferredDisclaimerLanguage = 'vi';
  try {
    preferredDisclaimerLanguage = localStorage.getItem(disclaimerLanguageKey) === 'en' ? 'en' : 'vi';
  } catch (err) { /* private mode */ }
  setDisclaimerLanguage(preferredDisclaimerLanguage);

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function parsePhoneNumbers(hotline) {
    // Chỉ dùng "/" để tách các số độc lập. Phần nhánh trong ngoặc là
    // hướng dẫn hiển thị, không được đưa vào liên kết tel:.
    return String(hotline || '')
      .split(/\s*\/\s*/)
      .map(label => label.trim())
      .filter(Boolean)
      .map(label => {
        const extension = label.match(/\(\s*(?:nhấn|nhánh|nhan|ext|extension)\s*[:.]?\s*(\d+)\s*\)/i);
        const numberLabel = extension
          ? label.replace(extension[0], '').trim()
          : label;
        return {
          label,
          number: numberLabel.replace(/[^\d]/g, ''),
          extension: extension ? extension[1] : '',
        };
      })
      .filter(phone => phone.number);
  }

  function telHrefFromPhone(phone) {
    return phone && phone.number ? `tel:${phone.number}` : '#';
  }

  function mapsDirectionUrl(address, name, lat, lng) {
    const hasCoordinates = Number.isFinite(Number(lat)) && Number.isFinite(Number(lng));
    // Use the same coordinates used for the distance calculation. This avoids
    // Google Maps geocoding a hospital name/address to a different location.
    const destination = hasCoordinates ? `${Number(lat)},${Number(lng)}` : `${name}, ${address}`;
    const query = encodeURIComponent(destination);
    return `https://www.google.com/maps/dir/?api=1&destination=${query}&travelmode=driving`;
  }

  function badge(label, value) {
    const isYes = value === 'Có';
    return `<span class="badge ${isYes ? 'yes' : 'no'}">${escapeHtml(label)}: ${escapeHtml(value)}</span>`;
  }

  // ====== TÌM GẦN TÔI NHẤT (định vị + sắp xếp theo khoảng cách) ======
  let userLocation = null; // { lat, lng }

  function haversineKm(lat1, lng1, lat2, lng2) {
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat/2) ** 2 +
      Math.cos(lat1 * Math.PI/180) * Math.cos(lat2 * Math.PI/180) *
      Math.sin(dLng/2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  }

  function setNearestStatus(msg, isError) {
    const el = document.getElementById('nearestStatus');
    el.textContent = msg;
    el.classList.toggle('err', !!isError);
  }

  // Nhận diện nền tảng để đưa đúng hướng dẫn khôi phục quyền định vị —
  // iOS Safari và Android Chrome có đường dẫn cài đặt khác nhau hoàn toàn.
  function detectPlatform() {
    const ua = navigator.userAgent || '';
    const isIOS = /iPad|iPhone|iPod/.test(ua) ||
      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1); // iPadOS giả làm Mac
    if (isIOS) return 'ios';
    if (/Android/.test(ua)) return 'android';
    return 'other';
  }

  function renderPermissionHelp() {
    const platform = detectPlatform();
    const helpEl = document.getElementById('nearestHelp');

    const stepsByPlatform = {
      ios: [
        'Trong Safari, chạm chữ <b>"AA"</b> ở đầu thanh địa chỉ (bên trái, cùng hàng với URL trang này)',
        'Chọn <b>Cài đặt cho Trang Web</b> (Website Settings)',
        'Tìm mục <b>Vị trí</b> (Location) → chọn <b>Cho phép</b> (Allow)',
        'Quay lại trang, bấm <b>Thử lại</b> bên dưới',
      ],
      android: [
        'Chạm vào biểu tượng <b>ổ khóa 🔒</b> hoặc chữ <b>ⓘ</b> bên trái thanh địa chỉ trình duyệt',
        'Chọn <b>Quyền của trang web</b> (Site settings) → <b>Vị trí</b>',
        'Chọn <b>Cho phép</b> (Allow)',
        'Quay lại trang này, bấm <b>Thử lại</b> bên dưới',
      ],
      other: [
        'Mở phần cài đặt của trình duyệt cho trang web này',
        'Tìm mục quyền <b>Vị trí / Location</b> và chọn Cho phép',
        'Bấm <b>Thử lại</b> bên dưới',
      ],
    };
    const steps = stepsByPlatform[platform];

    // iOS có thêm lớp cài đặt hệ thống độc lập với cài đặt riêng-từng-trang ở trên —
    // nếu bước chính không có tác dụng, đây thường là nguyên nhân thật sự.
    const iosExtra = platform === 'ios' ? `
      <p class="help-subtitle">Nếu vẫn không được, kiểm tra thêm 2 nơi này:</p>
      <ol start="1">
        <li><b>Cài đặt</b> → <b>Quyền riêng tư &amp; Bảo mật</b> → <b>Dịch vụ định vị</b>: đảm bảo bật ở đầu trang, rồi cuộn xuống mục <b>Safari Websites</b> → chọn <b>Hỏi lần tới hoặc khi chia sẻ</b> (không để "Không bao giờ")</li>
        <li>Kiểm tra Safari không đang mở ở chế độ <b>Duyệt web Riêng tư</b> (Private Browsing) — chế độ này luôn chặn định vị</li>
      </ol>
    ` : '';

    helpEl.innerHTML = `
      <p>Cách cấp lại quyền vị trí:</p>
      <ol>${steps.map(s => `<li>${s}</li>`).join('')}</ol>
      ${iosExtra}
      <div class="help-actions">
        <button class="btn-retry" id="btnRetryLocation" type="button">🔄 Thử lại</button>
        <button class="btn-manual" id="btnManualProvince" type="button">📍 Chọn tỉnh thủ công thay thế</button>
      </div>
    `;
    helpEl.hidden = false;

    document.getElementById('btnRetryLocation').addEventListener('click', findNearest);
    document.getElementById('btnManualProvince').addEventListener('click', () => {
      document.getElementById('filterProv').focus();
      document.getElementById('filterProv').scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  }

  function hidePermissionHelp() {
    document.getElementById('nearestHelp').hidden = true;
  }

  function findNearest() {
    hidePermissionHelp();

    if (!('geolocation' in navigator)) {
      setNearestStatus('Trình duyệt không hỗ trợ định vị. Vui lòng chọn tỉnh thủ công bên dưới.', true);
      return;
    }
    setNearestStatus('Đang xác định vị trí của bạn…');
    navigator.geolocation.getCurrentPosition(
      pos => {
        userLocation = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        setNearestStatus('Đã xác định vị trí — đang sắp xếp theo khoảng cách đường thẳng gần nhất.');
        document.getElementById('filterProv').value = '';
        document.getElementById('searchBox').value = '';
        applyFilter();
      },
      err => {
        if (err.code === 1) {
          setNearestStatus('Bạn đã từ chối quyền truy cập vị trí trước đó.', true);
          renderPermissionHelp();
          return;
        }
        const msgs = {
          2: 'Không xác định được vị trí hiện tại (GPS yếu hoặc bị chặn). Vui lòng thử lại hoặc chọn tỉnh thủ công.',
          3: 'Định vị quá thời gian chờ. Vui lòng thử lại.',
        };
        setNearestStatus(msgs[err.code] || 'Có lỗi khi định vị. Vui lòng thử lại hoặc chọn tỉnh thủ công.', true);
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }


  function renderList(items) {
    const list = document.getElementById('list');
    document.getElementById('countNum').textContent = items.length;
    const distanceNote = document.getElementById('distanceNote');
    if (distanceNote) distanceNote.hidden = !userLocation;

    if (items.length === 0) {
      list.innerHTML = '<div class="empty-state">Không tìm thấy cơ sở phù hợp.</div>';
      return;
    }

    // Nếu đã có vị trí người dùng: tính khoảng cách, sắp xếp gần -> xa
    // Cơ sở chưa có toạ độ xếp cuối, giữ nguyên thứ tự.
    let sorted = items;
    if (userLocation) {
      sorted = items.map(h => ({
        ...h,
        _distanceKm: (h.lat && h.lng)
          ? haversineKm(userLocation.lat, userLocation.lng, h.lat, h.lng)
          : null,
      })).sort((a, b) => {
        if (a._distanceKm === null && b._distanceKm === null) return 0;
        if (a._distanceKm === null) return 1;
        if (b._distanceKm === null) return -1;
        return a._distanceKm - b._distanceKm;
      });
    }

    list.innerHTML = sorted.map(h => {
      const phones = parsePhoneNumbers(h.hotline);
      const phoneButtons = phones.map(p =>
        `<a class="call-link" href="${telHrefFromPhone(p)}">📞 ${escapeHtml(p.label)}</a>`
      ).join('');
      const distanceHtml = (h._distanceKm != null)
        ? `<span class="distance-badge" title="Khoảng cách đường thẳng từ vị trí của bạn" aria-label="Khoảng cách đường thẳng ${h._distanceKm < 1 ? Math.round(h._distanceKm*1000)+' mét' : h._distanceKm.toFixed(1)+' kilômét'}">${h._distanceKm < 1 ? Math.round(h._distanceKm*1000)+' m' : h._distanceKm.toFixed(1)+' km'} đường thẳng</span>`
        : '';

      return `
      <article class="card" itemscope itemtype="https://schema.org/Hospital">
        <div class="card-top">
          <h2 itemprop="name">${escapeHtml(h.name)}</h2>
          <div class="card-top-right">
            <span class="tag-prov">${escapeHtml(h.province)}</span>
            ${distanceHtml}
          </div>
        </div>
        <p class="type-label">${escapeHtml(h.type || '')}</p>
        <p class="addr" itemprop="address">${escapeHtml(h.address)}</p>
        <div class="badges">
          ${badge('Tiêu sợi huyết', h.thrombolysis)}
          ${badge('Can thiệp', h.intervention)}
        </div>
        <div class="card-actions-row">
        <div class="phone-group" itemprop="telephone">${phoneButtons}</div>
          <a class="map-link" href="${mapsDirectionUrl(h.address, h.name, h.lat, h.lng)}" target="_blank" rel="noopener noreferrer">🧭 Chỉ đường</a>
        </div>
      </article>
    `;
    }).join('');
  }

  // ====== TẢI THƯ VIỆN BẢN ĐỒ THEO NHU CẦU (LAZY LOAD) ======
  // Chỉ tải Leaflet (~150KB CSS+JS) khi người dùng thực sự bấm tab "Bản đồ" lần đầu.
  // Người chỉ dùng chế độ Danh sách (trường hợp khẩn cấp phổ biến nhất) không tốn
  // băng thông/CPU cho phần này — quan trọng với mạng yếu hoặc máy cấu hình thấp.
  //
  // BẢO MẬT: mỗi resource kèm integrity (SRI) — hash tự tính từ đúng gói npm
  // leaflet@1.9.4 / leaflet.markercluster@1.5.3 (đã đối chiếu khớp hash chính thức
  // công bố tại leafletjs.com/download.html). Nếu cdnjs bị giả mạo/tấn công chuỗi
  // cung ứng, trình duyệt sẽ TỰ CHẶN không chạy file bị thay đổi.
  let mapLibsPromise = null;

  function loadMapLibraries() {
    if (mapLibsPromise) return mapLibsPromise;

    mapLibsPromise = new Promise((resolve, reject) => {
      const cssFiles = [
        { href: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css',
          integrity: 'sha384-sHL9NAb7lN7rfvG5lfHpm643Xkcjzp4jFvuavGOndn6pjVqS6ny56CAt3nsEVT4H' },
        { href: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.css',
          integrity: 'sha384-pmjIAcz2bAn0xukfxADbZIb3t8oRT9Sv0rvO+BR5Csr6Dhqq+nZs59P0pPKQJkEV' },
        { href: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.Default.css',
          integrity: 'sha384-wgw+aLYNQ7dlhK47ZPK7FRACiq7ROZwgFNg0m04avm4CaXS+Z9Y7nMu8yNjBKYC+' },
      ];
      cssFiles.forEach(({ href, integrity }) => {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = href;
        link.integrity = integrity;
        link.crossOrigin = 'anonymous';
        document.head.appendChild(link);
      });

      const loadScript = (src, integrity) => new Promise((res, rej) => {
        const s = document.createElement('script');
        s.src = src;
        s.integrity = integrity;
        s.crossOrigin = 'anonymous';
        s.onload = res;
        s.onerror = () => rej(new Error(`Không tải được ${src} (có thể bị chặn do sai integrity hash — dấu hiệu file đã bị thay đổi)`));
        document.body.appendChild(s);
      });

      loadScript(
        'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js',
        'sha384-cxOPjt7s7Iz04uaHJceBmS+qpjv2JkIHNVcuOrM+YHwZOmJGBXI00mdUXEq65HTH'
      )
        .then(() => loadScript(
          'https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/leaflet.markercluster.js',
          'sha384-eXVCORTRlv4FUUgS/xmOyr66XBVraen8ATNLMESp92FKXLAMiKkerixTiBvXriZr'
        ))
        .then(resolve)
        .catch(reject);
    });

    return mapLibsPromise;
  }

  let map, markerCluster;
  const markerCache = new Map();
  let renderedMapKey = '';

  function setMapStatus(message, isError = false) {
    const statusEl = document.getElementById('mapStatus');
    statusEl.textContent = message;
    statusEl.classList.toggle('err', isError);
    statusEl.hidden = !message;
  }

  function initMapIfNeeded() {
    if (map) return;
    map = L.map('mapEl').setView([16.0, 106.0], 5.4); // trung tâm Việt Nam
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map);
    markerCluster = L.markerClusterGroup();
    map.addLayer(markerCluster);
  }

  function createMapMarker(h) {
    const marker = L.marker([h.lat, h.lng]);
    marker.on('click', () => {
      if (!marker.getPopup()) {
        const firstPhone = parsePhoneNumbers(h.hotline)[0];
        const popupHtml = `
          <div class="map-popup">
            <h3>${escapeHtml(h.name)}</h3>
            <p class="popup-addr">${escapeHtml(h.address)}</p>
            <div class="popup-actions">
              <a class="pop-call" href="${telHrefFromPhone(firstPhone)}">📞 Gọi</a>
              <a class="pop-dir" href="${mapsDirectionUrl(h.address, h.name, h.lat, h.lng)}" target="_blank" rel="noopener noreferrer">🧭 Chỉ đường</a>
            </div>
          </div>`;
        marker.bindPopup(popupHtml);
      }
      marker.openPopup();
    });
    return marker;
  }

  function renderMap(items) {
    initMapIfNeeded();
    const withCoords = items.filter(h => h.lat && h.lng);
    const visibleIds = new Set(withCoords.map(h => h.id));
    const mapKey = [...visibleIds].sort().join('|');

    if (mapKey !== renderedMapKey) {
      markerCache.forEach((marker, id) => {
        if (!visibleIds.has(id)) markerCluster.removeLayer(marker);
      });

      withCoords.forEach(h => {
        let marker = markerCache.get(h.id);
        if (!marker) {
          marker = createMapMarker(h);
          markerCache.set(h.id, marker);
        }
        if (!markerCluster.hasLayer(marker)) markerCluster.addLayer(marker);
      });

      renderedMapKey = mapKey;
    }

    setTimeout(() => map.invalidateSize(), 50);
  }

  function switchView(view) {
    const listEl = document.getElementById('list');
    const mapEl = document.getElementById('mapView');
    const signsEl = document.getElementById('signsView');
    const countRow = document.getElementById('listCountRow');
    const controlsEl = document.querySelector('.controls');
    const nearestBarEl = document.querySelector('.nearest-bar');
    const btnList = document.getElementById('btnListView');
    const btnMap = document.getElementById('btnMapView');
    const btnSigns = document.getElementById('btnSignsView');

    // Ẩn hết, rồi bật đúng 1 khối theo view đang chọn
    listEl.style.display = 'none';
    mapEl.style.display = 'none';
    signsEl.hidden = true;
    countRow.style.display = 'none';
    controlsEl.style.display = 'none';
    nearestBarEl.style.display = 'none';
    [btnList, btnMap, btnSigns].forEach(b => b.classList.remove('active'));

    if (view === 'map') {
      mapEl.style.display = 'block';
      controlsEl.style.display = 'flex';
      nearestBarEl.style.display = 'block';
      btnMap.classList.add('active');

      if (!window.L) {
        setMapStatus('Đang tải thư viện bản đồ từ CDN…');
        loadMapLibraries()
          .then(() => {
            setMapStatus('');
            renderMap(getCurrentFiltered());
          })
          .catch(() => {
            setMapStatus('Không tải được thư viện bản đồ. Vui lòng kiểm tra kết nối mạng hoặc dùng tab Danh sách.', true);
          });
      } else {
        setMapStatus('');
        renderMap(getCurrentFiltered());
      }
    } else if (view === 'signs') {
      signsEl.hidden = false;
      btnSigns.classList.add('active');
    } else {
      listEl.style.display = 'flex';
      countRow.style.display = 'block';
      controlsEl.style.display = 'flex';
      nearestBarEl.style.display = 'block';
      btnList.classList.add('active');
    }
  }

  let currentView = 'list';

  // Bỏ dấu tiếng Việt để so khớp tìm kiếm — người dùng trong tình huống gấp thường
  // gõ không dấu (bàn phím tiếng Anh, gõ vội). "bach mai" vẫn phải khớp "Bạch Mai".
  function stripDiacritics(str) {
    return str
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/đ/g, 'd')
      .replace(/Đ/g, 'D')
      .toLowerCase();
  }

  // Từ viết tắt / từ đồng nghĩa thường gặp khi người dân tìm bệnh viện.
  // Mỗi cặp: [dạng đầy đủ (đã bỏ dấu), các cách viết tắt/gọi khác].
  // Nếu tên/loại hình/địa chỉ chứa dạng đầy đủ, chỉ mục tìm kiếm sẽ được
  // cộng thêm các dạng viết tắt tương ứng để gõ tắt vẫn tìm ra.
  const SEARCH_SYNONYMS = [
    ['benh vien', ['bv']],
    ['da khoa', ['dk', 'đk']],
    ['trung tam', ['tt']],
    ['don vi', ['dv']],
    ['thanh pho', ['tp']],
    ['ho chi minh', ['hcm', 'tphcm', 'tp hcm', 'sai gon', 'saigon']],
    ['ha noi', ['hn']],
    ['dot quy', ['dq', 'stroke']],
    ['cap cuu', ['cc']],
    ['tim mach', ['timmach']],
  ];

  // Xây "chỉ mục tìm kiếm" cho 1 bệnh viện: gộp tên + loại hình + tỉnh + địa chỉ
  // (đã bỏ dấu) và cộng thêm các từ đồng nghĩa/viết tắt liên quan.
  // Tính 1 lần khi tải dữ liệu — KHÔNG tính lại mỗi lần gõ phím (tối ưu hiệu năng).
  function buildSearchIndex(h) {
    let text = stripDiacritics([h.name, h.type, h.province, h.address].filter(Boolean).join(' '));
    SEARCH_SYNONYMS.forEach(([full, aliases]) => {
      if (text.includes(full)) {
        text += ' ' + aliases.join(' ');
      } else {
        // chiều ngược lại: nếu văn bản chứa 1 alias, cũng cộng thêm dạng đầy đủ
        aliases.forEach(alias => {
          if (text.includes(alias)) text += ' ' + full;
        });
      }
    });
    return text;
  }

  // So khớp theo TỪNG TỪ (token-based AND): mọi từ trong câu tìm phải xuất hiện
  // đâu đó trong chỉ mục — cho phép gõ đúng 1 phần tên, không cần đúng thứ tự.
  // VD: gõ "tam tri" vẫn khớp "Bệnh viện Đa khoa Tâm Trí Đồng Tháp".
  function getCurrentFiltered() {
    const prov = document.getElementById('filterProv').value;
    const rawQ = stripDiacritics(document.getElementById('searchBox').value.trim());
    const tokens = rawQ.split(/\s+/).filter(Boolean);

    return ALL.filter(h => {
      const matchesProv = !prov || h.province === prov;
      const matchesQ = tokens.length === 0 ||
        tokens.every(tok => h._searchIndex.includes(tok));
      return matchesProv && matchesQ;
    });
  }

  function applyFilter() {
    const filtered = getCurrentFiltered();
    renderList(filtered);
    if (currentView === 'map') renderMap(filtered);
  }

  function populateProvinces(items) {
    const provinces = [...new Set(items.map(h => h.province))].sort((a, b) => a.localeCompare(b, 'vi'));
    const sel = document.getElementById('filterProv');
    provinces.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p;
      opt.textContent = p;
      sel.appendChild(opt);
    });
  }

  function formatUpdatedAt(updatedAt) {
    if (!updatedAt) return '—';
    const match = String(updatedAt).match(/^(\d{4})-(\d{2})$/);
    return match ? `${match[2]}/${match[1]}` : String(updatedAt);
  }

  function formatPublishedAt(publishedAt) {
    if (!publishedAt) return '—';
    const date = new Date(publishedAt);
    if (Number.isNaN(date.getTime())) return '—';
    const parts = new Intl.DateTimeFormat('vi-VN', {
      timeZone: 'Asia/Ho_Chi_Minh',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }).formatToParts(date).reduce((result, part) => {
      result[part.type] = part.value;
      return result;
    }, {});
    return `${parts.hour}:${parts.minute}:${parts.second} ${parts.day}/${parts.month}/${parts.year}`;
  }

  // Cung cấp dữ liệu có cấu trúc sau khi JSON được tải. Nội dung này giúp
  // Search Engine/AI hiểu trực tiếp tên, địa chỉ, hotline và tọa độ từng cơ sở.
  // Dữ liệu được tạo từ cùng nguồn đang hiển thị để tránh lệch thông tin.
  function updateStructuredData(dateModified) {
    const existing = document.getElementById('hospitalStructuredData');
    if (existing) existing.remove();

    const items = ALL.map((h, index) => {
      const item = {
        '@type': 'ListItem',
        position: index + 1,
        item: {
          '@type': 'Hospital',
          name: h.name,
          telephone: h.hotline || undefined,
          address: {
            '@type': 'PostalAddress',
            streetAddress: h.address,
            addressLocality: h.province,
            addressCountry: 'VN',
          },
        },
      };
      if (Number.isFinite(Number(h.lat)) && Number.isFinite(Number(h.lng))) {
        item.item.geo = {
          '@type': 'GeoCoordinates',
          latitude: Number(h.lat),
          longitude: Number(h.lng),
        };
      }
      return item;
    });

    const script = document.createElement('script');
    script.id = 'hospitalStructuredData';
    script.type = 'application/ld+json';
    script.textContent = JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'MedicalWebPage',
      name: 'Danh sách bệnh viện điều trị đột quỵ tại Việt Nam',
      inLanguage: 'vi-VN',
      dateModified,
      mainEntity: {
        '@type': 'ItemList',
        numberOfItems: items.length,
        itemListElement: items,
      },
    });
    document.head.appendChild(script);
  }

  // Revalidate the data file so the timestamp on the Dấu hiệu tab can confirm
  // that a newly released Google Sheet version has reached the page.
  fetch('./data/hospitals.json', { cache: 'no-cache' })
    .then(res => {
      if (!res.ok) throw new Error('Không tải được dữ liệu');
      return res.json();
    })
    .then(data => {
      ALL = data.filter(h => h.status === 'active');
      document.getElementById('list').setAttribute('aria-busy', 'false');
      ALL.forEach(h => { h._searchIndex = buildSearchIndex(h); });
      document.getElementById('metaCount').innerHTML = `<b>${ALL.length}</b> đơn vị`;
      document.getElementById('metaProv').innerHTML = `<b>${new Set(ALL.map(h=>h.province)).size}</b> tỉnh/thành`;
      const withCoordinates = ALL.filter(h =>
        Number.isFinite(Number(h.lat)) && Number.isFinite(Number(h.lng))
      );
      document.getElementById('mapCoordinateCount').textContent = withCoordinates.length;
      document.getElementById('mapTotalCount').textContent = ALL.length;
      const updatedAt = ALL.map(h => h.updatedAt).filter(Boolean).sort().pop();
      const publishedAt = ALL.map(h => h.publishedAt).filter(Boolean).sort().pop();
      document.getElementById('metaUpdated').textContent = formatUpdatedAt(updatedAt);
      document.getElementById('signsUpdatedAt').textContent =
        `* Website cập nhật lúc: ${formatPublishedAt(publishedAt)}`;
      updateStructuredData(publishedAt || updatedAt);
      populateProvinces(ALL);
      renderList(ALL);
    })
    .catch(err => {
      document.getElementById('list').innerHTML =
        `<div class="empty-state">Lỗi tải dữ liệu: ${escapeHtml(err.message)}</div>`;
    });

  document.getElementById('filterProv').addEventListener('change', applyFilter);

  // Debounce ô tìm kiếm: gộp các lần gõ liên tiếp trong 150ms thành 1 lần render,
  // giảm tải CPU khi gõ nhanh trên điện thoại cấu hình thấp.
  let searchDebounceTimer = null;
  document.getElementById('searchBox').addEventListener('input', () => {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(applyFilter, 150);
  });
  document.getElementById('btnListView').addEventListener('click', () => { currentView = 'list'; switchView('list'); });
  document.getElementById('btnMapView').addEventListener('click', () => { currentView = 'map'; switchView('map'); });
  document.getElementById('btnSignsView').addEventListener('click', () => { currentView = 'signs'; switchView('signs'); });
  document.getElementById('btnUrgentSigns').addEventListener('click', () => {
    currentView = 'signs';
    switchView('signs');
    document.getElementById('signsView').scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  document.getElementById('btnSignsFindHospital').addEventListener('click', () => {
    currentView = 'list';
    switchView('list');
    findNearest();
  });

  // Nếu tài nguyên poster không thể tải, không để lại vùng trắng lớn kèm biểu tượng ảnh lỗi.
  // Poster thực tế được đặt trong assets/ để GitHub Pages luôn triển khai cùng mã nguồn.
  const signsPosterImage = document.querySelector('.signs-poster-image');
  const posterLoadFallback = document.getElementById('posterLoadFallback');
  if (signsPosterImage && posterLoadFallback) {
    const showPosterFallback = () => {
      signsPosterImage.hidden = true;
      posterLoadFallback.hidden = false;
    };
    signsPosterImage.addEventListener('error', showPosterFallback);
    signsPosterImage.addEventListener('load', () => {
      posterLoadFallback.hidden = true;
    });
    if (signsPosterImage.complete && signsPosterImage.naturalWidth === 0) {
      showPosterFallback();
    }
  }
  document.getElementById('btnNearest').addEventListener('click', findNearest);
