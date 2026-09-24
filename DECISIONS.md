---
svcdesk_decisions:
  C1: business       # wallclock | business
  C2: immutable      # reopen | immutable
  C3: matrix         # matrix | vip
---
<!-- ai-generated: 40% - I chose desision and created draft then Claude revised the description based on my draft and decisions, I reviewed and edited final description-->

# Decisions

## C1 - SLA clock for P1

**Decision:** The P1 clock pauses outside business hours (Mon-Fri 08:00-16:00), same as every other priority, no special exception for P1.

**Rejected alternative:** P1 running around the clock 24/7 regardless of business hours.

**Reason:** R-13 is phrased as a rule covering every SLA target without exception, while R-14's "around the clock" wording would require an exception that is nowhere else in the document actually named as one. Operationally: a desk that promises a P1 acknowledgement in 15 minutes at 3am on a Saturday is promising something nobody is on shift to deliver - a target that is structurally impossible to meet outside business hours generates routine breaches that agents simply learn to ignore, which defeats the point of tracking breaches at all. One clock model for every priority is also simpler to implement, test and explain to agents than a P1-only carve-out.

**Service owner:** The service desk manager - SLA policy and shift staffing are theirs to own, and they would be the one explaining to leadership why a P1 "breached" SLA in the middle of the night when nobody was on duty

**Customer outcome:** The SLA report stays trustworthy - a P1 breach means someone genuinely missed a deadline during business hours, not that the office was empty. Reporters get one consistent expectation across every priority instead of an undocumented exception for P1.

## C2 - Closed tickets and reopening

**Decision:** Reopen only works from the `resolved` state. A `closed` ticket is permanently immutable regardless of age.

**Rejected alternative:** Reopen also available from `closed` within a 7-day window after closure.

**Reason:** R-07 draws a real line between `resolved` and `closed` - closing requires an active confirmation from the reporter that the fix worked, a stronger signal than an agent simply marking the ticket resolved. If a closed ticket can still be reopened, that confirmation stops meaning anything, and `closed` becomes just another name for `resolved`. `related_to` already gives a clean path for "this continues that closed issue" - the immutability in R-09 and ticket linking in R-03 work together as one consistent mechanism, so treating R-10's extension onto closed tickets as the error keeps the rest of the model coherent.

**Service owner:** The service desk manager, as owner of service quality - they own what "closed" actually means for reporting, and would have to defend the stability of closure statistics over time.

**Customer outcome:** The reporter always gets a fresh ticket (with full history via `related_to`) for anything after a formal closure, so nothing silently reopens without a trace. An agent working a "new" ticket sees a clean state with an explicit backward link, instead of inheriting old state through a technically-reopened closed ticket.

## C3 - VIP reporters and the priority matrix

**Decision:** Priority always comes from the impact/urgency matrix alone. `reporter.vip` is stored on the ticket but never changes the computed priority.

**Rejected alternative:** VIP ticket at P3/P4 is raised to P2.

**Reason:** R-05 is the most categorical requirement in the whole document 0 "from nothing else", "neither the reporter nor the agent" 0 written explicitly as a guard against exactly the kind of pressure R-06 formalizes. Letting the reporter's identity change the computed weight of a problem turns priority from a measure of organizational impact into a measure of who is asking, which quietly corrupts every SLA report built on that data. The intent behind R-06 - making executive issues visible quickly 0 does not require the priority field itself to misrepresent the problem's weight: `reporter.vip` is still stored and visible to agents for manual triage, it just does not overwrite the matrix result.

**Service owner:** The service desk manager - priority policy is theirs, and they would have to defend to operations why VIP status does not override the computed weight.

**Customer outcome:** Every reporter gets the same priority for the same technical impact - a VIP's cosmetic issue is still P4, so SLA reports stay a genuine measure of organizational impact rather than of who is reporting. VIP status stays visible to agents for informal triage, without inflating the official metrics.
