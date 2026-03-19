# ML-Driven Pricing Optimizations Plan

1. Summary
To improve and optimize our prices globally, we will implement and launch a new ML-driven pricing optimization engine. Its recommendations will be automatically applied to mid- and long-tail corridors, and surfaced in the top 50 corridors to pricing analysts as a signal for price optimizations.
The implementation of this engine will be across the following phases:
Phase 1: Foundations and data readiness (Q1-Q2 ’26). Set up the initiative for future success and build inputs required to optimize prices.
Phase 2: Model development and controlled rollout (Q2 ’26). Build the pricing model using Phase 1 data and deploy it in a controlled environment with human oversight.
Phase 3: Expansion and portfolio optimization (Q3 ’26). Automate the pricing recommendations, roll out the model to more corridors, and drive business outcomes.
Decisions required
Decision
Options
Impact if unresolved
What is the goal for ML-driven pricing optimizations? Related:
Over what time horizon do we evaluate success? What is our forecast horizon?
Cross-subsidization policy for corridors and customer segments
A: RLTE growth
B: QAU growth with GM guardrail
C: Portfolio approach (destination)

Time horizon: Recommended: rolling 12  months evaluation
Cross-subsidization: 
1. No cross-subsidization
2. Budgeted (recommended)
3. Time-bound
Model design cannot begin; experimentation framework can’t be scoped. 

Every price change will become an ad-hoc debate, repeating past failures.
Customer experience guardrails for pricing optimizations: how would these changes impact our customers?
1. FX rates only
2. FX rates and fees (recommended)
3. FX rates, fees, pricing structures (out of scope scope initially)
Model design and experimentation scope can’t be defined. Risk of inconsistent customer experience.
Opportunities to accelerate the development of ML-driven pricing optimizations & rollout plan
Availability of competitive data
Availability of costs data
Alignment on the rollout plan (start as a recommendation mechanism in the top 50 before deploying wider)
Availability of a long history of pricing configurations in Lakehouse, cleaned from outages/LSEs/emittance issues
Delay of the rollout of this model to our target corridors

2. Goals
Corridors outside of the top 50 represent ~60% of the total addressable market for remittances, but currently account for ~20% of our volume. By optimizing pricing, we target overall volume growth of X% and incremental revenue growth of Y% over one year following the complete deployment of the system.
Discuss: What is the goal for ML-driven pricing optimizations?
To succeed with ML-driven pricing optimizations, we need to align on what we are optimizing for and the time horizon over which we measure impact. This direction will lead to very different systems and customer experiences. Given where we are today - limited elasticity data, higher per-transaction costs, and thin competitive intelligence, we see three realistic objectives:
Objective A: Grow revenue less transaction expenses (RLTE) across non-core corridors. The critical question is the time horizon over which we forecast and measure that growth, because it fundamentally changes what the model does:
Measured over a short window (day/week/month), the model will likely gravitate toward price increases. This model will work for a while, but in non-core corridors with an already small customer base, price increases compress volume, and concentrate revenue on a shrinking pool of users. This is what we observed when Prometheus MAB was deployed with a 1-week refresh window.
Measured over a longer window (quarter/year), the model can grow RLTE even as we lower prices through increased transaction frequency, but longer feedback loops mean slower learning, fewer iteration cycles, and more difficulty isolating the effect of pricing changes from external factors.
Objective B: Grow quarterly active users and send volume within the target GM guardrail. This model will price to bring new senders and increase transaction frequency. In non-core corridors, this likely means lowering prices where demand is elastic. 
As we don’t merchandise our everyday pricing and competitive comparison to new customers, there is an upper bound to the efficacy of this strategy, unless we change that approach.
Growing QAUs almost certainly compresses RLTE per transaction. The bet is that the volume gain more than offsets the per-transaction margin loss, and that scale eventually brings costs down within the relevant timeframe
Objective C: Optimize prices across the corridor portfolio (our end goal). This approach will be the most sophisticated of these three. Rather than optimizing each corridor independently, the model considers the full portfolio, with some corridors priced for margin, others for growth, and the mix is managed to hit overall targets. 
This approach requires a clear position on cross-corridor subsidization. The main risk for this approach is complexity: portfolio optimization requires more data, more governance, and more trust in the model’s recommendations.
Measurement safeguard and time horizon impact
Measurement safeguard: We strongly recommend that any objective that touches RLTE should be evaluated over a rolling twelve-months window, not quarterly. This protects against the short-term incentive to raise prices, undermining any growth-oriented pricing strategy regardless of which objective we choose.
This impacts the results we get from selecting a particular optimization objective, the forecast horizon of our model, and the data needs that we need to have to make this model work.
Applying these objectives to specific corridors
When the model looks at a specific corridor to define pricing, the answer will depend on the objective. Example scenarios are listed below:
Scenario
RLTE growth priority
QAU priority
Portfolio priority
Corridor with low volume but inelastic demand
(e.g. USA-CHN)
Raise price
Hold price, invest in acquisition (e.g. promotions)
Raise price, use margin where we expect to see more price sensitivity.
Corridor with elastic demand and high costs
(e.g. MAR, ZWE receive)
Hold price at floor
Lower price, accept near-term loss
Lower price if the portfolio can absorb it.
Corridor with strong volume growth but negative RLTE
<e.g.>
Reprice upward or exit
Maintain low price to sustain growth
Continue funding if growth justifies portfolio-level investment
New competitor entry
(e.g. TapTap investments in AUS)
Hold price, protect margin
Lower price to defend share
Depends on corridor’s portfolio role

