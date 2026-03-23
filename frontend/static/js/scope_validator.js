// ================================================================
// scope_validator.js — Scope & Deliverables Validator Logic
// Handles: File upload, scope file import, API call, results,
//          highlight hover popups, validation history
// ================================================================

// ── State ───────────────────────────────────────────────────────
let svSelectedFile = null;
let svScopeFile = null;

// ── DOM Ready Setup ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const textarea = document.getElementById('svScopeInput');
    const fileInput = document.getElementById('svFileInput');
    const uploadBox = document.getElementById('svUploadBox');
    const scopeFileInput = document.getElementById('svScopeFileInput');

    // Live item counter
    if (textarea) {
        textarea.addEventListener('input', svUpdateItemCount);
    }

    // Validation plan file input
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                svHandleFile(e.target.files[0]);
            }
        });
    }

    // Scope support file input
    if (scopeFileInput) {
        scopeFileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                svHandleScopeFile(e.target.files[0]);
            }
        });
    }

    // Drag & drop for validation plan
    if (uploadBox) {
        uploadBox.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadBox.classList.add('dragover');
        });
        uploadBox.addEventListener('dragleave', () => {
            uploadBox.classList.remove('dragover');
        });
        uploadBox.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadBox.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                svHandleFile(e.dataTransfer.files[0]);
            }
        });
    }

    // Load history
    svLoadHistory();
});

// ── Item Counter ────────────────────────────────────────────────
function svUpdateItemCount() {
    const textarea = document.getElementById('svScopeInput');
    const countEl = document.getElementById('svItemCount');
    if (!textarea || !countEl) return;

    const items = textarea.value.split('\n').filter(l => l.trim().length > 0);
    countEl.textContent = `${items.length} item${items.length !== 1 ? 's' : ''}`;

    svUpdateValidateButton();
}

// ════════════════════════════════════════════════════════════════
//  SCOPE FILE IMPORT (Word, PDF, TXT, Image)
// ════════════════════════════════════════════════════════════════

