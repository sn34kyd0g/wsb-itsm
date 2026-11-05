---
lab4_comms:
  awareness: 2026-11-05T17:06:05Z
  detection: 2026-11-05T17:00:19Z
  classification: 2026-11-05T17:36:00Z
  nis2:
    early_warning_due: 2026-11-06T17:06:05Z      # awareness + 24 h
    notification_due: 2026-11-08T17:06:05Z       # awareness + 72 h
    notification_sent: 2026-11-06T15:00:00Z
    final_report_due: 2026-12-06T15:00:00Z       # a month after notification_sent
  ksc:
    early_warning_due: 2026-11-06T17:00:19Z      # detection + 24 h
    notification_due: 2026-11-08T17:00:19Z       # detection + 72 h
    notification_sent: 2026-11-06T15:00:00Z
    final_report_due: 2026-12-06T15:00:00Z       # a month after notification_sent
  dora:
    initial_due: 2026-11-05T21:36:00Z            # classification + 4 h; earlier than awareness + 24 h (2026-11-06T17:06:05Z)
    initial_sent: 2026-11-05T20:30:00Z
    intermediate_due: 2026-11-08T20:30:00Z       # initial_sent + 72 h
    intermediate_sent: 2026-11-06T15:30:00Z
    final_due: 2026-12-06T15:30:00Z              # a month after intermediate_sent
  log:
    - {at: 2026-11-05T20:30:00Z, to: the financial supervisor, what: DORA initial notification}
    - {at: 2026-11-06T08:00:00Z, to: the CSIRT, what: NIS2 and KSC early warning}
    - {at: 2026-11-06T15:00:00Z, to: the CSIRT, what: NIS2 and KSC incident notification}
    - {at: 2026-11-06T15:30:00Z, to: the financial supervisor, what: DORA intermediate report}
---
<!-- ai-generated: 80% - drafted with Claude from my incident notes and the postmortem; the dates were recomputed with a script, and the three instants are the ones I defend -->

# Communications log: the regulators' clocks

The shop is treated here as an entity that NIS2, the Polish KSC act and DORA all apply to, and the incident of 2026-11-05 (postmortem.md) as significant under the first two and major under the third. That is the exercise's assumption: no real authority is told anything, so the `*_sent` instants and the `at` column are when each report would go out. Every instant is in UTC, so the 24 h, 72 h and 4 h clocks are elapsed hours and a month is counted on the UTC calendar.

## The three instants you defend

- **Detection (KSC), 17:00:19Z.** The detecting alert CheckoutErrorRate (P1; CheckoutLatencyHigh started in the same evaluation) began firing: that is "od momentu jego wykrycia", the moment the shop's own monitoring detected the incident, and the same instant as `detection` in the postmortem and in `itsmlab incident 4`. The KSC clocks run from here: early warning by 2026-11-06T17:00:19Z, notification by 2026-11-08T17:00:19Z.
- **Awareness (NIS2), 17:06:05Z.** The pager had two firing notifications by 17:00:33Z and I acknowledged the ticket at 17:02:13Z, but a page and an acknowledgement say that a rule fired, not that the incident is significant. At 17:04:04Z I read `flags.json` and saw three faults set (errors, latency and a resource leak). At 17:06:05Z, the timestamp of my note, I had measured the damage myself: over the last five minutes 13.8 % of the calls to checkout, the shop's critical function, had failed (product-catalog 8.5 %, frontend 8.4 %, frontend-proxy 7.9 %), the cause was three failing flags, and none of them was off yet. That is the instant I defend as the awareness of a significant incident, so the NIS2 clocks run from here: early warning by 2026-11-06T17:06:05Z, notification by 2026-11-08T17:06:05Z. The choice costs nothing: the KSC clocks start earlier, at the detection, and every report below is planned against them, so even a regulator who counted my awareness from the acknowledgement (17:02:13Z) would find no NIS2 report late.
- **Classification (DORA), 17:36:00Z.** All three flags were off at 17:15:45Z. Only then could the impact be counted from the snapshot (taken at 17:27:23Z): 13 of 149 orders failed, 9 took 10 s or more, 215 frontend requests for products and recommendations failed, and the recommendation service ran into its memory limit and restarted (section Impact of the postmortem). I set that against the DORA classification criteria (clients and transactions affected, duration, critical service affected), treat it as major, and allow about 20 minutes after the last flag went off for it: 17:36:00Z. That is within 24 h of the awareness (29 min 55 s after it), so the initial notification is due at the earlier of classification + 4 h (2026-11-05T21:36:00Z) and awareness + 24 h (2026-11-06T17:06:05Z): the 4 h bind.

## The log

| when (UTC) | to whom | what | which clock |
|---|---|---|---|
| 2026-11-05T20:30:00Z | the financial supervisor | DORA initial notification: a major incident in the shop's ordering from 16:57:25Z to 17:15:45Z, 13 of 149 orders failed and 9 were slow, service restored, cause (three failing feature flags) still being written up | initial_due 2026-11-05T21:36:00Z, sent 66 minutes early |
| 2026-11-06T08:00:00Z | the CSIRT | NIS2 and KSC early warning: a significant incident, first assessment an operational fault (three failing feature flags) with nothing in the postmortem pointing to an attack, shop restored | due 2026-11-06T17:00:19Z (KSC) and 2026-11-06T17:06:05Z (NIS2), sent about nine hours early |
| 2026-11-06T15:00:00Z | the CSIRT | NIS2 and KSC incident notification: the postmortem's impact, timeline and root causes | due 2026-11-08T17:00:19Z (KSC) and 2026-11-08T17:06:05Z (NIS2); the final report is due one month after, 2026-12-06T15:00:00Z |
| 2026-11-06T15:30:00Z | the financial supervisor | DORA intermediate report: root causes and the action items ITSM-501 to ITSM-504 | due 2026-11-08T20:30:00Z, 72 h after the initial notification; the final report is due 2026-12-06T15:30:00Z |

2026-11-05 is a Thursday. The two 72 h deadlines of the CSIRT and the DORA intermediate deadline all fall on Sunday 2026-11-08, so those reports go out on Friday afternoon, when the postmortem is done and someone who can approve the text is at work; the weekend relief of the DORA technical standard is ignored, as the exercise says. The early warning goes out on Friday morning, nine hours before the earliest of its two deadlines, which is the KSC one.