Recommendation
Our recommendation is to adopt Objective C (portfolio optimization) as the governing framework, while monitoring RLTE and QAU growth as the two metrics the portfolio is managed against. This will allow us to be more intentional about which corridors serve which purpose. However, this approach only works if we have a clear answer to the following question: 
Question: How are we willing to cross-subsidize corridors across the portfolio? 
We have the following options:
Each corridor type must be RLTE positive on a standalone basis. This reduces Objective C to Objective A.
Cross-subsidization is permitted within a defined quarterly budget, allocated to corridors that demonstrate measurable QAU and volume growth during the test phase. Our recommended approach.
Cross-subsidization is permitted for a specific time window per corridor (e.g. two quarters), after which the corridor must show a move toward standalone RLTE sustainability. Less risky than 2, but hard time cutoffs may pressure teams to raise prices, effectively regressing to option 1.

3. Current state and constraints
Pricing optimizations are primarily focused on top 50 corridors, leaving mid- and long-tail corridors with the pricing that has not been monitored or updated since corridor launch. This under-investment has led to a low 4% market penetration, compared to ~25% in the top 50 corridors. We believe that ML-driven pricing optimization can offer more relevant pricing in corridors outside of the top 50 to fuel their growth.
Constraints
Non-core corridors have characteristics that require a different approach compared to top 50 markets:
Higher per-transaction costs. We lack scale with payout partners, leading to higher costs and compressing the margin band available for optimization. 
Furthermore, we currently lack the visibility into our overall transaction costs per corridor - making it difficult to perform any optimizations.
Lacking both the competitive positioning and customer elasticity data. Without these inputs, any pricing model is operating on assumptions rather than evidence. 
Misalignment on corridor cross-subsidization. There is no established policy on whether profitable corridors should fund growth in promising but currently unprofitable ones. This question will surface every time the model recommends a price reduction in a marginally profitable corridor.
Past learnings
Historically, we used three different approaches to automated/ML pricing in the past (Hyperion model, Quote-level MABs, Prometheus MABs), with none live as of March 2026. The key learnings from these initiatives are:
Short-term optimization metrics drove price increases. The biggest recurring issue across all three past approaches was that optimization metrics were short-term focused, leading to price increase in most cases, which did not reflect how we make pricing decisions strategically.
Insufficient operational and financial commitment. Each initiative faced headwinds that undermine execution: the Hyperion model lacked relevant competitive data, Quote-level MABs required a complete rearchitecture to support new pricing models, and Prometheus MAB rollout was stalled by the 80/20 rule implemented in Q1 '25.
Customer experience impact of pricing optimizations
As we merchandise 
Price optimizations might involve optimizing FX rates and fees - and any time we change prices, they might lead to inconsistent price merchandising. In order to succeed, our price optimizations should be able to change fees, FX rates and pricing structures; however, we need to maintain the customer experience within the specific guardrails:
FX changes are deemed to be less-risky, and with the recent repeal of 80/20 rule we are able to A/B test FX rates - both for use in a model and as a holdout to measure the model performance.
Fee optimizations are more risky, as several jurisdictions require to maintain 30-45 days between fee changes to avoid “bait and switch” pricing. Our current platform allows fee A/B testing; however, there is a chance that customers might get different fee levels between their sessions.
We are currently unable to A/B test different pricing structures in the same corridor. We believe that this change is very risky, and will perform this as a pre-post change.

