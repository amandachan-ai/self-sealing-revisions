# Self-Sealing Revisions

**When an agent learns the wrong lesson from a failure, its own fix can destroy the evidence that would have corrected it.**

This repo is a **novelty audit**: a record of trying to stake out a foundational research question in agent self-improvement, watching two candidate framings collapse under verification, and arriving at the one that survived.

Every claim below was checked against primary sources — arXiv abstract pages fetched directly, one paper read in full. Nothing here is cited from memory.

---

## The thesis that survived

> **Self-Sealing Revisions.** A self-improving agent's revisions do not merely change its behavior; they change **which evidence it will ever observe again**. The **breadth** of a revision determines the **breadth of the resulting evidence blackout**: narrow revisions remain falsifiable, broad revisions foreclose their own refutation. Learnability can therefore be destroyed not by capacity growth but by **support collapse** — a failure mode invisible to capacity-based guarantees, and unaddressed by capacity-based guardrails.

An agent observes `condition X → Tool A → failure`. It can write at least three rules:

| Revision | What it blocks | Still falsifiable? |
|---|---|---|
| `r₁` don't use A for this task | almost nothing | ✅ |
| `r₂` don't use A under X | A under X only | ✅ A under ¬X stays observable |
| `r₃` A is unreliable, never use it | **all** evidence about A | ❌ **no counter-evidence can ever arrive** |

All three repair the observed failure. Only one may be correct. And the broadest one is the one that can never be found wrong.

### The consequence

