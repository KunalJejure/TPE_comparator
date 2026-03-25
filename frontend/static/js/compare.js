// ================================================================
// compare.js — File Upload & Comparison Logic
// ================================================================

let originalFile = null;
let revisedFile = null;

const dropOriginal = document.getElementById('dropOriginal');
const dropRevised = document.getElementById('dropRevised');
const fileOriginal = document.getElementById('fileOriginal');
const fileRevised = document.getElementById('fileRevised');
const compareBtn = document.getElementById('compareBtn');

// Drag & Drop for Original
dropOriginal.addEventListener('dragover', (e) => { e.preventDefault(); dropOriginal.classList.add('dragover'); });
dropOriginal.addEventListener('dragleave', () => dropOriginal.classList.remove('dragover'));
dropOriginal.addEventListener('drop', (e) => {
    e.preventDefault();
    dropOriginal.classList.remove('dragover');
    const f = Array.from(e.dataTransfer.files).find(f =>
        f.name.toLowerCase().endsWith('.pdf') || f.type === 'application/pdf' ||
        f.name.toLowerCase().endsWith('.docx') || f.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document');
    if (f) { originalFile = f; renderUploadBoxes(); }
});

// Drag & Drop for Revised
dropRevised.addEventListener('dragover', (e) => { e.preventDefault(); dropRevised.classList.add('dragover'); });
dropRevised.addEventListener('dragleave', () => dropRevised.classList.remove('dragover'));
dropRevised.addEventListener('drop', (e) => {
    e.preventDefault();
    dropRevised.classList.remove('dragover');
    const f = Array.from(e.dataTransfer.files).find(f =>
        f.name.toLowerCase().endsWith('.pdf') || f.type === 'application/pdf' ||
        f.name.toLowerCase().endsWith('.docx') || f.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document');
    if (f) { revisedFile = f; renderUploadBoxes(); }
});

fileOriginal.addEventListener('change', (e) => {
    if (e.target.files[0]) { originalFile = e.target.files[0]; renderUploadBoxes(); }
});
fileRevised.addEventListener('change', (e) => {
    if (e.target.files[0]) { revisedFile = e.target.files[0]; renderUploadBoxes(); }
});

function renderUploadBoxes() {
    // Original
    const origInfo = document.getElementById('fileInfoOriginal');
    if (originalFile) {
        dropOriginal.classList.add('has-file');
        const size = (originalFile.size / 1024).toFixed(1) + ' KB';
        origInfo.innerHTML = `
        <div class="file-info" onclick="event.stopPropagation();">
            <span class="fi-icon"><i data-lucide="file-text" style="width:16px;height:16px;"></i></span>
            <span class="fi-name">${originalFile.name}</span>
            <span class="fi-size">${size}</span>
            <span class="fi-remove" onclick="removeOriginal(event)">
                <i data-lucide="x" style="width:14px;height:14px;"></i>
            </span>
        </div>`;
    } else {
        dropOriginal.classList.remove('has-file');
        origInfo.innerHTML = '';
    }

    // Revised
    const revInfo = document.getElementById('fileInfoRevised');
    if (revisedFile) {
        dropRevised.classList.add('has-file');
        const size = (revisedFile.size / 1024).toFixed(1) + ' KB';
        revInfo.innerHTML = `
        <div class="file-info" onclick="event.stopPropagation();">
            <span class="fi-icon"><i data-lucide="file-text" style="width:16px;height:16px;"></i></span>
            <span class="fi-name">${revisedFile.name}</span>
            <span class="fi-size">${size}</span>
            <span class="fi-remove" onclick="removeRevised(event)">
                <i data-lucide="x" style="width:14px;height:14px;"></i>
            </span>
        </div>`;
    } else {
        dropRevised.classList.remove('has-file');
        revInfo.innerHTML = '';
    }

    compareBtn.disabled = !(originalFile && revisedFile);
    lucide.createIcons();
}

function removeOriginal(e) {
    e.stopPropagation();
    originalFile = null;
    fileOriginal.value = '';
    renderUploadBoxes();
}
function removeRevised(e) {
    e.stopPropagation();
    revisedFile = null;
    fileRevised.value = '';
    renderUploadBoxes();
}

function resetUpload() {
    originalFile = null;
    revisedFile = null;
    fileOriginal.value = '';
    fileRevised.value = '';
    renderUploadBoxes();
}

// ================================================================
// RUN COMPARISON
// ================================================================
// lastResult is declared in results.js — shared global
// (if results.js hasn't loaded yet, declare a fallback here)
if (typeof lastResult === 'undefined') {
    var lastResult = null;
}

async function runCompare() {
    if (!originalFile || !revisedFile) return;

    const btn = document.getElementById('compareBtn');
    const btnText = document.getElementById('compareBtnText');
    const spinner = document.getElementById('spinner');
    const progressBar = document.getElementById('progressBar');
    const progressFill = document.getElementById('progressFill');

    btn.disabled = true;
    btnText.textContent = 'Analyzing...';
    spinner.style.display = 'block';
    progressBar.style.display = 'block';
    progressFill.style.width = '0%';

    // Simulate progress
    let progress = 0;
    const progressInterval = setInterval(() => {
        progress = Math.min(progress + Math.random() * 12, 90);
        progressFill.style.width = progress + '%';
    }, 500);

    // Log activity (safe call)
    if (typeof addActivity === 'function') {
        addActivity('SY', '#6366F1', 'System', 'Uploading & processing documents...');
    }

    const formData = new FormData();
    formData.append('original', originalFile);
    formData.append('revised', revisedFile);

    // Append optional page range
    const startPage = document.getElementById('startPage')?.value;
    const endPage = document.getElementById('endPage')?.value;
    if (startPage) formData.append('start_page', startPage);
    if (endPage) formData.append('end_page', endPage);

    try {
        const resp = await fetch('/api/compare', {
            method: 'POST',
            body: formData,
        });

        clearInterval(progressInterval);
        progressFill.style.width = '100%';

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || 'Comparison failed');
        }

        const data = await resp.json();
        lastResult = data;

        // Send desktop notification
        if (typeof NotificationManager !== 'undefined') {
            const passed = data.pages ? data.pages.filter(p => p.status === 'PASS').length : 0;
            const total = data.total_pages || 0;
            const status = data.overall?.overall_change || (passed === total ? 'No' : 'Some');
            NotificationManager.sendNotification(
                'Comparison Completed',
                `Analysis of ${data.original_name} vs ${data.revised_name} is done. ${status} changes detected.`
            );
        }

        // Compute summary stats
        const total = data.total_pages || 0;
        const passed = data.pages ? data.pages.filter(p => p.status === 'PASS').length : 0;
        const failed = total - passed;

        // Log AI activity (safe call)
        if (typeof addActivity === 'function') {
            addActivity('AI', '#EC4899', 'Groq AI',
                `Analysis complete: ${data.overall?.overall_change || 'N/A'} changes detected. Confidence: ${((data.overall?.confidence || 0) * 100).toFixed(0)}%`);
        }

        // Update chart if available (safe call)
        if (typeof updateChart === 'function') {
            updateChart(data);
        }

        // Show results nav item (safe)
        const navResults = document.getElementById('navResults');
        if (navResults) navResults.style.display = 'flex';

        // Render results and switch to results view
        if (typeof renderResults === 'function') {
            renderResults(data);
        }
        if (typeof switchView === 'function') {
            switchView('results');
        }

    } catch (err) {
        clearInterval(progressInterval);
        if (typeof addActivity === 'function') {
            addActivity('SY', '#EF4444', 'Error', err.message);
        }
        console.error('Comparison error:', err);
    } finally {
        btn.disabled = false;
        btnText.textContent = 'Compare Documents';
        spinner.style.display = 'none';
        setTimeout(() => { progressBar.style.display = 'none'; }, 1000);
    }
}
