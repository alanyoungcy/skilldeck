GAINR Technology Stack Paper 

 

 

Overview 

GAINR is a decentralized zkIP (hidden signal) strategy marketplace for prediction-market investing. The platform is designed to connect Analysts, who originate opaque trading signals, with Professionals/Investors and Recreational Investors, who allocate capital to strategies without seeing the underlying bets. This design is materially different from copy-betting. In the GAINR model, strategy followers are investing into protected analyst workflows, while the platform preserves analyst intellectual property through zero-knowledge-oriented signal opacity and protected execution design. 

 

From a product architecture perspective, GAINR separates access rights from strategy capital. The GAINR token is used for staking and queue priority, while USDC is used for strategy allocation, market execution, settlement, and performance-fee accounting. This distinction is fundamental to the platform’s operating model and should remain explicit in all engineering, data, and product documentation. 

 

The technology philosophy behind GAINR is to combine a mobile-first product surface with a flexible application backend and a verifiable on-chain settlement layer. The frontend is built around Flutter, which the official documentation describes as a way to build “beautiful, multiplatform apps from a single codebase.”1 The operational data layer relies on MongoDB, which MongoDB describes as a “document-oriented, operational database” for modern applications.2 On-chain settlement is anchored to Solana, whose documentation describes it as a high-performance blockchain designed for mass adoption and scalable applications.3 Token functionality is extended through SPL Token-2022, which provides optional token extensions such as transfer fees and metadata-oriented functionality.4 

 

The current confirmed stack is summarized below. 

 

Layer 

Confirmed Technology 

Role in GAINR 

Status 

Frontend 

Flutter 

Cross-platform mobile application experience 

Confirmed 

Backend services 

Node.js 

Core API services, orchestration, application logic 

Confirmed 

Backend tooling 

[TBD — to be confirmed by engineering team] 

[TBD — to be confirmed by engineering team] 

Pending confirmation 

Database 

MongoDB 

Customer data, Proof of Alpha queue state, operational records 

Confirmed 

Blockchain 

Solana 

On-chain settlement, tokenized accounting, smart contract execution 

Confirmed 

Token layer 

SPL Token-2022 

GAINR token extensions for configurable token behavior 

Confirmed 

Venue connectivity 

DFlow Prediction Markets API 

Programmatic access to tokenized Kalshi markets on Solana 

Confirmed 

Smart contract framework 

Anchor 

Solana program development for settlement and distribution logic 

Confirmed 

Future venue expansion 

Polymarket via Gamma API + CLOB API 

Post-MVP market discovery and execution expansion 

Future / post-MVP 

 

 

Backend 

The backend architecture for GAINR is currently centered on Node.js for primary application services. The supporting tooling layer for automation, data jobs, CI helpers, internal agents, and related engineering workflows is not yet confirmed and should remain explicitly unassigned until the engineering team finalizes that portion of the stack. 

 

Node.js is the appropriate fit for the transactional API layer because GAINR requires responsive service endpoints for onboarding, wallet-linked account state, analyst strategy management, follower allocations, execution orchestration, and settlement event handling. In the current architecture, Node.js should be understood as the service layer responsible for coordinating application state between the mobile client, MongoDB, the Solana settlement layer, and external execution infrastructure such as DFlow. 

 

The secondary tooling layer should be treated as [TBD — to be confirmed by engineering team]. This category is expected to cover internal tooling, support scripts, automation, data-quality jobs, CI helpers, analytics support, and product-operation agents, but the implementation language and operating pattern should not be presumed at this stage. 

 

The backend must preserve one of the most important product constraints in the GAINR model: followers do not receive direct visibility into underlying analyst bets. As a result, backend services are not merely CRUD layers; they also enforce information boundaries. Public-facing APIs should expose strategy summaries, track records, allocation controls, queue rank, and settled performance outcomes, while keeping signal-level details permissioned or abstracted until execution and settlement are complete. 

 

The backend responsibilities can be summarized as follows. 

 

Backend Capability 

Primary Technology 

GAINR Function 

Client-facing APIs 

Node.js 

Account management, allocations, portfolio views, analyst discovery 