Discuss: What types of price changes should this model be authorized to make?
While we will train this model to provide recommendations first, without automatically applying them to corridors, we need to align on the types of pricing optimizations we are willing to implement:.
FX rates only. This is the lowest risk, and operationally ready today, but it offers the narrowest optimization lever. FX margin alone may not provide enough room to meaningfully change pricing outcomes in corridors and transaction segments where the fee component is the primary cost to customers.
FX rates and fees. Broadens the optimization space; however, requires managing the constraints on fee change frequency. We will avoid fee A/B tests with this model to reduce price inconsistencies. Recommended approach initially.
FX rates, fees, and pricing structures. This allows us to have the most powerful optimizations; however, it might lead to the highest possible risk. We recommend performing pricing structure changes using the new bulk tools implemented as a part of product catalog work based on the related corridors.

4. Prerequisites and decision gates
Leadership decisions (required before any model work)
The optimization goal decision is the single most critical prerequisite for this initiative. It defines what the model optimizes for, what data we need to collect, what elasticity we need to measure, and how we evaluate success. Every other prerequisite flows from this decision. Without it, the team can’t design experiments, select features, or define success criteria.
Pricing ML prototype
We are building a prototype pricing ML model to validate our assumptions and data needs. We are planning to launch it in the top 50 corridors to clearly define the data needs, corridor specification and modeling approach. Outcomes that we expect from this prototype:
Define clear pricing data requirements for the initial version of the model
Define the modeling approach and how it would improve our objectives
Validate optimization objectives and test them in the shadow mode
Data and infrastructure
Competitive data
We lack systematic competitive pricing data for non-core corridors. Our competitive intelligence plan covers the phased expansion from key corridors to a coverage across the full portfolio:
Q1-Q2: establish competitive coverage for the top 50-100 corridors.
Q3: expand the coverage to all corridors - required for portfolio-level optimization of all corridors
How to accelerate competitive pricing data availability:
Our current competitive intelligence plan provides a phased implementation approach with key questions that we need to resolve.
Alternative: $490K/yr contract with FXCIntel will provide competitive data in the top 24 corridors; however, it will be insufficient for wider rollouts even in our largest markets.

Cost data
Reliable cost data is a prerequisite for any pricing optimization. However, the cost data is currently fragmented, and several components are missing or incomplete:
Pay-out costs: Currently maintained in GSheets, with some cost data dating back to 2023. Analytics engineering is working on making pay-out costs available in Q2-Q3. As pay-out costs are the largest variable cost component, they are essential for accurate margin calculations. Flagging this as a dependency that requires prioritization.
Transactional data: We have high-level transactional data at a send country level. The accuracy vs actuals (invoices) varies based on the type of cost:
Pay-in costs (card pay-in, mostly Checkout and Stripe)
Coverage: 80% / Accuracy: 98%
Pay-out costs (disbursement costs)
Coverage: unknown (pricing doesn’t have full visibility today) / Accuracy: ~50% at a partner/currency/payout method level; ±10% at the group level
Fraud Reserve 
Coverage: 100% / Accuracy: 99%
Tooling costs (that can be directly attributed to transactions)
Coverage: unknown / Accuracy: 80%
Treasury related costs (mostly spreads today)
Coverage: 100% / Accuracy: TBC
Cost data needs to empower ML-driven pricing:
Transactional data at a segment level
Across all cost types: Coverage 100% / Accuracy 98%+
How to accelerate cost data availability
We do not have a unified, corridor-level cost view that neither the model nor our analysts can consume. Building this pipeline is critical, but depends on cross-team prioritization decisions that are not fully within our control. Specific areas requested:
Help with analytics engineering resourcing to cover pay-out costs and improve the coverage of pay-in costs
Work with the Treasury to measure the accuracy of treasury-related costs.

Customer elasticity data
The optimization metric dictates what type of elasticity we need to measure and our experimentation approach:
Short-term price elasticity (price sensitivity at the transaction level): price jitters provide a proxy for short-term elasticity measurement. We are planning to launch price jitters in Q2.
Long-term price elasticity (impact on retention, frequency and LTV/NPV): requires structured A/B testing over longer time horizons. We have approximate long term elasticity data only in top 50 corridors.
If we want the model to optimize corridors with no-to-extremely limited traffic, then we don’t have any measures of customer elasticity, and thus would have to make decisions based on other data points.
If we optimize for short-term RLTE (Objective A with a short measurement window), jitters may be sufficient. For other objectives, we need to combine jitters with A/B testing and cross-corridor testing infrastructure - reinforcing why the metric decision must precede the data collection strategy.
Organizational readiness
Pricing governance. Who makes pricing decisions before the model is live? This question derailed past rollouts and must be resolved before deployment. We need to define who reviews model recommendations, what triggers a human override, and how overrides are documented and fed back into the model + what is the escalation path when the model recommends something unexpected.
Model validation before wider deployment. A model that systematically misprices corridors can cause damage that will take quarters to reverse. We will validate the model before a wider rollout:
Shadow mode: the model will generate pricing recommendations based on the current pricing. Pricing analysts will evaluate these recommendations for accuracy.
Limited deployment: the model will be used for setting prices in 10-20 corridors with human approval for every change and predefined rollback criteria. Performance will be measured either via A/B tests or against holdout corridors.
Expansion: we will roll out the model to additional corridors only after meeting the defined performance thresholds.
Discuss: rollout plan
Should we validate the model before a wider rollout?
Our strong recommendation is yes. While the staged validation approach (shadow mode → limited deployment → expansion) adds 2-3 months to the timeline, it drastically reduces the risk of bad model causing damage in smaller corridors.
As we have stronger data coverage in top 50 corridors (competitor coverage, price elasticity, cost data), we recommend to start testing this model in these corridors. As we expand our data availability in smaller corridors, we could deploy model recommendations there.

