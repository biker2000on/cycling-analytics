# Feature Research

**Domain:** Cycling Analytics Platform
**Researched:** 2026-02-10
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete or non-functional.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Data Import from Major Platforms** | Standard across all platforms; users expect Garmin/Strava connectivity | MEDIUM | Must support FIT, TCX, GPX formats; API integration with rate limits |
| **Activity List/Table View** | Users need to see their ride history at a glance | LOW | Sortable, filterable by date, type, distance, TSS |
| **Calendar View** | Universal in cycling analytics; visual organization of training | MEDIUM | Weekly summaries, configurable start day (Mon/Sun), drag-drop planning |
| **Basic Power Metrics** | Core value prop; users expect normalized power, IF, TSS | MEDIUM | Requires power zone configuration, proper TSS calculation |
| **Heart Rate Analysis** | Standard fitness tracking metric across all platforms | LOW | Zone-based analysis, average/max HR, HR zones |
| **Activity Detail View** | Users need drill-down into individual ride data | MEDIUM | Timeline plot, basic statistics, lap/interval breakdown |
| **Route Map Display** | Visual representation expected for outdoor activities | LOW-MEDIUM | OpenStreetMap + Leaflet (user already specified); tile server setup |
| **Power Zones Configuration** | Required for any power-based analysis | LOW | Based on FTP/threshold; 7-zone Coggan model standard |
| **CTL/ATL/TSB Tracking** | Core fitness tracking; Coggan model widely adopted | MEDIUM | 42-day CTL, 7-day ATL, TSB = CTL - ATL; proper weighting |
| **Fitness Chart/PMC** | Visual representation of fitness progression over time | MEDIUM | Line chart with CTL/ATL/TSB, date range selection |
| **Critical Power Curve** | Expected by power meter users; standard analysis | MEDIUM | Best efforts over various durations (5s, 1min, 5min, 20min, etc.) |
| **FTP/Threshold Estimation** | Users need automated threshold detection | MEDIUM | 95% of 20min is standard; support manual override |
| **Multi-Activity Support** | Users do multiple ride types (indoor/outdoor, race/training) | LOW | Activity type classification, sport-specific zones |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Xert XSS Metrics (Low/High/Peak)** | Advanced training load calculation; more nuanced than TSS | HIGH | Reverse-engineering required; user explicitly requested; separates by intensity type |
| **Xert-style Threshold Power Model** | Continuous threshold estimation without testing | HIGH | Alternative to manual FTP tests; user explicitly requested |
| **Fat/Carb Utilization Calculation** | Metabolic insight rare in free platforms | HIGH | Requires HR/power modeling; substrate utilization analysis; TrainingPeaks premium feature |
| **30-Second Power Zone Shading** | Granular visualization of intensity distribution | MEDIUM | More detailed than lap-based; user explicitly requested; compute-intensive |
| **Configurable Threshold Methods** | Flexibility in FTP calculation (95% 20min, 90% 8min, manual, Xert) | MEDIUM | User explicitly requested; accommodates different testing protocols |
| **Block Periodization Planning** | Structured season planning with training blocks | HIGH | User explicitly requested; CTL progression modeling for target events |
| **Goal-Based Plan Generation** | Automated training plan from target event + fitness | HIGH | User explicitly requested; reverse-engineers CTL ramp to hit target on event day |
| **Self-Hosted/Privacy-First** | Full data ownership; no cloud dependency | LOW | Differentiates from Strava/TrainingPeaks; Docker deployment; user controls data |
| **Open Algorithm Implementation** | Transparency in calculations; educational value | LOW | Unlike proprietary platforms; can verify CTL/XSS formulas |
| **Power Analysis Detail** | Deep dive into power metrics per activity | MEDIUM | Mean max power, quartile analysis, variability index, power distribution |
| **Totals Page with Charts** | Aggregated statistics (weekly/monthly/yearly) | MEDIUM | Intervals.icu feature; distance, time, elevation, TSS totals with trends |
| **Advanced Power Modeling** | Morton 3-parameter or Monod-Scherrer 2-parameter CP models | HIGH | Intervals.icu offers this; more sophisticated than simple FTP |
| **Automatic Interval Detection** | AI-powered workout structure recognition | MEDIUM | Identifies efforts without manual lap marking; improves analysis |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Real-Time Live Tracking** | Users think it's "modern" | Requires websockets, polling infra, mobile app; scope creep; rarely used | Post-ride analysis is core value; defer until proven demand |
| **Social Feed/Activity Comments** | Strava has it | Becomes moderation problem; feature bloat; not core value prop | Keep focus on analytics; integrate with Strava for social |
| **Workout Recommendations AI** | Sounds impressive | Complex ML; needs large dataset; high maintenance; Xert/TrainerRoad territory | Manual planning + block periodization sufficient for MVP |
| **Mobile App** | Users assume it's needed | 2x development effort; sync complexity; web-first is sufficient | Responsive web design covers 90% of mobile needs; defer native app |
| **Video Analysis Integration** | Seems valuable | Wrong domain (form analysis vs power analysis); scope creep | Stick to power/HR data; route mapping sufficient for activity context |
| **Nutrition Tracking** | Common in fitness apps | Feature bloat; not differentiator; many dedicated apps exist | Fat/carb calculation from ride data sufficient; don't track meals |
| **Equipment Tracking** | TrainingPeaks has it | Low value-add; maintenance burden; not analytics focus | Component wear estimates could work (e.g., chain wear from km) if simple |
| **Custom Charts/Dashboards** | Power users request | Infinite feature requests; never "done"; maintenance nightmare | Curated, opinionated views based on research (PMC, power curve, etc.) |
| **Built-in Workout Player** | Seems like table stakes | Requires device integration (Zwift, trainers); complex; many solutions exist | Export workouts in standard formats (ZWO, MRC); let users use existing tools |
| **Automatic FTP Detection** | Easier than testing | Algorithms vary wildly; often inaccurate; users distrust "magic" | Offer multiple estimation methods (95% 20min, 90% 8min, Xert model) + manual override |