Strategy orchestration 

Node.js 

Signal intake, protected routing, execution lifecycle management 

Queue and access logic 

Node.js + MongoDB 

Proof of Alpha queue ordering and staking-linked priority state 

Settlement support 

Node.js + Solana programs 

Triggering and reconciling profit distribution workflows 

Tooling and automation 

[TBD — to be confirmed by engineering team] 

Operational scripts, CI support, data validation, internal analysis 

Future analytics support 

[TBD — to be confirmed by engineering team] 

Strategy diagnostics, performance pipelines, monitoring helpers 

From a product-management standpoint, the backend should be treated as the policy enforcement layer of the marketplace. It is where queue eligibility, KYC-linked access controls, venue routing eligibility, protected signal handling, and off-chain-to-on-chain coordination are applied consistently. 

 

 

 

Frontend 

GAINR’s frontend is confirmed as Flutter, which is well aligned with the platform’s mobile-first user experience and the requirement to move quickly with a single cross-platform codebase. Flutter’s official documentation emphasizes its role in building multiplatform applications from one codebase, which is particularly useful for a startup product that needs to deliver a consistent experience across iOS and Android without maintaining separate native stacks.1 

 

In GAINR, the frontend is not a generic trading UI. It must support a very specific trust model in which users can discover analysts, stake for access, allocate USDC capital, monitor strategy performance, and review settled outcomes without ever receiving the raw signal data that constitutes analyst alpha. This means the mobile product should prioritize clarity of allocation, capital status, queue status, performance attribution, and redemption flows over traditional market-depth disclosure. 

 

The Flutter layer should therefore be designed around a set of highly opinionated product surfaces: onboarding and KYC initiation, analyst discovery, strategy detail views, Proof of Alpha queue views, capital allocation workflows, active strategy exposure, settlement history, and staking/account management. Because GAINR separates GAINR staking from USDC strategy capital, the frontend must keep those balances visually and functionally distinct in every core user flow. 

 

Frontend Product Area 

User Need 

Flutter Role 

Onboarding and identity 

Create account, connect wallet, begin verification 

Mobile-first guided flows 

Analyst discovery 

Compare strategy providers and protected products 

Rich, responsive discovery and filtering UI 

Allocation workflow 

Commit USDC to a hidden-signal strategy 

Stepwise forms and portfolio confirmation states 

Queue visibility 

Understand stake-based access priority 

Real-time or near-real-time queue views 

Portfolio monitoring 

Track strategy-level exposure and performance 

Unified mobile dashboards and summaries 

Settlement and history 

Review realized results and fee outcomes 

Clear transaction and performance history screens 

Staking management 

Stake or adjust GAINR token position 

Separate staking balance interface from capital balance 

From a design-governance standpoint, Flutter also supports a strong component architecture, which is useful for keeping the user experience consistent as GAINR expands from MVP to broader market coverage. The main product risk on the frontend is not technology feasibility; it is ensuring that UX language and information architecture reinforce the hidden-signal model rather than drifting toward copy-trading conventions. 

 

 

 

Database 

GAINR’s primary operational database is MongoDB. MongoDB describes itself as a document-oriented operational database and highlights native support for rich JSON-like documents, ACID transactions, scaling characteristics, and enterprise-oriented security primitives.2 Those qualities map well to a product that must combine user profiles, analyst entities, strategy metadata, queue state, execution records, and portfolio summaries within an evolving application model. 

 

MongoDB is particularly appropriate for GAINR because many of the platform’s core objects are naturally document-shaped rather than rigidly relational at the product layer. Analyst profiles, strategy summaries, KYC state, queue entries, signal metadata, follower allocations, execution status objects, and settlement receipts all lend themselves to flexible schema evolution as the MVP matures. 

 

The database should not be treated as the final source of truth for settled financial ownership. Instead, MongoDB functions as the operational system of record for the application layer, while final settlement and tokenized state transitions are recorded on Solana. In practical terms, MongoDB stores the off-chain state that makes the mobile product usable, whereas the blockchain anchors the parts of the system that require verifiability and deterministic settlement. 

 

