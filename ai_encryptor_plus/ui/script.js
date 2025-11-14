/* ========= Global Helpers ========= */
// ID se element select karne ke liye helper
const $ = id => document.getElementById(id);
let comparisonChart; // Global chart instance
let chosenFilesEnc = []; // Encryption ke liye select kiye hue files
let chosenFilesCmp = []; // Comparison ke liye select kiye hue files

// Bytes ko readable format mein convert karo (B, KB, MB, GB)
function fmtBytes(n) {
    if (n < 1) return "0 B";
    if (n < 1024) return n.toFixed(0) + " B";
    if (n < 1024 ** 2) return (n / 1024).toFixed(1) + " KB";
    if (n < 1024 ** 3) return (n / 1024 ** 2).toFixed(1) + " MB";
    return (n / 1024 ** 3).toFixed(1) + " GB";
}

// Blob ko download karo
function downloadBlob(blob, filename) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 800);
}

// Log message ko text ke taur par add karo
function log(tab, m) {
    const logEl = $(`log-${tab}`);
    logEl.textContent += m + "\n";
    logEl.scrollTop = logEl.scrollHeight;
}

// Log mein HTML element (jaise links) add karo
function logHTML(tab, html) {
    const logEl = $(`log-${tab}`);
    logEl.appendChild(html);
    logEl.scrollTop = logEl.scrollHeight;
}

// Status message footer mein dikhaao
function setStatus(text) {
    $('footer').textContent = `Status: ${text}`;
}

/* ========= Auto-Settings Fetcher ========= */
// Server se auto settings fetch karo aur UI mein update karo
async function fetchAutoSettings() {
    try {
        const response = await fetch('/api/settings');
        if (!response.ok) throw new Error('Failed to fetch settings');
        const settings = await response.json();
        
        // Encrypt tab ko update karo
        $('auto-workers-enc').textContent = settings.workers;
        $('auto-chunk-enc').textContent = settings.chunk_mb;
        
        // Compare tab ko update karo
        $('auto-workers-cmp').textContent = settings.workers;
        $('auto-chunk-cmp').textContent = settings.chunk_mb;
        
    } catch (e) {
        console.error("Failed to load auto-settings", e);
        // Default values set karo agar fetch fail ho
        $('auto-workers-enc').textContent = '4 (Default)';
        $('auto-chunk-enc').textContent = '8 (Default)';
        $('auto-workers-cmp').textContent = '4 (Default)';
        $('auto-chunk-cmp').textContent = '8 (Default)';
    }
}

/* ========= Tab/Page Switching ========= */
// Sab tabs, pages aur settings panels collect karo
const tabs = [$('btnTabEncrypt'), $('btnTabDecrypt'), $('btnTabCompare')];
const pages = [$('encrypt-page'), $('decrypt-page'), $('compare-page')];
const settingsPanels = [$('settings-encrypt'), $('settings-decrypt'), $('settings-compare')];

// Tab switch karo - pehle sab ko hide karo, phir selected ko show karo
function switchTab(tabId) {
    tabs.forEach(t => t.classList.remove('active'));
    pages.forEach(p => p.classList.remove('active'));
    settingsPanels.forEach(s => s.classList.add('hidden'));

    if (tabId === 'encrypt') {
        $('btnTabEncrypt').classList.add('active');
        $('encrypt-page').classList.add('active');
        $('settings-encrypt').classList.remove('hidden');
    } else if (tabId === 'decrypt') {
        $('btnTabDecrypt').classList.add('active');
        $('decrypt-page').classList.add('active');
        $('settings-decrypt').classList.remove('hidden');
    } else {
        $('btnTabCompare').classList.add('active');
        $('compare-page').classList.add('active');
        $('settings-compare').classList.remove('hidden');
    }
}
// Tab buttons ke liye click handlers
$('btnTabEncrypt').onclick = () => switchTab('encrypt');
$('btnTabDecrypt').onclick = () => switchTab('decrypt');
$('btnTabCompare').onclick = () => switchTab('compare');


/* ========= File List Renderer ========= */
// File list ko UI mein render karo aur summary dikhao
function renderFileList(fileArray, listElId, summaryElId, enableFn) {
    const listEl = $(listElId);
    const summaryEl = $(summaryElId);
    enableFn();
    let totalSize = 0;
    if (!fileArray.length) {
        listEl.innerHTML = "";
        summaryEl.classList.add('hidden');
        return;
    }
    summaryEl.classList.remove('hidden');
    listEl.innerHTML = fileArray.map(f => {
        totalSize += f.size;
        return `<div class="file-item"><div class="file-details"><h4>${f.name}</h4><p>${fmtBytes(f.size)}</p></div></div>`;
    }).join('');
    summaryEl.textContent = `${fileArray.length} file(s) — Total size: ${fmtBytes(totalSize)}`;
}

