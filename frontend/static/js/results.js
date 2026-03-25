// ================================================================
// results.js — Results Rendering (Text Diff, Visual Diff, AI Chat)
// ================================================================

// ---- Utility Functions ----
function escapeHtml(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

// Simple markdown-ish rendering for AI chat replies
function renderMarkdown(text) {
    let html = escapeHtml(text);
    // Bold
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    // Bullet lists
    html = html.replace(/^[-•] (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    // Numbered lists
    html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code style="background:#F1F5F9;padding:1px 5px;border-radius:4px;font-size:.82rem;">$1</code>');
    // Line breaks
    html = html.replace(/\n/g, '<br>');
    return html;
}

// Chat history for AI conversation
let chatHistory = [];

// ================================================================
// RENDER RESULTS — Centralized Tabs with Page Headers
// ================================================================
function renderResults(data) {
    const container = document.getElementById('resultsContainer');
    chatHistory = []; // Reset chat on new comparison

    const total = data.total_pages || 0;
    const pages = data.pages || [];
    const passed = pages.filter(p => p.status === 'PASS').length;
    const changed = pages.filter(p => p.status === 'FAIL').length;
    const avgConf = pages.length > 0
        ? (pages.reduce((s, p) => s + (p.confidence || 0), 0) / pages.length * 100).toFixed(1)
        : '0';
    const totalTextChanges = pages.reduce((s, p) => s + (p.text_changes_count || 0), 0);

    const origPages = data.original_pages || total;
    const revPages = data.revised_pages || total;
    const pageCountNote = origPages !== revPages
        ? `<div style="font-size:.82rem;color:var(--warning);margin-top:8px;display:flex;align-items:center;gap:6px;">
        <i data-lucide="alert-circle" style="width:14px;height:14px;"></i>
        Page count differs: Original has ${origPages} pages, Revised has ${revPages} pages
       </div>`
        : '';

    // Count pages with visual diffs
    const visualDiffPages = pages.filter(p =>
        p.disposition === 'added' || p.disposition === 'removed' ||
        (p.image_similarity !== undefined && p.image_similarity < 1.0)
    ).length;

    let html = `
    <!-- Summary -->
    <div class="result-summary">
        <div class="result-summary-top">
            <h3>
                <i data-lucide="git-compare" style="width:20px;height:20px;display:inline;vertical-align:middle;margin-right:6px;"></i>
                ${escapeHtml(data.original_name || 'Original')} vs ${escapeHtml(data.revised_name || 'Revised')}
            </h3>
            <div class="result-actions">
                <button onclick="switchView('compare')">
                    <i data-lucide="plus" style="width:14px;height:14px;"></i>
                    New Comparison
                </button>
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

    <!-- Filter Bar -->
    <div class="result-filter-bar">
        <label class="filter-label">
            <i data-lucide="filter" style="width:16px;height:16px;"></i>
            Filter Results:
        </label>
        <div class="filter-btn-group">
            <button class="filter-btn filter-all active" onclick="filterPages('all', this)">
                <i data-lucide="layers" style="width:16px;height:16px;"></i>
                <span>All Pages</span>
                <span class="badge">${total}</span>
            </button>
            <button class="filter-btn filter-changed" onclick="filterPages('changed', this)">
                <i data-lucide="alert-triangle" style="width:16px;height:16px;"></i>
                <span>Changed</span>
                <span class="badge">${changed}</span>
            </button>
            <button class="filter-btn filter-identical" onclick="filterPages('identical', this)">
                <i data-lucide="check-circle" style="width:16px;height:16px;"></i>
                <span>Identical</span>
                <span class="badge">${passed}</span>
            </button>
        </div>
    </div>

    <!-- Centralized Tabs -->
    <div class="central-tabs">
        <div class="central-tab-nav">
            <button class="central-tab-btn active" onclick="switchCentralTab('textdiff', this)">
                <i data-lucide="code-2" style="width:16px;height:16px;"></i>
                Text Changes
                <span class="ctab-count">${totalTextChanges}</span>
            </button>
            <button class="central-tab-btn" onclick="switchCentralTab('visualdiff', this)">
                <i data-lucide="scan-search" style="width:16px;height:16px;"></i>
                Visual Differences
                <span class="ctab-count">${visualDiffPages}</span>
            </button>
            <button class="central-tab-btn" onclick="switchCentralTab('aichat', this)">
                <i data-lucide="message-circle" style="width:16px;height:16px;"></i>
                AI Assistant
            </button>
        </div>

        <!-- ========== TEXT CHANGES TAB ========== -->
        <div class="central-tab-panel active" id="ctab_textdiff">
            ${renderAllTextDiffs(pages, data)}
        </div>

        <!-- ========== VISUAL DIFF TAB ========== -->
        <div class="central-tab-panel" id="ctab_visualdiff">
            ${renderAllVisualDiffs(pages)}
        </div>

        <!-- ========== AI CHAT TAB ========== -->
        <div class="central-tab-panel" id="ctab_aichat">
            ${renderAIChatPanel()}
        </div>
    </div>`;

    container.innerHTML = html;
    lucide.createIcons();

    // Attach event listeners for collapsible page sections
    document.querySelectorAll('.page-section-header').forEach(h => {
        h.addEventListener('click', () => {
            h.classList.toggle('collapsed');
            const body = h.nextElementSibling;
            if (body) body.classList.toggle('collapsed');
        });
    });

    // Attach chat handlers
    const chatInput = document.getElementById('chatInput');
    const chatSendBtn = document.getElementById('chatSendBtn');
    if (chatInput && chatSendBtn) {
        chatSendBtn.addEventListener('click', () => sendChatMessage());
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendChatMessage();
            }
        });
    }
}

