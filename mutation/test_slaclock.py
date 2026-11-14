# ai-generated: 90% - Claude wrote these cases from the docstrings of slaclock.py and tuned them against mutants of its own making; I read and ran them
"""Tests for slaclock.py (Lab 5, Stretch 1). The docstrings of the module are the specification: every boundary here
comes from one of them, and the date arithmetic is also checked against a slow minute-by-minute simulation."""

from datetime import datetime, timedelta

import pytest

import slaclock

# 2026-11-09 is a Monday.
MON, TUE, WED, THU, FRI, SAT, SUN = (datetime(2026, 11, 9 + i) for i in range(7))
NEXT_MON = datetime(2026, 11, 16)


def at(day, hour, minute=0, second=0, micro=0):
    return day.replace(hour=hour, minute=minute, second=second, microsecond=micro)


# ----------------------------------------------------------------------------------------------- priority_of


MATRIX = {(1, 1): "P1", (1, 2): "P2", (2, 1): "P2", (1, 3): "P3", (2, 2): "P3", (3, 1): "P3",
          (2, 3): "P4", (3, 2): "P4", (3, 3): "P4"}
VIP_MATRIX = {(1, 1): "P1", (1, 2): "P2", (2, 1): "P2", (1, 3): "P2", (2, 2): "P2", (3, 1): "P2",
              (2, 3): "P2", (3, 2): "P2", (3, 3): "P2"}


@pytest.mark.parametrize("cell", sorted(MATRIX))
def test_priority_matrix(cell):
    impact, urgency = cell
    assert slaclock.priority_of(impact, urgency) == MATRIX[cell]
    assert slaclock.priority_of(impact, urgency, False) == MATRIX[cell]
    assert slaclock.priority_of(impact, urgency, vip=False) == MATRIX[cell]


@pytest.mark.parametrize("cell", sorted(VIP_MATRIX))
def test_priority_vip(cell):
    impact, urgency = cell
    assert slaclock.priority_of(impact, urgency, True) == VIP_MATRIX[cell]
    assert slaclock.priority_of(impact, urgency, vip=True) == VIP_MATRIX[cell]


BAD_LEVELS = [0, 4, -1, 2.0, 1.0, True, False, "1", None, 10, 100]


@pytest.mark.parametrize("bad", BAD_LEVELS)
@pytest.mark.parametrize("vip", [False, True])
def test_priority_rejects_bad_impact_and_urgency(bad, vip):
    with pytest.raises(ValueError):
        slaclock.priority_of(bad, 1, vip)
    with pytest.raises(ValueError):
        slaclock.priority_of(1, bad, vip)
    with pytest.raises(ValueError):
        slaclock.priority_of(bad, bad, vip)
    with pytest.raises(ValueError):
        slaclock.priority_of(bad, 3, vip)
    with pytest.raises(ValueError):
        slaclock.priority_of(3, bad, vip)


def test_priority_returns_a_plain_string():
    for cell in MATRIX:
        result = slaclock.priority_of(*cell)
        assert type(result) is str and len(result) == 2 and result[0] == "P"


# --------------------------------------------------------------------------------------------------- targets


@pytest.mark.parametrize("priority, expected", [("P1", (15, 240)), ("P2", (60, 480)), ("P3", (240, 1440)),
                                                 ("P4", (480, 4320))])
def test_targets(priority, expected):
    assert slaclock.targets(priority) == expected
    response, resolution = slaclock.targets(priority)
    assert response == expected[0] and resolution == expected[1]
    assert type(response) is int and type(resolution) is int


@pytest.mark.parametrize("bad", ["p1", " P1", "P1 ", "P5", "P0", "P", "", "1", "P1P2", "p4", "PP1", "P 1"])
def test_targets_rejects_anything_but_an_exact_priority(bad):
    with pytest.raises(ValueError):
        slaclock.targets(bad)


# ------------------------------------------------------------------------------------------------ sla_state


