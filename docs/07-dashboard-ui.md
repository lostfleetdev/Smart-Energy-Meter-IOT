# 7. Dashboard UI

## 7.1 Overview

The web dashboard is a single-page application built with Material Design 2, providing:

1. **Live Monitoring** — Real-time power gauges and metrics
2. **Historical Charts** — Power consumption over time
3. **ML Predictions** — Next-hour power forecast
4. **Relay Control** — Remote appliance switching
5. **Anomaly Alerts** — Visual notifications for unusual readings

---

## 7.2 Technology Stack

| Component | Technology |
|-----------|------------|
| Design System | Material Design 2 |
| Font | Roboto |
| Icons | Material Icons Outlined |
| Charts | Chart.js 4.4 |
| Data Streaming | Server-Sent Events (SSE) |
| HTTP | Fetch API |

---

## 7.3 UI Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TOP APP BAR                                     │
│  ┌──────┐                                              ┌────────┐ ┌───────┐ │
│  │ ⚡   │  Smart Energy Monitor                        │ Fridge▼│ │🟢 Live│ │
│  └──────┘                                              └────────┘ └───────┘ │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                         LIVE METRICS CARDS                           │   │
│   │                                                                      │   │
│   │   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐           │   │
│   │   │   VOLTAGE     │  │   CURRENT     │  │    POWER      │           │   │
│   │   │               │  │               │  │               │           │   │
│   │   │   228.5 V     │  │   2.34 A      │  │   534.7 W     │           │   │
│   │   │   ───────     │  │   ───────     │  │   ───────     │           │   │
│   │   │   [▓▓▓▓░░]    │  │   [▓▓░░░░]    │  │   [▓▓▓░░░]    │           │   │
│   │   └───────────────┘  └───────────────┘  └───────────────┘           │   │
│   │                                                                      │   │
│   │   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐           │   │
│   │   │    ENERGY     │  │   RELAY       │  │  ML PREDICT   │           │   │
│   │   │               │  │               │  │               │           │   │
│   │   │  1.234 kWh    │  │   ● ON        │  │   Next: 520W  │           │   │
│   │   │   ───────     │  │               │  │   ───────     │           │   │
│   │   │   Today       │  │   [TOGGLE]    │  │   85% conf    │           │   │
│   │   └───────────────┘  └───────────────┘  └───────────────┘           │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                         POWER CHART                                  │   │
│   │                                                                      │   │
│   │   600W │     •••                                                     │   │
│   │        │   ••   ••                                                   │   │
│   │   400W │ ••       ••                                                 │   │
│   │        │•           ••••                                             │   │
│   │   200W │                 ••••••••                                    │   │
│   │        │                                                             │   │
│   │    0W  └────────────────────────────────────────────────────────     │   │
│   │         10:00   10:15   10:30   10:45   11:00   11:15   11:30        │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                         ML INSIGHTS                                  │   │
│   │                                                                      │   │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │   │
│   │   │ Prediction  │  │  Anomaly    │  │   Status    │                 │   │
│   │   │ Next Hour   │  │  Detection  │  │             │                 │   │
│   │   │             │  │             │  │             │                 │   │
│   │   │   520 W     │  │  ✓ Normal   │  │  Will be ON │                 │   │
│   │   │   ±45 W     │  │  z=0.8      │  │  conf: 92%  │                 │   │
│   │   └─────────────┘  └─────────────┘  └─────────────┘                 │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7.4 Component Details

### Top App Bar

```html
<header class="top-app-bar">
    <div class="top-app-bar__leading">
        <div class="top-app-bar__icon">
            <span class="material-icons-outlined">bolt</span>
        </div>
        <h1 class="top-app-bar__title">Smart Energy Monitor</h1>
    </div>
    
    <div class="top-app-bar__spacer"></div>
    
    <div class="top-app-bar__actions">
        <div class="device-selector">
            <span class="material-icons-outlined">devices</span>
            <select id="appliance-select">
                <option value="fridge">Fridge</option>
                <option value="ac_1">AC 1</option>
                <!-- ... -->
            </select>
        </div>
        
        <div class="status-chip online" id="connection-status">
            <span class="status-indicator"></span>
            <span>Live</span>
        </div>
    </div>
</header>
```

### Metric Cards

```html
<div class="metric-card">
    <div class="metric-card__header">
        <span class="material-icons-outlined">electric_bolt</span>
        <span class="metric-card__label">Power</span>
    </div>
    <div class="metric-card__value" id="power-value">534.7</div>
    <div class="metric-card__unit">W</div>
    <div class="metric-card__progress">
        <div class="progress-bar" style="width: 53%"></div>
    </div>
</div>
```

### Power Chart

```javascript
const powerChart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: timestamps,
        datasets: [{
            label: 'Power (W)',
            data: powerData,
            borderColor: '#0061a4',
            backgroundColor: 'rgba(0, 97, 164, 0.1)',
            fill: true,
            tension: 0.4
        }]
    },
    options: {
        responsive: true,
        plugins: {
            legend: { display: false }
        },
        scales: {
            y: {
                beginAtZero: true,
                title: { display: true, text: 'Watts' }
            }
        }
    }
});
```

---

## 7.5 Color Palette

### Material Design 2 Colors