function switchCentralTab(tabName, el) {
    const wrapper = el.closest('.central-tabs');
    wrapper.querySelectorAll('.central-tab-panel').forEach(p => p.classList.remove('active'));
    wrapper.querySelectorAll('.central-tab-btn').forEach(b => b.classList.remove('active'));
    const target = document.getElementById('ctab_' + tabName);
    if (target) target.classList.add('active');
    el.classList.add('active');
    lucide.createIcons();

    // Auto-scroll chat to bottom
    if (tabName === 'aichat') {
        const msgs = document.getElementById('chatMessages');
        if (msgs) setTimeout(() => msgs.scrollTop = msgs.scrollHeight, 100);
    }
}

// ---- All Text Diffs (centralized) ----
function renderAllTextDiffs(pages, data) {
    // Filter only pages with actual text changes
    const diffPages = pages ? pages.filter(p => p.text_changes_count > 0) : [];

    if (diffPages.length === 0) {
        return '<div style="padding:40px;text-align:center;color:var(--text-muted);">No text differences found.</div>';
    }

    let html = '';
    diffPages.forEach((p) => {
        const status = p.status || 'FAIL';
        const lineDiff = p.line_diff || [];
        const changesCount = p.text_changes_count || 0;
        const addCount = lineDiff.filter(d => d.type === 'insert').length;
        const delCount = lineDiff.filter(d => d.type === 'delete').length;
        const replaceCount = lineDiff.filter(d => d.type === 'replace').length;

        let badgeClass = 'fail';
        if (status === 'PASS') badgeClass = 'pass';
        else if (status === 'ADDED') badgeClass = 'added';
        else if (status === 'REMOVED') badgeClass = 'removed';

        const hasVisual = p.image_similarity !== undefined && p.image_similarity < 1.0;
        html += `
        <div class="page-section" data-status="${status}" data-has-visual-diff="${hasVisual}" data-image-similarity="${p.image_similarity || 1.0}">
            <div class="page-section-header">
                <div class="psh-left">
                    <i data-lucide="chevron-down" style="width:16px;height:16px;" class="chevron"></i>
                    <i data-lucide="file-text" style="width:16px;height:16px;"></i>
                    Page ${p.page}
                </div>
                <div class="psh-right">
                    <span>Changes: <strong>${((1 - p.image_similarity) * 100).toFixed(2)}%</strong></span>
                    <span>Visual: <strong>${((1 - p.image_similarity) * 100).toFixed(2)}%</strong></span>
                </div>
            </div>
            <div class="page-section-body">
                ${renderTextDiff(lineDiff, addCount, delCount, replaceCount, data.original_name, data.revised_name)}
            </div>
        </div>`;
    });
    return html;
}

