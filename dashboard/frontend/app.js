// ระบบชั่งน้ำหนักขยะติดเชื้อ — Senses Scale Dashboard
// Status logic: กำลังชั่ง | ยอดแล้ว | ยังไม่ยอด 24ชม. | ไม่ยอดเกิน 48ชม.

const API_BASE_URL     = '/api';
const REFRESH_INTERVAL = 15000; // 15 sec

// ── Auth guard ────────────────────────────────────────
const SS_TOKEN = sessionStorage.getItem('ss_token');
if (!SS_TOKEN) {
    window.location.replace('login.html');
}

function logout() {
    fetch(`/api/auth/logout`, {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + SS_TOKEN }
    }).catch(() => {});
    sessionStorage.clear();
    window.location.replace('login.html');
}

let fillLevelChart = null;
let statusPieChart = null;
let refreshTimer   = null;

// Panel state
let chartsVisible  = false;
let alertsVisible  = false;
let filterVisible  = false;

// Data cache
let binsCache      = [];
let dailyCache     = [];   // from /api/stats/daily-weight
let alertsCache    = [];
let currentFilter  = 'all';
let exportType     = 'csv';

/* ────────────────────────────────────────────────────
   Init
   ──────────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('exportStartDate').value = today;
    document.getElementById('exportEndDate').value   = today;

    // Show logged-in username in navbar
    const displayName = sessionStorage.getItem('ss_display_name') ||
                        sessionStorage.getItem('ss_username') || '';
    const navEl = document.getElementById('navUsername');
    if (navEl && displayName) navEl.textContent = displayName;

    initCharts();
    loadAll();
    refreshTimer = setInterval(loadAll, REFRESH_INTERVAL);
});

window.addEventListener('beforeunload', () => clearInterval(refreshTimer));

/* ────────────────────────────────────────────────────
   Panel toggles
   ──────────────────────────────────────────────────── */

function toggleFilter() {
    filterVisible = !filterVisible;
    document.getElementById('filterPanel').classList.toggle('ss-hidden', !filterVisible);
    document.getElementById('btnFilter').classList.toggle('active', filterVisible);
}

function toggleCharts() {
    chartsVisible = !chartsVisible;
    document.getElementById('chartsPanel').classList.toggle('ss-hidden', !chartsVisible);
    document.getElementById('btnChart').classList.toggle('active', chartsVisible);
    if (chartsVisible) updateBarChart(binsCache);
}

function toggleAlerts() {
    alertsVisible = !alertsVisible;
    document.getElementById('alertsPanel').classList.toggle('ss-hidden', !alertsVisible);
    document.getElementById('overlayBg').classList.toggle('ss-hidden', !alertsVisible);
}

function closeAllPanels() {
    alertsVisible = false;
    document.getElementById('alertsPanel').classList.add('ss-hidden');
    document.getElementById('overlayBg').classList.add('ss-hidden');
}

/* ────────────────────────────────────────────────────
   Filter
   ──────────────────────────────────────────────────── */

function setFilter(status) {
    currentFilter = status;
    document.querySelectorAll('.ss-filter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.status === status);
    });
    renderBins(binsCache);
}

/* ────────────────────────────────────────────────────
   Export CSV / Xlsx Modal
   ──────────────────────────────────────────────────── */

function showExportModal(type) {
    exportType = type;
    document.getElementById('exportTitle').textContent =
        type === 'csv' ? 'Export to CSV' : 'Export to Xlsx Report';
    document.getElementById('exportDoBtn').textContent = 'Export';
    document.getElementById('exportModal').classList.remove('ss-hidden');
    document.getElementById('overlayModal').classList.remove('ss-hidden');
}

function closeExport() {
    document.getElementById('exportModal').classList.add('ss-hidden');
    document.getElementById('overlayModal').classList.add('ss-hidden');
}

