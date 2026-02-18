// ================================================================
// dashboard.js — Dashboard Chart Initialization
// ================================================================

const ctx = document.getElementById('perfChart').getContext('2d');
const perfChart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: ['01', '02', '03', '04', '05', '06', '07'],
        datasets: [
            {
                label: 'Similarity %',
                data: [95, 87, 92, 78, 96, 88, 91],
                borderColor: '#3B82F6',
                backgroundColor: 'rgba(59,130,246,.08)',
                fill: true,
                tension: .4,
                pointRadius: 4,
                pointBackgroundColor: '#3B82F6',
                borderWidth: 2,
            },
            {
                label: 'Pages Checked',
                data: [12, 8, 15, 10, 6, 14, 9],
                borderColor: '#CBD5E1',
                backgroundColor: 'transparent',
                borderDash: [6, 4],
                tension: .4,
                pointRadius: 3,
                pointBackgroundColor: '#CBD5E1',
                borderWidth: 2,
            },
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: '#1E293B',
                titleFont: { family: 'Inter', weight: '600' },
                bodyFont: { family: 'Inter' },
                cornerRadius: 8,
                padding: 12,
            }
        },
        scales: {
            x: {
                grid: { display: false },
                ticks: { font: { family: 'Inter', size: 12 }, color: '#94A3B8' }
            },
            y: {
                grid: { color: '#F1F5F9' },
                ticks: { font: { family: 'Inter', size: 12 }, color: '#94A3B8' }
            }
        },
        interaction: { intersect: false, mode: 'index' }
    }
});

function updateChart(data) {
    if (!data.pages) return;
    const labels = data.pages.map(p => 'Page ' + p.page);
    const changes = data.pages.map(p => ((1 - (p.image_similarity || 0)) * 100).toFixed(1));

    perfChart.data.labels = labels;
    perfChart.data.datasets[0].data = changes;
    perfChart.data.datasets[0].label = 'Change %';
    perfChart.data.datasets[1].data = data.pages.map(p => p.confidence ? (p.confidence * 100).toFixed(0) : 90);
    perfChart.data.datasets[1].label = 'AI Confidence %';
    perfChart.update();
}

function updateTaskStatus(index, text, color) {
    const items = document.querySelectorAll('#tasksList .task-item');
    if (items[index]) {
        const statusEl = items[index].querySelector('.task-status');
        if (statusEl) {
            statusEl.innerHTML = `<div class="status-dot ${color}"></div> ${text}`;
        }
    }
}

function addActivity(initials, bg, name, desc) {
    const feed = document.getElementById('activityFeed');
    const time = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    feed.innerHTML = `
    <div class="activity-item">
        <div class="activity-avatar" style="background:${bg};">${initials}</div>
        <div class="activity-content">
            <div class="act-header">
                <span class="act-name">${name}</span>
                <span class="act-time">${time}</span>
            </div>
            <div class="act-desc">${desc}</div>
        </div>
    </div>` + feed.innerHTML;
    lucide.createIcons();
}