// ---- All Visual Diffs (centralized) ----
function renderAllVisualDiffs(pages, idPrefix = '') {
    // Filter only pages with visual differences (or added/removed pages)
    const diffPages = pages ? pages.filter(p =>
        p.disposition === 'added' ||
        p.disposition === 'removed' ||
        (p.image_similarity !== undefined && p.image_similarity < 1.0)
    ) : [];

    if (diffPages.length === 0) {
        return '<div style="padding:40px;text-align:center;color:var(--text-muted);">No visual differences found.</div>';
    }

    let html = '';
    diffPages.forEach((p) => {
        const status = p.status || 'FAIL';
        const regionCount = p.diff_region_count || 0;
        const similarity = ((p.image_similarity || 0) * 100).toFixed(1);

        let badgeClass = 'fail';
        if (status === 'PASS') badgeClass = 'pass';
        else if (status === 'ADDED') badgeClass = 'added';
        else if (status === 'REMOVED') badgeClass = 'removed';

        const hasVisualChange = p.disposition === 'added' || p.disposition === 'removed' || (p.image_similarity !== undefined && p.image_similarity < 1.0);
        html += `
        <div class="page-section" data-status="${status}" data-has-visual-diff="${hasVisualChange}" data-image-similarity="${p.image_similarity || 1.0}">
            <div class="page-section-header">
                <div class="psh-left">
                    <i data-lucide="chevron-down" style="width:16px;height:16px;" class="chevron"></i>
                    <i data-lucide="image" style="width:16px;height:16px;"></i>
                    Page ${p.page}
                </div>
                <div class="psh-right">
                    <span>Changes: <strong>${((1 - (p.image_similarity || 0)) * 100).toFixed(2)}%</strong></span>
                    ${regionCount > 0 ? `<span>Regions: <strong>${regionCount}</strong></span>` : ''}
                </div>
            </div>
            <div class="page-section-body">
                ${renderImageDiff(p, idPrefix)}
            </div>
        </div>`;
    });
    return html;
}

// ---- AI Chat Panel ----
function renderAIChatPanel() {
    return `
    <div class="chat-container">
        <div class="chat-messages" id="chatMessages">
            <div class="chat-msg ai">
                <div class="chat-avatar ai-av">AI</div>
                <div class="chat-bubble">
                    Hi! I've analyzed your PDF comparison results. Ask me anything about the differences, such as:
                    <ul>
                        <li>What are the most significant changes?</li>
                        <li>Summarize the changes on page 3</li>
                        <li>Are there any critical modifications?</li>
                        <li>Which pages are identical?</li>
                    </ul>
                </div>
            </div>
        </div>
        <div class="chat-suggestions" id="chatSuggestions">
            <button class="chat-suggestion-chip" onclick="askSuggestion(this)">Summarize all changes</button>
            <button class="chat-suggestion-chip" onclick="askSuggestion(this)">Which pages have the most changes?</button>
            <button class="chat-suggestion-chip" onclick="askSuggestion(this)">Are there any critical differences?</button>
            <button class="chat-suggestion-chip" onclick="askSuggestion(this)">What is the overall similarity?</button>
        </div>
        <div class="chat-input-bar">
            <input type="text" class="chat-input" id="chatInput" placeholder="Ask about the comparison results..." autocomplete="off" />
            <button class="chat-send-btn" id="chatSendBtn">
                <i data-lucide="send" style="width:16px;height:16px;"></i>
                Send
            </button>
        </div>
    </div>`;
}

function askSuggestion(el) {
    const text = el.textContent.trim();
    const chatInput = document.getElementById('chatInput');
    chatInput.value = text;
    sendChatMessage();
    // Hide suggestions after first use
    const suggestions = document.getElementById('chatSuggestions');
    if (suggestions) suggestions.style.display = 'none';
}

