/* Software Generation Compiler – Frontend Logic */

const API_BASE = window.location.origin;
let currentResult = null;

const SAMPLES = [
    'Build a CRM with login, contacts, dashboard, role-based access, and premium plan with payments. Admins can see analytics.',
    'Create an e-commerce store with product listings, shopping cart, checkout with Stripe, user accounts, order tracking, and admin inventory management.',
    'I need a project management tool like Trello. Users can create boards, add tasks, assign members, set due dates, and move tasks between columns. Admins can manage teams.',
    'Build a blog platform where authors can write and publish articles, readers can comment, and admins can moderate content. Support categories and tags.',
    'Create an online learning platform with courses, lessons, quizzes, student enrollment, progress tracking, and instructor dashboards. Support premium courses with payment.',
];

function loadSample(idx) {
    document.getElementById('prompt-input').value = SAMPLES[idx];
}

function resetStages() {
    ['intent', 'design', 'schema', 'refine'].forEach(s => {
        const el = document.getElementById(`ps-${s}`);
        el.className = 'pipeline-stage';
        document.getElementById(`status-${s}`).textContent = '—';
    });
}

function setStageStatus(stageIdx, status) {
    const ids = ['intent', 'design', 'schema', 'refine'];
    const el = document.getElementById(`ps-${ids[stageIdx]}`);
    const statusEl = document.getElementById(`status-${ids[stageIdx]}`);
    el.className = 'pipeline-stage ' + status;
    statusEl.textContent = status === 'active' ? 'Running…' : status === 'completed' ? 'Done' : status === 'failed' ? 'Failed' : '—';
}

async function runCompile() {
    const prompt = document.getElementById('prompt-input').value.trim();
    if (!prompt) { alert('Please enter a prompt'); return; }

    const btn = document.getElementById('compile-btn');
    btn.disabled = true;
    btn.textContent = 'Compiling…';
    document.getElementById('loading').classList.remove('hidden');
    document.getElementById('results').classList.add('hidden');
    document.getElementById('eval-results').classList.add('hidden');
    resetStages();

    // Animate stages
    for (let i = 0; i < 4; i++) {
        setStageStatus(i, 'active');
        await sleep(200);
    }

    try {
        const res = await fetch(`${API_BASE}/api/compile`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt }),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Compilation failed');
        }

        currentResult = await res.json();
        updateStagesFromResult(currentResult);
        renderResults(currentResult);
    } catch (err) {
        alert('Error: ' + err.message);
        resetStages();
    } finally {
        btn.disabled = false;
        btn.textContent = 'Compile';
        document.getElementById('loading').classList.add('hidden');
    }
}

function updateStagesFromResult(result) {
    const stageMap = {
        'intent_extraction': 0,
        'system_design': 1,
        'schema_generation': 2,
        'refinement': 3,
    };
    if (result.stage_results) {
        result.stage_results.forEach(sr => {
            const idx = stageMap[sr.stage_name];
            if (idx !== undefined) {
                setStageStatus(idx, sr.status === 'completed' ? 'completed' : 'failed');
            }
        });
    }
}

function renderResults(result) {
    const section = document.getElementById('results');
    section.classList.remove('hidden');

    // Metrics bar
    const m = result.metrics || {};
    document.getElementById('metrics-bar').innerHTML = `
        <div class="metric-card">
            <div class="metric-value ${result.success ? 'success' : 'danger'}">${result.success ? 'Success' : 'Failed'}</div>
            <div class="metric-label">Status</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">${(m.total_duration_ms || 0).toFixed(0)}ms</div>
            <div class="metric-label">Total Duration</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">${m.stages_completed || 0}/4</div>
            <div class="metric-label">Stages Completed</div>
        </div>
        <div class="metric-card">
            <div class="metric-value ${m.total_retries > 0 ? 'warning' : 'success'}">${m.total_retries || 0}</div>
            <div class="metric-label">Repair Cycles</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">${m.validation_issues_found || 0}</div>
            <div class="metric-label">Issues Found</div>
        </div>
        <div class="metric-card">
            <div class="metric-value success">${m.validation_issues_repaired || 0}</div>
            <div class="metric-label">Auto-Repaired</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">${((m.confidence_score || 0) * 100).toFixed(0)}%</div>
            <div class="metric-label">Confidence</div>
        </div>
    `;

    switchTab('overview');
}

function switchTab(tabName) {
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tabName));
    const content = document.getElementById('tab-content');

    if (!currentResult) { content.innerHTML = '<p>No results</p>'; return; }

    switch (tabName) {
        case 'overview': content.innerHTML = renderOverview(); break;
        case 'intent': content.innerHTML = renderJson(currentResult.intent); break;
        case 'design': content.innerHTML = renderJson(currentResult.design); break;
        case 'ui-schema': content.innerHTML = renderJson(currentResult.app_config?.ui_schema); break;
        case 'api-schema': content.innerHTML = renderApiSchema(); break;
        case 'db-schema': content.innerHTML = renderDbSchema(); break;
        case 'auth-schema': content.innerHTML = renderJson(currentResult.app_config?.auth_schema); break;
        case 'code': content.innerHTML = renderCodeFiles(); break;
        case 'validation': content.innerHTML = renderValidation(); break;
        case 'raw': content.innerHTML = renderJson(currentResult); break;
    }
}

