// ================================================================
// requalifications.js — Batch PDF Pair Comparison with Sessions
// ================================================================

let requalNextSlotIndex = 0;
let requalCurrentSessionId = null;
let requalCurrentSessionName = '';

// Month names for validation
const MONTHS = [
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december',
    'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'
];

// ================================================================
// SESSION LIST
// ================================================================

async function loadRequalSessions() {
    const container = document.getElementById('requalSessionCards');
    const emptyState = document.getElementById('requalEmptyState');
    if (!container) return;

    try {
        const res = await fetch('/api/requalifications/sessions');
        if (!res.ok) throw new Error('Failed to load sessions');
        const sessions = await res.json();

        if (sessions.length === 0) {
            container.innerHTML = '';
            container.appendChild(emptyState);
            emptyState.style.display = 'flex';
            lucide.createIcons();
            return;
        }

        emptyState.style.display = 'none';
        let html = '';
        sessions.forEach(s => {
            const date = new Date(s.created_at).toLocaleDateString('en-US', {
                year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
            });

            const statusClass = s.status === 'COMPLETED' ? 'success' :
                s.status === 'IN_PROGRESS' ? 'running' :
                    s.status === 'FAILED' ? 'error' : '';

            const statusLabel = s.status === 'COMPLETED' ? 'Completed' :
                s.status === 'IN_PROGRESS' ? 'In Progress' :
                    s.status === 'FAILED' ? 'Failed' : s.status;

            const passedCount = s.passed_pairs || 0;
            const totalPairs = s.pair_count || 0;
            const completedPairs = s.completed_pairs || 0;

            html += `
            <div class="requal-session-card">
                <div class="requal-sc-top">
                    <div class="requal-sc-info">
                        <h4 class="requal-sc-name">${s.name}</h4>
                        <span class="requal-sc-date">${date}</span>
                    </div>
                    <span class="slot-status ${statusClass}">
                        <i data-lucide="${s.status === 'COMPLETED' ? 'check-circle' : s.status === 'IN_PROGRESS' ? 'loader' : 'x-circle'}" style="width:14px; height:14px;"></i>
                        ${statusLabel}
                    </span>
                </div>
                <div class="requal-sc-stats">
                    <div class="requal-sc-stat">
                        <span class="requal-sc-stat-val">${totalPairs}</span>
                        <span class="requal-sc-stat-label">Pairs</span>
                    </div>
                    <div class="requal-sc-stat">
                        <span class="requal-sc-stat-val">${completedPairs}</span>
                        <span class="requal-sc-stat-label">Compared</span>
                    </div>
                    <div class="requal-sc-stat">
                        <span class="requal-sc-stat-val requal-stat-pass">${passedCount}</span>
                        <span class="requal-sc-stat-label">Passed</span>
                    </div>
                </div>
                <div class="requal-sc-actions">
                    ${s.status === 'COMPLETED' ? `
                    <button class="requal-sc-view-btn" onclick="viewRequalResults(${s.id})">
                        <i data-lucide="eye" style="width:16px; height:16px;"></i>
                        View Results
                    </button>` : ''}
                    <button class="requal-sc-delete-btn" onclick="deleteRequalSession(${s.id})">
                        <i data-lucide="trash-2" style="width:14px; height:14px;"></i>
                    </button>
                </div>
            </div>`;
        });

        container.innerHTML = html;
        lucide.createIcons();
    } catch (err) {
        console.error('Failed to load requal sessions:', err);
        container.innerHTML = '<div style="padding:24px;text-align:center;color:var(--danger);">Failed to load sessions.</div>';
    }
}

async function deleteRequalSession(sessionId) {
    if (!confirm('Delete this session and all its results?')) return;
    try {
        await fetch(`/api/requalifications/sessions/${sessionId}`, { method: 'DELETE' });
        loadRequalSessions();
    } catch (err) {
        console.error('Failed to delete session:', err);
    }
}

// ================================================================
// NEW SESSION MODAL
// ================================================================

function showNewSessionForm() {
    const modal = document.getElementById('requalNameModal');
    const input = document.getElementById('requalSessionName');
    const errorEl = document.getElementById('requalNameError');
    modal.style.display = 'flex';
    errorEl.style.display = 'none';
    input.value = '';
    input.focus();
    lucide.createIcons();
}