async function sendChatMessage() {
    const chatInput = document.getElementById('chatInput');
    const chatMessages = document.getElementById('chatMessages');
    const chatSendBtn = document.getElementById('chatSendBtn');
    const msg = chatInput.value.trim();
    if (!msg || !lastResult) return;

    // Add user message to UI
    chatMessages.innerHTML += `
    <div class="chat-msg user">
        <div class="chat-avatar user-av">You</div>
        <div class="chat-bubble">${escapeHtml(msg)}</div>
    </div>`;

    chatInput.value = '';
    chatSendBtn.disabled = true;

    // Show typing indicator
    const typingId = 'typing_' + Date.now();
    chatMessages.innerHTML += `
    <div class="chat-msg ai" id="${typingId}">
        <div class="chat-avatar ai-av">AI</div>
        <div class="chat-bubble">
            <div class="chat-typing"><span></span><span></span><span></span></div>
        </div>
    </div>`;
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Add to history
    chatHistory.push({ role: 'user', content: msg });

    try {
        // Build a lightweight context (strip base64 images to save bandwidth)
        const ctxData = {
            total_pages: lastResult.total_pages,
            original_name: lastResult.original_name,
            revised_name: lastResult.revised_name,
            original_pages: lastResult.original_pages,
            revised_pages: lastResult.revised_pages,
            overall: lastResult.overall,
            pages: (lastResult.pages || []).map(p => ({
                page: p.page,
                status: p.status,
                image_similarity: p.image_similarity,
                text_changes_count: p.text_changes_count,
                diff_region_count: p.diff_region_count,
                confidence: p.confidence,
                disposition: p.disposition,
                text_changes: p.text_changes || [],
                ai_text_changes: p.ai_text_changes || [],
                ai_image_changes: p.ai_image_changes || [],
            }))
        };

        const resp = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: msg,
                context: ctxData,
                history: chatHistory.slice(-10),
            }),
        });

        const typingEl = document.getElementById(typingId);

        if (!resp.ok) {
            const err = await resp.json();
            if (typingEl) typingEl.querySelector('.chat-bubble').innerHTML =
                `<span style="color:var(--danger);">Error: ${escapeHtml(err.detail || 'Failed to get response')}</span>`;
        } else {
            const result = await resp.json();
            chatHistory.push({ role: 'assistant', content: result.reply });
            if (typingEl) typingEl.querySelector('.chat-bubble').innerHTML = renderMarkdown(result.reply);
        }
    } catch (err) {
        const typingEl = document.getElementById(typingId);
        if (typingEl) typingEl.querySelector('.chat-bubble').innerHTML =
            `<span style="color:var(--danger);">Connection error: ${escapeHtml(err.message)}</span>`;
    }

    chatSendBtn.disabled = false;
    chatMessages.scrollTop = chatMessages.scrollHeight;
    lucide.createIcons();
}

// ---- Intra-line word-level token renderer ----
function renderIntraTokens(tokens) {
    if (!tokens || tokens.length === 0) return '';
    return tokens.map(t => {
        const text = escapeHtml(t.text || '');
        if (t.type === 'delete') {
            return `<span class="intra-del">${text}</span>`;
        } else if (t.type === 'insert') {
            return `<span class="intra-ins">${text}</span>`;
        }
        return text;
    }).join(' ');
}

