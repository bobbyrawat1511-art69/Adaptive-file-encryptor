/* ========= Global Helpers ========= */
// helper to get element by id quickly
const $ = id => document.getElementById(id);
// variable for the comparison Chart.js instance (will be set later)
let comparisonChart; 
// arrays to hold selected files for encrypt and compare flows
let chosenFilesEnc = []; 
let chosenFilesCmp = []; 
// flag to ensure settings are fetched only once after first upload
let settingsLoaded = false; // Flag to prevent spamming server

// format bytes into human readable string
function fmtBytes(n) {
    if (n < 1) return "0 B"; // zero or negative -> 0 B
    if (n < 1024) return n.toFixed(0) + " B"; // bytes
    if (n < 1024 ** 2) return (n / 1024).toFixed(1) + " KB"; // kilobytes
    if (n < 1024 ** 3) return (n / 1024 ** 2).toFixed(1) + " MB"; // megabytes
    return (n / 1024 ** 3).toFixed(1) + " GB"; // gigabytes and above
}

// append a plain text log line to the given tab's log element
function log(tab, m) {
    const logEl = $(`log-${tab}`); // get the log element for the tab
    logEl.textContent += m + "\n"; // append message + newline
    logEl.scrollTop = logEl.scrollHeight; // scroll to bottom
}

// append an HTML element to the given tab's log element
function logHTML(tab, html) {
    const logEl = $(`log-${tab}`); // get the log element for the tab
    logEl.appendChild(html); // append the provided node
    logEl.scrollTop = logEl.scrollHeight; // scroll to bottom
}

// set the footer status text
function setStatus(text) {
    $('footer').textContent = `Status: ${text}`; // update footer
}

/* ========= UI REVEAL LOGIC (The "On Upload" Trigger) ========= */
// fetch tuned settings from the server and reveal them in the UI
async function revealSettings() {
    // If we already tuned the system, don't do it again.
    if (settingsLoaded) return; // no-op if already loaded

    setStatus("Analyzing hardware & workload..."); // indicate work
    try {
        const response = await fetch('/api/settings'); // call backend
        if (!response.ok) throw new Error('Failed'); // throw on bad status
        const settings = await response.json(); // parse JSON
        
        const w = settings.workers; // recommended workers
        const c = settings.chunk_mb; // recommended chunk size

        // Update DOM with recommended values for both encrypt and compare UIs
        $('auto-workers-enc').textContent = w;
        $('auto-chunk-enc').textContent = c;
        $('auto-workers-cmp').textContent = w;
        $('auto-chunk-cmp').textContent = c;
        
        settingsLoaded = true; // mark as done
        setStatus("System optimized. Ready."); // update status
    } catch (e) {
        console.error("Settings fetch error", e); // log error to console
        setStatus("Ready (Default Settings)"); // fallback status
    }
}

/* ========= Tab Switching ========= */
// cache tab buttons and page containers
const tabs = [$('btnTabEncrypt'), $('btnTabDecrypt'), $('btnTabCompare')];
const pages = [$('encrypt-page'), $('decrypt-page'), $('compare-page')];
const settingsPanels = [$('settings-encrypt'), $('settings-decrypt'), $('settings-compare')];

// switch visible tab/page and show corresponding settings panel
function switchTab(tabId) {
    tabs.forEach(t => t.classList.remove('active')); // deactivate all tab buttons
    pages.forEach(p => p.classList.remove('active')); // hide all pages
    settingsPanels.forEach(s => s.classList.add('hidden')); // hide all settings panels

    if (tabId === 'encrypt') { // encrypt tab selected
        $('btnTabEncrypt').classList.add('active'); // highlight encrypt tab
        $('encrypt-page').classList.add('active'); // show encrypt page
        $('settings-encrypt').classList.remove('hidden'); // show encrypt settings
    } else if (tabId === 'decrypt') { // decrypt tab selected
        $('btnTabDecrypt').classList.add('active'); // highlight decrypt tab
        $('decrypt-page').classList.add('active'); // show decrypt page
        $('settings-decrypt').classList.remove('hidden'); // show decrypt settings
    } else { // compare tab selected
        $('btnTabCompare').classList.add('active'); // highlight compare tab
        $('compare-page').classList.add('active'); // show compare page
        $('settings-compare').classList.remove('hidden'); // show compare settings
    }
}
$('btnTabEncrypt').onclick = () => switchTab('encrypt'); // wire encrypt tab click
$('btnTabDecrypt').onclick = () => switchTab('decrypt'); // wire decrypt tab click
$('btnTabCompare').onclick = () => switchTab('compare'); // wire compare tab click