@pytest.mark.parametrize("elapsed, target, expected", [
    # target 15: the warning starts at 11.25 minutes, no rounding
    (0, 15, "ok"), (1, 15, "ok"), (10, 15, "ok"), (11, 15, "ok"), (12, 15, "warning"), (13, 15, "warning"),
    (14, 15, "warning"), (15, 15, "warning"), (16, 15, "breached"), (17, 15, "breached"), (150, 15, "breached"),
    # target 100: exactly 75 % is warning, exactly 100 % is still warning
    (0, 100, "ok"), (74, 100, "ok"), (75, 100, "warning"), (76, 100, "warning"), (99, 100, "warning"),
    (100, 100, "warning"), (101, 100, "breached"),
    # target 4: 3 is exactly 75 %
    (0, 4, "ok"), (2, 4, "ok"), (3, 4, "warning"), (4, 4, "warning"), (5, 4, "breached"),
    # target 1
    (0, 1, "ok"), (1, 1, "warning"), (2, 1, "breached"),
    # target 8 and 200: 6 and 150 are exactly 75 %
    (5, 8, "ok"), (6, 8, "warning"), (8, 8, "warning"), (9, 8, "breached"),
    (149, 200, "ok"), (150, 200, "warning"), (200, 200, "warning"), (201, 200, "breached"),
    # the real targets
    (179, 240, "ok"), (180, 240, "warning"), (240, 240, "warning"), (241, 240, "breached"),
    (359, 480, "ok"), (360, 480, "warning"), (480, 480, "warning"), (481, 480, "breached"),
    (1079, 1440, "ok"), (1080, 1440, "warning"), (1440, 1440, "warning"), (1441, 1440, "breached"),
    (3239, 4320, "ok"), (3240, 4320, "warning"), (4320, 4320, "warning"), (4321, 4320, "breached"),
    (44, 60, "ok"), (45, 60, "warning"), (60, 60, "warning"), (61, 60, "breached"),
    # large numbers
    (749999, 1000000, "ok"), (750000, 1000000, "warning"), (1000000, 1000000, "warning"), (1000001, 1000000, "breached"),
    # target 3 and 7 (non-integer thresholds 2.25 and 5.25)
    (2, 3, "ok"), (3, 3, "warning"), (4, 3, "breached"), (5, 7, "ok"), (6, 7, "warning"), (7, 7, "warning"),
    (8, 7, "breached"),
])
def test_sla_state(elapsed, target, expected):
    assert slaclock.sla_state(elapsed, target) == expected


@pytest.mark.parametrize("elapsed, target", [(-1, 10), (-100, 10), (0, 0), (5, 0), (5, -1), (-1, -1), (-1, 0), (0, -10)])
def test_sla_state_rejects(elapsed, target):
    with pytest.raises(ValueError):
        slaclock.sla_state(elapsed, target)


def test_sla_state_zero_elapsed_is_fine():
    assert slaclock.sla_state(0, 1) == "ok"
    assert slaclock.sla_state(0, 1000) == "ok"


# ------------------------------------------------------------------------------------------- is_business_time


def test_business_time_edges_on_a_weekday():
    assert slaclock.is_business_time(at(WED, 7, 59)) is False
    assert slaclock.is_business_time(at(WED, 8, 0)) is True
    assert slaclock.is_business_time(at(WED, 8, 1)) is True
    assert slaclock.is_business_time(at(WED, 12, 0)) is True
    assert slaclock.is_business_time(at(WED, 15, 59)) is True
    assert slaclock.is_business_time(at(WED, 16, 0)) is False
    assert slaclock.is_business_time(at(WED, 16, 1)) is False
    assert slaclock.is_business_time(at(WED, 0, 0)) is False
    assert slaclock.is_business_time(at(WED, 23, 59)) is False
    assert slaclock.is_business_time(at(WED, 7, 0)) is False
    assert slaclock.is_business_time(at(WED, 17, 0)) is False
    assert slaclock.is_business_time(at(WED, 9, 30)) is True
    assert slaclock.is_business_time(at(WED, 11, 59)) is True
    assert slaclock.is_business_time(at(WED, 13, 1)) is True


@pytest.mark.parametrize("day", [MON, TUE, WED, THU, FRI])
def test_every_weekday_is_open(day):
    assert slaclock.is_business_time(at(day, 8, 0)) is True
    assert slaclock.is_business_time(at(day, 10, 30)) is True
    assert slaclock.is_business_time(at(day, 15, 59)) is True
    assert slaclock.is_business_time(at(day, 7, 59)) is False
    assert slaclock.is_business_time(at(day, 16, 0)) is False