5. Implementation phases
Phase
Outcomes
Phase 1: Foundations and data readiness (Q1’26-Q2’26)
Goal: Set up the initiative for future success & build inputs required to optimize prices.

Outcomes: optimization metric(s), corridor prioritization, data feeds (elasticity, competitive, cost data, pricing configuration history).
Optimization metric alignment
Select the optimization metric and forecast horizon based on the corridor type.
These should be corridor-level metrics to offer price recommendations.
Data: Costs data pipeline
Build and validate the pipeline that provides true margin visibility, broken down by payment costs, FX costs, risk costs and operational overhead. Defines the floor for any pricing decision.
Data: Competitive pricing audit
Expansion of the competitive pricing infrastructure (Q1-Q3)
Building dashboards, metrics and UELs that measure and store our competitive positioning
Development of competitive reaction plans
Fallback strategy in case of competitive data issues
Data: Elasticity measurement
Based on the optimization metric, either of:
Design and launch controlled price experiments that measure customer elasticity
Building pricing jitters to introduce short-term price variations (Q2)
Data: Price history
Clean, searchable price history of price configurations
Experimentation framework
Launching controlled pricing experiments to ingest model recommendations
Synthetic rules-based experiment
Measure customer interactions with the calculator in the CX (glance view)
Prototype ML model
Build an ML model prototype to validate data requirements and the optimization objective
Phase 2: Model development and controlled rollout (Q2’26)
Goal: Build the pricing model using Phase 1 data, deploy it in a controlled environment with human oversight, and validate recommendations alignment with the business strategy.

Prerequisites: 
Aligned optimization metric, cross-subsidization policy
Built data pipelines (costs, competitive data, elasticity)
Governance model for pricing decisions

Outcomes: An ML-driven model that surfaces pricing decisions to pricing analysts. Implemented success metrics, guardrails and dashboards that could be used for production rollout of the said model.
Model training and architecture
Build the pricing model incorporating elasticity data, cost structures, competitive positioning, metrics and strategic guardrails (sections 2, 4).
Shadow mode → Limited deployment
Controlled deployment
Deploy to a small number of corridors (10-20) with human review 
Define clear rollout and rollback criteria for each corridors
Governance setup
Who reviews recommendations, what triggers escalations, how overrides are documented, how the model learns from overridden decisions
Pricing platform interaction
Pricing UI changes to display and accept/reject recommendations
Feature store buildout & production hardening
Alarms and notification mechanisms
Expand data collection
Competitive data expansion across more mid-tail corridors
Customer elasticity (e.g. expansion of price jitters)
Expand cost data collection
Phase 3: Expansion and portfolio optimization (Q3’26)
Goal: expand the model to the full non-core corridor portfolio and transition to portfolio-level optimization, managing corridor-level pricing against overall RLTE and QAU targets.

Prerequisites:
Proven model performance in Phase 2 corridors
Leadership confidence in the governance model
Agreement on criteria for expanding the corridor set

Outcomes: Measurable RLTE growth across the non-core portfolio on a rolling twelve-month basis; QAU growth in corridors priced for growth; reduction in per-transaction costs where volume improves unit economics; clear corridor classification.
Portfolio expansion
Expand the model to all non-core corridors (Limited deployment → Wider rollout)
Expand data collection across all non-core corridors
Corridor reclassification: evaluate whether any corridors need to be reclassified.
Automation
Automated pricing updates: shift from human approval of every recommendation to human oversight. 
Fallback architecture: what happens when the model stops working?
Expand data collection
Competitive data expansion to thousands of long-tail corridors
Customer elasticity measurement to long-tail
UI for jitterbug management across thousands of corridors
Clear corridor classification
Corridor clustering/classification: which are profit centers, which are growth investments, which should be deprioritized


