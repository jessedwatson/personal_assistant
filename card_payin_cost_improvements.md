# Card Pay-in Cost Data Estimation Improvements
**Contributors: Jeff Brumley, Caroline Thompson, Caroline Montanari, Katherine Chiodo**
**JIRA: AE-3694: Money Movement Analytics**

## Project Background

Phase 3 of 4 to improve pay-in card cost estimates at Remitly, aimed at the "lower costs" spoke of Remitly's Flywheel Narrative. The new estimation model makes card transaction costs responsive to real-time pricing changes, updating without manual intervention. Data is based on the pay-in fees pipeline developed earlier in the year — actual costs billed by Stripe and Checkout for pay-in cards.

## Issues Resolved
- Improved accuracy of card estimates by 81% on average
- Automated updating of pay-in card cost estimates, removing manual intervention
- Resolved inaccuracies in non-card payment methods: Payto, Interac, Open Banking, Klarna
- Simplified process for updating non-card payment method costs

## Reasoning
Historically, pay-in cost estimation in Public was based on static calculations manually updated every 3-6 months. By making estimates dynamic and closer to actuals, analysts and business partners can use the data more confidently for cost-conscious engineering and product decisions.

## Timeline
- 12/8/2025: fpa.transaction_economics starts reading from pax.fact_transaction_cost
- 2/1/2026: transaction_inflow_processing_fee_amount column from Public deprecated
- 2/1/2026: transaction_inflow_processing_fee_currency_key column from Public deprecated

## Key Tables
- **New**: pax.fact_transaction_cost — column: estimated_total_payin_fee_cost_processing_currency_amount
- **Deprecated**: Public.transaction_inflow_processing_fee_amount (after 2/1/2026)
- **fpa.transaction_economics** — no changes required for users of this table

## FAQs

**What data is impacted?**
transaction_inflow_processing_fee_amount values for transactions in fpa.transaction_economics after 10/1/2025.

**How much will estimates change?**
Costs change by 10% on average, but vary considerably by payment processor and country. Historical data prior to 10/1/2025 will NOT be changed in production.

**Why estimates instead of only actuals?**
Estimates used for first 9 days due to lag in realtime data. Actuals plus rebates and average chargeback costs default after 9 days. Dashboard maintained by MMA team for actuals only.

**Why is there no estimate for a transaction?**
- Alternative payment method: business partners need to provide estimate to MMA or AENG team
- Card transaction through gateway without pricing reports (e.g. Chase, Fatzebra)
- Integration without current pricing (loans, SoV)

**Pricing recently changed but not reflected in estimates?**
Estimates based on 90-day lookback on actuals — takes time to flow through. Actuals updated within 1-3 days.

**Non-card costs seem off?**
Non-card costs are still hard-coded based on information from finance and business analysts. File ticket to AENG to update.

**Access**
Request pax schema access through DINFRA's process for adhoc analysis.
Questions: file ticket to AENG board or post in #analytics-engineering-comms.