| Token | Value | Usage |
|-------|-------|-------|
| `--md-sys-color-primary` | #0061a4 | Primary actions, links |
| `--md-sys-color-on-primary` | #ffffff | Text on primary |
| `--md-sys-color-primary-container` | #d1e4ff | Card backgrounds |
| `--md-sys-color-surface` | #fdfcff | Main background |
| `--md-sys-color-on-surface` | #1a1c1e | Main text |
| `--md-sys-color-error` | #ba1a1a | Errors, anomalies |
| `--md-sys-color-success` | #006d3b | Connected, normal |
| `--md-sys-color-warning` | #7d5800 | Warnings |

---

## 7.6 Real-Time Updates

### SSE Connection

```javascript
class DataStream {
    constructor() {
        this.eventSource = null;
        this.reconnectDelay = 1000;
    }
    
    connect() {
        this.eventSource = new EventSource('/stream');
        
        this.eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.updateUI(data);
        };
        
        this.eventSource.onerror = () => {
            this.updateStatus('offline');
            setTimeout(() => this.connect(), this.reconnectDelay);
        };
        
        this.eventSource.onopen = () => {
            this.updateStatus('online');
        };
    }
    
    updateUI(data) {
        document.getElementById('voltage-value').textContent = data.voltage.toFixed(1);
        document.getElementById('current-value').textContent = data.current.toFixed(2);
        document.getElementById('power-value').textContent = data.power.toFixed(1);
        
        // Update chart
        addDataPoint(data.timestamp, data.power);
        
        // Check anomaly
        if (data.anomaly) {
            showAnomalyAlert(data);
        }
    }
}
```

### Relay Control

```javascript
async function toggleRelay() {
    const response = await fetch('/relay', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ on: !currentRelayState })
    });
    
    const result = await response.json();
    updateRelayUI(result.requested);
}
```

### ML Predictions

```javascript
async function fetchPrediction(appliance) {
    const response = await fetch(`/ml/predict/${appliance}`);
    const data = await response.json();
    
    if (!data.error) {
        document.getElementById('ml-prediction').textContent = 
            `${data.predicted_power} W`;
    }
}
```

---

## 7.7 Responsive Design

### Breakpoints

| Breakpoint | Width | Layout |
|------------|-------|--------|
| Mobile | < 600px | Single column |
| Tablet | 600-1024px | 2 columns |
| Desktop | > 1024px | 3 columns |

### Grid Layout

```css
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
    padding: 16px;
}

@media (max-width: 600px) {
    .metrics-grid {
        grid-template-columns: 1fr;
    }
    
    .top-app-bar__title {
        display: none;
    }
}
```

---

## 7.8 Animations

### Card Hover

```css
.metric-card {
    transition: transform 0.2s, box-shadow 0.2s;
}

.metric-card:hover {
    transform: translateY(-4px);
    box-shadow: var(--md-elevation-3);
}
```

### Value Updates

```css
@keyframes pulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.05); }
    100% { transform: scale(1); }
}

.metric-card__value.updating {
    animation: pulse 0.3s ease-out;
}
```

### Status Indicator

```css
.status-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--md-sys-color-success);
    animation: blink 2s infinite;
}

@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}
```

---

## 7.9 Anomaly Alerts

### Alert Toast

```html
<div class="alert-toast error" id="anomaly-alert">
    <span class="material-icons-outlined">warning</span>
    <div class="alert-content">
        <div class="alert-title">Anomaly Detected</div>
        <div class="alert-message">Power spike: 1250W (z-score: 4.2)</div>
    </div>
    <button class="alert-dismiss">
        <span class="material-icons-outlined">close</span>
    </button>
</div>
```

### Alert Styling

```css
.alert-toast {
    position: fixed;
    bottom: 24px;
    right: 24px;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px 24px;
    background: var(--md-sys-color-error-container);
    color: var(--md-sys-color-error);
    border-radius: var(--md-radius-lg);
    box-shadow: var(--md-elevation-3);
    animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
    from { transform: translateX(100%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
}
```

---

## 7.10 Chart Configuration

### Line Chart Options

```javascript
const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
        intersect: false,
        mode: 'index'
    },
    plugins: {
        legend: { display: false },
        tooltip: {
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            titleFont: { size: 14 },
            bodyFont: { size: 12 },
            padding: 12,
            cornerRadius: 8
        }
    },
    scales: {
        x: {
            type: 'time',
            time: {
                unit: 'minute',
                displayFormats: { minute: 'HH:mm' }
            },
            grid: { display: false }
        },
        y: {
            beginAtZero: true,
            grid: { color: 'rgba(0, 0, 0, 0.05)' },
            ticks: { callback: (v) => `${v}W` }
        }
    }
};
```

---

## 7.11 Screenshots

### Desktop View
```
┌─────────────────────────────────────────────────────────────┐
│  [Full dashboard with all 6 metric cards and chart]         │
│  - Top bar with device selector and status                  │
│  - 3x2 grid of metric cards                                 │
│  - Full-width power chart                                   │
│  - ML insights panel                                        │
└─────────────────────────────────────────────────────────────┘
```

### Mobile View
```
┌───────────────┐
│ ⚡ Monitor    │
│ [🟢] [⚙️]    │
├───────────────┤
│ ┌───────────┐ │
│ │  534.7 W  │ │
│ │   POWER   │ │
│ └───────────┘ │
│ ┌───────────┐ │
│ │  228.5 V  │ │
│ │  VOLTAGE  │ │
│ └───────────┘ │
│      ...      │
│ ┌───────────┐ │
│ │ [CHART]   │ │
│ │           │ │
│ └───────────┘ │
└───────────────┘
```

---

## Next: [Deployment Guide →](./08-deployment-guide.md)
