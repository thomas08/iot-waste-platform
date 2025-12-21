// IoT Waste Management Dashboard - JavaScript

// Configuration
const API_BASE_URL = 'http://localhost:8000/api';
const REFRESH_INTERVAL = 10000; // 10 seconds

// Global variables
let fillLevelChart = null;
let statusPieChart = null;
let refreshTimer = null;

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard initializing...');
    initializeCharts();
    loadDashboardData();
    startAutoRefresh();
});

// Initialize charts
function initializeCharts() {
    // Fill Level Timeline Chart
    const fillCtx = document.getElementById('fillLevelChart').getContext('2d');
    fillLevelChart = new Chart(fillCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Average Fill Level (%)',
                data: [],
                borderColor: '#198754',
                backgroundColor: 'rgba(25, 135, 84, 0.1)',
                borderWidth: 2,
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                }
            }
        }
    });

    // Status Pie Chart
    const pieCtx = document.getElementById('statusPieChart').getContext('2d');
    statusPieChart = new Chart(pieCtx, {
        type: 'doughnut',
        data: {
            labels: ['Low', 'Medium', 'High', 'Critical'],
            datasets: [{
                data: [0, 0, 0, 0],
                backgroundColor: [
                    '#198754', // success
                    '#0dcaf0', // info
                    '#ffc107', // warning
                    '#dc3545'  // danger
                ],
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

// Load all dashboard data
async function loadDashboardData() {
    try {
        await Promise.all([
            loadStatistics(),
            loadBins(),
            loadAlerts(),
            loadTimelineData()
        ]);
        updateLastUpdateTime();
    } catch (error) {
        console.error('Error loading dashboard data:', error);
        showError('Failed to load dashboard data');
    }
}

// Load statistics
async function loadStatistics() {
    try {
        const response = await fetch(`${API_BASE_URL}/stats`);
        const result = await response.json();

        if (result.success) {
            const data = result.data;

            document.getElementById('totalBins').textContent = data.total_bins || 0;
            document.getElementById('activeAlerts').textContent = data.active_alerts || 0;
            document.getElementById('binsNeedAttention').textContent = data.bins_need_attention || 0;
            document.getElementById('avgFillLevel').textContent = (data.avg_fill_level || 0) + '%';

            // Update pie chart
            updateStatusPieChart(data.fill_status_distribution);
        }
    } catch (error) {
        console.error('Error loading statistics:', error);
    }
}

// Update status pie chart
function updateStatusPieChart(distribution) {
    const statusMap = { low: 0, medium: 1, high: 2, critical: 3 };
    const data = [0, 0, 0, 0];

    distribution.forEach(item => {
        const index = statusMap[item.fill_status];
        if (index !== undefined) {
            data[index] = item.count;
        }
    });

    statusPieChart.data.datasets[0].data = data;
    statusPieChart.update();
}

// Load bins
async function loadBins() {
    try {
        const response = await fetch(`${API_BASE_URL}/bins`);
        const result = await response.json();

        if (result.success) {
            renderBins(result.data);
        }
    } catch (error) {
        console.error('Error loading bins:', error);
    }
}

// Render bins grid
function renderBins(bins) {
    const container = document.getElementById('binsGrid');

    if (!bins || bins.length === 0) {
        container.innerHTML = '<div class="empty-state"><i class="bi bi-inbox"></i><p>No bins found</p></div>';
        return;
    }

    container.innerHTML = bins.map(bin => {
        const fillLevel = bin.fill_level || 0;
        const fillStatus = bin.fill_status || 'low';
        const temperature = bin.temperature_c || '--';
        const battery = bin.battery_level || '--';

        let progressColor = 'bg-success';
        if (fillLevel >= 90) progressColor = 'bg-danger';
        else if (fillLevel >= 75) progressColor = 'bg-warning';
        else if (fillLevel >= 50) progressColor = 'bg-info';

        const lastReading = bin.last_reading ? new Date(bin.last_reading).toLocaleString() : 'No data';

        return `
            <div class="col-md-6">
                <div class="bin-card status-${fillStatus} fade-in">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <div class="bin-code">${bin.bin_code}</div>
                            <div class="bin-location">
                                <i class="bi bi-geo-alt"></i> ${bin.location}
                            </div>
                        </div>
                        <span class="status-badge ${fillStatus}">${fillStatus}</span>
                    </div>

                    <div class="progress mt-2">
                        <div class="progress-bar ${progressColor}" role="progressbar"
                             style="width: ${fillLevel}%"
                             aria-valuenow="${fillLevel}" aria-valuemin="0" aria-valuemax="100">
                            ${fillLevel.toFixed(1)}%
                        </div>
                    </div>

                    <div class="bin-stats">
                        <div class="stat-item">
                            <i class="bi bi-thermometer-half"></i>
                            <span>${typeof temperature === 'number' ? temperature.toFixed(1) + '°C' : temperature}</span>
                        </div>
                        <div class="stat-item">
                            <i class="bi bi-battery-half"></i>
                            <span>${typeof battery === 'number' ? battery.toFixed(0) + '%' : battery}</span>
                        </div>
                        <div class="stat-item">
                            <i class="bi bi-trash"></i>
                            <span>${bin.bin_type}</span>
                        </div>
                    </div>

                    ${bin.open_alerts > 0 ? `
                        <div class="alert alert-warning alert-sm mt-2 mb-0 py-1">
                            <i class="bi bi-exclamation-triangle"></i> ${bin.open_alerts} active alert(s)
                        </div>
                    ` : ''}

                    <div class="text-muted mt-2" style="font-size: 0.75rem;">
                        <i class="bi bi-clock"></i> ${lastReading}
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// Load alerts
async function loadAlerts() {
    try {
        const response = await fetch(`${API_BASE_URL}/alerts?status=open`);
        const result = await response.json();

        if (result.success) {
            renderAlerts(result.data);
        }
    } catch (error) {
        console.error('Error loading alerts:', error);
    }
}

// Render alerts
function renderAlerts(alerts) {
    const container = document.getElementById('alertsList');

    if (!alerts || alerts.length === 0) {
        container.innerHTML = '<div class="empty-state"><i class="bi bi-check-circle"></i><p>No active alerts</p></div>';
        return;
    }

    container.innerHTML = alerts.map(alert => {
        const triggeredTime = new Date(alert.triggered_at).toLocaleString();
        const severity = alert.severity || 'low';

        return `
            <div class="alert-item severity-${severity} fade-in">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="alert-type">${alert.alert_type.replace(/_/g, ' ')}</div>
                    <span class="badge bg-${getSeverityColor(severity)}">${severity}</span>
                </div>
                <div class="alert-message">${alert.message}</div>
                <div class="d-flex justify-content-between align-items-center mt-2">
                    <div class="alert-time">
                        <i class="bi bi-clock"></i> ${triggeredTime}
                    </div>
                    <div>
                        <i class="bi bi-trash"></i> ${alert.bin_code}
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// Get severity color
function getSeverityColor(severity) {
    const colors = {
        'low': 'info',
        'medium': 'warning',
        'high': 'warning',
        'critical': 'danger'
    };
    return colors[severity] || 'secondary';
}

// Load timeline data for charts
async function loadTimelineData() {
    try {
        const response = await fetch(`${API_BASE_URL}/stats/timeline?hours=24`);
        const result = await response.json();

        if (result.success) {
            updateFillLevelChart(result.data.fill_level_timeline);
        }
    } catch (error) {
        console.error('Error loading timeline data:', error);
    }
}

// Update fill level chart
function updateFillLevelChart(timeline) {
    if (!timeline || timeline.length === 0) return;

    const labels = timeline.map(item => {
        const date = new Date(item.hour);
        return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    });

    const data = timeline.map(item => parseFloat(item.avg_fill_level) || 0);

    fillLevelChart.data.labels = labels;
    fillLevelChart.data.datasets[0].data = data;
    fillLevelChart.update();
}

// Update last update time
function updateLastUpdateTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString();
    document.getElementById('lastUpdate').textContent = `Last updated: ${timeString}`;
}

// Start auto-refresh
function startAutoRefresh() {
    refreshTimer = setInterval(() => {
        loadDashboardData();
    }, REFRESH_INTERVAL);
}

// Stop auto-refresh
function stopAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
}

// Show error message
function showError(message) {
    console.error(message);
    // You can implement a toast notification here
}

// Clean up on page unload
window.addEventListener('beforeunload', function() {
    stopAutoRefresh();
});