> **When in doubt, under-generalize** — not because narrow hypotheses are a priori more likely (that is the size principle's reason), but because **narrow revisions preserve their own falsifiability**.

This yields a *derived* answer to a question that self-improvement work has only ever answered by intuition — *how much evidence should justify a change?*

> The evidence threshold for a revision should scale with **how much future evidence that revision forecloses**, not with how many situations it affects.

These come apart. A revision that affects many situations but stays observable (changing a ranking strategy) is safer than one that affects few but is totally self-sealing (disabling a tool).

### Why it should outlast current architectures

An end-to-end RL-trained agent that learns "never call A" also stops generating data about A. The phenomenon has nothing to do with memory, prompts, or weights — it is a property of **any system that changes its actions based on its own conclusions**. It is substrate-independent.

---

## Two framings that did not survive

### Round 1 — "Which component should the agent revise?"

The idea: failure localization (*which step broke?*) is not the same as **update attribution** (*what part of the agent should change?* — memory, world model, policy, tools, evaluator, or goal).

The insight is real. The research position is gone. Between 2025-09 and 2026-08:

```
2025-09  AgenTracer          who caused the failure? (step / agent level)
2026-01  AgentDevel          minimal patch + flip-centered regression gating
2026-03  Kumiho              AGM postulates proven for agent memory
2026-05  AgingBench          component-level oracle-swap counterfactual probes
2026-05  CausalFlow          counterfactual attribution + minimal repair
2026-06  HiMPO               "which component deserves blame" as a premise, not a finding
2026-07  two surveys         the whole line collapsed into taxonomy
2026-08  TelemetrySuffBench  non-identifiability + safe abstention
```

Eleven months, end to end. Notably:

- **TelemetrySuffBench** (`2608.07899`, 2026-08-08) already builds *"exact-equal ambiguous origin pairs"* and tests *"safe abstention under insufficient evidence"* — the paired-case benchmark and the identifiability framing, together. It reports a **detection–localization gap**: 99.5–100% detection F1 while origin-step accuracy collapses to ≤0.5%.
- **AgingBench** (`2605.26302`) already runs *"paired counterfactual probes that swap each component with an oracle"*, noting that *"each stage is a candidate site where the same end-to-end failure can originate."*
- **HiMPO** (`2606.16285`) opens by treating the whole idea as background: *"a memory update may be rewarded or penalized due to downstream tool failures, noisy observations, or reasoning errors rather than its own contribution."*

### Round 2 — "What should this experience generalize to?"

Better question. The proposed formalization — define a revision's locus by the set of future contexts whose behavior it changes, note that several revisions fit the observation but differ on the future, then design *discriminating probes* — turned out to have precise earlier names:

| Proposed construct | Existing name | Source |
|---|---|---|
| the set of future contexts a revision changes | **consequential region** | Tenenbaum & Griffiths, BBS 2001 |
| several revisions consistent with data, differing on the future | **an uncollapsed version space** | Mitchell, *Generalization as Search*, AIJ 1982 |
| discriminating probe | **membership query** | Angluin 1988; Settles 2009 |
| how far should one example generalize; prefer narrower | **size principle** | Tenenbaum & Griffiths 1999–2001 |
| the three-level `r₁/r₂/r₃` structure | **the number game** | ibid. |

On the LLM side it is equally occupied: **generality vs. locality** is the central metric pair of every knowledge-editing benchmark, **ripple effects** were formalized by Cohen et al. (TACL 2024), and **over-ripple errors** already name over-generalization. `2512.20162` (2025-12) has already run the number game on LLMs.

**One correction in the other direction:** DiagEval (`2605.17439`) is often described as naming a "single-trajectory identifiability gap." It does not — that phrase does not appear in the paper. Its actual scope is narrower: GUI-agent evaluation, disambiguating *evaluator-side execution error* vs. *genuine software defect*. That slot is less occupied than it looks.

---

## Why Round 3 survived: the nearest neighbor, read in full

The closest existing work is **_On The Statistical Limits of Self-Improving Agents_** (`arXiv:2510.04399`, Wang, Dorchen & Jin, Columbia; **TMLR 2026**). It proves that *"utility-rational self-changes can make learnable tasks unlearnable."* That is the general principle — already established, already peer-reviewed.

I read all ~12,000 words, appendices included. It does not close this question. It **opens** it.

**Its data distribution is exogenous and fixed.** From §3: *"We study supervised learning under an unknown distribution 𝒟… Let S ~ 𝒟^m denote the training sample and V ~ 𝒟^{n_v} an independent validation sample."* Its five modification axes — algorithmic, representational, architectural, substrate, metacognitive — are **all properties of the learner**. None concerns what data the agent will see next. That is the missing sixth axis.

**It declares this case out of scope, twice, and names the tools:**

> §10 — *"**Nonstationary, adaptive, and interactive data.** If data are collected online, **selected adaptively**, or drawn from a changing distribution, the same invariant must be paired with concentration tools suited to the data-generating process… martingale concentration, online-to-batch conversion, covariate-shift or importance-weighting assumptions, reusable holdout methods, or explicit mixing and drift conditions."*

> Appendix C — *"For non-i.i.d., nonstationary, adversarial, or **interactively collected** data, the PAC statements should be read as **baseline guarantees rather than direct deployment guarantees**… The policy-reachable-envelope invariant remains the proposed structural object, **but the proof technique must change.**"*

**And the decisive line**, §3 "Data-path integrity":

> *"Permitted data-path operations are those that **preserve i.i.d. draws**… **If selection depends on labels** or on V, standard importance-weighting or covariate-shift corrections must be used; **otherwise guarantees may fail.**"*

A self-sealing revision **is** label-dependent selection. The agent stops sampling Tool A *precisely because* A produced a failure. The paper's own stated precondition is violated by the phenomenon.

Term frequencies across the full text, appendices included: `i.i.d.` 17 · `endogenous` **0** · `feedback loop` **0** · `distribution shift` **0** · `counterfactual` **0** · `coverage` **0** · `exploration` 2 (both in related work, citing bandits generically).

### The delta, in one line

> **Their obstruction is capacity growing too fast. This one is support shrinking too far.** Both destroy learnability; the second is invisible to the first framework because 𝒟 is held fixed.

|  | `2510.04399` | Self-sealing revisions |
|---|---|---|
| data distribution | exogenous, fixed 𝒟 | **𝒟ₜ determined by the agent's own past revisions** |
| failure mechanism | reachable hypothesis capacity grows unbounded | **the agent severs its own evidence stream** |
| object diagnosed | the learner's expressiveness | the learner's **sampling access** |
| proposed guardrail | capacity cap (Two-Gate) | scope threshold ∝ evidence foreclosed |

A concrete, checkable claim follows: **Two-Gate does not defend against this.** An agent can pass every validation-improvement and capacity check while going blind — because its capacity does not grow, it *shrinks*. That makes this a necessary complement to their result rather than a competitor.

Two further openings. Their §11 Outlook names one open problem — *"how to construct computable capacity proxies that remain valid under composition"* — pointing at capacity proxies, not the data path. And their closing principle reads as an epigraph for this work: *"self-improvement should be evaluated not only by whether an edit improves near-term utility, but also by whether it preserves the statistical conditions required for continued learning."* Agreed — and in deployed agents the binding condition is not capacity, it is **evidence access**.

---

## Open problems

> ### Scope inference under non-random evidence
> The size principle — the standard answer to *"how far should a single example generalize?"* — derives its force from **strong sampling**: examples drawn at random from the concept itself. An agent's failures are not sampled from the scope it must infer. They are task-driven, policy-selected, and **truncated by the agent's own revisions**.
>
> **(a)** What inference rule replaces the size principle under this sampling regime, where the sampling process is *endogenous* to the inference?
> **(b)** Discriminating probes are not free — they cost money and latency, and are sometimes **irreversible**. What is the value-of-information criterion for probing, and when should an agent commit without probing?
> **(c)** Because adopting a broad revision **destroys the evidence stream that could refute it**, scope inference is not passive estimation but a **self-truncating** process. How should that feed back into the evidence threshold?

### The cheapest experiment that would settle it

Inject an over-broad reflection (*"Tool A is unreliable"*) into an agent whose environment only breaks A under condition X. Run long-horizon. Measure whether the agent ever recovers.

**Prediction: almost never** — and for a structural reason. Nothing in Reflexion-style or memory-based architectures ever re-tests a rule that prevents its own testing.

If that holds, the figure is the paper: **under-generalizing agents converge over time; over-generalizing agents are stuck forever.** The asymmetry is the contribution.

---

## Adjacent work, checked and non-overlapping

| Work | What it does | Why it doesn't cover this |
|---|---|---|
| `2606.28347` *Agentic Safety is an Epistemic Property* | proposes **teachability** — preserving future corrective leverage | about preserving **external/human** correction; this is about whether the agent can detect its own error unaided |
| `2605.29463` *Honest Lying* | documents self-reinforcing false reflective memories; proposes the RRR metric | verified: does **not** link a rule's **breadth** to how much evidence it blocks |
| `2605.05583` *BeliefMem* | keeps multiple candidate conclusions with probabilities | a mitigation mechanism, not a theory of scope |
| `2605.06527` *STALE* | benchmark for memories invalidated by world change | exogenous staleness, not self-induced blindness |
| Apple tasting (Helmbold, Littlestone & Warmuth); Selective labels (Lakkaraju et al., KDD 2017) | the classical machinery for *"you only observe the label if you act"* | both treat a **single binary decision**, never rules of varying breadth |

The classical lineage worth reading before claiming novelty here — all verified to source:

| Year | Work | Venue | What it already formalized |
|---|---|---|---|
| 1979 | Doyle, *A Truth Maintenance System* | *Artificial Intelligence* 12:231–272 | dependency-directed backtracking: which assumption to retract |
| **1985** | **Alchourrón, Gärdenfors & Makinson, *On the Logic of Theory Change*** | *J. Symbolic Logic* **50(2):510–530** | minimal change to a belief set under conflicting evidence, axiomatized |
| 1986 | de Kleer, *An Assumption-Based TMS* | *Artificial Intelligence* 28:127–162 | environments and labels tracking what supports a belief |
| 1994 | Ourston & Mooney, *Theory Refinement* | *Artificial Intelligence* | locating which rule to fix from incomplete proofs |
| 1999 | Zeller, *Yesterday, my program worked. Today, it does not. Why?* | ESEC/FSE | delta debugging: the minimal change producing a behavior |

---

## The methodological lesson

The first two framings failed for opposite reasons, and both failures came from searching in only one direction.

> **Reading only recent arXiv underestimates prior art *and* current competition at the same time.**
>
> "Which step failed ≠ what should change" is a genuine insight — and AGM belief revision (1985) and delta debugging (1999) are its symbolic ancestors. Meanwhile the modern version was occupied eight days before it was proposed.

A related observation, offered without comfort: this subfield's iteration period is **months, not years**. Slow, careful formalization does not win land-grabs — not for lack of quality, but because deliberation time is itself a cost. That is an argument for choosing problems whose value does not depend on being first.

---

## Method and limitations

**Verification:** arXiv abstract pages fetched directly to confirm title, authors, and date; classical sources cross-checked independently for journal, volume, and pages; `2510.04399` read in full (v3, including appendices) with term-frequency counts over the complete text.

**Limitations, stated plainly:**

- Except for `2510.04399`, judgments rest on **abstracts, not full texts**. Treat every "already occupied" verdict as needing full-text confirmation.
- **Not an exhaustive search.** Keyword retrieval only; this cluster almost certainly contains more.
- The open problems in this document have **not** received the same verification intensity as the collision map. In particular, (c) may well have a counterpart in the bandit or causal selective-sampling literature; apple tasting and selective labels were checked, but not exhaustively.
- Occupancy is not quality. One benchmark surveyed here (`2605.04624`) was **withdrawn by its authors** for flawed experimental design.

---

## Status

Round 3 has cleared the only risk that would have killed the question outright. The remaining decisive risk is **empirical, not bibliographic**: does self-sealing actually occur, and do agents genuinely never recover?

That is an experiment, not a literature review.