## Feature Dependencies

```
Data Import
    └──requires──> Activity Storage
                       └──requires──> Activity List View
                       └──enables──> Activity Detail View
                                         └──requires──> Route Map Display
                                         └──requires──> Power Analysis
                                         └──requires──> HR Analysis

Power Zones Config
    └──requires──> FTP/Threshold Estimation
                       └──enables──> Power Metrics (TSS, IF, NP)
                                         └──enables──> CTL/ATL/TSB
                                                           └──enables──> Fitness Chart
                                                           └──enables──> Season Planning

Critical Power Curve
    └──requires──> Historical Activity Data
                       └──requires──> Power Modeling (optional: Morton/Monod-Scherrer)

Xert XSS Metrics
    └──requires──> Xert Threshold Model
                       └──requires──> Power Curve Analysis
                                         └──enables──> Low/High/Peak XSS Breakdown

Block Periodization
    └──requires──> CTL/ATL/TSB
                       └──requires──> Calendar View
                                         └──enables──> Goal-Based Planning

Multi-User Auth
    └──enables──> Coach/Athlete Sharing
                       └──requires──> Privacy Controls
```

### Dependency Notes

- **Data Import is foundational:** Nothing works without activity data; priority #1
- **FTP/Threshold required before power metrics:** Can't calculate TSS/IF without zones
- **CTL calculation requires TSS history:** Need 42+ days of data for accurate CTL
- **Xert features are interdependent:** XSS Low/High/Peak requires Xert threshold model, which requires power curve analysis
- **Season planning builds on fitness tracking:** Can't plan CTL progression without current CTL/ATL/TSB
- **Power analysis enhances activity detail:** Not required for basic view but significantly improves value
- **Multi-user is independent:** Can defer; doesn't block single-user MVP
- **Route mapping is parallel:** Enhances activity view but doesn't block metrics

