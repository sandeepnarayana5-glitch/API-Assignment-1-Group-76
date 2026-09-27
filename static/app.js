// Interactive logic for Cloud Monitoring Dashboard

let nextRunTimestamp = null;

// Tab switcher
function switchTab(tabId, btn) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  
  const target = document.getElementById(tabId);
  if (target) {
    target.classList.add('active');
    btn.classList.add('active');
  }
}

// Fetch and update pipeline status & KPIs
async function updateStatus() {
  try {
    const res = await fetch('/api/pipeline/status');
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById('val-status').innerText = data.current_status || 'IDLE';
    document.getElementById('val-total-runs').innerText = data.total_runs || 0;
    document.getElementById('val-success-rate').innerText = 'Success Rate: ' + (data.success_rate || 100) + '%';
    document.getElementById('val-duration').innerText = (data.average_duration_seconds || 0) + 's';

    // FIX BUG: update records from latest_run.metrics (now parsed dict, not raw string)
    if (data.latest_run && data.latest_run.metrics && data.latest_run.metrics.records_processed) {
      document.getElementById('val-records').innerText = data.latest_run.metrics.records_processed.toLocaleString();
    }

    const dot = document.getElementById('dot-pipeline');
    if (data.current_status === 'RUNNING') {
      dot.className = 'status-dot dot-blue';
    } else if (data.current_status === 'FAILED') {
      dot.className = 'status-dot dot-red';
    } else {
      dot.className = 'status-dot dot-green';
    }

    // FIX BUG: next_run_time is nested inside data.scheduler object
    if (data.scheduler && data.scheduler.next_run_time) {
      nextRunTimestamp = new Date(data.scheduler.next_run_time).getTime();
    }
  } catch (err) {
    console.error('Failed to load pipeline status', err);
  }
}

// Update Next Run countdown ticker
function updateCountdown() {
  if (!nextRunTimestamp) {
    document.getElementById('val-next-run').innerText = '--:--';
    return;
  }
  const now = new Date().getTime();
  const diff = Math.max(0, Math.floor((nextRunTimestamp - now) / 1000));
  const minutes = Math.floor(diff / 60);
  const seconds = diff % 60;
  document.getElementById('val-next-run').innerText = minutes + ':' + (seconds < 10 ? '0' : '') + seconds;
  document.getElementById('val-countdown').innerText = 'Cadence: 120s (' + diff + 's remaining)';
}

