# presentation outline and speaking flow

## recommended 12-minute flow

1. **Opening hook (0:00-0:30)**  
   State the exact problem: aggregate electricity bills do not identify which appliance is wasting power.

2. **Problem and objective (0:30-1:30)**  
   Explain why whole-house meters and NILM are not enough for exact per-device diagnosis.

3. **Architecture and build sequence (1:30-6:30)**  
   Walk through sensing, edge computation, MQTT transport, backend inference, dashboard control.

4. **What is different from existing approaches (6:30-7:30)**  
   Compare direct per-appliance metering vs probabilistic disaggregation.

5. **Live demo (7:30-10:00)**  
   Show kettle load response, dashboard update by SSE, relay control, and anomaly behavior.

6. **Academic contribution slide (10:00-11:00)**  
   Present measurable outputs and implementation traceability.

7. **Viva defense (11:00-12:00+)**  
   Keep the contribution slide visible and use transition lines to bring discussion back to core technical depth.

## speaker split suggestion

- **Speaker 1:** hook, motivation, objective.
- **Speaker 2:** architecture, hardware + firmware pipeline.
- **Speaker 3:** backend interfaces + ML runtime.
- **Speaker 4:** results, contribution slide, viva handling.