async function doExport() {
    const startDate = document.getElementById('exportStartDate').value;
    const startTime = document.getElementById('exportStartTime').value;
    const endDate   = document.getElementById('exportEndDate').value;
    const endTime   = document.getElementById('exportEndTime').value;

    if (!startDate || !endDate) { alert('กรุณาเลือกช่วงวันที่'); return; }

    const startDt = new Date(`${startDate}T${startTime || '00:00'}`);
    const endDt   = new Date(`${endDate}T${endTime || '23:59'}`);
    if (endDt <= startDt) { alert('วันที่สิ้นสุดต้องหลังวันที่เริ่มต้น'); return; }

    const hours = Math.max(1, Math.ceil((endDt - startDt) / (1000 * 60 * 60)));

    const btn = document.getElementById('exportDoBtn');
    btn.textContent = 'กำลังโหลด...';
    btn.disabled    = true;

    try {
        const res    = await fetch(`${API_BASE_URL}/readings?hours=${Math.min(hours, 720)}`);
        const result = await res.json();

        if (!result.success || !result.data?.length) {
            alert('ไม่พบข้อมูลในช่วงเวลาที่เลือก'); return;
        }

        const rows = result.data.filter(r => {
            const t = new Date(r.timestamp);
            return t >= startDt && t <= endDt;
        });

        if (!rows.length) { alert('ไม่พบข้อมูลในช่วงเวลาที่เลือก'); return; }

        // Enrich rows with location from binsCache
        const binMap = {};
        binsCache.forEach(b => { binMap[b.bin_id] = b.location; });
        rows.forEach(r => { r.department = binMap[r.bin_id] || r.bin_code; });

        const filename = `infectious_waste_${startDate}_${endDate}`;
        exportType === 'xlsx' ? downloadXlsx(rows, filename) : downloadCsv(rows, filename);
        closeExport();
    } catch (e) {
        console.error(e);
        alert('เกิดข้อผิดพลาดในการดึงข้อมูล');
    } finally {
        btn.textContent = 'Export';
        btn.disabled    = false;
    }
}

