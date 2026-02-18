// ================================================================
// reports.js — Reports View Logic (Stats, Charts, History Table)
// ================================================================

function exportCSV() {
    const filterEl = document.getElementById('histFilterStatus');
    const status = filterEl ? filterEl.value : '';
    let url = '/api/reports/export?';
    if (status) url += `status=${encodeURIComponent(status)}`;
    window.location.href = url;
}

async function loadReports() {
    try {
        const res = await fetch('/api/reports/stats');
        if (!res.ok) throw new Error('Failed to load stats');
        const data = await res.json();

        // KPIs
        const repTotal = document.getElementById('repTotal');
        const repSuccess = document.getElementById('repSuccess');
        const repAvgPages = document.getElementById('repAvgPages');

        if (repTotal) repTotal.textContent = data.total_comparisons;
        if (repSuccess) repSuccess.textContent = data.success_rate + '%';
        if (repAvgPages) repAvgPages.textContent = data.avg_pages;

        // Charts
        renderActivityChart(data.activity_trend);
        renderDistChart(data.page_distribution);

        // Load Table
        loadReportsHistory();

    } catch (err) {
        console.error("Failed to load reports stats", err);
    }
}


async function loadReportsHistory() {
    const filterEl = document.getElementById('histFilterStatus');
    const status = filterEl ? filterEl.value : '';

    let url = '/api/reports/history_full?';
    if (status) url += `status=${encodeURIComponent(status)}`;

    try {
        const res = await fetch(url);
        const data = await res.json();

        const tbody = document.getElementById('reportsTableBody');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="padding: 24px; text-align: center; color: var(--text-muted);">No records found</td></tr>';
            return;
        }

        data.forEach(item => {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid var(--border)';

            let statusColor = 'var(--text-secondary)';
            if (item.status === 'PASS' || item.status === 'NO CHANGES') statusColor = 'var(--success)';
            else if (item.status === 'FAIL') statusColor = 'var(--danger)';
            else if (item.status === 'CHANGES FOUND') statusColor = 'var(--warning)';

            tr.innerHTML = `
                <td style="padding: 12px;">${item.timestamp}</td>
                <td style="padding: 12px;">${item.original_filename}</td>
                <td style="padding: 12px;">${item.revised_filename}</td>
                <td style="padding: 12px;">${item.total_pages}</td>
                <td style="padding: 12px; color: ${statusColor}; font-weight: 600;">${item.status}</td>
                <td style="padding: 12px; display: flex; align-items: center; gap: 8px;">
                    ${item.report_url ? `<a href="${item.report_url}" target="_blank"
                        style="color: var(--accent); font-weight: 500; font-size: 0.9rem; text-decoration: none;">PDF Report</a>` : ''}
                    <button onclick="viewHistoryResult(${item.id})" style="padding: 6px 12px; font-size: 0.8rem; background: var(--accent); color: white; border: none; border-radius: 4px; cursor: pointer; transition: background 0.2s;">View Results</button>
                </td>
            `;
            tbody.appendChild(tr);
        });

    } catch (err) {
        console.error("Failed to load history table", err);
    }
}

let activityChartInstance2 = null;
function renderActivityChart(trendData) {
    const ctxEl = document.getElementById('activityChart');
    if (!ctxEl) return;
    const ctx = ctxEl.getContext('2d');

    if (activityChartInstance2) activityChartInstance2.destroy();

    const labels = trendData.map(d => d.date);
    const values = trendData.map(d => d.count);

    activityChartInstance2 = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Comparisons',
                data: values,
                borderColor: '#3B82F6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
        }
    });
}

let distChartInstance2 = null;
function renderDistChart(distData) {
    const ctxEl = document.getElementById('distChart');
    if (!ctxEl) return;
    const ctx = ctxEl.getContext('2d');

    if (distChartInstance2) distChartInstance2.destroy();

    distChartInstance2 = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Small (1-10)', 'Medium (11-50)', 'Large (50+)'],
            datasets: [{
                data: [distData.small, distData.medium, distData.large],
                backgroundColor: ['#22C55E', '#3B82F6', '#EF4444']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } }
        }
    });
}

async function viewHistoryResult(id) {
    try {
        const res = await fetch(`/api/reports/history/${id}`);
        if (!res.ok) throw new Error('Failed to load result');
        const result = await res.json();

        if (!result || Object.keys(result).length === 0) {
            alert("Comparison details not available for this record (it might be an old record without stored JSON).");
            return;
        }

        // Set global result
        lastResult = result;

        // Update dashboard stats
        if (result.total_pages !== undefined) {
            const total = result.total_pages || 0;
            const passed = result.pages ? result.pages.filter(p => p.status === 'PASS').length : 0;
            const failed = total - passed;

            const statTotal = document.getElementById('statTotal');
            const statMatches = document.getElementById('statMatches');
            const statDiffs = document.getElementById('statDiffs');
            const doneTag = document.getElementById('doneTag');

            if (statTotal) statTotal.textContent = total;
            if (statMatches) statMatches.textContent = passed;
            if (statDiffs) statDiffs.textContent = failed;
            if (doneTag) doneTag.textContent = `Done ${Math.round((passed / total) * 100)}%`;
        }

        // Update chart
        if (typeof updateChart === 'function') updateChart(result);

        // Show results nav item
        const navResults = document.getElementById('navResults');
        if (navResults) navResults.style.display = 'flex';

        // Render results and switch to results view
        if (typeof renderResults === 'function') {
            renderResults(result);
            switchView('results');
        } else {
            console.error('renderResults function not found');
        }

    } catch (err) {
        console.error(err);
        alert("Failed to load comparison details.");
    }
}