@pytest.mark.parametrize("day", [SAT, SUN])
def test_weekend_is_closed(day):
    for hour, minute in [(0, 0), (8, 0), (10, 30), (12, 0), (15, 59), (16, 0), (23, 59)]:
        assert slaclock.is_business_time(at(day, hour, minute)) is False


def test_business_time_ignores_seconds():
    assert slaclock.is_business_time(at(WED, 15, 59, 59, 999999)) is True
    assert slaclock.is_business_time(at(WED, 16, 0, 0, 1)) is False
    assert slaclock.is_business_time(at(WED, 7, 59, 59)) is False
    assert slaclock.is_business_time(at(WED, 8, 0, 0)) is True


# ---------------------------------------------------------------------------------------- date arithmetic: oracle


def _minute(moment):
    return moment.replace(second=0, microsecond=0)


def _open(moment):
    return moment.weekday() < 5 and 8 * 60 <= moment.hour * 60 + moment.minute < 16 * 60


def oracle_add(start, minutes):
    """Minute by minute: the instant at which `minutes` business minutes have run after start."""
    moment = _minute(start)
    if minutes == 0:
        while not _open(moment):
            moment += timedelta(minutes=1)
        return moment
    used = 0
    while True:
        if _open(moment):
            used += 1
            if used == minutes:
                return moment + timedelta(minutes=1)
        moment += timedelta(minutes=1)


def oracle_between(start, end):
    moment, end = _minute(start), _minute(end)
    total = 0
    while moment < end:
        total += _open(moment)
        moment += timedelta(minutes=1)
    return total


STARTS = [at(MON, 8, 0), at(MON, 9, 17), at(MON, 15, 59), at(MON, 16, 0), at(MON, 7, 59), at(MON, 23, 59),
          at(WED, 12, 0), at(FRI, 15, 30), at(FRI, 16, 0), at(FRI, 8, 0), at(SAT, 10, 0), at(SUN, 23, 59),
          at(THU, 15, 59), at(TUE, 8, 1)]
AMOUNTS = [0, 1, 2, 60, 61, 479, 480, 481, 960, 961, 1440, 2400, 2401]


@pytest.mark.parametrize("start", STARTS, ids=lambda d: d.strftime("%a %H:%M"))
def test_add_business_minutes_matches_the_simulation(start):
    for minutes in AMOUNTS:
        assert slaclock.add_business_minutes(start, minutes) == oracle_add(start, minutes), (start, minutes)


@pytest.mark.parametrize("start", STARTS, ids=lambda d: d.strftime("%a %H:%M"))
def test_business_minutes_between_matches_the_simulation(start):
    for hours in (0, 1, 8, 9, 24, 25, 48, 100, 170):
        end = start + timedelta(hours=hours)
        assert slaclock.business_minutes_between(start, end) == oracle_between(start, end), (start, end)
    for minutes in (1, 59, 481, 1441):
        end = start + timedelta(minutes=minutes)
        assert slaclock.business_minutes_between(start, end) == oracle_between(start, end), (start, end)
        assert type(slaclock.business_minutes_between(start, end)) is int


@pytest.mark.parametrize("start", STARTS, ids=lambda d: d.strftime("%a %H:%M"))
def test_the_round_trip_of_the_docstring(start):
    for minutes in AMOUNTS:
        due = slaclock.add_business_minutes(start, minutes)
        assert slaclock.business_minutes_between(start, due) == minutes, (start, minutes, due)


# ------------------------------------------------------------------------------------ add_business_minutes, by hand


def test_add_inside_one_day():
    assert slaclock.add_business_minutes(at(MON, 9, 0), 60) == at(MON, 10, 0)
    assert slaclock.add_business_minutes(at(MON, 9, 15), 45) == at(MON, 10, 0)
    assert slaclock.add_business_minutes(at(MON, 8, 0), 1) == at(MON, 8, 1)
    assert slaclock.add_business_minutes(at(MON, 12, 30), 90) == at(MON, 14, 0)


def test_a_target_that_ends_exactly_at_closing_is_due_at_closing():
    assert slaclock.add_business_minutes(at(MON, 15, 0), 60) == at(MON, 16, 0)
    assert slaclock.add_business_minutes(at(MON, 8, 0), 480) == at(MON, 16, 0)
    assert slaclock.add_business_minutes(at(FRI, 15, 59), 1) == at(FRI, 16, 0)
    assert slaclock.add_business_minutes(at(FRI, 8, 0), 480) == at(FRI, 16, 0)


