---
lab2_edge_cases:
  E1: {rule: R-08, count: 3}
  E2: {rule: R-06, count: 2}
  E3: {rule: R-09, count: 4}
  E4: {rule: R-10, count: 4}
  E5: {rule: R-12, count: 1}
  E6: {rule: R-13, count: 11}
---
<!-- ai-generated: 80% - drafted by Claude Code from METRIC-SPEC.md and the practice log, numbers taken from the running service, reviewed by me -->

# Edge cases in the practice event log

Every count in the front matter is what `POST /dora/metrics` in this repository returns for
`fixtures/events-practice.jsonl` over the published window (`metrics.json` is that answer, verbatim).

## E1 - clock skew produces a negative lead time

- What the log contains: three successful production deployments carry a commit stamped after the
  deployment itself: `sha-0040` on DEP-0012 (834 s later), `sha-0094` on DEP-0024 (51 s later) and `sha-0123`
  on DEP-0031 (780 s later). A deployment cannot ship code that does not yet exist, so these are clocks that
  disagreed between the developer laptop or CI runner and the deploy system.
- What a default definition would have done: a naive `deployment.at - commit.at` puts three negative values
  into the median, and the usual "fix" is to filter them out as bad data. Dropping them shrinks the pair count
  from 125 to 122 and silently removes the fastest deliveries of the period, so the median drifts upwards; keeping
  them raw would let a sufficiently skewed clock drag the median below zero, which nobody can interpret.
- Why the rule is defensible: the commit really was delivered by that deployment, and the true lead time was
  "about zero", so clamping to 0 is the closest honest value and keeps the pair in the population. Counting the
  clamped pairs in `anomalies.negative_lead_time_pairs` tells the reader of the dashboard that the clocks need
  fixing, instead of hiding the symptom by deleting the evidence.

## E2 - a revert of a revert

- What the log contains: `sha-0069` belongs to CHG-0033; `sha-0070` reverts it and `sha-0071` reverts the
  revert (re-applying the original work). Both reverts carry `change_id: null`, and all three ship together in
  DEP-0018. The service reports `revert_chains_collapsed = 2`: the two commits that contributed no change of
  their own.
- What a default definition would have done: counting distinct commits (or treating each revert as its own
  unit of work) turns one piece of work into three "changes", inflating throughput and diluting the lead-time
  median with the reverts' short, recent timestamps. Treating `null` as a change id would instead merge every
  revert in the log into one fake change.
- Why the rule is defensible: a revert is not new value, it is the same change going back and forth. Resolving
  the chain transitively to CHG-0033 means the change is counted once and its lead time is measured from its
  earliest commit (R-07), so churn on a change makes that change look slower, not the team look busier.

## E3 - a hotfix that never touched `main`

- What the log contains: four commits live only on hotfix branches and still went straight to production:
  `sha-0019` (`hotfix/2609`, DEP-0006), `sha-0077` (`hotfix/4347`, DEP-0019), `sha-0108` (`hotfix/6085`,
  DEP-0028) and `sha-0127` (`hotfix/1544`, DEP-0033).
- What a default definition would have done: the common "lead time for changes on main" definition filters
  commits on `branch == "main"` and drops all four pairs. Those are exactly the urgent fixes, typically the
  fastest deliveries a team makes, so the median becomes slower than reality and the hotfix path becomes
  invisible to anyone reading the metric.
- Why the rule is defensible: DORA measures what reached production, not which branch a commit sat on; the
  branch name is free text and a policy detail of one team. Never consulting it keeps the metric about delivery,
  while `commits_never_on_main` still surfaces the fact that code bypassed `main`, which is a governance
  question worth asking separately rather than a reason to hide the delivery.

## E4 - a deployment with zero linked commits

- What the log contains: four production deployments in the window carry an empty `commits` array: DEP-0026
  and DEP-0032 (successful, e.g. a config or infrastructure redeploy) and DEP-0043 and DEP-0044 (both failed,
  each followed by its own incident).
