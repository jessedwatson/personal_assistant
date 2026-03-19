# Pricing Platform Brief - 2026 Goals
**Author: Aleksey Maslov | Sponsors: Gil Shulman**
**Company KR 1.1: Grow AMER region send volume by 40%**
**TTKR: Increase activity with strategic, marketable and competitor-aware pricing**

## Summary

By the end of 2026, the Pricing platform will evolve from the manual configuration tool that is only focused on remittances to an intelligent pricing platform that automates human decisions, and empowers additional ways to transfer money. The core of this evolution is based on the reliable competitive intelligence and cost data pipelines. Based on these, we will build an ML-driven pricing platform that will optimize pricing globally across 5,300+ corridors.

For the Core remittance business, it will help to increase customer activity and grow RLTE via pricing optimizations. We will:
- Expand our infrastructure by incorporating reliable competitive intelligence infrastructure, costs and historic price configurations
- Improved customer elasticity measurement: both by analyzing historical A/B tests, and by building capabilities that measure ongoing price elasticity (e.g. price jitters, FX trend-aware dynamic spread)
- Automate price optimizations with ML-driven pricing platform
- Improve our price merchandising capabilities: make our merchandising more flexible and move away from legacy packages both to empower new pricing models, and set the foundation for intelligent price optimization
- Improve the ability to merchandise price changes throughout customer touchpoints and lifecycle channels

For new initiatives, the Pricing platform will enable new ways to send money:
- Unlock currency-based pricing. We will invest in new ways to use, store and manage currencies, including stablecoins - empowering multi-currency senders.
- Pricing and promotions for focus segments (SMB, Freelancers and others) to offer differentiated pricing and pay-in/pay-out choices to those segments. Offer transfer benefits to Remitly One members.
- Pricing for new transfer types. We will offer pricing and promotions for new transfer types, including wallet deposits, withdrawals, currency conversions, P2P transfers.

Pricing is used to price every single transfer. Promotions are used for passing discrete benefits to customers (e.g. new customers signing up, rewarding discrete actions, X times/month benefits).

## Current State

Our current pricing platform is focused on remittance pricing. It allows pricing analysts to set prices for each corridor and conduit separately, and measure customer responses to price changes via A/B testing.

In 2026, we launched capabilities foundational for the future ML-driven intelligent pricing platform:
- Offering differentiated pricing to different customer segments.
- A/B testing pricing structure changes (requires changes from other teams to adopt new API)
- Observability of current pricing structures
- Improve pricing operations related to pricing structure changes.

## Existing Challenges and Opportunities

**Data availability:** We do not have all data points required for pricing decisions.
- Competitive pricing infrastructure: need reliable, timely competitive pricing data in the top 50 corridors. Currently takes weeks or months to respond to competitor price movements.
- Cost data: need accurate pay-in, pay-out, treasury and fraud costs available to pricing analysts and included in pricing models.
- Customer elasticity data: limited understanding. Test results maintained per corridor basis, no elasticity curves measured.
- Price changes history: not searchable, making it hard to analyze historic performance.

**Manual price optimizations:** Long tail is unmanaged — corridors outside top 50 represent ~60% of TAM, capture only ~20% of volume.

**Inefficiencies of price merchandising:** Customers don't understand our pricing. No automated mechanisms to let customers know when prices have changed or when we beat a competitor.

**Platform evolution needs:**
- New segments: SMB, Freelancers need differentiated pricing
- New priceable actions: wallet deposits, currency conversions, wallet-to-wallet transfers
- Multi-surface expansion: Remitly One, WhatsApp, Tiqmo

## Solution Tenets

- **Transfers at core:** Focused on transfer pricing only — expanding to currency-first pricing, wallet pricing. Will not focus on non-transfer pricing (interest, debit cards, subscription fees).
- **One Price Does Not Fit All:** Price by customer group. Use pricing in tandem with promotions.
- **Automation is the default:** Build pricing systems that automate all pricing decisions.
- **Value Driven:** Price competitively with trust earning the premium.
- **Data-informed decisions:** Measure impact of pricing on customer behavior.

## 2026 OKRs (Draft)

### Objective 1: Pricing Data Foundations
**Impact: Large — key goal for pricing and promo decisions. $X,XXXM/3yr**

- Q1'26: Launch 8 new scrapers to cover top 50 corridors (DONE)
- Q1'26: Integrate with Inventory Tracking System for treasury costs (DONE)
- Q2'26: Hourly competitive pricing data in top 50 corridors
- Q2'26: 24 months price change history available for ML and analytics
- Q2'26: Pay-in costs ingestion; update integration with Treasury
- Q2'26: Price jitters to estimate FX price sensitivities
- Q3'26: Expand competitive data coverage to 5,000+ corridors
- Q3'26: Pay-out costs ingestion
- Q3'26: Searchable price experiment history
- Q4'26: Real-time competitive coverage in top 50 corridors

### Objective 2: ML-Driven Pricing and Optimizations
**Impact: Large — $XXX/yr**

- Q1'26: Segment-specific pricing experiments (LIVE)
- Q1'26: Interaction between pricing & promos — measure interaction to optimize for NPV (LIVE)
- Q1'26: Define merchandising guardrails for ML-driven price optimizations
- Q2'26: Long-tail cost-plus repricing across ~4,800 long-tail corridors
- Q2'26: Launch FX trend-aware dynamic spread test in top 5 corridors
- Q3'26: Build true price elasticity curve for top 10 corridors using A/B tests and historical data
- Q3'26: Launch fully guardrailed automated optimization pricing in 3 corridors
- Q3'26: Independent pricing & promo tests
- Q4'26: Management dashboard for ML pricing optimizations

### Objective 3: Price Merchandising Investments
**Impact: Large — $XXM/yr**

- Q2'26: Define guardrails and tenets for price merchandising
- Q2'26: Expand live FX rate alerts via better targeting and automation
- Q2-Q3'26: Price change communications — highlight price advantages via home screen, LCM, SEO
- Q2'26: Competitive price comparison — allow customers to compare our pricing to key competitors
- Q3'26: Price communications targeting specific segments
- Q3'26: Quote validity merchandising — expose quote lock-in period in customer experience
- Q4'26: Locked FX rate exploration

### Objective 4: Pricing for New Initiatives and New Segments
**Impact: Large — potentially transformational. $XXXM/yr**

- Q3'26: Currency-based pricing — multi-currency remittances (increase statistical power of pricing tests for shared currencies)
- Q3'26: Multi-currency support in Wallet (enable wallet expansion + stablecoin)
- Pricing and promotions for SMB, Freelancers: bulk payments, recipient checkout, payment requests
- Remitly One remittance benefits
- Wallet pay-in pricing and promotions
- Wallet P2P transfer pricing
- Split payments, bulk payments for SMB