def test_one_minute_past_closing_goes_to_the_next_opening():
    assert slaclock.add_business_minutes(at(MON, 15, 0), 61) == at(TUE, 8, 1)
    assert slaclock.add_business_minutes(at(MON, 8, 0), 481) == at(TUE, 8, 1)
    assert slaclock.add_business_minutes(at(FRI, 15, 0), 61) == at(NEXT_MON, 8, 1)
    assert slaclock.add_business_minutes(at(FRI, 15, 59), 2) == at(NEXT_MON, 8, 1)


def test_add_spans_days_and_weekends():
    assert slaclock.add_business_minutes(at(MON, 15, 30), 60) == at(TUE, 8, 30)
    assert slaclock.add_business_minutes(at(FRI, 15, 30), 60) == at(NEXT_MON, 8, 30)
    assert slaclock.add_business_minutes(at(FRI, 8, 0), 960) == at(NEXT_MON, 16, 0)
    assert slaclock.add_business_minutes(at(MON, 8, 0), 2400) == at(FRI, 16, 0)
    assert slaclock.add_business_minutes(at(MON, 8, 0), 2401) == at(NEXT_MON, 8, 1)
    assert slaclock.add_business_minutes(at(WED, 10, 0), 4320) == datetime(2026, 11, 24, 10, 0)


def test_add_from_outside_business_hours():
    assert slaclock.add_business_minutes(at(MON, 7, 0), 30) == at(MON, 8, 30)
    assert slaclock.add_business_minutes(at(MON, 7, 59), 1) == at(MON, 8, 1)
    assert slaclock.add_business_minutes(at(MON, 16, 0), 10) == at(TUE, 8, 10)
    assert slaclock.add_business_minutes(at(MON, 23, 59), 10) == at(TUE, 8, 10)
    assert slaclock.add_business_minutes(at(FRI, 16, 0), 10) == at(NEXT_MON, 8, 10)
    assert slaclock.add_business_minutes(at(FRI, 20, 0), 10) == at(NEXT_MON, 8, 10)
    assert slaclock.add_business_minutes(at(SAT, 10, 0), 10) == at(NEXT_MON, 8, 10)
    assert slaclock.add_business_minutes(at(SUN, 10, 0), 10) == at(NEXT_MON, 8, 10)
    assert slaclock.add_business_minutes(at(SAT, 10, 0), 480) == at(NEXT_MON, 16, 0)


def test_zero_minutes():
    assert slaclock.add_business_minutes(at(MON, 10, 0), 0) == at(MON, 10, 0)
    assert slaclock.add_business_minutes(at(MON, 8, 0), 0) == at(MON, 8, 0)
    assert slaclock.add_business_minutes(at(MON, 15, 59), 0) == at(MON, 15, 59)
    assert slaclock.add_business_minutes(at(MON, 7, 0), 0) == at(MON, 8, 0)
    assert slaclock.add_business_minutes(at(MON, 16, 0), 0) == at(TUE, 8, 0)
    assert slaclock.add_business_minutes(at(FRI, 16, 0), 0) == at(NEXT_MON, 8, 0)
    assert slaclock.add_business_minutes(at(SAT, 12, 0), 0) == at(NEXT_MON, 8, 0)
    assert slaclock.add_business_minutes(at(SUN, 12, 0), 0) == at(NEXT_MON, 8, 0)


def test_add_ignores_seconds_and_microseconds():
    assert slaclock.add_business_minutes(at(MON, 10, 0, 45, 123), 30) == at(MON, 10, 30)
    assert slaclock.add_business_minutes(at(MON, 10, 0, 59, 999999), 0) == at(MON, 10, 0)
    assert slaclock.add_business_minutes(at(MON, 15, 59, 30), 1) == at(MON, 16, 0)


def test_add_rejects_negative_minutes():
    for minutes in (-1, -60, -10000):
        with pytest.raises(ValueError):
            slaclock.add_business_minutes(at(MON, 10, 0), minutes)
        with pytest.raises(ValueError):
            slaclock.add_business_minutes(at(SAT, 10, 0), minutes)