// ---- Text diff renderer ----
function renderTextDiff(lineDiff, addCount, delCount, replaceCount, origName, revName) {
    if (!lineDiff || lineDiff.length === 0) {
        return '<div style="padding:24px;text-align:center;color:var(--text-muted);font-size:.88rem;">No text content to compare on this page.</div>';
    }

    const allEqual = lineDiff.every(d => d.type === 'equal');
    if (allEqual) {
        return `<div style="padding:24px;text-align:center;color:var(--success);font-size:.88rem;">
        <i data-lucide="check-circle" style="width:18px;height:18px;display:inline;vertical-align:middle;margin-right:6px;"></i>
        Text content is identical. No differences found.
    </div>`;
    }

    let html = `
    <div class="diff-file-header">
        <div class="diff-stats-inline">
            <span class="ds-add">+${addCount + replaceCount} additions</span>
            <span class="ds-del">-${delCount + replaceCount} deletions</span>
        </div>
        <div style="display:flex;gap:16px;font-size:.78rem;">
            <span class="dfh-left">${escapeHtml(origName || 'Original')}</span>
            <span class="dfh-right">${escapeHtml(revName || 'Revised')}</span>
        </div>
    </div>
    <div class="diff-table-wrap">
    <table class="diff-table">
        <colgroup>
            <col class="gutter"><col class="content">
            <col style="width:1px;">
            <col class="gutter"><col class="content">
        </colgroup>
        <tbody>`;

    lineDiff.forEach(d => {
        const leftNum = d.left_line_no !== null ? d.left_line_no : '';
        const rightNum = d.right_line_no !== null ? d.right_line_no : '';
        const leftText = escapeHtml(d.left_content || '');
        const rightText = escapeHtml(d.right_content || '');

        if (d.type === 'equal') {
            html += `<tr class="diff-equal">
                <td class="gutter gutter-left">${leftNum}</td>
                <td class="code code-left">${leftText}</td>
                <td class="diff-divider"></td>
                <td class="gutter gutter-right">${rightNum}</td>
                <td class="code code-right">${rightText}</td>
            </tr>`;
        } else if (d.is_trivial) {
            html += `<tr class="diff-trivial" title="Ignored: Date/Time/Duration Change">
                <td class="gutter gutter-left">${leftNum}</td>
                <td class="code code-left">${leftText} <span style="font-size:0.7rem; color:var(--text-muted); margin-left:8px;">(Ignored)</span></td>
                <td class="diff-divider"></td>
                <td class="gutter gutter-right">${rightNum}</td>
                <td class="code code-right">${rightText}</td>
            </tr>`;
        } else if (d.type === 'delete') {
            html += `<tr class="diff-delete">
                <td class="gutter gutter-left">${leftNum}</td>
                <td class="code code-left">${leftText}</td>
                <td class="diff-divider"></td>
                <td class="gutter gutter-right"></td>
                <td class="code code-right"></td>
            </tr>`;
        } else if (d.type === 'insert') {
            html += `<tr class="diff-insert">
                <td class="gutter gutter-left"></td>
                <td class="code code-left"></td>
                <td class="diff-divider"></td>
                <td class="gutter gutter-right">${rightNum}</td>
                <td class="code code-right">${rightText}</td>
            </tr>`;
        } else if (d.type === 'replace') {
            // Use intra-line word-level tokens if available
            const leftDisplay = d.intra_left ? renderIntraTokens(d.intra_left) : leftText;
            const rightDisplay = d.intra_right ? renderIntraTokens(d.intra_right) : rightText;
            html += `<tr class="diff-replace">
                <td class="gutter gutter-left">${leftNum}</td>
                <td class="code code-left">${leftDisplay}</td>
                <td class="diff-divider"></td>
                <td class="gutter gutter-right">${rightNum}</td>
                <td class="code code-right">${rightDisplay}</td>
            </tr>`;
        }
    });

    html += '</tbody></table></div>';
    return html;
}