function downloadCsv(rows, filename) {
    const headers = ['timestamp', 'bin_code', 'department', 'weight_kg',
                     'battery_level', 'signal_strength', 'temperature_c'];
    const thHeaders = ['วันที่/เวลา', 'รหัสเครื่อง', 'หน่วยงาน', 'น้ำหนัก (กก.)',
                       'แบตเตอรี่ (%)', 'สัญญาณ (dBm)', 'อุณหภูมิ (°C)'];
    const lines = [
        thHeaders.join(','),
        ...rows.map(r => headers.map(h => {
            const v = r[h] ?? '';
            return typeof v === 'string' && v.includes(',') ? `"${v}"` : v;
        }).join(','))
    ];
    const blob = new Blob(['\uFEFF' + lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    triggerDownload(blob, `${filename}.csv`);
}

function downloadXlsx(rows, filename) {
    const headers   = ['timestamp', 'bin_code', 'department', 'weight_kg',
                       'battery_level', 'signal_strength', 'temperature_c'];
    const thHeaders = ['วันที่/เวลา', 'รหัสเครื่อง', 'หน่วยงาน', 'น้ำหนัก (กก.)',
                       'แบตเตอรี่ (%)', 'สัญญาณ (dBm)', 'อุณหภูมิ (°C)'];
    const wsData = [
        thHeaders,
        ...rows.map(r => headers.map(h => r[h] ?? ''))
    ];
    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.aoa_to_sheet(wsData);
    // Column widths
    ws['!cols'] = [{ wch: 22 }, { wch: 10 }, { wch: 35 }, { wch: 14 },
                   { wch: 14 }, { wch: 14 }, { wch: 14 }];
    XLSX.utils.book_append_sheet(wb, ws, 'ขยะติดเชื้อ');
    XLSX.writeFile(wb, `${filename}.xlsx`);
}

function triggerDownload(blob, name) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    URL.revokeObjectURL(a.href);
}

/* ────────────────────────────────────────────────────
   Detail Modal
   ──────────────────────────────────────────────────── */

async function openModal(binId) {
    const bin = binsCache.find(b => b.bin_id === binId);
    if (!bin) return;

    const cs    = cardStatus(bin);
    const daily = dailyCache.find(d => d.bin_id === binId);

    document.getElementById('modalTitle').textContent = bin.location;
    document.getElementById('modalBody').innerHTML = buildModalBody(bin, cs, daily, null);
    document.getElementById('detailModal').classList.remove('ss-hidden');
    document.getElementById('overlayModal').classList.remove('ss-hidden');

    // Load weighing history async
    try {
        const r = await fetch(`${API_BASE_URL}/bins/${binId}`);
        const detail = await r.json();
        if (detail.success && document.getElementById('detailModal').classList.contains('ss-hidden') === false) {
            document.getElementById('modalBody').innerHTML =
                buildModalBody(bin, cs, daily, detail.data.recent_readings);
        }
    } catch(e) { console.warn('Modal history load error:', e); }
}

function buildModalBody(bin, cs, daily, readings) {
    const todayKg  = daily ? parseFloat(daily.total_weight_today) : 0;
    const todayCnt = daily ? parseInt(daily.reading_count_today)  : 0;
    const lastKg   = bin.weight_kg != null ? parseFloat(bin.weight_kg) : null;
    const batt     = bin.battery_level != null ? parseFloat(bin.battery_level).toFixed(0) + '%' : '--';
    const signal   = bin.signal_strength != null ? bin.signal_strength + ' dBm' : '--';

    // Summary strip
    const summaryHtml = `
        <div class="ss-modal-summary">
            <div class="ss-modal-summary-item">
                <div class="ss-modal-summary-num">${todayKg.toFixed(3)}</div>
                <div class="ss-modal-summary-lbl">น้ำหนักสะสม (กก.)</div>
            </div>
            <div class="ss-modal-summary-item">
                <div class="ss-modal-summary-num">${todayCnt}</div>
                <div class="ss-modal-summary-lbl">ครั้ง (24ชม.)</div>
            </div>
            <div class="ss-modal-summary-item">
                <div class="ss-modal-summary-num">${batt}</div>
                <div class="ss-modal-summary-lbl">แบตเตอรี่</div>
            </div>
            <div class="ss-modal-summary-item">
                <div class="ss-modal-summary-num" style="font-size:0.95rem">${signal}</div>
                <div class="ss-modal-summary-lbl">สัญญาณ</div>
            </div>
        </div>`;

    // Info row: device code + status badge
    const infoHtml = `
        <div class="ss-modal-row">
            <span class="ss-modal-label">รหัสเครื่อง</span>
            <span class="ss-modal-value">${bin.bin_code}</span>
        </div>
        <div class="ss-modal-row" style="margin-bottom:4px">
            <span class="ss-modal-label">สถานะ</span>
            <span class="ss-modal-status-badge status-${cs}" style="width:auto;padding:3px 12px;margin:0">
                ${STATUS_TH[cs] ?? cs}
            </span>
        </div>`;

    // Weighing history
    let historyHtml = '<div class="ss-history-header"><i class="bi bi-list-ul"></i> ประวัติการชั่ง (ล่าสุด 10 ครั้ง)</div>';
    if (readings === null) {
        historyHtml += '<div class="ss-history-empty"><i class="bi bi-hourglass-split"></i> กำลังโหลด...</div>';
    } else {
        const weighings = readings.filter(r => r.weight_kg > 0);
        if (weighings.length === 0) {
            historyHtml += '<div class="ss-history-empty">ไม่มีข้อมูลการชั่งน้ำหนัก</div>';
        } else {
            historyHtml += '<div class="ss-history-list">' + weighings.map((r, i) => {
                const t = new Date(r.timestamp).toLocaleString('th-TH', {
                    day: '2-digit', month: '2-digit',
                    hour: '2-digit', minute: '2-digit', second: '2-digit'
                });
                const wt = parseFloat(r.weight_kg).toFixed(3) + ' กก.';
                return `<div class="ss-history-row">
                    <span class="ss-history-time">${i === 0 ? '🟢 ' : ''}${t}</span>
                    <span class="ss-history-weight">${wt}</span>
                </div>`;
            }).join('') + '</div>';
        }
    }

    return summaryHtml + infoHtml + historyHtml;
}

function closeModal() {
    document.getElementById('detailModal').classList.add('ss-hidden');
    document.getElementById('exportModal').classList.add('ss-hidden');
    document.getElementById('overlayModal').classList.add('ss-hidden');
}

/* ────────────────────────────────────────────────────
   Charts init
   ──────────────────────────────────────────────────── */

function initCharts() {
    // Left: Bar chart — weight per department today
    fillLevelChart = new Chart(
        document.getElementById('fillLevelChart').getContext('2d'), {
        type: 'bar',
        data: { labels: [], datasets: [{
            label: 'น้ำหนักวันนี้ (กก.)',
            data: [],
            backgroundColor: 'rgba(168,216,176,0.7)',
            borderColor: '#1B6B42',
            borderWidth: 1.5,
            borderRadius: 4
        }] },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: { legend: { display: false } },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { callback: v => v + ' กก.' },
                    grid: { color: 'rgba(232,200,75,0.2)' }
                },
                x: {
                    grid: { display: false },
                    ticks: { font: { size: 10 }, maxRotation: 45 }
                }
            }
        }
    });

    // Right: Doughnut — status distribution
    statusPieChart = new Chart(
        document.getElementById('statusPieChart').getContext('2d'), {
        type: 'doughnut',
        data: {
            labels: ['กำลังชั่ง', 'ยอดแล้ววันนี้', 'ยังไม่ยอด 24ชม.', 'ไม่ยอดเกิน 48ชม.', 'ไม่มีข้อมูล'],
            datasets: [{
                data: [0, 0, 0, 0, 0],
                backgroundColor: ['#A8D8B0', '#FFF3C4', '#F5B7C0', '#C9D5E0', '#C4BAD0'],
                borderColor:     ['#7EC89A', '#E8C84B', '#E8939E', '#A9BDD0', '#A89DBE'],
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: { legend: { position: 'bottom', labels: { font: { size: 11 } } } }
        }
    });
}

/* ────────────────────────────────────────────────────
   Data loading
   ──────────────────────────────────────────────────── */

async function loadAll() {
    try {
        await Promise.all([loadBins(), loadDailyWeight(), loadAlerts()]);
        updateTime();
    } catch (e) { console.error('loadAll error:', e); }
}

async function loadBins() {
    try {
        const r = await fetch(`${API_BASE_URL}/bins`).then(r => r.json());
        if (!r.success) return;
        binsCache = r.data;
        renderBins(r.data);
    } catch(e) {
        console.error('loadBins error:', e);
        document.getElementById('binsGrid').innerHTML =
            '<div class="ss-empty"><i class="bi bi-exclamation-triangle"></i><p>ไม่สามารถเชื่อมต่อ API ได้</p></div>';
    }
}

async function loadDailyWeight() {
    try {
        const r = await fetch(`${API_BASE_URL}/stats/daily-weight`).then(r => r.json());
        if (!r.success) return;
        dailyCache = r.data;
        if (chartsVisible) updateBarChart(binsCache);
    } catch(e) { console.error('loadDailyWeight:', e); }
}

async function loadAlerts() {
    try {
        const r = await fetch(`${API_BASE_URL}/alerts?status=open`).then(r => r.json());
        if (!r.success) return;
        alertsCache = r.data;
        renderAlerts(r.data);
    } catch(e) { console.error('loadAlerts error:', e); }
}

/* ────────────────────────────────────────────────────
   Status logic — Compliance-based (Senses Scale)

   green  (good)   : last_reading < 2 min  → กำลังชั่งขยะติดเชื้อ
   yellow (medium) : last_reading 2min–24h → ยอดแล้ววันนี้
   pink   (high)   : last_reading 24h–48h  → ยังไม่ยอดภายใน 24 ชม.
   blue   (offline): last_reading > 48h    → ไม่ยอดเกิน 48 ชม.
   mauve  (none)   : ไม่เคยมีข้อมูลเลย
   ──────────────────────────────────────────────────── */

const MIN2  =  2 * 60 * 1000;
const H24   = 24 * 60 * 60 * 1000;
const H48   = 48 * 60 * 60 * 1000;

function cardStatus(bin) {
    if (!bin.last_reading) return 'none';
    const age = Date.now() - new Date(bin.last_reading).getTime();
    if (age <  MIN2) return 'good';     // กำลังชั่ง (green)
    if (age <  H24)  return 'medium';   // ยอดแล้ววันนี้ (yellow)
    if (age <  H48)  return 'high';     // ยังไม่ยอด 24ชม. (pink)
    return 'offline';                    // ไม่ยอดเกิน 48ชม. (blue-grey)
}

const STATUS_TH = {
    good:    '🟢 กำลังชั่งขยะติดเชื้อ',
    medium:  '🟡 ยอดแล้ววันนี้',
    high:    '🩷 ยังไม่ยอดขยะภายใน 24 ชม.',
    offline: '⚫ ไม่ยอดขยะเกิน 48 ชม.',
    none:    '— ยังไม่เคยมีข้อมูล'
};

/* ────────────────────────────────────────────────────
   Render: Department cards
   ──────────────────────────────────────────────────── */

function renderBins(bins) {
    const grid = document.getElementById('binsGrid');

    if (!bins || bins.length === 0) {
        grid.innerHTML = '<div class="ss-empty"><i class="bi bi-inbox"></i><p>ไม่พบข้อมูลหน่วยงาน</p></div>';
        return;
    }

    // Count currently weighing
    const activeCnt = bins.filter(b => cardStatus(b) === 'good').length;
    document.getElementById('activeWeighing').textContent = `${activeCnt} / ${bins.length}`;
    document.getElementById('totalDepts').textContent  = bins.length;
    document.getElementById('totalDepts2').textContent = bins.length;

    // Pie + Bar chart — only update when panel is visible (avoid canvas 0x0 error)
    if (chartsVisible) {
        try {
            const dist = { good: 0, medium: 0, high: 0, offline: 0, none: 0 };
            bins.forEach(b => { dist[cardStatus(b)] = (dist[cardStatus(b)] || 0) + 1; });
            statusPieChart.data.datasets[0].data = [
                dist.good, dist.medium, dist.high, dist.offline, dist.none
            ];
            statusPieChart.update();
            updateBarChart(bins);
        } catch(e) { console.warn('Chart update skipped:', e.message); }
    }

    // Filter
    const filtered = currentFilter === 'all'
        ? bins
        : bins.filter(b => cardStatus(b) === currentFilter);

    if (filtered.length === 0) {
        grid.innerHTML = '<div class="ss-empty"><i class="bi bi-filter"></i><p>ไม่มีหน่วยงานในสถานะที่เลือก</p></div>';
        return;
    }

    grid.innerHTML = filtered.map(bin => {
        const cs      = cardStatus(bin);
        const daily   = dailyCache.find(d => d.bin_id === bin.bin_id);
        const todayKg = daily && daily.total_weight_today > 0
            ? parseFloat(daily.total_weight_today).toFixed(2) + ' กก.'
            : null;
        const lastKg  = bin.weight_kg != null
            ? parseFloat(bin.weight_kg).toFixed(2) + ' กก.'
            : null;

        // Sub-text: show today's total if available, else last reading
        let subText = '';
        if (cs === 'good') {
            subText = lastKg ? `⚖️ ${lastKg}` : 'กำลังชั่ง...';
        } else if (todayKg) {
            subText = `วันนี้ ${todayKg}`;
        } else if (lastKg) {
            subText = `ล่าสุด ${lastKg}`;
        }

        return `
            <div class="ss-bin-card status-${cs} fade-in"
                 onclick="openModal(${bin.bin_id})"
                 title="คลิกเพื่อดูรายละเอียด">
                ${cs === 'good' ? '<div class="ss-alert-dot ss-weighing-dot"></div>' : ''}
                <div class="ss-card-name">${bin.location}</div>
                ${subText ? `<div class="ss-card-sub">${subText}</div>` : ''}
            </div>`;
    }).join('');
}

/* ────────────────────────────────────────────────────
   Render: Alerts
   ──────────────────────────────────────────────────── */

const ALERT_TYPE_TH = {
    bin_full:         'น้ำหนักเกินขีด',
    sensor_fault:     'แบตเตอรี่ต่ำ',
    unusual_activity: 'อุณหภูมิสูง',
    maintenance:      'บำรุงรักษา'
};

function renderAlerts(alerts) {
    const cnt = alerts?.length ?? 0;
    const el  = document.getElementById('alertsList');
    if (cnt === 0) {
        el.innerHTML = '<div class="ss-empty"><i class="bi bi-check-circle"></i><p>ไม่มีการแจ้งเตือน</p></div>';
        return;
    }
    el.innerHTML = alerts.map(a => {
        const sev    = a.severity || 'low';
        const typeTh = ALERT_TYPE_TH[a.alert_type] || a.alert_type.replace(/_/g, ' ');
        const t      = new Date(a.triggered_at).toLocaleString('th-TH', {
            day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'
        });
        return `
            <div class="ss-alert-item sev-${sev} fade-in">
                <div class="ss-alert-title">${typeTh} · ${a.bin_code ?? ''}</div>
                <div class="ss-alert-msg">${a.message}</div>
                <div class="ss-alert-meta">
                    <span><i class="bi bi-clock"></i> ${t}</span>
                    <span>${sev.toUpperCase()}</span>
                </div>
            </div>`;
    }).join('');
}

/* ────────────────────────────────────────────────────
   Charts update
   ──────────────────────────────────────────────────── */

function updateBarChart(bins) {
    if (!bins?.length) return;

    // Sort by bin_id, get labels (short department name) and today's weight
    const sorted = [...bins].sort((a, b) => a.bin_id - b.bin_id);
    const labels = sorted.map(b => {
        // Shorten long department names for chart
        const loc = b.location || b.bin_code;
        return loc.length > 14 ? loc.substring(0, 13) + '…' : loc;
    });
    const weights = sorted.map(b => {
        const daily = dailyCache.find(d => d.bin_id === b.bin_id);
        return daily ? parseFloat(daily.total_weight_today) || 0 : 0;
    });
    const colors = sorted.map(b => {
        const cs = cardStatus(b);
        return cs === 'good' ? 'rgba(168,216,176,0.85)'
             : cs === 'medium' ? 'rgba(255,243,196,0.9)'
             : cs === 'high' ? 'rgba(245,183,192,0.85)'
             : 'rgba(201,213,224,0.75)';
    });

    fillLevelChart.data.labels = labels;
    fillLevelChart.data.datasets[0].data = weights;
    fillLevelChart.data.datasets[0].backgroundColor = colors;
    fillLevelChart.update();
}

/* ────────────────────────────────────────────────────
   Misc
   ──────────────────────────────────────────────────── */

function updateTime() {
    const el = document.querySelector('.ss-last-update');
    if (el) el.textContent = 'อัปเดต ' + new Date().toLocaleTimeString('th-TH');
}