function svHandleScopeFile(file) {
    const allowed = ['.docx', '.pdf', '.txt', '.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();

    if (!allowed.includes(ext)) {
        alert('Unsupported file type. Supported: Word, PDF, Text, Images (PNG/JPG)');
        return;
    }

    svScopeFile = file;

    // Show file badge
    const fileInfo = document.getElementById('svScopeFileInfo');
    const fileName = document.getElementById('svScopeFileName');
    if (fileInfo) fileInfo.style.display = 'flex';
    if (fileName) fileName.textContent = file.name;

    svUpdateValidateButton();
    lucide.createIcons();
}

function svRemoveScopeFile() {
    svScopeFile = null;
    const fileInfo = document.getElementById('svScopeFileInfo');
    const fileInput = document.getElementById('svScopeFileInput');
    if (fileInfo) fileInfo.style.display = 'none';
    if (fileInput) fileInput.value = '';
    svUpdateValidateButton();
    lucide.createIcons();
}

// ════════════════════════════════════════════════════════════════
//  VALIDATION PLAN FILE HANDLING
// ════════════════════════════════════════════════════════════════

function svHandleFile(file) {
    if (!file.name.toLowerCase().endsWith('.docx') && !file.name.toLowerCase().endsWith('.pdf')) {
        alert('Please upload a .docx or .pdf document');
        return;
    }

    svSelectedFile = file;

    const uploadBox = document.getElementById('svUploadBox');
    const fileInfo = document.getElementById('svFileInfo');
    const fileName = document.getElementById('svFileName');
    const fileSize = document.getElementById('svFileSize');

    if (uploadBox) uploadBox.style.display = 'none';
    if (fileInfo) fileInfo.style.display = 'flex';
    if (fileName) fileName.textContent = file.name;
    if (fileSize) fileSize.textContent = svFormatSize(file.size);

    svUpdateValidateButton();
    lucide.createIcons();
}

function svRemoveFile() {
    svSelectedFile = null;

    const uploadBox = document.getElementById('svUploadBox');
    const fileInfo = document.getElementById('svFileInfo');
    const fileInput = document.getElementById('svFileInput');

    if (uploadBox) uploadBox.style.display = '';
    if (fileInfo) fileInfo.style.display = 'none';
    if (fileInput) fileInput.value = '';

    svUpdateValidateButton();
    lucide.createIcons();
}

function svFormatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ── Validate Button State ───────────────────────────────────────
function svUpdateValidateButton() {
    const btn = document.getElementById('svValidateBtn');
    if (!btn) return;

    const textarea = document.getElementById('svScopeInput');
    const hasTextItems = textarea && textarea.value.split('\n').some(l => l.trim().length > 0);
    const hasScopeFile = svScopeFile !== null;
    const hasValidationPlan = svSelectedFile !== null;

    // Either text items OR scope file must be provided, PLUS the validation plan
    btn.disabled = !((hasTextItems || hasScopeFile) && hasValidationPlan);
}

// ════════════════════════════════════════════════════════════════
//  RUN VALIDATION
// ════════════════════════════════════════════════════════════════

async function svRunValidation() {
    const textarea = document.getElementById('svScopeInput');
    const btn = document.getElementById('svValidateBtn');
    const btnText = document.getElementById('svValidateBtnText');
    const spinner = document.getElementById('svSpinner');

    if (!svSelectedFile) return;

    const items = textarea
        ? textarea.value.split('\n').filter(l => l.trim().length > 0).map(l => l.trim())
        : [];

    // Must have at least one source of scope items
    if (items.length === 0 && !svScopeFile) {
        alert('Please provide scope items via text or upload a support document.');
        return;
    }

    btn.disabled = true;
    btnText.textContent = 'Analyzing...';
    spinner.style.display = 'inline-block';

    try {
        const formData = new FormData();
        formData.append('document', svSelectedFile);
        formData.append('scope_items', JSON.stringify(items));

        // Attach scope support document if provided
        if (svScopeFile) {
            formData.append('scope_document', svScopeFile);
        }

        const response = await fetch('/api/scope-validator/validate', {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Server error (${response.status})`);
        }

        const data = await response.json();
        svRenderResults(data);

        // Refresh history
        svLoadHistory();

    } catch (err) {
        alert('Validation failed: ' + err.message);
        console.error('[ScopeValidator] Error:', err);
    } finally {
        btn.disabled = false;
        btnText.textContent = 'Validate Coverage';
        spinner.style.display = 'none';
        svUpdateValidateButton();
    }
}

// ════════════════════════════════════════════════════════════════
//  RENDER RESULTS
// ════════════════════════════════════════════════════════════════

function svRenderResults(data) {
    document.getElementById('svInputSection').style.display = 'none';
    document.getElementById('svResultsSection').style.display = 'block';

    // Summary
    document.getElementById('svCoveragePct').textContent = data.coverage_pct + '%';
    document.getElementById('svMatchedCount').textContent = data.matched_count;
    document.getElementById('svUnmatchedCount').textContent = (data.total_count - data.matched_count);
    document.getElementById('svResultDocName').textContent = data.document_filename;

    // Show source summary if available
    const sourceBadge = document.getElementById('svSourceSummary');
    if (sourceBadge && data.source_summary) {
        sourceBadge.textContent = data.source_summary;
        sourceBadge.style.display = 'inline-block';
    } else if (sourceBadge) {
        sourceBadge.style.display = 'none';
    }

    // Connect Delete Button if record_id is present
    const deleteBtn = document.getElementById('svResultDeleteBtn');
    if (deleteBtn) {
        if (data.record_id) {
            deleteBtn.style.display = 'flex';
            deleteBtn.onclick = (e) => svDeleteHistoryRecord(e, data.record_id, true);
        } else {
            deleteBtn.style.display = 'none';
        }
    }

    // Coverage ring animation
    const ringFill = document.getElementById('svRingFill');
    if (ringFill) {
        ringFill.setAttribute('stroke-dasharray', '0, 100');
        setTimeout(() => {
            ringFill.setAttribute('stroke-dasharray', `${data.coverage_pct}, 100`);
        }, 100);
    }

    // Checklist
    const checklist = document.getElementById('svChecklist');
    checklist.innerHTML = '';
    data.items.forEach((item, idx) => {
        const el = document.createElement('div');
        el.className = `sv-check-item ${item.matched ? 'matched' : 'unmatched'}`;

        // Determine match type badge
        let matchTypeBadge = '';
        if (item.matched) {
            const typeLabels = {
                'exact': { label: 'Exact', class: 'sv-match-badge exact' },
                'keyword_full': { label: 'Keyword', class: 'sv-match-badge keyword' },
                'keyword': { label: 'Keyword', class: 'sv-match-badge keyword' },
                'phrase': { label: 'Phrase', class: 'sv-match-badge phrase' },
                'tfidf_semantic': { label: 'TF-IDF', class: 'sv-match-badge tfidf' },
                'semantic': { label: 'AI Match', class: 'sv-match-badge semantic' },
                'full': { label: 'AI Match', class: 'sv-match-badge semantic' },
                'partial': { label: 'Partial', class: 'sv-match-badge partial' },
            };
            const typeInfo = typeLabels[item.match_type] || { label: 'Matched', class: 'sv-match-badge keyword' };
            matchTypeBadge = `<span class="${typeInfo.class}">${typeInfo.label}</span>`;
        }

        // Build reasoning tooltip for AI-matched items
        let reasoningHtml = '';
        if (item.reasoning) {
            reasoningHtml = `<span class="sv-check-reasoning" title="${svEscapeHtml(item.reasoning)}">
                <i data-lucide="message-circle" style="width:13px; height:13px;"></i>
                ${svEscapeHtml(item.reasoning)}
            </span>`;
        }

        el.innerHTML = `
            <div class="sv-check-icon">
                <i data-lucide="${item.matched ? 'check-circle-2' : 'x-circle'}" 
                   style="width:18px; height:18px;"></i>
            </div>
            <div class="sv-check-content">
                <span class="sv-check-text">${svEscapeHtml(item.scope_item)}</span>
                <div class="sv-check-meta">
                    ${item.matched
                ? `${matchTypeBadge}<span class="sv-check-confidence">${item.confidence}% confidence</span>`
                : '<span class="sv-check-not-found">Not found in document</span>'
            }
                </div>
                ${reasoningHtml}
            </div>
        `;

        if (item.matched) {
            el.style.cursor = 'pointer';
            el.addEventListener('click', () => {
                const highlight = document.querySelector(`.sv-highlight[data-item-index="${idx}"]`);
                if (highlight) {
                    highlight.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    highlight.classList.add('sv-highlight-flash');
                    setTimeout(() => highlight.classList.remove('sv-highlight-flash'), 1500);
                }
            });
        }

        checklist.appendChild(el);
    });

    // Document HTML (rich formatted)
    const docContent = document.getElementById('svDocumentContent');
    docContent.innerHTML = data.document_html;

    // Attach hover listeners to highlights
    svAttachHighlightListeners();

    lucide.createIcons();
}

// ════════════════════════════════════════════════════════════════
//  HIGHLIGHT HOVER POPUP
// ════════════════════════════════════════════════════════════════

function svAttachHighlightListeners() {
    const highlights = document.querySelectorAll('.sv-highlight');
    const popup = document.getElementById('svPopup');

    highlights.forEach(hl => {
        hl.addEventListener('mouseenter', (e) => {
            const scopeItem = hl.getAttribute('data-scope-item');
            const confidence = hl.getAttribute('data-confidence');

            document.getElementById('svPopupBody').textContent = scopeItem;
            document.getElementById('svPopupConfidence').textContent = `${confidence}% match confidence`;

            const confEl = document.getElementById('svPopupConfidence');
            if (parseInt(confidence) >= 80) {
                confEl.className = 'sv-popup-confidence high';
            } else if (parseInt(confidence) >= 60) {
                confEl.className = 'sv-popup-confidence medium';
            } else {
                confEl.className = 'sv-popup-confidence low';
            }

            popup.style.display = 'block';
            svPositionPopup(e, popup);

            const itemIndex = hl.getAttribute('data-item-index');
            const checkItem = document.querySelectorAll('.sv-check-item')[itemIndex];
            if (checkItem) checkItem.classList.add('sv-check-hover');
        });

        hl.addEventListener('mousemove', (e) => {
            svPositionPopup(e, popup);
        });

        hl.addEventListener('mouseleave', () => {
            popup.style.display = 'none';
            document.querySelectorAll('.sv-check-item.sv-check-hover')
                .forEach(el => el.classList.remove('sv-check-hover'));
        });
    });
}

function svPositionPopup(e, popup) {
    const offset = 16;
    let x = e.clientX + offset;
    let y = e.clientY + offset;

    const rect = popup.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    if (x + rect.width > vw - 20) {
        x = e.clientX - rect.width - offset;
    }
    if (y + rect.height > vh - 20) {
        y = e.clientY - rect.height - offset;
    }

    popup.style.left = x + 'px';
    popup.style.top = y + 'px';
}

// ════════════════════════════════════════════════════════════════
//  HISTORY
// ════════════════════════════════════════════════════════════════

async function svLoadHistory() {
    try {
        const response = await fetch('/api/scope-validator/history', { cache: 'no-store' });
        if (!response.ok) return;

        const records = await response.json();
        const list = document.getElementById('svHistoryList');
        const empty = document.getElementById('svHistoryEmpty');
        const count = document.getElementById('svHistoryCount');

        if (!list) return;

        list.innerHTML = '';

        if (!records || records.length === 0) {
            if (empty) {
                list.appendChild(empty);
                empty.style.display = 'flex';
            }
            if (count) count.textContent = '0 records';
            return;
        }

        if (count) count.textContent = `${records.length} record${records.length !== 1 ? 's' : ''}`;

        records.forEach(rec => {
            const card = document.createElement('div');
            card.className = 'sv-history-card';

            const coverageColor = rec.coverage_pct >= 80 ? 'green'
                : rec.coverage_pct >= 50 ? 'amber' : 'red';

            card.innerHTML = `
                <div class="sv-history-card-left">
                    <div class="sv-history-card-icon">
                        <i data-lucide="file-check" style="width:18px; height:18px;"></i>
                    </div>
                    <div class="sv-history-card-info">
                        <span class="sv-history-card-name">${svEscapeHtml(rec.document_filename)}</span>
                        <span class="sv-history-card-date">${svFormatDate(rec.timestamp)}</span>
                    </div>
                </div>
                <div class="sv-history-card-right">
                    <span class="sv-history-coverage-badge ${coverageColor}">
                        ${rec.coverage_pct}%
                    </span>
                    <span class="sv-history-match-info">
                        ${rec.matched_count}/${rec.total_count} matched
                    </span>
                    <button class="sv-history-view-btn" onclick="svViewHistoryRecord(${rec.id})" title="View details">
                        <i data-lucide="eye" style="width:16px; height:16px;"></i>
                    </button>
                    <button class="sv-history-delete-btn" onclick="svDeleteHistoryRecord(event, ${rec.id})" title="Delete">
                        <i data-lucide="trash-2" style="width:16px; height:16px;"></i>
                    </button>
                </div>
            `;

            list.appendChild(card);
        });

        lucide.createIcons();

    } catch (err) {
        console.error('[ScopeValidator] History load error:', err);
    }
}

async function svViewHistoryRecord(recordId) {
    try {
        const response = await fetch(`/api/scope-validator/history/${recordId}`, { cache: 'no-store' });
        if (!response.ok) {
            throw new Error('Record not found');
        }

        const record = await response.json();
        if (record.result_data) {
            record.result_data.record_id = recordId;
            svRenderResults(record.result_data);
        }
    } catch (err) {
        alert('Failed to load record: ' + err.message);
    }
}

async function svDeleteHistoryRecord(event, recordId, isFromResultsView = false) {
    if (event) {
        event.stopPropagation();
        const btn = event.currentTarget;
        if (btn) btn.disabled = true;
    }

    try {
        await fetch(`/api/scope-validator/history/${recordId}`, { method: 'DELETE' });
        svLoadHistory();
        if (isFromResultsView) {
            svBackToInput();
        }
    } catch (err) {
        console.error('[ScopeValidator] Delete error:', err);
    }
}

function svFormatDate(timestamp) {
    try {
        const d = new Date(timestamp);
        return d.toLocaleDateString('en-US', {
            month: 'short', day: 'numeric', year: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    } catch {
        return timestamp;
    }
}

// ── Back to Input ───────────────────────────────────────────────
function svBackToInput() {
    document.getElementById('svInputSection').style.display = 'block';
    document.getElementById('svResultsSection').style.display = 'none';

    // Refresh history
    svLoadHistory();
}

// ── Utility ─────────────────────────────────────────────────────
function svEscapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
