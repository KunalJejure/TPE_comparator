let currentReportsCount = 0;

function exportCSV() {
    // Check if there are any records loaded
    if (currentReportsCount === 0) {
        showToast("No records Found", "warning");
        return;
    }

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
        currentReportsCount = 0; // Reset before fetch
        const res = await fetch(url);
        const data = await res.json();
        
        currentReportsCount = data.length || 0;

        const tbody = document.getElementById('reportsTableBody');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (currentReportsCount === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="padding: 24px; text-align: center; color: var(--text-muted);">No records found</td></tr>';
            return;
        }

        data.forEach(item => {
            const tr = document.createElement('tr');
            
            const statusClass = item.status.toLowerCase().replace(/\s+/g, '-');
            const statusBadge = `<span class="status-badge status-${statusClass}">${item.status}</span>`;

            tr.innerHTML = `
                <td>${item.timestamp}</td>
                <td title="${item.original_filename}">${item.original_filename}</td>
                <td title="${item.revised_filename}">${item.revised_filename}</td>
                <td>${item.total_pages}</td>
                <td>${statusBadge}</td>
                <td>
                    <div class="table-actions">
                        ${item.report_url ? `<a href="${item.report_url}" target="_blank" class="btn-table-action" title="Download PDF Report">
                            <i data-lucide="file-down"></i>
                        </a>` : ''}
                        <button onclick="viewHistoryResult(${item.id})" class="btn-table-action primary" title="View Results">
                            <i data-lucide="eye"></i>
                        </button>
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });

        // Re-initialize Lucide icons for the newly added buttons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }

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