/* ========= Encrypt Page Logic ========= */
// Encrypt button ko enable/disable karo based on files aur password
const enableEncrypt = () => { $('btnEncrypt').disabled = !(chosenFilesEnc.length && $('pwEnc').value.trim()); };
$('pwEnc').oninput = enableEncrypt;

// Encrypt file drop zone setup
const dzEnc = $('drop-enc');
dzEnc.onclick = () => $('files-enc').click();
dzEnc.ondragover = (e) => { e.preventDefault(); dzEnc.classList.add('drag-over'); };
dzEnc.ondragleave = () => dzEnc.classList.remove('drag-over');
dzEnc.ondrop = (e) => {
    e.preventDefault();
    dzEnc.classList.remove('drag-over');
    chosenFilesEnc = Array.from(e.dataTransfer.files || []);
    renderFileList(chosenFilesEnc, 'fileList-enc', 'summary-enc', enableEncrypt);
};
// File input change handler
$('files-enc').onchange = (e) => {
    chosenFilesEnc = Array.from(e.target.files || []);
    renderFileList(chosenFilesEnc, 'fileList-enc', 'summary-enc', enableEncrypt);
};

// Encrypt button click - files ko server pe bhejo aur download link dalo
$('btnEncrypt').onclick = async () => {
    $('btnEncrypt').disabled = true;
    log('enc', "🚀 Starting encryption... Uploading files to server.");
    setStatus("Encrypting...");

    const formData = new FormData();
    formData.append('password', $('pwEnc').value.trim());
    formData.append('mode', $('aesModeEnc').value);
    formData.append('policy', $('policyEnc').value);
    chosenFilesEnc.forEach(f => formData.append('files', f, f.name));

    try {
        const response = await fetch('/api/encrypt', { method: 'POST', body: formData });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.error || `Server responded with ${response.status}`);
        }
        
        // Server se time elapsed aur encrypted file le aao
        const time = parseFloat(response.headers.get('X-Time-Elapsed') || '0');
        log('enc', `✅ Success! Run complete in ${time.toFixed(4)}s.`);
        
        const blob = await response.blob();
        const filename = response.headers.get('content-disposition')?.split('filename=')[1]?.replace(/"/g, '') || "encrypted.zip";
        
        log('enc', `Package created: ${filename}`);
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.textContent = `⬇️ Download "${filename}"`;
        link.className = 'download-link';
        logHTML('enc', link); // Download link log mein add karo
        
        setStatus("Encryption complete.");

    } catch (e) {
        log('enc', `❌ ERROR: ${e.message}`);
        setStatus(`Error: ${e.message}`);
    } finally {
        $('btnEncrypt').disabled = false;
    }
};

/* ========= Compare Page Logic ========= */
// Compare button ko enable/disable karo
const enableCompare = () => { $('btnCompare').disabled = !(chosenFilesCmp.length && $('pwCmp').value.trim()); };
$('pwCmp').oninput = enableCompare;

// Compare file drop zone setup
const dzCmp = $('drop-cmp');
dzCmp.onclick = () => $('files-cmp').click();
dzCmp.ondragover = (e) => { e.preventDefault(); dzCmp.classList.add('drag-over'); };
dzCmp.ondragleave = () => dzCmp.classList.remove('drag-over');
dzCmp.ondrop = (e) => {
    e.preventDefault();
    dzCmp.classList.remove('drag-over');
    chosenFilesCmp = Array.from(e.dataTransfer.files || []);
    renderFileList(chosenFilesCmp, 'fileList-cmp', 'summary-cmp', enableCompare);
};
$('files-cmp').onchange = (e) => {
    chosenFilesCmp = Array.from(e.target.files || []);
    renderFileList(chosenFilesCmp, 'fileList-cmp', 'summary-cmp', enableCompare);
};