def test_add_accepts_a_due_date_366_days_out_and_rejects_367():
    start = at(MON, 8, 0)  # day 366 is Wednesday 2027-11-10, day 367 Thursday: 263 weekdays in days 0..366
    last_allowed = 263 * 480
    assert slaclock.add_business_minutes(start, last_allowed) == datetime(2027, 11, 10, 16, 0)
    assert slaclock.add_business_minutes(start, last_allowed - 1) == datetime(2027, 11, 10, 15, 59)
    with pytest.raises(ValueError):
        slaclock.add_business_minutes(start, last_allowed + 1)
    with pytest.raises(ValueError):
        slaclock.add_business_minutes(start, last_allowed + 480)
    with pytest.raises(ValueError):
        slaclock.add_business_minutes(start, 10 ** 7)


def test_add_just_inside_the_limit_from_a_late_start():
    start = at(MON, 15, 0)  # the first day has 60 minutes left, the other 366 days (0..366) as before
    last_allowed = 60 + 262 * 480
    assert slaclock.add_business_minutes(start, last_allowed) == datetime(2027, 11, 10, 16, 0)
    with pytest.raises(ValueError):
        slaclock.add_business_minutes(start, last_allowed + 1)


# ---------------------------------------------------------------------------------- business_minutes_between, by hand


def test_between_returns_an_int():
    for start, end in [(at(MON, 10, 0), at(MON, 10, 0)), (at(MON, 8, 0), at(MON, 16, 0)), (at(MON, 9, 0), at(TUE, 10, 0)),
                       (at(SAT, 10, 0), at(SUN, 10, 0)), (at(FRI, 15, 0), at(NEXT_MON, 9, 0)), (at(MON, 7, 0), at(MON, 7, 30))]:
        assert type(slaclock.business_minutes_between(start, end)) is int


def test_between_basics():
    assert slaclock.business_minutes_between(at(MON, 10, 0), at(MON, 10, 0)) == 0
    assert slaclock.business_minutes_between(at(MON, 10, 0), at(MON, 10, 1)) == 1
    assert slaclock.business_minutes_between(at(MON, 10, 0), at(MON, 11, 0)) == 60
    assert slaclock.business_minutes_between(at(MON, 8, 0), at(MON, 16, 0)) == 480
    assert slaclock.business_minutes_between(at(MON, 7, 0), at(MON, 17, 0)) == 480
    assert slaclock.business_minutes_between(at(MON, 15, 59), at(MON, 16, 0)) == 1
    assert slaclock.business_minutes_between(at(MON, 16, 0), at(MON, 17, 0)) == 0
    assert slaclock.business_minutes_between(at(MON, 7, 0), at(MON, 8, 0)) == 0
    assert slaclock.business_minutes_between(at(MON, 7, 59), at(MON, 8, 1)) == 1
    assert slaclock.business_minutes_between(at(MON, 0, 0), at(MON, 23, 59)) == 480


def test_between_is_half_open():
    assert slaclock.business_minutes_between(at(MON, 8, 0), at(MON, 8, 0)) == 0
    assert slaclock.business_minutes_between(at(MON, 8, 0), at(MON, 8, 1)) == 1
    assert slaclock.business_minutes_between(at(MON, 15, 58), at(MON, 15, 59)) == 1
    assert slaclock.business_minutes_between(at(MON, 15, 59), at(MON, 15, 59)) == 0
    assert slaclock.business_minutes_between(at(MON, 16, 0), at(MON, 16, 0)) == 0


def test_between_spans_days_and_weekends():
    assert slaclock.business_minutes_between(at(MON, 9, 0), at(TUE, 10, 0)) == 540
    assert slaclock.business_minutes_between(at(FRI, 15, 0), at(NEXT_MON, 9, 0)) == 120
    assert slaclock.business_minutes_between(at(SAT, 10, 0), at(NEXT_MON, 9, 0)) == 60
    assert slaclock.business_minutes_between(at(SUN, 10, 0), at(NEXT_MON, 9, 0)) == 60
    assert slaclock.business_minutes_between(at(MON, 8, 0), at(NEXT_MON, 8, 0)) == 2400
    assert slaclock.business_minutes_between(at(MON, 0, 0), at(NEXT_MON, 0, 0)) == 2400
    assert slaclock.business_minutes_between(at(SAT, 0, 0), at(SUN, 23, 59)) == 0
    assert slaclock.business_minutes_between(at(SAT, 10, 0), at(SAT, 12, 0)) == 0
    assert slaclock.business_minutes_between(at(SUN, 10, 0), at(SUN, 12, 0)) == 0
    assert slaclock.business_minutes_between(at(FRI, 12, 0), at(SAT, 12, 0)) == 240
    assert slaclock.business_minutes_between(at(SUN, 12, 0), at(NEXT_MON, 12, 0)) == 240
    assert slaclock.business_minutes_between(at(MON, 12, 0), at(WED, 12, 0)) == 960