/* ========= File Lists (Trigger Logic Here) ========= */
// render a list of files in the given container and show a summary
function renderFileList(fileArray, listElId, summaryElId, enableFn) {
    const listEl = $(listElId); // container for file items
    const summaryEl = $(summaryElId); // summary element
    
    // 1. TRIGGER OPTIMIZATION ON UPLOAD
    if (fileArray.length > 0) {
        revealSettings(); // trigger settings fetch on first upload
    }

    enableFn(); // call provided enable/disable function for action buttons
    let totalSize = 0; // accumulator for total size
    if (!fileArray.length) {
        listEl.innerHTML = ""; // clear list if no files
        summaryEl.classList.add('hidden'); // hide summary
        return; // nothing more to do
    }
    summaryEl.classList.remove('hidden'); // show summary area
    listEl.innerHTML = fileArray.map(f => {
        totalSize += f.size; // add to total
        // create an HTML fragment per file (name + formatted size)
        return `<div class="file-item"><div class="file-details"><h4>${f.name}</h4><p>${fmtBytes(f.size)}</p></div></div>`;
    }).join(''); // join fragments into a single string
    summaryEl.textContent = `${fileArray.length} file(s) — Total size: ${fmtBytes(totalSize)}`; // set summary text
}

/* ========= Encrypt Page ========= */
// enable/disable encrypt button based on chosen files and password presence
const enableEncrypt = () => { $('btnEncrypt').disabled = !(chosenFilesEnc.length && $('pwEnc').value.trim()); };
$('pwEnc').oninput = enableEncrypt; // re-evaluate when password input changes

const dzEnc = $('drop-enc'); // dropzone element for encrypt page
dzEnc.onclick = () => $('files-enc').click(); // clicking dropzone opens file selector
dzEnc.ondragover = (e) => { e.preventDefault(); dzEnc.classList.add('drag-over'); }; // styling on dragover
dzEnc.ondragleave = () => dzEnc.classList.remove('drag-over'); // remove styling on drag leave

// Drop Event
dzEnc.ondrop = (e) => {
    e.preventDefault(); // prevent default browser behavior
    dzEnc.classList.remove('drag-over'); // remove drag styling
    chosenFilesEnc = Array.from(e.dataTransfer.files || []); // capture dropped files
    renderFileList(chosenFilesEnc, 'fileList-enc', 'summary-enc', enableEncrypt); // render UI
};
// File Select Event
$('files-enc').onchange = (e) => {
    chosenFilesEnc = Array.from(e.target.files || []); // capture selected files
    renderFileList(chosenFilesEnc, 'fileList-enc', 'summary-enc', enableEncrypt); // render UI
};