// Chart initialize karo - FIFO vs AI comparison ke liye
function initChart() {
    const chartCtx = $("chart").getContext('2d');
    comparisonChart = new Chart(chartCtx, {
        type: 'bar',
        data: {
            labels: ['FIFO (Naive)', 'AI-Priority'],
            datasets: [{
                label: 'Time (seconds)',
                data: [0, 0],
                backgroundColor: ['rgba(239, 68, 68, 0.6)', 'rgba(59, 130, 246, 0.6)'],
                borderColor: ['rgba(239, 68, 68, 1)', 'rgba(59, 130, 246, 1)'],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { y: { beginAtZero: true, title: { display: true, text: 'Time (seconds)' } } },
            plugins: { legend: { display: false } }
        }
    });
}

// Chart data update karo new times ke saath
function updateChart(fifoTime, priorityTime) {
    if (!comparisonChart) initChart();
    comparisonChart.data.datasets[0].data = [fifoTime, priorityTime];
    comparisonChart.update();
}

// Compare button click - dono methods ko server pe run karo aur results dikhao
$('btnCompare').onclick = async () => {
    $('btnCompare').disabled = true;
    log('cmp', "🚀 Starting comparison... Uploading files to server.");
    setStatus("Running comparison...");
    updateChart(0, 0);

    const formData = new FormData();
    formData.append('password', $('pwCmp').value.trim());
    formData.append('mode', $('aesModeCmp').value);
    chosenFilesCmp.forEach(f => formData.append('files', f, f.name));

    try {
        const response = await fetch('/api/compare', { method: 'POST', body: formData });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.error || `Server responded with ${response.status}`);
        }
        log('cmp', "✅ Comparison complete on server.");
        
        // Server se FIFO aur AI times le aao
        const timeFIFO = parseFloat(response.headers.get('X-Time-FIFO') || '0');
        const timeAI = parseFloat(response.headers.get('X-Time-AI') || '0');
        
        log('cmp', `--- RESULTS ---`);
        log('cmp', `FIFO (Naive):   ${timeFIFO.toFixed(4)} seconds`);
        log('cmp', `AI (Priority):  ${timeAI.toFixed(4)} seconds`);
        updateChart(timeFIFO, timeAI);
        
        // Kitna time save hua calculate karo
        const saved = timeFIFO - timeAI;
        const percent = (timeFIFO > 0) ? (saved / timeFIFO * 100) : 0;
        
        if (saved > 0.0001) {
            log('cmp', `🏆 AI was ${saved.toFixed(4)}s (${percent.toFixed(1)}%) faster!`);
        } else {
            log('cmp', `🐌 AI was ${Math.abs(saved).toFixed(4)}s slower.`);
        }
        
        const blob = await response.blob();
        const filename = response.headers.get('content-disposition')?.split('filename=')[1]?.replace(/"/g, '') || "encrypted_ai.zip";
        
        log('cmp', `AI-Priority package created: ${filename}`);
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.textContent = `⬇️ Download AI-Priority Package`;
        link.className = 'download-link';
        logHTML('cmp', link); // Download link log mein add karo

        setStatus("Comparison complete.");

    } catch (e) {
        log('cmp', `❌ ERROR: ${e.message}`);
        setStatus(`Error: ${e.message}`);
    } finally {
        $('btnCompare').disabled = false;
    }
};

/* ========= Decrypt Page Logic ========= */
// Decrypt button ko enable/disable karo
const enableDecrypt = () => { $('btnDecrypt').disabled = !($('pkg').files.length && $('pwDec').value.trim()); };
$('pkg').onchange = enableDecrypt;
$('pwDec').oninput = enableDecrypt;

// Decrypt button click - encrypted package ko server ke pass bhejo
$('btnDecrypt').onclick = async () => {
    $('btnDecrypt').disabled = true;
    log('dec', "🚀 Sending package to server for decryption...");
    setStatus("Decrypting...");
    
    const file = $('pkg').files[0];
    const password = $('pwDec').value.trim();
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('password', password);
    
    try {
        const response = await fetch('/api/decrypt', { method: 'POST', body: formData });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.error || `Server responded with ${response.status}`);
        }
        
        // Server se JSON response le aao (files list ke saath)
        const data = await response.json();
        
        if (data.files && data.files.length > 0) {
            log('dec', `✅ Success! Server decrypted ${data.files.length} file(s):`);
            
            // Har file ke liye download link banao
            data.files.forEach(file => {
                const link = document.createElement('a');
                // Filename ko URL mein encode karo (spaces etc. handle karne ke liye)
                link.href = `/api/download_decrypted/${data.session_id}/${encodeURIComponent(file)}`;
                // Download attribute browser ko bata deta hai download karo, navigate nahi
                link.download = file.split('/').pop(); // Sirf filename nikalo
                link.textContent = `⬇️ Download "${file}"`;
                link.className = 'download-link';
                logHTML('dec', link); // Link ko log mein add karo
            });
        } else {
            log('dec', "✅ Decryption complete, but no files were found in the package.");
        }
        
        setStatus("Decryption complete.");
        
    } catch (e) {
        log('dec', `❌ ERROR: ${e.message}`);
        setStatus(`Error: ${e.message}`);
    } finally {
        $('btnDecrypt').disabled = false;
    }
};

/* ========= Initial Load ========= */
// Page load hone ke baad sab setup karo
window.onload = () => {
    initChart();
    switchTab('encrypt'); // "Encrypt" tab se shuru karo
    setStatus("Ready");
    fetchAutoSettings(); // Auto-detected settings fetch karo
};