# ClaimRaptor Hackathon Submission Copy

## Project Name

ClaimRaptor

## One-Line Description

Evidence-grounded insurance claim decision support that uses NDI to understand real documents and Drex to make fast, low-cost recommendations.

---

## Short Description

ClaimRaptor converts messy insurance PDFs into normalized evidence using Nace Document Intelligence, then uses Drex to recommend APPROVE, DENY, or MANUAL REVIEW.

For the Apex Predator track, ClaimRaptor compares Drex directly against Qwen3.8-27B through DeepInfra on identical claim evidence.

On a frozen 30-claim controlled benchmark, Drex achieved 100% accuracy compared with 96.7% for Qwen while delivering lower median latency, dramatically lower p95 latency, perfect repeatability, and approximately 5.19× lower inference cost.

The project also includes a real-world evaluation using public insurance-document packets processed through NDI.

---

# Inspiration

Insurance decisions are not primarily writing tasks. They are structured decisions under incomplete evidence.

Claims arrive as messy PDFs containing policy information, estimates, notices, tables, adjuster correspondence, and supporting records.

A general-purpose LLM can read those documents, but we wanted to test whether a specialized decision model could make the actual claim-handling decision more consistently and efficiently.

That led to ClaimRaptor.

---

# What It Does

ClaimRaptor has two modes.

### Real-World Claim Analyzer

A user uploads insurance PDFs.

Nace Document Intelligence parses each PDF into normalized Markdown evidence.

The exact same parsed evidence is then sent simultaneously to:

- Drex Max v1.1
- Qwen3.8-27B through DeepInfra

Both models choose between:

- APPROVE
- MANUAL REVIEW
- DENY

The application displays:

- decision
- agreement
- model latency
- inference cost
- Drex confidence
- Drex decision probabilities
- NDI output

Incomplete policy evidence is intentionally routed to MANUAL REVIEW rather than allowing either model to invent missing coverage.

### Apex Predator Benchmark

ClaimRaptor also includes a frozen controlled benchmark containing 30 labeled synthetic insurance claims:

- 10 approve
- 10 deny
- 10 manual review

Both models receive identical structured claim states and explicit policy rules.

Each model is evaluated three times per claim.

---

# Benchmark Results

## Controlled Benchmark

Drex Max v1.1:

- 100.00% primary accuracy
- ~225 ms median latency
- ~324 ms p95 latency
- 100% consistency

Qwen3.8-27B:

- 96.67% primary accuracy
- ~283 ms median latency
- ~1239 ms p95 latency
- 96.67% consistency

Qwen cost approximately 5.19× more per decision in the benchmark.

Drex therefore achieved:

- higher accuracy
- better consistency
- approximately 1.25× lower median latency
- approximately 3.82× lower p95 latency
- approximately 5.19× lower inference cost

---

# Real-World Test

ClaimRaptor was also run against three cleaned public insurance document packets.

Results:

- 3 documents
- 3 / 3 Drex-Qwen decision agreement
- all three routed to MANUAL REVIEW
- Drex median latency: ~770 ms
- Qwen median latency: ~483 ms
- Qwen inference cost: ~4.80× Drex

We do not claim accuracy on these documents because independent ground-truth adjudication labels are not available.

This test exists to demonstrate behavior on messy real documents, while the controlled benchmark measures accuracy.

---

# How We Built It

### Document understanding

Nace Document Intelligence parses insurance PDFs into Markdown while preserving useful document structure such as pages and tables.

### Specialized decision layer

Drex receives the normalized evidence and returns a structured claim-handling recommendation with confidence and probability information.

### General-purpose baseline

Qwen3.8-27B is called through DeepInfra with the same evidence and equivalent decision instructions.

### Frontend

Streamlit provides a live interface for:

- uploading multiple PDFs
- running NDI
- comparing models
- viewing benchmark results
- inspecting technical details

### Engineering agent

Nace Intern was used with Drex as System 1 and Qwen via DeepInfra as System 2.

Intern reviewed the application and identified a batch reliability issue where one failing PDF could terminate the entire demonstration.

The application was updated with per-document fault isolation and safe handling of all-failure batches.

Intern was then used again for the final repository audit.

---

# Challenges

The biggest challenge was creating a comparison that was fair and defensible.

Early experiments risked testing the two systems under slightly different assumptions.

We therefore froze a benchmark where:

- ground-truth labels were defined first
- both models receive identical structured states
- explicit policy rules are supplied
- API calls are warmed
- execution order is randomized
- accuracy uses unique claims rather than repeated requests
- repeated trials are used only for latency and consistency

Another challenge was working with public insurance PDFs.

Many public regulatory files contain large mixed packets with unrelated records.

We created cleaned excerpts so that each real-world evaluation represents a coherent insurance record rather than feeding unrelated pages into the models.

---

# Accomplishments

We are especially proud that ClaimRaptor does not rely on a single cherry-picked demonstration.

It includes both:

1. a controlled labeled benchmark for quantitative comparison, and
2. a live real-document pipeline using NDI.

The benchmark showed that Drex can outperform a much larger general-purpose model on a focused decision task while costing substantially less.

We also designed the application to explicitly prefer human review when evidence is incomplete instead of hallucinating coverage.

---

# What We Learned

Specialized decision models and general-purpose language models have different strengths.

On the controlled benchmark, Drex was more accurate, consistent, cost-efficient, and had much better tail latency.

On the small real-world document session, Qwen happened to respond faster.

That difference reinforced an important lesson: benchmark results and live API behavior should be reported separately rather than selectively presenting whichever number looks best.

We also learned that document processing and decision-making should be separated.

NDI handles the messy document understanding problem once, after which different decision systems can operate on the same normalized evidence.

---

# What's Next

With more time, ClaimRaptor could expand into:

- multi-document claim packets
- insurer-specific policy rules
- adjuster feedback loops
- decision audit trails
- fraud-risk routing
- human approval workflows
- larger real-world labeled datasets
- policy-document retrieval
- more baseline models
- longitudinal performance monitoring

The production goal would remain decision support rather than fully autonomous claim adjudication.

---

# Responsible AI

ClaimRaptor is a hackathon prototype.

It is not intended to automatically approve or deny real insurance claims without human oversight.

Real deployment would require:

- complete policy information
- verified evidence
- insurer-specific rules
- regulatory compliance
- privacy controls
- auditability
- human adjuster review

Incomplete evidence is intentionally routed to MANUAL REVIEW.

---

# Technologies

- Nace Drex
- Nace Document Intelligence
- Nace Intern
- DeepInfra
- Qwen3.8-27B
- Streamlit
- Python
- Pandas

---

# Track

Apex Predator

ClaimRaptor compares Drex against a general-purpose LLM on an identical insurance-decision task and measures accuracy, latency, consistency, and inference cost.

---

# GitHub

https://github.com/Soham-Raj-Jain/ClaimRaptor