function hideNewSessionForm() {
    document.getElementById('requalNameModal').style.display = 'none';
}

function validateSessionName(name) {
    if (!name || !name.trim()) return 'Session name is required';
    const lower = name.toLowerCase();

    // Check for month
    const hasMonth = MONTHS.some(m => lower.includes(m));
    if (!hasMonth) return 'Name must include a month (e.g., January, Feb, March…)';

    // Check for year (4-digit number between 2020-2099)
    const yearMatch = name.match(/20[2-9][0-9]/);
    if (!yearMatch) return 'Name must include a year (e.g., 2025, 2026…)';

    return null; // Valid
}

async function startNewSession() {
    const input = document.getElementById('requalSessionName');
    const errorEl = document.getElementById('requalNameError');
    const errorText = document.getElementById('requalNameErrorText');
    const name = input.value.trim();

    const validationError = validateSessionName(name);
    if (validationError) {
        errorText.textContent = validationError;
        errorEl.style.display = 'flex';
        lucide.createIcons();
        input.focus();
        return;
    }

    errorEl.style.display = 'none';
    requalCurrentSessionName = name;

    // Show the active session view
    hideNewSessionForm();
    showActiveSession(name);
}

// Listen for Enter key on session name input
document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('requalSessionName');
    if (input) {
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') startNewSession();
        });
    }
});

// ================================================================
// ACTIVE SESSION (UPLOAD + COMPARE)
// ================================================================

function showActiveSession(name) {
    document.getElementById('requalSessionList').style.display = 'none';
    document.getElementById('requalViewResults').style.display = 'none';
    document.getElementById('requalActiveSession').style.display = 'block';
    document.getElementById('requalActiveSessionName').textContent = name;

    // Reset slots
    requalNextSlotIndex = 0;
    const container = document.getElementById('requalSlots');
    container.innerHTML = '';
    addRequalSlot(); // Add first default slot
    updateRequalCounts();

    // Hide progress
    document.getElementById('requalProgressSection').style.display = 'none';

    lucide.createIcons();
}

function backToSessionList() {
    document.getElementById('requalActiveSession').style.display = 'none';
    document.getElementById('requalViewResults').style.display = 'none';
    document.getElementById('requalSessionList').style.display = 'block';
    requalCurrentSessionId = null;
    loadRequalSessions();
}

// ================================================================
// SLOT MANAGEMENT
// ================================================================

function createSlotHTML(idx, pairNum) {
    return `
    <div class="requal-slot" data-slot-index="${idx}" id="requalSlot_${idx}" style="animation: slideDown 0.3s ease;">
        <div class="requal-slot-header">
            <div class="requal-slot-number">
                <span class="slot-badge">Pair ${pairNum}</span>
                <span class="slot-status" id="slotStatus_${idx}">
                    <i data-lucide="clock" style="width:14px; height:14px;"></i>
                    Waiting
                </span>
            </div>
            <button class="requal-slot-remove" onclick="removeRequalSlot(${idx})" title="Remove this pair">
                <i data-lucide="trash-2" style="width:16px; height:16px;"></i>
            </button>
        </div>
        <div class="requal-slot-body">
            <div class="requal-upload" id="reqDrop_${idx}_orig" onclick="document.getElementById('reqFile_${idx}_orig').click()">
                <div class="requal-upload-icon original">
                    <i data-lucide="file-minus" style="width:20px; height:20px;"></i>
                </div>
                <div class="requal-upload-text">
                    <strong>Original PDF</strong>
                    <span>Drop or browse</span>
                </div>
                <div class="requal-file-info" id="reqInfo_${idx}_orig"></div>
            </div>
            <input type="file" id="reqFile_${idx}_orig" accept=".pdf" hidden onchange="handleRequalFile(${idx}, 'orig', this)" />

            <div class="requal-equals">
                <i data-lucide="equal" style="width:24px; height:24px;"></i>
            </div>

            <div class="requal-upload" id="reqDrop_${idx}_rev" onclick="document.getElementById('reqFile_${idx}_rev').click()">
                <div class="requal-upload-icon revised">
                    <i data-lucide="file-plus" style="width:20px; height:20px;"></i>
                </div>
                <div class="requal-upload-text">
                    <strong>Revised PDF</strong>
                    <span>Drop or browse</span>
                </div>
                <div class="requal-file-info" id="reqInfo_${idx}_rev"></div>
            </div>
            <input type="file" id="reqFile_${idx}_rev" accept=".pdf" hidden onchange="handleRequalFile(${idx}, 'rev', this)" />
        </div>
    </div>`;
}