function renderOverview() {
    const r = currentResult;
    const intent = r.intent || {};
    const config = r.app_config || {};
    let html = `
        <h3 style="margin-bottom:1rem">${intent.app_name || 'Application'}</h3>
        <p style="color:var(--text-muted);margin-bottom:1rem">${intent.description || ''}</p>
        <table>
            <tr><th style="width:200px">App Type</th><td>${intent.app_type || '—'}</td></tr>
            <tr><th>Entities</th><td>${(intent.entities || []).map(e => e.name).join(', ') || '—'}</td></tr>
            <tr><th>Roles</th><td>${(intent.roles || []).map(r => r.name).join(', ') || '—'}</td></tr>
            <tr><th>Features</th><td>${(intent.features || []).map(f => f.name).join(', ') || '—'}</td></tr>
            <tr><th>UI Pages</th><td>${(config.ui_schema?.pages || []).length}</td></tr>
            <tr><th>API Endpoints</th><td>${(config.api_schema?.endpoints || []).length}</td></tr>
            <tr><th>DB Tables</th><td>${(config.db_schema?.tables || []).length}</td></tr>
            <tr><th>Auth Roles</th><td>${(config.auth_schema?.roles || []).length}</td></tr>
            <tr><th>Generated Files</th><td>${(r.generated_code || []).length}</td></tr>
        </table>
    `;
    if (r.assumptions && r.assumptions.length) {
        html += `<div class="assumptions"><h4>Assumptions Made</h4><ul>${r.assumptions.map(a => `<li>${esc(a)}</li>`).join('')}</ul></div>`;
    }
    if (intent.business_rules && intent.business_rules.length) {
        html += `<h4 style="margin-top:1rem">Business Rules</h4><ul>${intent.business_rules.map(br => `<li><strong>${esc(br.name)}:</strong> ${esc(br.description)}</li>`).join('')}</ul>`;
    }
    return html;
}

function renderApiSchema() {
    const eps = currentResult.app_config?.api_schema?.endpoints || [];
    if (!eps.length) return '<p>No endpoints</p>';

    const methodColors = { GET: 'badge-success', POST: 'badge-info', PUT: 'badge-warning', DELETE: 'badge-danger', PATCH: 'badge-warning' };

    let html = `<table><thead><tr><th>Method</th><th>Path</th><th>Description</th><th>Auth</th><th>Roles</th></tr></thead><tbody>`;
    eps.forEach(ep => {
        html += `<tr>
            <td><span class="badge ${methodColors[ep.method] || 'badge-info'}">${ep.method}</span></td>
            <td style="font-family:var(--mono);font-size:0.85rem">${esc(ep.path)}</td>
            <td>${esc(ep.description)}</td>
            <td>${ep.auth_required ? '🔒' : '🌐'}</td>
            <td>${(ep.allowed_roles || []).join(', ') || '—'}</td>
        </tr>`;
    });
    html += '</tbody></table>';
    return html;
}

function renderDbSchema() {
    const tables = currentResult.app_config?.db_schema?.tables || [];
    if (!tables.length) return '<p>No tables</p>';

    let html = '';
    tables.forEach(table => {
        html += `<h4 style="margin:1rem 0 0.5rem">${esc(table.name)}</h4>`;
        html += `<table><thead><tr><th>Column</th><th>Type</th><th>PK</th><th>Nullable</th><th>Unique</th><th>FK</th></tr></thead><tbody>`;
        (table.columns || []).forEach(col => {
            const fk = col.foreign_key ? `→ ${col.foreign_key.table}.${col.foreign_key.column}` : '—';
            html += `<tr>
                <td style="font-family:var(--mono)">${esc(col.name)}</td>
                <td><span class="badge badge-info">${col.column_type}${col.max_length ? `(${col.max_length})` : ''}</span></td>
                <td>${col.primary_key ? '✓' : ''}</td>
                <td>${col.nullable ? '✓' : ''}</td>
                <td>${col.unique ? '✓' : ''}</td>
                <td style="font-size:0.8rem">${esc(fk)}</td>
            </tr>`;
        });
        html += '</tbody></table>';
    });
    return html;
}

function renderCodeFiles() {
    const files = currentResult.generated_code || [];
    if (!files.length) return '<p>No generated code</p>';
    return files.map(f => `
        <div class="code-file">
            <div class="code-file-header">
                <span class="filename">${esc(f.filename)}</span>
                <span class="lang">${esc(f.language)}</span>
            </div>
            <pre>${esc(f.content)}</pre>
        </div>
    `).join('');
}