$('btnEncrypt').onclick = async () => {
    $('btnEncrypt').disabled = true; // prevent double clicks
    
    // Note: No revealSettings() here anymore. It's already done!
    log('enc', "🚀 Starting encryption... Uploading files."); // log start message
    setStatus("Encrypting..."); // update status

    const formData = new FormData(); // create form payload
    formData.append('password', $('pwEnc').value.trim()); // add password
    formData.append('mode', $('aesModeEnc').value); // add AES mode
    formData.append('policy', $('policyEnc').value); // add policy
    chosenFilesEnc.forEach(f => formData.append('files', f, f.name)); // append each file

    try {
        const response = await fetch('/api/encrypt', { method: 'POST', body: formData }); // send to server
        if (!response.ok) {
            const err = await response.json(); // parse error body
            throw new Error(err.error || `Error ${response.status}`); // throw readable error
        }
        const time = parseFloat(response.headers.get('X-Time-Elapsed') || '0'); // read timing header
        log('enc', `✅ Run complete in ${time.toFixed(4)}s.`); // log server time
        
        const blob = await response.blob(); // get binary package
        const filename = response.headers.get('content-disposition')?.split('filename=')[1]?.replace(/"/g, '') || "encrypted.zip"; // derive filename
        
        log('enc', `Package created: ${filename}`); // log filename
        const link = document.createElement('a'); // create download link element
        link.href = URL.createObjectURL(blob); // create blob URL
        link.download = filename; // set suggested filename
        link.textContent = `⬇️ Download "${filename}"`; // link text
        link.className = 'download-link'; // class for styling
        logHTML('enc', link); // append link to the log area
        setStatus("Complete."); // update status

    } catch (e) {
        log('enc', `❌ ERROR: ${e.message}`); // log error message
        setStatus(`Error: ${e.message}`); // update status with error
    } finally {
        $('btnEncrypt').disabled = false; // re-enable button
    }
};

/* ========= Compare Page ========= */
// enable/disable compare button based on chosen files and password
const enableCompare = () => { $('btnCompare').disabled = !(chosenFilesCmp.length && $('pwCmp').value.trim()); };
$('pwCmp').oninput = enableCompare; // re-evaluate when password changes

const dzCmp = $('drop-cmp'); // compare dropzone
dzCmp.onclick = () => $('files-cmp').click(); // open file selector on click
dzCmp.ondragover = (e) => { e.preventDefault(); dzCmp.classList.add('drag-over'); }; // styling on dragover
dzCmp.ondragleave = () => dzCmp.classList.remove('drag-over'); // remove styling on drag leave

dzCmp.ondrop = (e) => {
    e.preventDefault(); // prevent default
    dzCmp.classList.remove('drag-over'); // remove drag class
    chosenFilesCmp = Array.from(e.dataTransfer.files || []); // capture files
    renderFileList(chosenFilesCmp, 'fileList-cmp', 'summary-cmp', enableCompare); // render
};
$('files-cmp').onchange = (e) => {
    chosenFilesCmp = Array.from(e.target.files || []); // capture selected files
    renderFileList(chosenFilesCmp, 'fileList-cmp', 'summary-cmp', enableCompare); // render
};

// initialize Chart.js chart for comparison
function initChart() {
    const ctx = $("chart").getContext('2d'); // get 2D context from canvas
    comparisonChart = new Chart(ctx, { // instantiate Chart.js
        type: 'bar',
        data: {
            labels: ['FIFO (Naive)', 'AI-Priority'], // two bars
            datasets: [{
                label: 'Time (seconds)', // dataset label
                data: [0, 0], // initial data
                backgroundColor: ['rgba(239, 68, 68, 0.6)', 'rgba(59, 130, 246, 0.6)'], // colors
                borderColor: ['rgba(239, 68, 68, 1)', 'rgba(59, 130, 246, 1)'], // border colors
                borderWidth: 1 // border width
            }]
        },
        options: {
            responsive: true, // responsive chart
            maintainAspectRatio: false, // allow resizing freely
            scales: { y: { beginAtZero: true, title: { display: true, text: 'Time (seconds)' } } }, // y-axis options
            plugins: { legend: { display: false } } // hide legend
        }
    });
}
// update chart with new timing values
function updateChart(fifoTime, priorityTime) {
    if (!comparisonChart) initChart(); // init chart if needed
    comparisonChart.data.datasets[0].data = [fifoTime, priorityTime]; // set new data
    comparisonChart.update(); // redraw chart
}

$('btnCompare').onclick = async () => {
    $('btnCompare').disabled = true; // prevent re-click
    
    // Note: No revealSettings() here anymore.
    log('cmp', "🚀 Starting comparison..."); // log start
    setStatus("Running comparison..."); // update status
    updateChart(0, 0); // reset chart to zeros

    const formData = new FormData(); // create payload
    formData.append('password', $('pwCmp').value.trim()); // add password
    formData.append('mode', $('aesModeCmp').value); // add AES mode
    chosenFilesCmp.forEach(f => formData.append('files', f, f.name)); // attach files

    try {
        const response = await fetch('/api/compare', { method: 'POST', body: formData }); // send request
        if (!response.ok) {
            const err = await response.json(); // parse error body
            throw new Error(err.error || `Error ${response.status}`); // throw
        }
        log('cmp', "✅ Comparison complete."); // log completion
        
        const timeFIFO = parseFloat(response.headers.get('X-Time-FIFO') || '0'); // read FIFO time header
        const timeAI = parseFloat(response.headers.get('X-Time-AI') || '0'); // read AI time header
        
        log('cmp', `--- RESULTS ---`); // log separator
        log('cmp', `FIFO (Naive):   ${timeFIFO.toFixed(4)} seconds`); // log FIFO time
        log('cmp', `AI (Priority):  ${timeAI.toFixed(4)} seconds`); // log AI time
        updateChart(timeFIFO, timeAI); // update chart with real values
        
        const saved = timeFIFO - timeAI; // compute time saved
        const percent = (timeFIFO > 0) ? (saved / timeFIFO * 100) : 0; // compute percent saved
        
        if (saved > 0.0001) {
            log('cmp', `🏆 AI was ${saved.toFixed(4)}s (${percent.toFixed(1)}%) faster!`); // AI faster
        } else {
            log('cmp', `🐌 AI was ${Math.abs(saved).toFixed(4)}s slower.`); // AI slower or equal
        }
        
        const blob = await response.blob(); // get package blob
        const filename = response.headers.get('content-disposition')?.split('filename=')[1]?.replace(/"/g, '') || "encrypted_ai.zip"; // derive filename
        
        log('cmp', `AI package created: ${filename}`); // log filename
        const link = document.createElement('a'); // create download link
        link.href = URL.createObjectURL(blob); // blob URL
        link.download = filename; // suggested filename
        link.textContent = `⬇️ Download Package`; // link text
        link.className = 'download-link'; // styling class
        logHTML('cmp', link); // append link to compare log

        setStatus("Complete."); // update status
    } catch (e) {
        log('cmp', `❌ ERROR: ${e.message}`); // log error
        setStatus(`Error: ${e.message}`); // update status with error
    } finally {
        $('btnCompare').disabled = false; // re-enable button
    }
};

/* ========= Decrypt Page ========= */
// enable/disable decrypt button depending on if a package file and password are present
const enableDecrypt = () => { $('btnDecrypt').disabled = !($('pkg').files.length && $('pwDec').value.trim()); };
$('pkg').onchange = enableDecrypt; // check when package input changes
$('pwDec').oninput = enableDecrypt; // check when password input changes

$('btnDecrypt').onclick = async () => {
    $('btnDecrypt').disabled = true; // prevent double clicks
    log('dec', "🚀 Sending package..."); // log action
    setStatus("Decrypting..."); // update status
    
    const formData = new FormData(); // create payload
    formData.append('file', $('pkg').files[0]); // attach selected package
    formData.append('password', $('pwDec').value.trim()); // attach password
    
    try {
        const response = await fetch('/api/decrypt', { method: 'POST', body: formData }); // send to backend
        if (!response.ok) {
            const err = await response.json(); // parse error body
            throw new Error(err.error || `Error ${response.status}`); // throw
        }
        const data = await response.json(); // parse JSON response
        if (data.files && data.files.length > 0) { // if server returned file list
            log('dec', `✅ Decrypted ${data.files.length} files:`); // log count
            data.files.forEach(file => {
                const link = document.createElement('a'); // create download link
                link.href = `/api/download_decrypted/${data.session_id}/${encodeURIComponent(file)}`; // server endpoint
                link.download = file.split('/').pop(); // suggested filename
                link.textContent = `⬇️ Download "${file}"`; // link text
                link.className = 'download-link'; // styling class
                logHTML('dec', link); // append to decrypt log
            });
        } else {
            log('dec', "✅ Complete (No files found)."); // no files returned
        }
        setStatus("Complete."); // update status
    } catch (e) {
        log('dec', `❌ ERROR: ${e.message}`); // log error
        setStatus(`Error: ${e.message}`); // update status
    } finally {
        $('btnDecrypt').disabled = false; // re-enable button
    }
};

// run initialization on window load
window.onload = () => {
    initChart(); // initialize the comparison chart
    switchTab('encrypt'); // default to encrypt tab
    setStatus("Ready"); // set initial status
};