function addRequalSlot() {
    const idx = requalNextSlotIndex++;
    const container = document.getElementById('requalSlots');
    const pairNum = container.children.length + 1;
    container.insertAdjacentHTML('beforeend', createSlotHTML(idx, pairNum));
    lucide.createIcons();
    setupRequalDragDrop(idx);
    updateRequalCounts();
}

function removeRequalSlot(idx) {
    const slotEl = document.getElementById(`requalSlot_${idx}`);
    if (!slotEl) return;

    const allSlots = document.querySelectorAll('.requal-slot');
    if (allSlots.length <= 1) return;

    slotEl.style.animation = 'slideUp 0.25s ease forwards';
    slotEl.style.overflow = 'hidden';
    setTimeout(() => {
        slotEl.remove();
        renumberSlots();
        updateRequalCounts();
    }, 250);
}

function renumberSlots() {
    document.querySelectorAll('.requal-slot').forEach((slot, i) => {
        const badge = slot.querySelector('.slot-badge');
        if (badge) badge.textContent = `Pair ${i + 1}`;
    });
}

function resetAllRequalSlots() {
    const container = document.getElementById('requalSlots');
    requalNextSlotIndex = 0;
    container.innerHTML = '';
    addRequalSlot();
    document.getElementById('requalProgressSection').style.display = 'none';
}

// ================================================================
// FILE HANDLING
// ================================================================

function handleRequalFile(idx, type, inputEl) {
    const file = inputEl.files[0];
    if (!file) return;

    const dropEl = document.getElementById(`reqDrop_${idx}_${type}`);
    const infoEl = document.getElementById(`reqInfo_${idx}_${type}`);

    if (dropEl) dropEl.classList.add('has-file');

    const size = file.size >= 1048576
        ? (file.size / 1048576).toFixed(1) + ' MB'
        : (file.size / 1024).toFixed(1) + ' KB';

    if (infoEl) {
        infoEl.innerHTML = `
        <div class="requal-file-chip" onclick="event.stopPropagation();">
            <i data-lucide="file-text" style="width:14px; height:14px; flex-shrink:0;"></i>
            <span class="requal-file-name">${file.name}</span>
            <span class="requal-file-size">${size}</span>
            <span class="requal-file-remove" onclick="removeRequalFile(${idx}, '${type}', event)">
                <i data-lucide="x" style="width:12px; height:12px;"></i>
            </span>
        </div>`;
    }

    if (dropEl) {
        dropEl.dataset.hasFile = 'true';
        dropEl._file = file;
    }

    lucide.createIcons();
    updateRequalCounts();
}

function removeRequalFile(idx, type, event) {
    event.stopPropagation();
    const dropEl = document.getElementById(`reqDrop_${idx}_${type}`);
    const infoEl = document.getElementById(`reqInfo_${idx}_${type}`);
    const fileInput = document.getElementById(`reqFile_${idx}_${type}`);

    if (dropEl) { dropEl.classList.remove('has-file'); dropEl.dataset.hasFile = 'false'; dropEl._file = null; }
    if (infoEl) infoEl.innerHTML = '';
    if (fileInput) fileInput.value = '';
    updateRequalCounts();
}

// ================================================================
// DRAG & DROP
// ================================================================