def test_between_ignores_seconds_and_microseconds():
    assert slaclock.business_minutes_between(at(MON, 10, 0, 59), at(MON, 10, 1, 0)) == 1
    assert slaclock.business_minutes_between(at(MON, 10, 0, 30), at(MON, 10, 0, 10)) == 0
    assert slaclock.business_minutes_between(at(MON, 10, 0, 0, 5), at(MON, 10, 2, 59, 999999)) == 2
    assert slaclock.business_minutes_between(at(MON, 15, 59, 59), at(MON, 16, 0, 59)) == 1


def test_between_rejects_an_end_before_the_start():
    for start, end in [(at(MON, 10, 1), at(MON, 10, 0)), (at(TUE, 8, 0), at(MON, 16, 0)), (at(SUN, 10, 0), at(MON, 10, 0)),
                       (at(SAT, 12, 0), at(SAT, 11, 0)), (at(MON, 17, 0), at(MON, 7, 0))]:
        with pytest.raises(ValueError):
            slaclock.business_minutes_between(start, end)


def test_between_accepts_366_days_apart_and_rejects_367():
    start = at(MON, 8, 0)
    assert slaclock.business_minutes_between(start, datetime(2027, 11, 10, 16, 0)) == 263 * 480
    assert slaclock.business_minutes_between(start, datetime(2027, 11, 10, 0, 0)) == 262 * 480
    assert slaclock.business_minutes_between(at(MON, 10, 0), datetime(2027, 11, 10, 23, 59)) == 263 * 480 - 120
    with pytest.raises(ValueError):
        slaclock.business_minutes_between(start, datetime(2027, 11, 11, 8, 0))
    with pytest.raises(ValueError):
        slaclock.business_minutes_between(start, datetime(2027, 11, 11, 0, 0))
    with pytest.raises(ValueError):
        slaclock.business_minutes_between(at(MON, 23, 59), datetime(2027, 11, 11, 0, 0))
    with pytest.raises(ValueError):
        slaclock.business_minutes_between(start, datetime(2030, 1, 1))


def test_between_counts_whole_calendar_days_apart_not_24_hour_blocks():
    # 2027-11-10 23:59 is 366 days and 15 h 59 min after Monday 2026-11-09 08:00, but only 366 calendar days apart
    assert slaclock.business_minutes_between(at(MON, 8, 0), datetime(2027, 11, 10, 23, 59)) == 263 * 480
    # 2027-11-11 00:00 is 366 days and 16 h after start, yet 367 calendar days apart
    with pytest.raises(ValueError):
        slaclock.business_minutes_between(at(MON, 8, 0), datetime(2027, 11, 11, 0, 0))


# ------------------------------------------------------------------------------------------------ escalation_tier


def expected_tier(priority, breached, reopens):
    base = {"P1": 1, "P2": 1, "P3": 0, "P4": 0}[priority]
    if breached:
        base += 2 if priority == "P1" else 1
    if reopens >= 2:
        base += 1
    return min(base, 3)


ESCALATION = {
    ("P1", False, 0): 1, ("P1", False, 1): 1, ("P1", False, 2): 2, ("P1", False, 3): 2, ("P1", False, 9): 2,
    ("P1", True, 0): 3, ("P1", True, 1): 3, ("P1", True, 2): 3, ("P1", True, 9): 3,
    ("P2", False, 0): 1, ("P2", False, 1): 1, ("P2", False, 2): 2, ("P2", False, 9): 2,
    ("P2", True, 0): 2, ("P2", True, 1): 2, ("P2", True, 2): 3, ("P2", True, 9): 3,
    ("P3", False, 0): 0, ("P3", False, 1): 0, ("P3", False, 2): 1, ("P3", False, 9): 1,
    ("P3", True, 0): 1, ("P3", True, 1): 1, ("P3", True, 2): 2, ("P3", True, 9): 2,
    ("P4", False, 0): 0, ("P4", False, 1): 0, ("P4", False, 2): 1, ("P4", False, 9): 1,
    ("P4", True, 0): 1, ("P4", True, 1): 1, ("P4", True, 2): 2, ("P4", True, 9): 2,
}