// Fetch and render execution history audit trail
async function updateHistory() {
  try {
    const res = await fetch('/api/pipeline/history?limit=8');
    if (!res.ok) return;
    const data = await res.json();
    const tbody = document.getElementById('tbody-history');
    
    if (!data.history || data.history.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No runs yet. The first one starts within two minutes.</td></tr>';
      return;
    }

    // FIX BUG: metrics is now a parsed dict from the API (metrics_json bug fixed)
    tbody.innerHTML = data.history.map(function(run) {
      const isSuccess = run.status === 'SUCCESS';
      const badgeClass = isSuccess ? 'badge-success' : (run.status === 'RUNNING' ? 'badge-running' : 'badge-failed');
      const timeFormatted = new Date(run.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      const records = (run.metrics && run.metrics.records_processed)
        ? run.metrics.records_processed.toLocaleString()
        : (run.records_processed ? run.records_processed.toLocaleString() : '-');
      return '<tr>'
        + '<td>' + run.run_id + '</td>'
        + '<td>' + timeFormatted + '</td>'
        + '<td><span class="badge-status ' + badgeClass + '">' + run.status + '</span></td>'
        + '<td>' + (run.duration_seconds ? run.duration_seconds + 's' : '-') + '</td>'
        + '<td>' + records + '</td>'
        + '</tr>';
    }).join('');
  } catch (err) {
    console.error('Failed to load history', err);
  }
}

// Fetch granular stage events for the activity log panel
async function updateEvents() {
  try {
    const res = await fetch('/api/pipeline/events?limit=25');
    if (!res.ok) return;
    const data = await res.json();
    const tbody = document.getElementById('tbody-events');
    if (!tbody) return;

    if (!data.events || data.events.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Nothing logged yet. Activity appears as soon as a run starts.</td></tr>';
      return;
    }

    tbody.innerHTML = data.events.map(function(ev) {
      const badgeClass = ev.status === 'SUCCESS' ? 'badge-success'
        : (ev.status === 'RUNNING' ? 'badge-running' : 'badge-failed');
      const t = new Date(ev.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      const msg = (ev.message || '').length > 62 ? ev.message.substring(0, 62) + '...' : (ev.message || '-');
      return '<tr>'
        + '<td>' + t + '</td>'
        + '<td><strong>' + ev.stage + '</strong></td>'
        + '<td>' + ev.event + '</td>'
        + '<td><span class="badge-status ' + badgeClass + '">' + ev.status + '</span></td>'
        + '<td>' + msg + '</td>'
        + '</tr>';
    }).join('');
  } catch (err) {
    console.error('Failed to load events', err);
  }
}

// Fetch Model Metrics
async function updateMetrics() {
  try {
    const res = await fetch('/api/model/metrics');
    if (!res.ok) return;
    const data = await res.json();
    const tbody = document.getElementById('tbody-models');
    
    tbody.innerHTML = '<tr>'
      + '<td><strong>' + data.baseline_model.name + '</strong></td>'
      + '<td>$' + Math.round(data.baseline_model.mae).toLocaleString() + '</td>'
      + '<td>$' + Math.round(data.baseline_model.rmse).toLocaleString() + '</td>'
      + '<td>' + data.baseline_model.r2.toFixed(3) + '</td>'
      + '</tr><tr>'
      + '<td><strong>' + data.improved_model.name + '</strong></td>'
      + '<td>$' + Math.round(data.improved_model.mae).toLocaleString() + '</td>'
      + '<td>$' + Math.round(data.improved_model.rmse).toLocaleString() + '</td>'
      + '<td>' + data.improved_model.r2.toFixed(3) + '</td>'
      + '</tr>';
  } catch (err) {
    console.error('Failed to load model metrics', err);
  }
}

// Refresh chart images with cache buster to show latest pipeline run charts
function refreshCharts() {
  const ts = new Date().getTime();
  ['img-corr', 'img-importance', 'img-price', 'img-sqft'].forEach(function(id) {
    const el = document.getElementById(id);
    if (!el) return;
    const src = el.src.split('?')[0];
    el.src = src + '?t=' + ts;
  });
}

// FIX BUG: SVG button label defined as constant to reliably restore after trigger
const BTN_RUN_HTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Run Pipeline Now';

// Trigger Pipeline Now
async function triggerPipeline() {
  const btn = document.getElementById('btn-trigger');
  btn.disabled = true;
  btn.innerText = 'Triggering...';
  try {
    await fetch('/api/pipeline/trigger', { method: 'POST' });
    // Wait 1.8s then refresh all panels
    setTimeout(function() {
      updateStatus();
      updateHistory();
      updateMetrics();
      refreshCharts();
      btn.disabled = false;
      btn.innerHTML = BTN_RUN_HTML;
    }, 1800);
  } catch (err) {
    console.error('Failed to trigger pipeline', err);
    btn.disabled = false;
    btn.innerHTML = BTN_RUN_HTML;
  }
}

// Price prediction calculator - invoked from prediction form submit
async function calculatePrice(event) {
  if (event && event.preventDefault) {
    event.preventDefault();
  }
  const sqft = parseFloat(document.getElementById('pred-sqft').value) || 2000;
  const payload = {
    sqft_living: sqft,
    bedrooms: parseFloat(document.getElementById('pred-beds').value) || 3,
    bathrooms: parseFloat(document.getElementById('pred-baths').value) || 2,
    sqft_lot: parseFloat(document.getElementById('pred-lot').value) || 7500,
    floors: parseFloat(document.getElementById('pred-floors').value) || 1,
    condition: parseInt(document.getElementById('pred-condition').value) || 3,
    view: parseInt(document.getElementById('pred-view').value) || 0,
    property_age: parseFloat(document.getElementById('pred-age').value) || 40,
    waterfront: 0,
    sqft_above: Math.round(sqft * 0.85),
    sqft_basement: Math.round(sqft * 0.15)
  };

  const priceEl = document.getElementById('pred-price-val');
  priceEl.innerText = 'Calculating...';

  try {
    const res = await fetch('/api/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const errData = await res.json().catch(function() { return {}; });
      priceEl.innerText = 'Error: ' + (errData.detail || res.statusText);
      return;
    }
    const result = await res.json();
    priceEl.innerText = '$' + Math.round(result.predicted_price).toLocaleString();
    // Update model label below price display
    const modelLabel = document.querySelector('.pred-result span:last-child');
    if (modelLabel) {
      modelLabel.innerText = 'Model: ' + (result.model_used || 'LinearRegression');
    }
  } catch (err) {
    priceEl.innerText = 'Network error: ' + err.message;
  }
}

// Initialization and auto-polling
window.addEventListener('DOMContentLoaded', function() {
  updateStatus();
  updateHistory();
  updateEvents();
  updateMetrics();
  calculatePrice(); // Compute initial price dynamically for default form values

  // 1s countdown timer tick
  setInterval(updateCountdown, 1000);

  // 5s periodic status and history auto-refresh
  setInterval(function() {
    updateStatus();
    updateHistory();
    updateEvents();
  }, 5000);
});