// ---- Visual diff renderer ----
function renderImageDiff(pageData, idPrefix = '') {
    const origImg = pageData.original_image;
    const revImg = pageData.revised_image;
    const overlayImg = pageData.overlay_image;
    // Use highlighted images if available, otherwise fallback to standard images
    const origHlImg = pageData.original_highlight_image || origImg;
    const revHlImg = pageData.revised_highlight_image || revImg;
    
    const disposition = pageData.disposition || 'compared';
    const regionCount = pageData.diff_region_count || 0;
    const similarityPercent = ((pageData.image_similarity || 0) * 100).toFixed(2);

    if (disposition === 'added') {
        return `<div class="image-overlay-section">
        <h5 style="color:var(--success);">
            <i data-lucide="plus-circle" style="width:14px;height:14px;"></i>
            New Page (only in revised document)
        </h5>
        ${revImg ? `<img src="${revImg}" alt="Added page" loading="lazy" style="max-width:70%;margin:0 auto;border:2px solid var(--success);">` : ''}
    </div>`;
    }

    if (disposition === 'removed') {
        return `<div class="image-overlay-section">
        <h5 style="color:var(--danger);">
            <i data-lucide="minus-circle" style="width:14px;height:14px;"></i>
            Removed Page (only in original document)
        </h5>
        ${origImg ? `<img src="${origImg}" alt="Removed page" loading="lazy" style="max-width:70%;margin:0 auto;border:2px solid var(--danger);opacity:0.8;">` : ''}
    </div>`;
    }

    if (!overlayImg && !origImg && !revImg) {
        return '<div style="padding:24px;text-align:center;color:var(--text-muted);font-size:.88rem;">No images available for this page.</div>';
    }

    // NEW: Only hide the overlay if similarity is 100% AND no regions were detected
    if (pageData.image_similarity >= 0.99999 && regionCount === 0) {
        return `
    <div class="image-overlay-section">
        <!-- Side-by-Side (Active by default for identical pages) -->
        <div id="sbs_view_${idPrefix}${pageData.page}" class="sbs-view active" style="display:flex; margin-bottom: 20px;">
            <div class="sbs-panel">
                <h6>Original</h6>
                <img src="${origImg}" alt="Original Page" loading="lazy" onclick="openImageModal('${origImg}', 'Original Page ${pageData.page}')" style="cursor:pointer;">
            </div>
            <div class="sbs-panel">
                <h6>Revised</h6>
                <img src="${revImg}" alt="Revised Page" loading="lazy" onclick="openImageModal('${revImg}', 'Revised Page ${pageData.page}')" style="cursor:pointer;">
            </div>
        </div>

        <div style="padding:16px;text-align:center;color:var(--success);font-size:.9rem;background:var(--success-light);border-radius:var(--radius-sm);border:1px solid var(--diff-add-hl);">
            <i data-lucide="check-circle" style="width:18px;height:18px;display:inline;vertical-align:middle;margin-right:6px;"></i>
            Pages are visually identical (${((1 - (pageData.image_similarity || 0)) * 100).toFixed(2)}% change). No visual differences found.
        </div>
    </div>`;
    }

    let html = '';
    if (overlayImg) {
        html += `
    <div class="image-overlay-section">
        <!-- Toggle -->
        <div class="toggle-container">
            <input type="checkbox" id="toggle_${idPrefix}${pageData.page}" class="toggle-switch-input" onchange="toggleSideBySide(${pageData.page}, '${idPrefix}')">
            <label for="toggle_${idPrefix}${pageData.page}" class="toggle-switch-label">
                <span class="toggle-knob-bg"></span>
                Show Side-by-Side Comparison
            </label>
        </div>

        <!-- Overlay (Default) -->
        <div id="overlay_view_${idPrefix}${pageData.page}" class="overlay-view">
            <h5>
                <i data-lucide="scan-search" style="width:14px;height:14px;"></i>
                Difference Overlay &mdash; ${regionCount} change region${regionCount !== 1 ? 's' : ''} detected (${((1 - (pageData.image_similarity || 0)) * 100).toFixed(2)}% change)
            </h5>
            <p style="font-size:.78rem;color:var(--text-secondary);margin-bottom:12px;text-align:center;">
                Changed areas are highlighted with red borders and a subtle tint. Text remains fully readable.
            </p>
            <img src="${overlayImg}" alt="Diff overlay" loading="lazy" style="max-width:80%;margin:0 auto;cursor:pointer;" onclick="openImageModal('${overlayImg}', 'Difference Overlay Page ${pageData.page}')">
        </div>

        <!-- Side-by-Side (Hidden) -->
        <div id="sbs_view_${idPrefix}${pageData.page}" class="sbs-view">
            <div class="sbs-panel">
                <h6>Original (Changes in Red)</h6>
                <img src="${origHlImg}" alt="Original Page" loading="lazy" onclick="openImageModal('${origHlImg}', 'Original Page ${pageData.page}')">
            </div>
            <div class="sbs-panel">
                <h6>Revised (Changes in Yellow)</h6>
                <img src="${revHlImg}" alt="Revised Page" loading="lazy" onclick="openImageModal('${revHlImg}', 'Revised Page ${pageData.page}')">
            </div>
        </div>
    </div>`;
    } else {
        html += '<div style="padding:24px;text-align:center;color:var(--text-muted);font-size:.88rem;">Visual diff overlay not available for this page.</div>';
    }

    return html;
}

// Toggle side-by-side view
function toggleSideBySide(page, idPrefix = '') {
    const overlay = document.getElementById(`overlay_view_${idPrefix}${page}`);
    const sbs = document.getElementById(`sbs_view_${idPrefix}${page}`);
    const toggle = document.getElementById(`toggle_${idPrefix}${page}`);

    if (toggle && overlay && sbs) {
        if (toggle.checked) {
            overlay.classList.add('hidden');
            sbs.classList.add('active');
        } else {
            overlay.classList.remove('hidden');
            sbs.classList.remove('active');
        }
    }
}

// ================================================================
// PAGE FILTER — show/hide page sections by status
// ================================================================
function filterPages(filterType, btnEl) {
    // Update active button
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    if (btnEl) btnEl.classList.add('active');

    // Filter all .page-section elements across all tab panels
    document.querySelectorAll('.page-section').forEach(section => {
        const status = section.getAttribute('data-status') || '';
        let show = true;

        if (filterType === 'changed') {
            show = status !== 'PASS';
        } else if (filterType === 'identical') {
            show = status === 'PASS';
        }
        // 'all' shows everything

        section.style.display = show ? '' : 'none';
    });
}