function setupRequalDragDrop(idx) {
    ['orig', 'rev'].forEach(type => {
        const dropEl = document.getElementById(`reqDrop_${idx}_${type}`);
        if (!dropEl) return;

        dropEl.addEventListener('dragover', (e) => { e.preventDefault(); dropEl.classList.add('dragover'); });
        dropEl.addEventListener('dragleave', () => { dropEl.classList.remove('dragover'); });
        dropEl.addEventListener('drop', (e) => {
            e.preventDefault();
            dropEl.classList.remove('dragover');
            const f = Array.from(e.dataTransfer.files).find(f =>
                f.name.toLowerCase().endsWith('.pdf') || f.type === 'application/pdf');
            if (f) {
                dropEl.classList.add('has-file');
                dropEl.dataset.hasFile = 'true';
                dropEl._file = f;

                const infoEl = document.getElementById(`reqInfo_${idx}_${type}`);
                const size = f.size >= 1048576 ? (f.size / 1048576).toFixed(1) + ' MB' : (f.size / 1024).toFixed(1) + ' KB';
                if (infoEl) {
                    infoEl.innerHTML = `
                    <div class="requal-file-chip" onclick="event.stopPropagation();">
                        <i data-lucide="file-text" style="width:14px; height:14px; flex-shrink:0;"></i>
                        <span class="requal-file-name">${f.name}</span>
                        <span class="requal-file-size">${size}</span>
                        <span class="requal-file-remove" onclick="removeRequalFile(${idx}, '${type}', event)">
                            <i data-lucide="x" style="width:12px; height:12px;"></i>
                        </span>
                    </div>`;
                }
                lucide.createIcons();
                updateRequalCounts();
            }
        });
    });
}

// ================================================================
// COUNTS & UI UPDATES
// ================================================================

function updateRequalCounts() {
    const slots = document.querySelectorAll('#requalSlots .requal-slot');
    let totalPairs = slots.length;
    let readyPairs = 0;

    slots.forEach(slot => {
        const idx = slot.dataset.slotIndex;
        const origDrop = document.getElementById(`reqDrop_${idx}_orig`);
        const revDrop = document.getElementById(`reqDrop_${idx}_rev`);
        if (origDrop && origDrop.dataset.hasFile === 'true' && revDrop && revDrop.dataset.hasFile === 'true') {
            readyPairs++;
        }
    });

    const pairCountEl = document.getElementById('requalPairCount');
    const readyCountEl = document.getElementById('requalReadyCount');
    const runBtn = document.getElementById('requalRunBtn');

    if (pairCountEl) pairCountEl.textContent = `${totalPairs} pair${totalPairs !== 1 ? 's' : ''}`;
    if (readyCountEl) readyCountEl.textContent = `${readyPairs} ready`;
    if (runBtn) runBtn.disabled = readyPairs === 0;
}

// ================================================================
// RUN ALL COMPARISONS (Batch)
// ================================================================