## MVP Definition

### Launch With (v1.0 - Core Analytics)

Minimum viable product — what's needed to validate the concept.

- [x] **Data Import (Garmin + Strava)** — Core value prop; can't analyze without data; REST API integration
- [x] **Activity List/Table View** — Users need to see their rides; sortable by date/distance/TSS
- [x] **Activity Detail View** — Drill-down into individual rides; timeline plot essential
- [x] **Basic Power Metrics (TSS, IF, NP)** — Core Coggan metrics; table stakes for power users
- [x] **FTP Configuration (Manual + 95% 20min)** — Need zones for any analysis; start with simplest methods
- [x] **Power Zones (7-zone Coggan)** — Required for TSS calculation and time-in-zone analysis
- [x] **CTL/ATL/TSB Calculation** — Core fitness tracking; user explicitly requested; 42/7-day weighted averages
- [x] **Fitness Chart (PMC)** — Visual representation of CTL/ATL/TSB over time; date range selection
- [x] **Calendar View** — Visual organization; weekly summaries; Monday-first configurable
- [x] **Critical Power Curve** — Power users expect this; best efforts over standard durations
- [x] **Route Map (OpenStreetMap + Leaflet)** — User explicitly requested; visual context for outdoor rides
- [x] **HR Analysis (Basic)** — Zones, avg/max HR; complements power analysis
- [x] **Single-User Auth** — Security basics; user management deferred to v1.x

**MVP Validation Criteria:**
- Can import rides from Garmin/Strava
- Calculates TSS and displays CTL/ATL/TSB accurately
- Shows power curve for performance tracking
- Displays calendar with weekly TSS summaries
- Activity detail shows timeline with basic stats + map

### Add After Validation (v1.x - Enhanced Analytics)

Features to add once core is working and users are engaged.

- [ ] **Xert XSS Metrics (Low/High/Peak)** — Differentiator; user requested; requires reverse-engineering
- [ ] **Xert Threshold Model** — Alternative FTP estimation; pairs with XSS
- [ ] **30-Second Power Zone Shading** — User requested; compute-intensive; enhances timeline view
- [ ] **Power Analysis Detail** — Mean max power, quartile analysis, variability index; deeper insights
- [ ] **HR Analysis Detail** — Cardiac drift, HR/power decoupling, aerobic efficiency
- [ ] **Totals Page + Charts** — Weekly/monthly/yearly aggregations; distance, time, elevation, TSS trends
- [ ] **Multiple Threshold Estimation Methods** — 90% 8min, Xert model; user requested flexibility
- [ ] **Advanced Power Modeling** — Morton 3-parameter, Monod-Scherrer 2-parameter CP models
- [ ] **Automatic Interval Detection** — AI-powered workout structure recognition
- [ ] **Activity Comparison** — Compare two rides side-by-side; progression tracking

**Trigger for v1.x:** 10+ active users, 100+ activities imported, positive feedback on core metrics

### Future Consideration (v2.0+ - Planning & Collaboration)

Features to defer until product-market fit is established.

- [ ] **Block Periodization Planning** — Season structure with training blocks; user requested but complex
- [ ] **Goal-Based Plan Generation** — CTL progression modeling to hit target fitness on event day
- [ ] **Multi-User + Coach/Athlete Sharing** — User requested but requires auth overhaul, privacy controls
- [ ] **Fat/Carb Utilization** — Metabolic insights; user requested; high complexity, niche value
- [ ] **Workout Builder** — Create structured workouts; export ZWO/MRC files
- [ ] **Training Plan Templates** — Pre-built plans for common goals (century, gran fondo, etc.)
- [ ] **Comparative Analysis** — Power curve vs age group, watts/kg rankings
- [ ] **Wellness Tracking** — Weight, HRV, sleep, resting HR; complements fitness tracking
- [ ] **Advanced Visualizations** — Heat maps, power histograms, duration curves, scatter plots
- [ ] **Export/Backup** — Data portability; CSV/JSON export of activities + metrics