function renderValidation() {
    const issues = currentResult.validation_issues || [];
    if (!issues.length) return '<p style="color:var(--success)">No validation issues found.</p>';

    const sevColors = { error: 'badge-danger', warning: 'badge-warning', info: 'badge-info' };
    let html = `<p style="margin-bottom:1rem">${issues.length} issue(s) found</p>`;
    html += `<table><thead><tr><th>Severity</th><th>Layer</th><th>Field</th><th>Message</th><th>Repaired</th></tr></thead><tbody>`;
    issues.forEach(issue => {
        html += `<tr>
            <td><span class="badge ${sevColors[issue.severity] || 'badge-info'}">${issue.severity}</span></td>
            <td>${esc(issue.layer)}</td>
            <td style="font-family:var(--mono);font-size:0.8rem">${esc(issue.field)}</td>
            <td>${esc(issue.message)}</td>
            <td>${issue.auto_repaired ? '<span class="badge badge-success">auto-fixed</span>' : '—'}</td>
        </tr>`;
    });
    html += '</tbody></table>';
    return html;
}

function renderJson(obj) {
    if (!obj) return '<p>No data</p>';
    return `<pre>${esc(JSON.stringify(obj, null, 2))}</pre>`;
}

/* ── Evaluation ──────────────────────────────────────────────────────── */

async function runEvaluation() {
    const btn = document.getElementById('eval-btn');
    btn.disabled = true;
    btn.textContent = 'Running…';
    document.getElementById('loading').classList.remove('hidden');
    document.getElementById('eval-results').classList.add('hidden');
    document.getElementById('results').classList.add('hidden');

    try {
        const res = await fetch(`${API_BASE}/api/evaluate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category: 'all' }),
        });
        if (!res.ok) throw new Error('Evaluation failed');
        const report = await res.json();
        renderEvaluation(report);
    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Run Evaluation (20 prompts)';
        document.getElementById('loading').classList.add('hidden');
    }
}

function renderEvaluation(report) {
    const section = document.getElementById('eval-results');
    section.classList.remove('hidden');

    let html = `
        <div class="eval-summary">
            <div class="metric-card"><div class="metric-value success">${report.success_rate}%</div><div class="metric-label">Success Rate</div></div>
            <div class="metric-card"><div class="metric-value">${report.successful}/${report.total_prompts}</div><div class="metric-label">Passed</div></div>
            <div class="metric-card"><div class="metric-value">${report.avg_duration_ms.toFixed(0)}ms</div><div class="metric-label">Avg Duration</div></div>
            <div class="metric-card"><div class="metric-value">${report.avg_retries.toFixed(1)}</div><div class="metric-label">Avg Retries</div></div>
            <div class="metric-card"><div class="metric-value">${report.total_issues_found}</div><div class="metric-label">Total Issues</div></div>
            <div class="metric-card"><div class="metric-value success">${report.total_issues_repaired}</div><div class="metric-label">Auto-Repaired</div></div>
        </div>
    `;

    // Category breakdown
    if (report.category_breakdown) {
        html += `<h3 style="margin:1.5rem 0 0.75rem">Category Breakdown</h3><table><thead><tr><th>Category</th><th>Total</th><th>Success</th><th>Rate</th><th>Avg Duration</th></tr></thead><tbody>`;
        Object.entries(report.category_breakdown).forEach(([cat, data]) => {
            html += `<tr><td>${esc(cat)}</td><td>${data.total}</td><td>${data.success}</td><td><span class="badge ${data.success_rate >= 80 ? 'badge-success' : data.success_rate >= 50 ? 'badge-warning' : 'badge-danger'}">${data.success_rate}%</span></td><td>${data.avg_ms.toFixed(0)}ms</td></tr>`;
        });
        html += '</tbody></table>';
    }

    // Individual results
    html += `<h3 style="margin:1.5rem 0 0.75rem">Individual Results</h3>`;
    html += `<table><thead><tr><th>ID</th><th>Category</th><th>Status</th><th>Duration</th><th>Entities</th><th>Endpoints</th><th>Tables</th><th>Files</th><th>Issues</th></tr></thead><tbody>`;
    (report.results || []).forEach(r => {
        html += `<tr>
            <td style="font-family:var(--mono);font-size:0.8rem">${esc(r.prompt_id)}</td>
            <td><span class="badge badge-info">${esc(r.category)}</span></td>
            <td><span class="badge ${r.success ? 'badge-success' : 'badge-danger'}">${r.success ? 'pass' : 'fail'}</span></td>
            <td>${r.duration_ms.toFixed(0)}ms</td>
            <td>${r.entity_count}</td>
            <td>${r.endpoint_count}</td>
            <td>${r.table_count}</td>
            <td>${r.generated_files}</td>
            <td>${r.issues_found}</td>
        </tr>`;
    });
    html += '</tbody></table>';

    document.getElementById('eval-content').innerHTML = html;
}

/* ── Utilities ───────────────────────────────────────────────────────── */

function esc(str) {
    if (str === null || str === undefined) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