The anticipated MongoDB role in GAINR can be organized as follows. 

 

Data Domain 

Expected MongoDB Role 

Notes 

Customer data 

User profiles, onboarding records, preferences, app state 

Subject to privacy and compliance controls 

Proof of Alpha queue 

Queue rank, stake-linked eligibility, operational ordering 

Core to access-rights logic 

Analyst records 

Analyst profiles, strategy metadata, protected summaries 

Public and private fields should be separated logically 

Allocation records 

Follower strategy subscriptions and capital commitments 

Must distinguish USDC capital from GAINR stake 

Execution operations 

Non-public execution metadata, status transitions, retries 

Sensitive application-layer records 

Reporting layer 

Portfolio summaries, performance snapshots, receipts 

Derived from execution and settlement events 

The main architecture principle for the database layer is that MongoDB stores operational application context, not the authoritative ownership outcome of on-chain settlement. This separation reduces conceptual confusion and helps preserve the correct product narrative around transparency, custody, and verifiable payout logic. 

 

 

 

Blockchain 

The blockchain layer is the core trust and settlement substrate of GAINR. The platform is built on Solana, which its documentation describes as a high-performance blockchain designed for mass adoption and scalable applications.3 Solana is the correct fit for GAINR because the product needs an execution environment capable of handling token operations, position-linked accounting, settlement distribution, and wallet-native interaction without imposing excessive latency or cost on a strategy marketplace. 

 

On top of Solana, GAINR uses SPL Token-2022 for the GAINR token. Solana’s Token Extensions documentation explains that Token-2022 adds optional extensions to token mints and accounts, including features such as transfer-fee configuration and metadata-related extensions.4 For GAINR, this is materially important because the staking/access token may require richer policy controls and extensibility than a plain legacy SPL token provides. 

 

GAINR’s venue connectivity to regulated prediction markets is provided through DFlow. DFlow’s documentation states that its Prediction Markets API gives builders programmatic access to tokenized Kalshi markets on Solana and that resulting outcome positions behave like SPL tokens until market resolution.5 This makes DFlow a natural bridge between GAINR’s protected signal engine and the external venue layer, allowing the platform to orchestrate access to Kalshi-linked prediction markets while keeping the user experience inside a Solana-native product frame. 

 

Smart contract development is expected to use Anchor, which Anchor describes as a framework for building secure Solana programs and simplifying the process of writing, testing, deploying, and interacting with Solana programs.6 Within GAINR, Anchor is the most suitable framework for implementing program logic tied to settlement, accounting, distribution, and token-handling workflows. 

 

The blockchain stack is summarized below. 

 

Blockchain Component 

Technology 

Function in GAINR 

Base chain 

Solana 

Settlement layer, token interactions, program execution 

Token standard 

SPL Token-2022 

GAINR staking/access token with extension support 

Venue connectivity 

DFlow Prediction Markets API 

Access to tokenized Kalshi markets on Solana 

Smart contract framework 

Anchor 

Program development for settlement and distribution 

Settlement asset 

USDC 

Strategy capital, realized PnL settlement, fee accounting 

Access asset 

GAINR token 

Staking for queue position and access rights 

The most important blockchain design principle in GAINR is the strict separation between GAINR token staking and USDC strategy capital. The GAINR token governs access and queue priority. USDC governs deployed capital, realized profit, and performance-fee settlement. These balances should remain distinct across contract design, database models, API semantics, and user experience. 

 

A second principle is that GAINR is not exposing raw analyst positions as a public social feed. Instead, blockchain settlement should verify economic outcomes while the application layer preserves signal confidentiality. That is the architectural expression of the platform’s hidden-signal thesis. 

 

Indicative Blockchain Responsibilities 

Responsibility 

Expected On-Chain / Off-Chain Positioning 

Token staking for queue eligibility 

On-chain token state, surfaced off-chain in app views 

Allocation initiation 

App-managed workflow with wallet-linked confirmations 

Venue execution routing 

Off-chain orchestration layer through DFlow and app services 

Position accounting before settlement 

Hybrid, with application tracking and venue-linked state 

Profit distribution 