**Trigger for v2.0:** Proven retention (30-day active users), revenue validation (donation/subscription interest), feature requests from 20+ users

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Data Import (Garmin/Strava) | HIGH | HIGH | P1 |
| Activity List/Table View | HIGH | LOW | P1 |
| Basic Power Metrics (TSS/IF/NP) | HIGH | MEDIUM | P1 |
| CTL/ATL/TSB Calculation | HIGH | MEDIUM | P1 |
| Fitness Chart (PMC) | HIGH | MEDIUM | P1 |
| Calendar View | HIGH | MEDIUM | P1 |
| Activity Detail + Timeline | HIGH | MEDIUM | P1 |
| Critical Power Curve | HIGH | MEDIUM | P1 |
| FTP Config (Manual + 95% 20min) | HIGH | LOW | P1 |
| Route Map Display | MEDIUM | LOW | P1 |
| HR Analysis (Basic) | MEDIUM | LOW | P1 |
| Single-User Auth | MEDIUM | MEDIUM | P1 |
| Xert XSS Metrics | HIGH | HIGH | P2 |
| Xert Threshold Model | HIGH | HIGH | P2 |
| 30s Power Zone Shading | MEDIUM | MEDIUM | P2 |
| Power Analysis Detail | HIGH | MEDIUM | P2 |
| Totals Page + Charts | MEDIUM | MEDIUM | P2 |
| Multiple Threshold Methods | MEDIUM | LOW | P2 |
| Advanced CP Modeling | MEDIUM | HIGH | P2 |
| Block Periodization | HIGH | HIGH | P3 |
| Goal-Based Planning | HIGH | HIGH | P3 |
| Multi-User + Coach Sharing | MEDIUM | HIGH | P3 |
| Fat/Carb Utilization | LOW | HIGH | P3 |
| Workout Builder | MEDIUM | MEDIUM | P3 |
| Wellness Tracking | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for MVP launch (v1.0) — validates core value proposition
- P2: Should have post-MVP (v1.x) — enhances differentiation, user requested
- P3: Nice to have for future (v2.0+) — advanced features, lower ROI, complex

## Competitor Feature Analysis

