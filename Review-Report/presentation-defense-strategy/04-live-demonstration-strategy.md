# live demonstration strategy

## demo setup

Use one stable resistive load (600 W kettle), one low-load device (65 W charger), the assembled meter, and the dashboard on a laptop connected to the same network.

## demo sequence (about 2.5 to 3 minutes)

1. Start with relay OFF, show OLED and dashboard both at near-zero power.  
2. Turn relay ON from the dashboard, then run kettle. Show voltage, current, and power rising on OLED and dashboard with SSE updates.  
3. Turn relay OFF from touch input on device. Show dashboard state syncing back through MQTT relay/state.  
4. Switch to charger load and show lower current range; mention known ACS712 low-current limitation and measured error profile.  
5. Trigger one anomaly scenario by sudden load transition (OFF to kettle ON) and point to anomaly panel response.

## what to say during demo

- "This proves full bidirectional control: browser to backend to MQTT to relay, then confirmation back to UI."  
- "This also proves local fallback. Even if the dashboard is unavailable, OLED still reports live values."  
- "We are not hiding limits. The low-current error increase is measured, documented, and tied to sensor resolution."

## backup plan if network is unstable

Show OLED live values and touch-based relay control first, then open stored history in dashboard to prove logged telemetry and continuity.