On-chain settlement logic 

Historical receipts and user reporting 

Hybrid, with blockchain references and app-layer presentation 

Post-MVP note: Future Polymarket support is in scope only as a later expansion through the Gamma API for market discovery and CLOB API for execution. It is not part of the current MVP operating stack. 

 

 

 

Version Control 

GAINR should use GitHub as the primary version-control and collaboration system, following the same general model outlined in the reference technology paper. GitHub is broadly used for distributed version control, branch-based development, pull-request review, and repository history management.7 

 

At the time of writing, the exact GAINR repository structure, branch protection rules, CODEOWNERS policy, release tagging convention, and mono-repo versus multi-repo strategy are not yet confirmed. 

 

Version Control Topic 

Current Status 

Source control platform 

GitHub 

Repository model 

[TBD — to be confirmed by engineering team] 

Branching strategy 

[TBD — to be confirmed by engineering team] 

Release tagging process 

[TBD — to be confirmed by engineering team] 

Code review policy 

[TBD — to be confirmed by engineering team] 

Protected branch settings 

[TBD — to be confirmed by engineering team] 

Until engineering confirms the repository model, the recommended assumption is a GitHub-centered workflow with protected main branches, pull-request reviews, and environment-based deployment gates. 

 

 

 

CI/CD 

GAINR’s CI/CD section should be updated to reflect an Azure DevOps-based delivery model. Microsoft describes Azure DevOps as a platform to plan, build, test, and deploy with integrated DevOps tools,8 while Azure Pipelines is the CI/CD service within that ecosystem for implementing continuous integration and continuous delivery for the application and platform of choice.9 

 

In practical terms, GAINR should adopt an Azure DevOps-centered workflow, with Azure Pipelines used for automated build, test, and deployment orchestration. This is compatible with a multi-layered delivery process in which code changes are developed on controlled branches, validated automatically, promoted through non-production environments, and only then released through approval-based production gates. 

 

Because GAINR combines mobile application code, backend services, database changes, and Solana program logic, the CI/CD model should eventually support linting, unit testing, integration testing, smart contract or program build checks, artifact packaging, release approvals, and rollback discipline across multiple technical surfaces. 

 

Some implementation details remain not yet fully confirmed, especially around final environment topology and deployment targets. For that reason, the following description should be treated as the intended operating pattern rather than a statement of finalized infrastructure. 

 

CI/CD Stage 

Intended GAINR Pattern 

Current Confirmation 

Development 

Branch-based development integrated into Azure DevOps workflow 

Confirmed direction 

Automated checks 

Azure Pipelines runs linting, unit tests, integration tests, and build verification 

Confirmed direction 

Test environment 

Azure DevOps release flow deploys validated changes for QA and functional review 

[TBD — environment details pending] 

Staging 

Azure DevOps-managed promotion to a production-like staging environment 

[TBD — environment details pending] 

Production deployment 

Controlled Azure DevOps release with approvals and rollback path 

Confirmed direction, target infrastructure TBD 

Monitoring after deploy 

Logs, metrics, alerting, runtime validation 

[TBD — observability stack pending] 

A mature GAINR CI/CD process should eventually include dedicated lanes for Flutter mobile validation, Node.js backend service validation, database migration controls, and Solana program compilation and test execution for Anchor-based smart contracts. Additional tooling lanes outside those confirmed components should remain [TBD — to be confirmed by engineering team] until finalized. 

 

 

 

DevSecOps 

A DevSecOps model is especially important for GAINR because the product handles financial allocations, token-based access rights, private strategy information, and execution connectivity to regulated prediction market infrastructure. Security, therefore, is not a separate function applied after development. It must be embedded throughout the application, data, and smart contract lifecycle. 

 

At a minimum, GAINR’s DevSecOps posture should include secure coding review, dependency scanning, secrets management, environment isolation, access-control discipline, contract review, and production monitoring. This is particularly important in a product where the business model depends on preserving analyst IP boundaries while maintaining follower trust in settlement and reporting. 

 