async function runAllRequalifications() {
    const slots = document.querySelectorAll('#requalSlots .requal-slot');
    const runBtn = document.getElementById('requalRunBtn');
    const runBtnText = document.getElementById('requalRunBtnText');
    const spinner = document.getElementById('requalSpinner');
    const progressSection = document.getElementById('requalProgressSection');
    const progressFill = document.getElementById('requalProgressFill');
    const progressText = document.getElementById('requalProgressText');

    // Gather ready pairs
    const pairs = [];
    let pairIdx = 0;
    slots.forEach(slot => {
        const idx = slot.dataset.slotIndex;
        const origDrop = document.getElementById(`reqDrop_${idx}_orig`);
        const revDrop = document.getElementById(`reqDrop_${idx}_rev`);
        if (origDrop && origDrop._file && revDrop && revDrop._file) {
            pairs.push({ idx, pairIndex: pairIdx++, orig: origDrop._file, rev: revDrop._file });
        }
    });

    if (pairs.length === 0) return;

    // 1. Create DB session
    let sessionId;
    try {
        const createRes = await fetch('/api/requalifications/sessions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: requalCurrentSessionName, pair_count: pairs.length })
        });
        if (!createRes.ok) throw new Error('Failed to create session');
        const sessionData = await createRes.json();
        sessionId = sessionData.id;
        requalCurrentSessionId = sessionId;
    } catch (err) {
        alert('Failed to create session: ' + err.message);
        return;
    }

    // 2. UI: disable & show progress
    runBtn.disabled = true;
    runBtnText.textContent = 'Running...';
    spinner.style.display = 'block';
    progressSection.style.display = 'block';
    progressFill.style.width = '0%';
    progressText.textContent = `0 / ${pairs.length} completed`;

    let completed = 0;
    let successes = 0;
    let failures = 0;

    // Helper: Process a single pair
    const processPair = async (pair) => {
        const statusEl = document.getElementById(`slotStatus_${pair.idx}`);

        if (statusEl) {
            statusEl.innerHTML = '<i data-lucide="loader" style="width:14px; height:14px;" class="requal-spin-icon"></i> Running...';
            statusEl.className = 'slot-status running';
        }
        lucide.createIcons();

        let pairStatus = 'FAILED';
        let comparisonId = null;
        let totalPages = 0;

        try {
            const formData = new FormData();
            formData.append('original', pair.orig);
            formData.append('revised', pair.rev);

            const resp = await fetch('/api/compare', { method: 'POST', body: formData });
            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || 'Comparison failed');
            }

            const data = await resp.json();
            comparisonId = data.comparison_id; // Get ID from backend
            totalPages = data.total_pages || 0;
            const passed = data.pages ? data.pages.filter(p => p.status === 'PASS').length : 0;
            pairStatus = passed === totalPages && totalPages > 0 ? 'PASS' : 'CHANGES FOUND';
            successes++;

            if (statusEl) {
                statusEl.innerHTML = `<i data-lucide="check-circle" style="width:14px; height:14px;"></i> Done — ${passed}/${totalPages} pages match`;
                statusEl.className = 'slot-status success';
            }
        } catch (err) {
            failures++;
            pairStatus = 'FAILED';
            if (statusEl) {
                statusEl.innerHTML = `<i data-lucide="x-circle" style="width:14px; height:14px;"></i> Failed: ${err.message}`;
                statusEl.className = 'slot-status error';
            }
        }

        // Save pair result to DB
        try {
            const pairForm = new FormData();
            pairForm.append('pair_index', pair.pairIndex);
            pairForm.append('original_filename', pair.orig.name);
            pairForm.append('revised_filename', pair.rev.name);
            pairForm.append('total_pages', totalPages);
            pairForm.append('status', pairStatus);

            // Use comparison_id to link data instead of sending huge JSON
            if (comparisonId) {
                pairForm.append('comparison_id', comparisonId);
            }

            await fetch(`/api/requalifications/sessions/${sessionId}/pair`, {
                method: 'POST',
                body: pairForm
            });
        } catch (err) {
            console.error('Failed to save pair result:', err);
        }

        completed++;
        const pct = Math.round((completed / pairs.length) * 100);
        progressFill.style.width = pct + '%';
        progressText.textContent = `${completed} / ${pairs.length} completed`;
        lucide.createIcons();
    };

    // 3. Run with Concurrency Limit (Pool)
    const CONCURRENCY_LIMIT = 4;
    let poolIndex = 0;

    // Worker function that picks tasks from the list
    const runWorker = async () => {
        while (poolIndex < pairs.length) {
            const pair = pairs[poolIndex++];
            await processPair(pair);
        }
    };

    // Start initial workers
    const workers = [];
    const workerCount = Math.min(CONCURRENCY_LIMIT, pairs.length);
    for (let i = 0; i < workerCount; i++) {
        workers.push(runWorker());
    }

    // Wait for all workers to finish
    await Promise.all(workers);

    // 5. Update session status
    const finalStatus = failures === pairs.length ? 'FAILED' : 'COMPLETED';
    try {
        await fetch(`/api/requalifications/sessions/${sessionId}/status?status=${finalStatus}`, {
            method: 'PUT'
        });
    } catch (err) {
        console.error('Failed to update session status:', err);
    }

    // Done
    runBtn.style.display = 'none'; // Hide run button

    // Show View Results button
    const actionContainer = document.querySelector('.requal-actions-buttons');
    const viewBtn = document.createElement('button');
    viewBtn.className = 'btn-compare';
    viewBtn.innerHTML = '<i data-lucide="eye" style="width:18px; height:18px;"></i> View Results';
    viewBtn.onclick = () => viewRequalResults(sessionId);
    actionContainer.appendChild(viewBtn);

    spinner.style.display = 'none';
    progressText.textContent = `All done! ${successes} succeeded, ${failures} failed`;

    // Send desktop notification
    if (typeof NotificationManager !== 'undefined') {
        NotificationManager.sendNotification(
            'Batch Comparison Completed',
            `${pairs.length} pairs processed. ${successes} succeeded, ${failures} failed.`
        );
    }

    lucide.createIcons();
}

// ================================================================
// VIEW RESULTS
// ================================================================