@pytest.mark.parametrize("case", sorted(ESCALATION))
def test_escalation_table(case):
    priority, breached, reopens = case
    assert slaclock.escalation_tier(priority, breached, reopens) == ESCALATION[case]
    assert slaclock.escalation_tier(priority, breached, reopens) == expected_tier(*case)


def test_escalation_tier_is_an_int_between_0_and_3():
    for priority in ("P1", "P2", "P3", "P4"):
        for breached in (False, True):
            for reopens in range(0, 6):
                tier = slaclock.escalation_tier(priority, breached, reopens)
                assert type(tier) is int and 0 <= tier <= 3


@pytest.mark.parametrize("priority, breached, reopens", [
    ("P5", False, 0), ("p1", False, 0), ("", True, 0), (" P1", False, 1), ("P0", True, 2), ("P1 ", False, 0),
    ("P1", False, -1), ("P2", True, -1), ("P3", False, -5), ("P4", True, -100), ("X", True, -1), ("P5", True, 5),
])
def test_escalation_rejects(priority, breached, reopens):
    with pytest.raises(ValueError):
        slaclock.escalation_tier(priority, breached, reopens)


def test_zero_reopens_is_valid():
    assert slaclock.escalation_tier("P3", False, 0) == 0
    assert slaclock.escalation_tier("P1", True, 0) == 3


# ----------------------------------------------------------------------------------------------- parse_duration


@pytest.mark.parametrize("text, minutes", [
    ("90m", 90), ("1m", 1), ("59m", 59), ("60m", 60), ("61m", 61), ("100m", 100), ("999m", 999),
    ("4h", 240), ("1h", 60), ("24h", 1440), ("25h", 1500), ("1h30m", 90), ("1h59m", 119), ("2h1m", 121), ("0h60m", 60),
    ("0h100m", 100), ("0h1m", 1), ("0d1m", 1), ("0d0h1m", 1), ("0d90m", 90), ("0d0h90m", 90),
    ("1d", 1440), ("2d", 2880), ("10d", 14400), ("1d4h", 1680), ("1d0h5m", 1445), ("1d1h1m", 1501), ("3d5h7m", 4627),
    ("1d59m", 1499), ("1d23h59m", 2879), ("2d3m", 2883), ("5h5m", 305),
    (" 90m", 90), ("90m ", 90), ("  1h30m  ", 90), ("\t2d\n", 2880), ("\n4h", 240), (" 1d4h ", 1680),
])
def test_parse_duration(text, minutes):
    assert slaclock.parse_duration(text) == minutes


@pytest.mark.parametrize("text", [
    "", " ", "\t", "0m", "0h", "0d", "0d0h0m", "00m", "0h0m", "0d0m", "1.5h", "0.5h", "30m1h", "1h1d", "1m1h", "-5m", "-1h",
    "+5m", "1 h", "1h 30m", "1d 4h", "1 d", "1H", "1h30M", "90M", "2D", "1D", "m", "h", "d", "hm", "1hh", "1h30", "30", "90",
    "abc", "1h60m", "1h61m", "1h99m", "1d60m", "2d90m", "5h120m", "0d1h60m", "1d1d", "1h1h", "1m1m", "1h30m30m", "1d4h30m5m",
    "1,5h", "1h-5m", "m5", "90 m", "9 0m", "1h:30m", "1h,30m", "1h+30m", "one hour", "1hour", "90min", "5s", "1w", "90ms",
    "1hm", "1dm", "2dh", "h30m", "d4h", "1dh", "dhm", "d1h", "1d h", "1d4hm", "d", "1d1", "x90m", "90mx", "(90m)", "90m\x00",
])
def test_parse_duration_rejects(text):
    with pytest.raises(ValueError):
        slaclock.parse_duration(text)


def test_parse_duration_returns_an_int():
    for text in ("90m", "1h30m", "2d", "1d4h"):
        assert type(slaclock.parse_duration(text)) is int
