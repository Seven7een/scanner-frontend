/**
 * Scanner Frontend — PWA Application Logic
 */
const App = (() => {
    let apiKey = localStorage.getItem('scanner_api_key') || '';
    let currentScanId = null;
    let pollInterval = null;

    // --- API Helper ---
    async function api(method, path, body = null) {
        const opts = {
            method,
            headers: {
                'X-API-Key': apiKey,
                'Content-Type': 'application/json',
            },
        };
        if (body) opts.body = JSON.stringify(body);
        const resp = await fetch(`/api/v1${path}`, opts);
        const data = await resp.json();
        if (!resp.ok) throw { status: resp.status, ...data };
        return data;
    }

    // --- Auth ---
    function authenticate() {
        const input = document.getElementById('api-key-input');
        const key = input.value.trim();
        if (!key) return;

        apiKey = key;
        fetch('/api/v1/scans?limit=1', {
            headers: { 'X-API-Key': key }
        }).then(r => {
            if (r.ok) {
                localStorage.setItem('scanner_api_key', key);
                document.getElementById('auth-gate').classList.add('hidden');
                document.getElementById('app').classList.remove('hidden');
                showView('scan');
            } else {
                document.getElementById('auth-error').textContent = 'Invalid API key';
                document.getElementById('auth-error').classList.remove('hidden');
            }
        }).catch(() => {
            document.getElementById('auth-error').textContent = 'Connection failed';
            document.getElementById('auth-error').classList.remove('hidden');
        });
    }

    function checkAuth() {
        if (apiKey) {
            fetch('/api/v1/scans?limit=1', {
                headers: { 'X-API-Key': apiKey }
            }).then(r => {
                if (r.ok) {
                    document.getElementById('auth-gate').classList.add('hidden');
                    document.getElementById('app').classList.remove('hidden');
                    showView('scan');
                } else {
                    localStorage.removeItem('scanner_api_key');
                    apiKey = '';
                }
            }).catch(() => {});
        }
    }

    // --- Navigation ---
    function showView(name) {
        document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
        document.getElementById(`view-${name}`).classList.remove('hidden');
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        const navBtn = document.querySelector(`[data-nav="${name}"]`);
        if (navBtn) navBtn.classList.add('active');

        if (name === 'history') loadHistory();
    }

    // --- Scan Submission ---
    async function submitScan(e) {
        e.preventDefault();
        const btn = document.getElementById('scan-btn');
        btn.disabled = true;
        btn.textContent = 'Starting...';

        const githubUsers = document.getElementById('github-users').value.trim();
        const gitlabUsers = document.getElementById('gitlab-users').value.trim();
        const repoUrls = document.getElementById('repo-urls').value.trim();
        const scanType = document.querySelector('input[name="scan-type"]:checked').value;

        try {
            const data = await api('POST', '/scans', {
                github_users: githubUsers,
                gitlab_users: gitlabUsers,
                repo_urls: repoUrls,
                scan_type: scanType,
            });

            currentScanId = data.id;
            document.getElementById('scan-progress').classList.remove('hidden');
            document.getElementById('scan-result').classList.add('hidden');
            document.getElementById('scan-status-text').textContent = 'Scan queued...';
            document.getElementById('scan-progress-bar').style.width = '10%';

            startPolling(data.id);
        } catch (err) {
            alert(err.detail || 'Failed to start scan');
        } finally {
            btn.disabled = false;
            btn.textContent = '🔍 Start Scan';
        }
    }

    function startPolling(scanId) {
        if (pollInterval) clearInterval(pollInterval);
        let ticks = 0;

        pollInterval = setInterval(async () => {
            ticks++;
            try {
                const scan = await api('GET', `/scans/${scanId}`);
                const statusText = document.getElementById('scan-status-text');
                const progressBar = document.getElementById('scan-progress-bar');

                if (scan.status === 'running') {
                    statusText.textContent = 'Scanning repositories...';
                    progressBar.style.width = Math.min(10 + ticks * 5, 85) + '%';
                } else if (scan.status === 'completed') {
                    clearInterval(pollInterval);
                    progressBar.style.width = '100%';
                    statusText.textContent = 'Scan complete!';
                    setTimeout(() => {
                        document.getElementById('scan-progress').classList.add('hidden');
                        showScanResult(scan);
                    }, 500);
                } else if (scan.status === 'failed') {
                    clearInterval(pollInterval);
                    progressBar.style.width = '100%';
                    progressBar.classList.remove('bg-blue-500');
                    progressBar.classList.add('bg-red-500');
                    statusText.textContent = `Scan failed: ${scan.error_message || 'Unknown error'}`;
                }
            } catch (err) {
                console.error('Poll error:', err);
            }
        }, 3000);
    }

    function showScanResult(scan) {
        const container = document.getElementById('scan-result');
        container.classList.remove('hidden');

        const total = scan.total_findings || 0;
        const statusClass = total > 0 ? 'text-red-400' : 'text-green-400';
        const statusIcon = total > 0 ? '⚠️' : '✅';

        container.innerHTML = `
            <div class="bg-surface rounded-xl p-6 shadow-lg">
                <div class="flex items-center gap-3 mb-4">
                    <span class="text-2xl">${statusIcon}</span>
                    <h3 class="text-lg font-semibold ${statusClass}">
                        ${total > 0 ? `${total} finding${total !== 1 ? 's' : ''} detected` : 'No findings — all clean!'}
                    </h3>
                </div>
                ${total > 0 ? `
                <div class="grid grid-cols-4 gap-3 mb-4">
                    ${severityCard('🔴', 'Critical', scan.critical_count)}
                    ${severityCard('🟠', 'High', scan.high_count)}
                    ${severityCard('🟡', 'Medium', scan.medium_count)}
                    ${severityCard('🔵', 'Low', scan.low_count)}
                </div>` : ''}
                <div class="text-sm text-gray-400 space-y-1">
                    <p>Repos scanned: ${scan.repos_scanned || 0}</p>
                    <p>Duration: ${scan.duration_seconds ? scan.duration_seconds.toFixed(1) + 's' : 'N/A'}</p>
                </div>
                ${total > 0 ? `
                <button onclick="App.viewResults('${scan.id}')"
                    class="mt-4 bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg text-sm transition">
                    View Details →
                </button>` : ''}
            </div>`;
    }

    function severityCard(icon, label, count) {
        return `<div class="bg-slate-800 rounded-lg p-3 text-center">
            <span class="text-lg">${icon}</span>
            <p class="text-xs text-gray-400 mt-1">${label}</p>
            <p class="text-xl font-bold">${count || 0}</p>
        </div>`;
    }

    // --- Scan description helper ---
    function scanDescription(scan) {
        const parts = [];
        if (scan.github_users) parts.push(scan.github_users);
        if (scan.gitlab_users) parts.push(scan.gitlab_users);
        if (scan.repo_urls) {
            const urls = scan.repo_urls.split(/[,\n;]+/).filter(u => u.trim());
            parts.push(urls.length + ' repo URL' + (urls.length !== 1 ? 's' : ''));
        }
        return parts.join(', ') || 'No targets specified';
    }

    // --- History ---
    async function loadHistory() {
        const container = document.getElementById('history-list');
        try {
            const data = await api('GET', '/scans?limit=50');
            if (data.scans.length === 0) {
                container.innerHTML = '<p class="text-gray-400 text-sm">No scans yet. Start one!</p>';
                return;
            }

            container.innerHTML = data.scans.map(scan => {
                const statusIcons = { pending: '⏳', running: '🔄', completed: '✅', failed: '❌' };
                const icon = statusIcons[scan.status] || '❓';
                const date = new Date(scan.created_at).toLocaleString();
                const desc = scanDescription(scan);
                const total = scan.total_findings || 0;

                return `<div class="bg-surface rounded-xl p-4 shadow-lg cursor-pointer hover:bg-slate-700 transition"
                             onclick="App.viewResults('${scan.id}')">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-sm font-medium">${icon} ${scan.scan_type.toUpperCase()} scan</span>
                        <span class="text-xs text-gray-400">${date}</span>
                    </div>
                    <p class="text-sm text-gray-300 mb-2">${escapeHtml(desc)}</p>
                    ${scan.status === 'completed' ? `
                    <div class="flex gap-2 text-xs">
                        ${scan.critical_count ? `<span class="badge badge-critical">🔴 ${scan.critical_count}</span>` : ''}
                        ${scan.high_count ? `<span class="badge badge-high">🟠 ${scan.high_count}</span>` : ''}
                        ${scan.medium_count ? `<span class="badge badge-medium">🟡 ${scan.medium_count}</span>` : ''}
                        ${scan.low_count ? `<span class="badge badge-low">🔵 ${scan.low_count}</span>` : ''}
                        ${total === 0 ? '<span class="text-green-400">✅ Clean</span>' : ''}
                    </div>` : ''}
                    ${scan.status === 'failed' ? `<p class="text-red-400 text-xs">${escapeHtml(scan.error_message || 'Failed')}</p>` : ''}
                    ${scan.status === 'running' ? '<p class="text-blue-400 text-xs animate-pulse">Scanning...</p>' : ''}
                    <div class="flex items-center justify-between mt-2">
                        <span class="text-xs text-gray-500">${scan.repos_scanned ? scan.repos_scanned + ' repos' : ''} ${scan.duration_seconds ? '• ' + scan.duration_seconds.toFixed(1) + 's' : ''}</span>
                        <button onclick="event.stopPropagation(); App.deleteScan('${scan.id}')"
                            class="text-red-400 hover:text-red-300 text-xs">🗑️</button>
                    </div>
                </div>`;
            }).join('');
        } catch (err) {
            container.innerHTML = '<p class="text-red-400 text-sm">Failed to load history</p>';
        }
    }

    async function deleteScan(id) {
        if (!confirm('Delete this scan and all its findings?')) return;
        try {
            await api('DELETE', `/scans/${id}`);
            loadHistory();
        } catch (err) {
            alert('Failed to delete scan');
        }
    }

    // --- Results View (paginated findings) ---
    let currentResultsScanId = null;
    const FINDINGS_PAGE_SIZE = 100;
    let findingsOffset = 0;
    let findingsTotal = 0;
    let findingsLoaded = [];

    async function viewResults(scanId) {
        currentResultsScanId = scanId;
        findingsOffset = 0;
        findingsLoaded = [];
        showView('results');

        try {
            const scan = await api('GET', `/scans/${scanId}`);
            const summary = document.getElementById('results-summary');
            const total = scan.total_findings || 0;
            const desc = scanDescription(scan);

            summary.innerHTML = `
                <div class="bg-surface rounded-xl p-6 shadow-lg">
                    <h2 class="text-xl font-semibold mb-3">Scan Results</h2>
                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                        ${severityCard('🔴', 'Critical', scan.critical_count)}
                        ${severityCard('🟠', 'High', scan.high_count)}
                        ${severityCard('🟡', 'Medium', scan.medium_count)}
                        ${severityCard('🔵', 'Low', scan.low_count)}
                    </div>
                    <div class="text-sm text-gray-400 space-y-1">
                        <p>Targets: ${escapeHtml(desc)}</p>
                        <p>Repos scanned: ${scan.repos_scanned || 0} • Total findings: ${total}</p>
                        <p>Duration: ${scan.duration_seconds ? scan.duration_seconds.toFixed(1) + 's' : 'N/A'} • Type: ${scan.scan_type}</p>
                    </div>
                </div>`;

            // Populate repo filter from first batch
            await loadFindings(true);
        } catch (err) {
            document.getElementById('results-summary').innerHTML =
                '<p class="text-red-400">Failed to load results</p>';
        }
    }

    async function loadFindings(resetFilters = false) {
        if (!currentResultsScanId) return;
        findingsOffset = 0;
        findingsLoaded = [];

        const severity = document.getElementById('filter-severity').value;
        const repo = document.getElementById('filter-repo').value;
        const tool = document.getElementById('filter-tool').value;

        let path = `/scans/${currentResultsScanId}/findings?limit=${FINDINGS_PAGE_SIZE}&offset=0`;
        if (severity) path += `&severity=${severity}`;
        if (repo) path += `&repo=${encodeURIComponent(repo)}`;
        if (tool) path += `&tool=${tool}`;

        try {
            const data = await api('GET', path);
            findingsTotal = data.total;
            findingsLoaded = data.findings;
            findingsOffset = data.findings.length;

            // Populate repo filter on first load
            if (resetFilters && !repo) {
                const repos = [...new Set(data.findings.map(f => f.repo))].sort();
                const repoSelect = document.getElementById('filter-repo');
                repoSelect.innerHTML = '<option value="">All Repos</option>' +
                    repos.map(r => `<option value="${r}">${r}</option>`).join('');
            }

            renderFindings(findingsLoaded);
            updateLoadMoreButton();
        } catch (err) {
            console.error('Failed to load findings:', err);
        }
    }

    async function loadMoreFindings() {
        if (!currentResultsScanId || findingsOffset >= findingsTotal) return;

        const severity = document.getElementById('filter-severity').value;
        const repo = document.getElementById('filter-repo').value;
        const tool = document.getElementById('filter-tool').value;

        let path = `/scans/${currentResultsScanId}/findings?limit=${FINDINGS_PAGE_SIZE}&offset=${findingsOffset}`;
        if (severity) path += `&severity=${severity}`;
        if (repo) path += `&repo=${encodeURIComponent(repo)}`;
        if (tool) path += `&tool=${tool}`;

        try {
            const data = await api('GET', path);
            findingsLoaded = findingsLoaded.concat(data.findings);
            findingsOffset += data.findings.length;

            renderFindings(findingsLoaded);
            updateLoadMoreButton();
        } catch (err) {
            console.error('Failed to load more findings:', err);
        }
    }

    function updateLoadMoreButton() {
        const container = document.getElementById('findings-load-more');
        const countEl = document.getElementById('findings-count');

        if (findingsOffset < findingsTotal) {
            container.classList.remove('hidden');
            countEl.textContent = `Showing ${findingsOffset} of ${findingsTotal} findings`;
        } else {
            container.classList.add('hidden');
            if (findingsTotal > FINDINGS_PAGE_SIZE) {
                countEl.textContent = `All ${findingsTotal} findings loaded`;
                countEl.classList.remove('hidden');
            }
        }
    }

    function renderFindings(findings) {
        const container = document.getElementById('findings-list');
        if (findings.length === 0) {
            container.innerHTML = '<p class="text-gray-400 text-sm">No findings match the current filters.</p>';
            return;
        }

        const severityIcons = { critical: '🔴', high: '🟠', medium: '🟡', low: '🔵' };

        container.innerHTML = findings.map((f, i) => `
            <div class="bg-surface rounded-xl shadow-lg overflow-hidden">
                <div class="p-4 cursor-pointer hover:bg-slate-700 transition"
                     onclick="document.getElementById('detail-${i}').classList.toggle('expanded')">
                    <div class="flex items-center gap-3">
                        <span class="badge badge-${f.severity}">${severityIcons[f.severity] || '⚪'} ${f.severity}</span>
                        <span class="text-sm font-medium truncate flex-1">${escapeHtml(f.repo)}</span>
                        <span class="text-xs text-gray-400">${f.tool}</span>
                    </div>
                    <div class="mt-2 text-sm text-gray-300">
                        ${f.file ? `<span class="font-mono text-xs">${escapeHtml(f.file)}${f.line ? ':' + f.line : ''}</span>` : ''}
                        ${f.rule_id ? `<span class="text-xs text-gray-500 ml-2">[${escapeHtml(f.rule_id)}]</span>` : ''}
                    </div>
                    ${f.description ? `<p class="text-xs text-gray-400 mt-1">${escapeHtml(f.description)}</p>` : ''}
                </div>
                <div id="detail-${i}" class="finding-details">
                    <div class="px-4 pb-4 border-t border-slate-700 pt-3 space-y-2">
                        ${f.description ? `<div><label class="text-xs text-gray-500 block mb-1">Description</label><p class="text-sm text-gray-300">${escapeHtml(f.description)}</p></div>` : ''}
                        ${f.snippet ? `<div><label class="text-xs text-gray-500 block mb-1">Snippet</label><div class="snippet">${escapeHtml(f.snippet)}</div></div>` : ''}
                        ${f.commit_hash ? `<p class="text-xs text-gray-400">Commit: <span class="font-mono">${escapeHtml(f.commit_hash)}</span></p>` : ''}
                        ${f.category ? `<p class="text-xs text-gray-400">Category: ${escapeHtml(f.category)}</p>` : ''}
                        ${f.recommendation ? `<div><label class="text-xs text-gray-500 block mb-1">Recommendation</label><p class="text-sm text-gray-300">${escapeHtml(f.recommendation)}</p></div>` : ''}
                    </div>
                </div>
            </div>
        `).join('');
    }

    function escapeHtml(str) {
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // --- Init ---
    document.addEventListener('DOMContentLoaded', checkAuth);

    document.addEventListener('DOMContentLoaded', () => {
        const input = document.getElementById('api-key-input');
        if (input) {
            input.addEventListener('keydown', e => {
                if (e.key === 'Enter') authenticate();
            });
        }
    });

    return {
        authenticate,
        showView,
        submitScan,
        loadHistory,
        deleteScan,
        viewResults,
        loadFindings,
        loadMoreFindings,
    };
})();