async function viewRequalResults(sessionId) {
    document.getElementById('requalSessionList').style.display = 'none';
    document.getElementById('requalActiveSession').style.display = 'none';
    document.getElementById('requalViewResults').style.display = 'block';

    const nameEl = document.getElementById('requalResultsSessionName');
    const badgeEl = document.getElementById('requalResultsBadge');
    const listEl = document.getElementById('requalPairsList');
    const contentEl = document.getElementById('requalResultsContent');

    nameEl.textContent = 'Loading...';
    listEl.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-muted);">Loading results...</div>';
    contentEl.style.display = 'none';
    contentEl.innerHTML = '';

    try {
        const res = await fetch(`/api/requalifications/sessions/${sessionId}`);
        if (!res.ok) throw new Error('Failed to load session');
        const session = await res.json();

        nameEl.textContent = session.name;
        badgeEl.textContent = session.status === 'COMPLETED' ? 'Completed' : session.status;
        badgeEl.className = 'slot-badge ' + (session.status === 'COMPLETED' ? 'badge-success' : '');

        if (!session.pairs || session.pairs.length === 0) {
            listEl.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-muted);">No pair results found.</div>';
            lucide.createIcons();
            return;
        }

        // Store session data for expanding pairs
        window._requalSessionData = session;

        // Build pairs list
        let listHtml = '';
        session.pairs.forEach((pair, i) => {
            const statusIcon = pair.status === 'PASS' || pair.status === 'NO CHANGES'
                ? 'check-circle' : pair.status === 'FAILED' ? 'x-circle' : 'alert-triangle';
            const statusClass = pair.status === 'PASS' || pair.status === 'NO CHANGES'
                ? 'requal-pl-pass' : pair.status === 'FAILED' ? 'requal-pl-fail' : 'requal-pl-warn';

            const data = pair.result_data;
            const totalPages = data ? (data.total_pages || (data.pages || []).length) : 0;
            const textChanges = data ? (data.pages || []).reduce((s, p) => s + (p.text_changes_count || 0), 0) : 0;

            listHtml += `
            <div class="requal-pair-row ${statusClass}" id="requal-pair-row-${i}">
                <div class="requal-pair-row-left">
                    <div class="requal-pair-row-index">
                        <i data-lucide="${statusIcon}" style="width:18px; height:18px;"></i>
                    </div>
                    <div class="requal-pair-row-info">
                        <div class="requal-pair-row-label">Pair ${i + 1}</div>
                        <div class="requal-pair-row-files">
                            <span class="requal-pr-orig">${pair.original_filename}</span>
                            <i data-lucide="arrow-right" style="width:12px; height:12px; flex-shrink:0; color:var(--text-muted);"></i>
                            <span class="requal-pr-rev">${pair.revised_filename}</span>
                        </div>
                    </div>
                </div>
                <div class="requal-pair-row-right">
                    <div class="requal-pair-row-meta">
                        <span>${totalPages} pages</span>
                        <span>${textChanges} changes</span>
                    </div>
                    <button class="requal-pair-expand-btn" title="View Results" onclick="expandRequalPairResult(${i})">
                        <i data-lucide="eye" style="width:18px; height:18px;"></i>
                    </button>
                </div>
            </div>`;
        });
        listEl.innerHTML = listHtml;
        lucide.createIcons();

    } catch (err) {
        console.error('Failed to load requal results:', err);
        listEl.innerHTML = '<div style="padding:40px;text-align:center;color:var(--danger);">Failed to load results.</div>';
    }
}

function expandRequalPairResult(pairIndex) {
    const session = window._requalSessionData;
    if (!session || !session.pairs[pairIndex]) return;

    const listEl = document.getElementById('requalPairsList');
    const contentEl = document.getElementById('requalResultsContent');

    // Highlight active row
    document.querySelectorAll('.requal-pair-row').forEach(r => r.classList.remove('requal-pair-row-active'));
    const activeRow = document.getElementById(`requal-pair-row-${pairIndex}`);
    if (activeRow) activeRow.classList.add('requal-pair-row-active');

    // Show results container with a back button
    contentEl.style.display = 'block';

    // Prepend a back button that collapses results and scrolls back to the list
    const backHtml = `
    <div class="requal-results-back-bar">
        <button class="requal-back-btn" onclick="collapseRequalPairResult()">
            <i data-lucide="arrow-left" style="width:16px; height:16px;"></i>
            Back to Pairs List
        </button>
        <span class="requal-results-back-label">Pair ${pairIndex + 1}: ${session.pairs[pairIndex].original_filename} vs ${session.pairs[pairIndex].revised_filename}</span>
    </div>`;

    // Create a temp container for the pair result
    const tempDiv = document.createElement('div');
    renderRequalPairResult(session.pairs[pairIndex], tempDiv);

    contentEl.innerHTML = backHtml + tempDiv.innerHTML;
    lucide.createIcons();

    // Scroll to the results
    contentEl.scrollIntoView({ behavior: 'smooth', block: 'start' });

    // Attach collapsible section handlers
    contentEl.querySelectorAll('.page-section-header').forEach(h => {
        h.addEventListener('click', () => {
            h.classList.toggle('collapsed');
            const body = h.nextElementSibling;
            if (body) body.classList.toggle('collapsed');
        });
    });

    // Attach chat handlers
    const chatInput = contentEl.querySelector('#chatInput');
    const chatSendBtn = contentEl.querySelector('#chatSendBtn');
    if (chatInput && chatSendBtn) {
        chatSendBtn.onclick = () => sendChatMessage();
        chatInput.onkeydown = (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendChatMessage();
            }
        };
    }
}