| Feature | intervals.icu | Xert | TrainingPeaks | Golden Cheetah | Our Approach |
|---------|---------------|------|---------------|----------------|--------------|
| **Data Import** | Garmin, Strava, Zwift, Polar, Wahoo, Coros, etc. | Garmin, Strava | Apple Watch, Garmin, Wahoo, Polar, etc. | ANT+, FIT/TCX files | **Garmin + Strava** (MVP); expand later |
| **FTP Estimation** | Automatic eFTP from single effort | Continuous threshold via fitness signature | Manual or auto-detect | Manual or CP model | **Manual + 95% 20min + Xert model** (phased) |
| **Training Load** | TSS (Coggan formula) | XSS (Xert Strain Score: Low/High/Peak) | TSS, rTSS | TSS, BikeStress, TRIMP | **TSS (v1) + XSS (v1.x)** — differentiation |
| **Fitness Tracking** | CTL/ATL/Form chart | Training Load + Status via XSS | CTL/ATL/TSB (PMC) | PMC with Banister model | **CTL/ATL/TSB (Coggan)** — standard model |
| **Power Curve** | Power curve vs season, watts/kg, MAP | MPA (Maximal Power Available) real-time | Power curve + percentile rankings | CP plot/curve with 2P/3P models | **Standard power curve + Morton/Monod-Scherrer** (v1.x) |
| **Activity Analysis** | 50+ metrics per interval, automatic detection | Real-time MPA tracking, difficulty score | Power/HR zones, decoupling | 300+ metrics, W'bal modeling | **Basic (v1) → 30s zone shading (v1.x)** |
| **Calendar View** | Drag-drop, weekly summaries, planned workouts | Adaptive training advisor, Forecast AI | Training calendar, plan builder | Season planning, event management | **Calendar + weekly TSS (v1) → planning (v2)** |
| **Route Mapping** | Elevation correction, gradient-adjusted pace | Not emphasized | GPS route display | GPS route display | **OpenStreetMap + Leaflet** (v1) |
| **Planning** | Workout builder, plan templates, coach tools | Adaptive Training Advisor, auto-adjusting plans | Structured plans, professional coaching | Season/phase planning, goal tracking | **Block periodization + goal-based (v2)** |
| **Multi-User** | Coach/athlete, team management, chat | Coach/athlete workflows | Premium coaching, athlete sharing | Single-user desktop app | **Single-user (v1) → multi-user (v2)** |
| **Metabolic** | Wellness tracking (HRV, sleep, weight, etc.) | Not emphasized | Nutrition, wellness metrics | Not emphasized | **Fat/carb calc (v2)** — niche differentiator |
| **Pricing** | $4/month (free option) | Subscription ($10-20/month) | $124.99/year premium | Free, open-source | **Free, self-hosted, open-source** |
| **Deployment** | Cloud SaaS | Cloud SaaS | Cloud SaaS | Desktop app | **Self-hosted (Docker)** — key differentiator |

### Competitive Positioning

**Strengths:**
- **Privacy/Control:** Self-hosted, no data lock-in (vs cloud platforms)
- **Transparency:** Open algorithms, verifiable calculations (vs proprietary)
- **Xert + Coggan Hybrid:** Best of both training load methodologies
- **Cost:** Free (self-host cost only) vs $50-125/year subscriptions
- **Advanced Metrics:** XSS + fat/carb calc in free platform (usually premium)

**Weaknesses:**
- **Setup Friction:** Self-hosting requires Docker/tech knowledge (vs click signup)
- **Feature Breadth:** Fewer integrations, no mobile app initially
- **No Adaptive Planning:** Manual planning vs Xert's AI advisor
- **Community:** No social features vs Strava's network effects
- **Polish:** MVP UX less polished than mature commercial platforms

