# Talking about the project

## Project title

**Data centre chilled-water pumping and N+1 capacity**

## Two main findings and CV bullets

- Modelled a conceptual 1 MW data hall's CRAH chilled-water loop in Python, comparing fixed-speed throttling with variable-speed differential-pressure reset; verified equal cooling-water flow and modelled 47% lower annual pumping energy under an illustrative load profile.
- Assessed steady-state N+1 pumping capacity for a two-duty, one-standby arrangement across 18 pump-outage cases, then challenged hydraulic resistance, terminal pressure and efficiency assumptions to identify capacity limits and cases where pumping-energy savings reversed.

The first bullet covers the energy comparison. Add the second when there is room to discuss reliability and engineering judgement. Keep the words “conceptual”, “modelled” and “illustrative” when adapting the wording: the project uses assumed hardware curves, and its energy result covers pumping electricity.

## Approximately 60 seconds

The question was whether variable-speed pumps could reduce electricity use in a data centre's chilled-water loop while still meeting cooling demand. I used a conceptual 1 MW data hall with CRAH coils and two duty pumps plus one standby. A heat balance gave the required flow, then pump and network curves set the operating points, including branch losses and throttling. At equal flow, variable speed used about 47% less annual pumping energy under an illustrative load profile. Every single-pump-unavailable case met the reference steady-state flow requirement. The sensitivity checks were particularly useful: higher resistance could defeat capacity, and unfavourable pressure, efficiency and load assumptions reversed the savings. Those results make variable speed worth investigating, with real equipment data and operating hours needed before a decision. The model leaves coil performance, rack temperatures and cooling during changeover unresolved.