function collapseRequalPairResult() {
    const contentEl = document.getElementById('requalResultsContent');
    contentEl.style.display = 'none';
    contentEl.innerHTML = '';

    // Remove active highlight
    document.querySelectorAll('.requal-pair-row').forEach(r => r.classList.remove('requal-pair-row-active'));

    // Scroll back to the list
    const listEl = document.getElementById('requalPairsList');
    if (listEl) listEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderRequalPairResult(pair, container) {
    if (!pair.result_data) {
        container.innerHTML = `
        <div class="requal-pair-result-error">
            <i data-lucide="alert-triangle" style="width:24px; height:24px;"></i>
            <h4>No result data available for this pair</h4>
            <p>${pair.original_filename} ↔ ${pair.revised_filename}</p>
            <p>Status: ${pair.status}</p>
        </div>`;
        return;
    }

    const data = pair.result_data;
    const pages = data.pages || [];
    const total = data.total_pages || pages.length;
    const passed = pages.filter(p => p.status === 'PASS').length;
    const changed = pages.filter(p => p.status !== 'PASS').length;
    const avgConf = pages.length > 0
        ? (pages.reduce((s, p) => s + (p.confidence || 0), 0) / pages.length * 100).toFixed(1)
        : '0';
    const totalTextChanges = pages.reduce((s, p) => s + (p.text_changes_count || 0), 0);
    const visualDiffPages = pages.filter(p =>
        p.disposition === 'added' || p.disposition === 'removed' ||
        (p.image_similarity !== undefined && p.image_similarity < 0.999)
    ).length;

    const pageCountNote = (data.original_pages || total) !== (data.revised_pages || total)
        ? `<div style="font-size:.82rem;color:var(--warning);margin-top:8px;display:flex;align-items:center;gap:6px;">
        <i data-lucide="alert-circle" style="width:14px;height:14px;"></i>
        Page count differs: Original has ${data.original_pages || total}, Revised has ${data.revised_pages || total}
       </div>`
        : '';

    // We set a global variable for the chat to access the current result context
    // This reuses the logic in results.js for the AI chat
    window.lastResult = data;

    let html = `
    <!-- Summary -->
    <div class="result-summary">
        <div class="result-summary-top">
            <h3>
                <i data-lucide="git-compare" style="width:20px;height:20px;display:inline;vertical-align:middle;margin-right:6px;"></i>
                ${pair.original_filename} vs ${pair.revised_filename}
            </h3>
            <div class="result-actions">
                ${data.report_url ? `
                <a href="${data.report_url}" download="diff_report.pdf">
                    <i data-lucide="download" style="width:14px;height:14px;"></i>
                    Download Report
                </a>` : ''}
            </div>
        </div>
        <div class="result-stats">
            <div class="r-stat"><div class="r-val">${total}</div><div class="r-lbl">Total Pages</div></div>
            <div class="r-stat"><div class="r-val" style="color:var(--success);">${passed}</div><div class="r-lbl">Matches</div></div>
            <div class="r-stat"><div class="r-val" style="color:var(--danger);">${changed}</div><div class="r-lbl">Changed</div></div>
            <div class="r-stat"><div class="r-val">${avgConf}%</div><div class="r-lbl">AI Confidence</div></div>
            <div class="r-stat"><div class="r-val">${totalTextChanges}</div><div class="r-lbl">Text Changes</div></div>
        </div>
        ${pageCountNote}
    </div>

    <!-- Centralized Tabs (Scoped to Requal) -->
    <div class="central-tabs" id="requalTabs_${pair.id}">
        <div class="central-tab-nav">
            <button class="central-tab-btn active" onclick="switchRequalTab('textdiff', this)">
                <i data-lucide="code-2" style="width:16px;height:16px;"></i>
                Text Changes
                <span class="ctab-count">${totalTextChanges}</span>
            </button>
            <button class="central-tab-btn" onclick="switchRequalTab('visualdiff', this)">
                <i data-lucide="scan-search" style="width:16px;height:16px;"></i>
                Visual Differences
                <span class="ctab-count">${visualDiffPages}</span>
            </button>
            <button class="central-tab-btn" onclick="switchRequalTab('aichat', this)">
                <i data-lucide="message-circle" style="width:16px;height:16px;"></i>
                AI Assistant
            </button>
        </div>

        <!-- ========== TEXT CHANGES TAB ========== -->
        <div class="central-tab-panel active" id="req_ctab_textdiff">
            ${typeof renderAllTextDiffs === 'function' ? renderAllTextDiffs(pages, data) : 'Error: renderAllTextDiffs not found'}
        </div>

        <!-- ========== VISUAL DIFF TAB ========== -->
        <div class="central-tab-panel" id="req_ctab_visualdiff">
            ${typeof renderAllVisualDiffs === 'function' ? renderAllVisualDiffs(pages, 'req_') : 'Error: renderAllVisualDiffs not found'}
        </div>

        <!-- ========== AI CHAT TAB ========== -->
        <div class="central-tab-panel" id="req_ctab_aichat">
            ${typeof renderAIChatPanel === 'function' ? renderAIChatPanel() : 'Error: renderAIChatPanel not found'}
        </div>
    </div>`;

    container.innerHTML = html;

    // Attach event listeners for collapsible page sections (reusing logic from results.js)
    container.querySelectorAll('.page-section-header').forEach(h => {
        h.addEventListener('click', () => {
            h.classList.toggle('collapsed');
            const body = h.nextElementSibling;
            if (body) body.classList.toggle('collapsed');
        });
    });

    // Attach chat handlers for this specific view
    const chatInput = container.querySelector('#chatInput');
    const chatSendBtn = container.querySelector('#chatSendBtn');
    if (chatInput && chatSendBtn) {
        // We'll use the global sendChatMessage from results.js which uses document.getElementById
        // This is a bit risky if IDs are duplicated. 
        // results.js uses IDs: chatInput, chatSendBtn, chatMessages.
        // Since we are replacing the innerHTML, if the main results view is hidden, this should be fine.
        // But to be safe, we should ensure only one view is active.

        chatSendBtn.onclick = () => sendChatMessage();
        chatInput.onkeydown = (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendChatMessage();
            }
        };
    }
}