Several GAINR-specific operational controls are apparent even before the final security toolchain is confirmed. First, protected signal data should never be exposed through the same interfaces that serve retail portfolio reporting. Second, staking state and strategy capital state should be handled as different risk domains, because confusing them would create both UX and accounting failures. Third, any integration touching regulated venue access through DFlow and Kalshi-linked infrastructure should be reviewed for jurisdictional, KYC, and policy compliance implications based on the applicable venue rules.5 

 

The detailed DevSecOps implementation remains to be confirmed by engineering and security leads, but the operating model below reflects the right structure for the current scope. 

 

DevSecOps Area 

Intended Control 

Current Status 

Secure development 

Code review, least-privilege design, secure coding practices 

Required 

Dependency security 

Automated dependency and package scanning 

[TBD — tool selection pending] 

Secrets management 

Segregated secrets and controlled runtime access 

[TBD — platform pending] 

Smart contract security 

Program review, test coverage, release checks 

Required 

API and data security 

Access controls, logging, payload validation, privacy boundaries 

Required 

Environment security 

Segmented non-prod and prod environments 

[TBD — infrastructure pending] 

Monitoring and response 

Runtime alerting, incident triage, rollback/runbook support 

[TBD — tooling pending] 

Compliance operations 

KYC and geography-aware controls where required by venue access 

Required but implementation details pending 

The long-term objective should be a system in which security controls are embedded into development, testing, deployment, and runtime operations, rather than handled informally as one-off reviews. 

 

 

 

Deployment 

The deployment architecture for GAINR is not yet confirmed. As instructed, unknown infrastructure specifics are left explicitly unresolved rather than inferred. 

 

The current paper therefore does not assume a finalized hosting model for backend services, database infrastructure, CI runners, secrets management, or production traffic management. The engineering team still needs to confirm whether GAINR will run on a managed cloud architecture, a containerized environment, a hybrid model, or another deployment pattern. 

 

Deployment Topic 

Current Status 

Production cloud provider 

[TBD — to be confirmed by engineering team] 

Backend hosting model 

[TBD — to be confirmed by engineering team] 

Container orchestration 

[TBD — to be confirmed by engineering team] 

Database hosting topology 

[TBD — to be confirmed by engineering team] 

Secrets and key management platform 

[TBD — to be confirmed by engineering team] 

CDN / edge strategy 

[TBD — to be confirmed by engineering team] 

Observability stack 

[TBD — to be confirmed by engineering team] 

Disaster recovery design 

[TBD — to be confirmed by engineering team] 

Until those decisions are finalized, the recommended product-management position is to keep deployment language conservative and explicitly marked as pending. 

 

 

 

Conclusion 

GAINR’s technology stack is well aligned with the product it is trying to build: a mobile-first, hidden-signal strategy marketplace with protected analyst IP, off-chain operational flexibility, and verifiable on-chain settlement. Flutter provides an efficient cross-platform client foundation.1 MongoDB provides a flexible operational data layer for queue state, customer records, and product orchestration.2 Solana provides the blockchain execution and settlement substrate.3 SPL Token-2022 allows GAINR to design a more expressive staking/access token than the legacy token standard.4 DFlow provides the venue connectivity needed to access tokenized Kalshi markets on Solana.5 Anchor offers a practical framework for implementing the program logic that will govern settlement and profit distribution.6 

 

At the same time, the paper deliberately distinguishes what is confirmed from what is still pending engineering confirmation. The application stack, blockchain stack, and marketplace model are sufficiently clear to document now. By contrast, deployment specifics, final CI/CD implementation details, and some DevSecOps tooling choices should remain marked as [TBD — to be confirmed by engineering team] until the responsible technical owners lock them. 

 

That distinction keeps the document accurate while still making it useful as a product, investor, and engineering alignment artifact. 

 

 

 

References 

[1] Flutter documentation 

[2] MongoDB Documentation - Homepage 

[3] Learn how the Solana blockchain works | Solana 

[4] Extensions | Solana 

[5] Prediction Markets - DFlow 

[6] Introduction | Anchor 

[7] GitHub 

[8] Azure DevOps documentation | Microsoft Learn 

[9] Azure Pipelines documentation - Azure DevOps | Microsoft Learn