- What a default definition would have done: either drop "empty" deployments as noise (40 instead of 42
  deployments, a lower frequency, and two failures missing from the change fail rate), or iterate over commits
  and divide by zero or produce an undefined lead time for them.
- Why the rule is defensible: an empty deployment is still a real production change of state that can fail and
  page people, as DEP-0043 and DEP-0044 did. It has no code to measure a lead time for, so it gives no pair,
  but it must count in frequency, change fail rate and rework rate; otherwise a team could make its failures
  disappear by shipping them without linked commits.

## E5 - a deployment that failed and never recovered

- What the log contains: DEP-0015 failed on 7 September at 06:12:35; its covering incident INC-0004 opened at
  06:35:41 and has no `resolved` event anywhere in the log. It is the one open failure (`counts.open_failures =
  1`); the other seven failures recovered.
- What a default definition would have done: either close it at the end of the window (inventing a recovery
  of roughly 14.7 days, which would dominate any mean and shift the median) or drop the deployment entirely,
  which also removes it from the change fail rate and makes 0.190476 look like 0.170732.
- Why the rule is defensible: we do not know its recovery time, so we must not make one up; excluding it from
  the recovery median but still counting it as a failure (R-14) and reporting it in `open_failures` is the only
  treatment that is honest in both directions. The reader sees a recovery time for what did recover and a
  separate, visible count of what is still broken.

## E6 - overlapping incidents

- What the log contains: eleven unordered pairs of incidents whose intervals intersect. INC-0004 never resolves,
  so its interval runs to the window end and overlaps seven others (INC-0005 to INC-0011); in addition INC-0010
  and INC-0011 overlap each other and INC-0005 (three pairs around the 7 September outage), and INC-0007 overlaps
  INC-0008 on 19 September.
- What a default definition would have done: computing MTTR per incident and merging overlapping incidents into
  one outage (or summing their durations) mixes up incident time with deployment recovery. Merging on 7 September
  would give DEP-0043 and DEP-0044 one shared recovery instant, and summing would count the same wall-clock hours
  twice, so the recovery median would say more about how incidents are filed than about how fast failures are fixed.
- Why the rule is defensible: the metric is failed deployment recovery time, so the unit is the failed deployment;
  each gets the resolution of its own earliest covering incident. That is deterministic, does not depend on how
  an on-call engineer happened to split or merge tickets, and the overlap count is still reported so that the
  reader knows several incidents were running at once.

## Gaming demonstration

I improved `deployment_frequency_per_day` by exploiting R-11: the frequency counts every production deployment
in the window, of any outcome and with any content, and R-10 guarantees that a deployment with no commits still
counts. `gaming/after.jsonl` (built by `gaming/make_after.py`) adds 42 automated no-op deployments at 06:00 and
18:00 UTC every day with empty `commits`, and at the same time holds every real successful deployment that
carried commits until the next Monday 10:00 UTC release train. Nothing is deleted, no commit is re-timed and no
outcome is flipped; deployments only move later (R-19). The frequency doubles from 2.0 to 4.0 per day (the
margin is +25 %). As side effects the change fail rate halves (0.190476 to 0.095238) and the rework rate halves
(0.119048 to 0.059524), purely because the denominators were padded. Meanwhile the real work got slower: over the
base changes alone, the true change lead time rises from 539452 s to 833420 s (about 6.2 to 9.6 days, 154 % of
the base; the harm gate is 125 %), and even the pair-based `change_lead_time_seconds_p50` rises from 375643 s to
735056 s - the one metric that tells the truth here, which a dashboard that celebrates frequency would not show
on the same slide.

The incentive that produces this in a real team is a target such as "at least two production deployments a day"
tied to a performance review or a DevOps maturity score, combined with a release manager who is punished for
incidents and therefore prefers big, infrequent, scheduled releases. The cheapest way to satisfy both is a
scheduled pipeline that redeploys the same artefact twice a day plus a weekly train for the real code. The people
rewarded are the team lead and the platform team who own the KPI slide ("we doubled deployment frequency and
halved our change fail rate"), and the release manager whose incident count looks calmer; the people who pay are
the users and the developers, who now wait up to a week longer for every fix to reach production.