// Tab switcher for Requalification view
function switchRequalTab(tabName, el) {
    const wrapper = el.closest('.central-tabs');
    wrapper.querySelectorAll('.central-tab-panel').forEach(p => p.classList.remove('active'));
    wrapper.querySelectorAll('.central-tab-btn').forEach(b => b.classList.remove('active'));

    // wrapper.querySelector(`#req_ctab_${tabName}`).classList.add('active'); // Scope search to wrapper
    // or by ID directly if unique
    const target = document.getElementById('req_ctab_' + tabName);
    if (target) target.classList.add('active');

    el.classList.add('active');
    lucide.createIcons();

    if (tabName === 'aichat') {
        const msgs = document.getElementById('chatMessages');
        if (msgs) setTimeout(() => msgs.scrollTop = msgs.scrollHeight, 100);
    }
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ================================================================
// AUTO-LOAD ON VIEW SWITCH
// ================================================================
// Called from switchView in app.js when the view changes to requalifications
// We hook into this by checking in a MutationObserver or overriding
// For simplicity, we'll use a periodic check or add to switchView

// This function is called when navigating to requalifications view
function loadRequalifications() {
    // Show session list by default
    document.getElementById('requalSessionList').style.display = 'block';
    document.getElementById('requalActiveSession').style.display = 'none';
    document.getElementById('requalViewResults').style.display = 'none';
    loadRequalSessions();
}