**Target User:**
- Privacy-conscious cyclists who distrust cloud platforms
- Power meter users who want Xert-level insights without subscription
- Data nerds who want to verify/customize calculations
- Coaches who want self-hosted solution for athlete data
- Budget-conscious athletes (already have Garmin/Strava, don't want another subscription)

## Implementation Complexity Notes

### LOW Complexity (1-3 days)
- Activity list/table view
- Basic HR analysis (zones, avg/max)
- Route map display (Leaflet + OSM tiles)
- FTP manual configuration
- Power zones setup

### MEDIUM Complexity (4-10 days)
- Data import (Garmin/Strava API integration, rate limits, OAuth)
- Activity detail view (timeline plot, metrics display)
- Calendar view (weekly summaries, date navigation)
- Basic power metrics (TSS, IF, NP calculations)
- CTL/ATL/TSB calculation (weighted averages, historical data)
- Fitness chart (date range selection, line chart rendering)
- Critical power curve (best efforts extraction, curve fitting)
- 30-second power zone shading (granular data processing)
- Power analysis detail (quartile analysis, variability index)
- Totals page (aggregation queries, chart rendering)
- Single-user auth (session management, password hashing)

### HIGH Complexity (10-30+ days)
- Xert XSS metrics (algorithm reverse-engineering, validation)
- Xert threshold model (continuous estimation, fitness signature)
- Fat/carb utilization (metabolic modeling, HR/power correlation)
- Advanced CP modeling (Morton 3-parameter, Monod-Scherrer 2-parameter)
- Block periodization (CTL progression modeling, constraint solving)
- Goal-based plan generation (reverse engineering target CTL on event day)
- Multi-user + coach/athlete (RBAC, privacy controls, data sharing)
- Automatic interval detection (ML/heuristics for workout structure)

## Feature Dependencies and Risk Flags

### Circular Dependencies (None Identified)
All dependencies are acyclic; no features create circular requirements.

### High-Risk Features
- **Xert XSS:** Reverse-engineering proprietary algorithm; may have errors vs actual Xert
- **Fat/Carb Calc:** Complex metabolic modeling; hard to validate accuracy
- **Goal-Based Planning:** Constraint solving with many variables; may not converge
- **Multi-User Auth:** Security critical; RBAC complexity; privacy regulations

### Deferred-Risk Strategy
- Start with Coggan metrics (well-documented, proven)
- Add Xert features in v1.x after core is stable
- Defer multi-user until single-user works perfectly
- Skip AI/ML features (interval detection) until proven demand

## Sources

### Primary Research Sources
- [Intervals.icu Features](https://intervals.icu/) — Feature comparison, implementation details
- [Intervals.icu Forum: Power Curve Analysis](https://forum.intervals.icu/t/critical-power-curve-point-selection/2998) — Technical implementation details
- [Fast Talk Labs: Intervals.icu Most Powerful Features](https://www.fasttalklabs.com/training/the-most-powerful-features-of-intervals-icu/) — Feature prioritization insights
- [Xert Breakthrough Training](https://www.xertonline.com/) — Xert features and methodology
- [Xert: Understanding XSS](https://www.baronbiosys.com/beginners-hub/discover/xss-strain-score/) — Training load calculation details
- [Xert: Fitness Signature](https://www.baronbiosys.com/your-fitness-signature/) — Threshold model explanation
- [TrainingPeaks WKO5 Features](https://www.trainingpeaks.com/wko5/) — Advanced metrics and features
- [TrainingPeaks: Power Training Levels](https://www.trainingpeaks.com/blog/power-training-levels/) — Zone configuration standards
- [Golden Cheetah GitHub](https://github.com/GoldenCheetah/GoldenCheetah) — Open-source implementation details
- [Cycling Analytics Features](https://www.cyclinganalytics.com/) — Competitor feature set

### Technical Implementation Sources
- [FTP Testing Methods Guide](https://gearandgrit.com/ftp-testing-methods-guide/) — Threshold estimation protocols
- [Training Zones: Power vs Heart Rate](https://www.bikeradar.com/advice/fitness-and-training/training-zones) — Zone configuration best practices
- [TrainingPeaks: Substrate Utilization](https://help.trainingpeaks.com/hc/en-us/articles/34580444343053-Substrate-Utilization-Fueling-Insights) — Fat/carb calculation methodology
- [Block Periodization for Cycling](https://www.highnorth.co.uk/articles/block-periodisation) — Season planning structure
- [Free 2026 CTL Planning Worksheet](https://forum.intervals.icu/t/free-2026-cycling-fitness-tss-ctl-planning-woksheet/116117) — CTL progression modeling examples

### Self-Hosted/Privacy Research
- [7 Best Self-Hosted Strava Alternatives](https://selfhostyourself.com/alternative-to/strava) — Market positioning
- [Open Source Alternatives to Cloud Services](https://www.dreamhost.com/blog/open-source-alternatives/) — Deployment strategy insights

### Anti-Features and MVP Strategy
- [Feature Bloat in Product Management](https://hellopm.co/what-is-feature-bloat/) — What to avoid
- [Real-Time vs Batch Analytics](https://www.sigmacomputing.com/blog/batch-vs-real-time-analytics) — Architecture decisions

---
*Feature research for: Cycling Analytics Platform*
*Researched: 2026-02-10*
*Confidence: HIGH (verified against official documentation, competitor analysis, technical implementation guides)*
