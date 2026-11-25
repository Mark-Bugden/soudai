"""The stage model: each case's path through the journey's stages, and its dates (filed, disposed, end).

Most histories are real ones from step 5's sample, some shortened or with dates moved, and the rest are
made up. The case numbers are made up.
"""

from datetime import date

import pandas as pd
import pytest

from soudai import events, reference

VALID_TO = date(2026, 11, 23)


def history(number, *rows):
    """An event table for one case from (code, date) or (code, date, "cancelled" or a linked case)
    tuples, with `poradi` in the order given."""
    out = []
    for poradi, (code, day, *extra) in enumerate(rows, 1):
        linked = extra[0] if extra and extra[0] != "cancelled" else None
        out.append(
            {
                "court": "OSVYCNA",
                "senate": 15,
                "number": number,
                "year": 2022,
                "code": code,
                "date": date.fromisoformat(day),
                "poradi": poradi,
                "cancelled": extra == ["cancelled"],
                "linked_court": "KSVYCHK" if linked else None,
                "linked_case": linked,
            }
        )
    return pd.DataFrame(out)


def run(*histories):
    """(path, visits, outcomes) for the given histories, shuffled, since the functions mustn't rely on
    the order of the table."""
    table = pd.concat(histories, ignore_index=True).sample(frac=1, random_state=1)
    cases = table[events.CASE].drop_duplicates().assign(valid_to=VALID_TO)
    visits = events.journey(table)
    outcomes = events.outcomes(cases, table)
    paths = visits.groupby("number")["stage"].agg(list).to_dict()
    return paths, visits, outcomes.set_index("number")


TYPICAL = history(  # after 23 C 35/2025 at Hodonín, with a hearing cancelled
    1,
    ("ZAHAJ_RIZ", "2025-11-18"),
    ("ZRUS_JED", "2026-04-08", "cancelled"),
    ("NAR_JED", "2026-04-16", "cancelled"),
    ("NAR_JED", "2026-05-21"),
    ("VYD_ROZH", "2026-05-21"),
    ("ST_VEC_VYR", "2026-05-21"),
    ("ST_VEC_PUK", "2026-06-20"),
    ("ST_VEC_ODS", "2026-06-29"),
)
APPEALED_TWICE = history(  # 98 C 226/2023 at Praha 9
    2,
    ("ZAHAJ_RIZ", "2023-07-19"),
    ("NAR_JED", "2024-03-18"),
    ("NAR_JED", "2024-05-16"),
    ("ZRUS_JED", "2024-06-14", "cancelled"),
    ("NAR_JED", "2024-07-12"),
    ("NAR_JED", "2024-07-15", "cancelled"),
    ("NAR_JED", "2024-07-25"),
    ("VYD_ROZH", "2024-07-25"),
    ("POD_OP_PR", "2024-08-12"),
    ("ODES_SPIS", "2024-10-01"),
    ("ODVOLANI", "2024-10-03", "30 CO 362/2024"),
    ("VYR_OP_PR", "2024-10-17"),
    ("VRAC_SPIS", "2024-10-22"),
    ("ST_VEC_OBZ", "2024-10-23"),
    ("NAR_JED", "2024-11-21"),
    ("VYD_ROZH", "2024-11-21"),
    ("ST_VEC_VYR", "2024-11-21"),
    ("POD_OP_PR", "2024-12-05"),
    ("ODES_SPIS", "2025-03-17"),
    ("ODVOLANI", "2025-03-18", "30 CO 102/2025"),
    ("VYR_OP_PR", "2025-05-13"),
    ("VRAC_SPIS", "2025-06-10"),
    ("ST_VEC_PUK", "2025-06-12"),
    ("ST_VEC_ODS", "2025-09-01"),
)
REVIVED = history(  # 86 C 25/2021 at Semily: no disposal shows before the revival
    3,
    ("ZAHAJ_RIZ", "2021-09-17"),
    ("VYD_ROZH", "2021-12-03"),
    ("ST_VEC_OBZ", "2022-03-18"),
    ("NAR_JED", "2022-04-29"),
    ("VYD_ROZH", "2022-04-29"),
    ("ST_VEC_VYR", "2022-04-29"),
    ("ST_VEC_PUK", "2022-05-16"),
    ("ST_VEC_ODS", "2022-06-29"),
)
STILL_REVIVED = history(  # revived after its disposal, and not decided again
    4,
    ("ZAHAJ_RIZ", "2025-02-03"),
    ("VYD_ROZH", "2025-04-10"),
    ("ST_VEC_VYR", "2025-04-10"),
    ("POD_OP_PR", "2025-04-24"),
    ("ST_VEC_OBZ", "2025-05-02"),
    ("NAR_JED", "2025-12-01"),
)
APPEAL_AFTER_FINAL = history(  # after 5 C 203/2020: an appeal lodged after the case was final
    5,
    ("ZAHAJ_RIZ", "2020-07-15"),
    ("NAR_JED", "2020-09-24"),
    ("VYD_ROZH", "2020-09-24"),
    ("ST_VEC_VYR", "2020-09-24"),
    ("POD_OP_PR", "2020-11-27"),
    ("ST_VEC_PUK", "2020-12-16"),
    ("POD_OP_PR", "2021-02-02"),
    ("ODES_SPIS", "2021-04-23"),
    ("ODVOLANI", "2021-04-26", "23 CO 113/2021"),
    ("ST_VEC_ODS", "2021-07-07"),
)
SUSPENDED = history(  # 4 C 70/2025 at Pelhřimov
    6,
    ("ZAHAJ_RIZ", "2025-01-14"),
    ("ST_VEC_PRE", "2025-04-24"),
)
RESUMED = history(  # 16 C 14/2024
    7,
    ("ZAHAJ_RIZ", "2024-01-17"),
    ("ST_VEC_PRE", "2024-04-16"),
    ("ST_VEC_UPR", "2024-10-21"),
    ("NAR_JED", "2024-11-21"),
    ("NAR_JED", "2025-01-22", "cancelled"),
    ("ZRUS_JED", "2025-01-22", "cancelled"),
    ("VYD_ROZH", "2025-08-14"),
    ("ST_VEC_VYR", "2025-08-14"),
    ("ST_VEC_PUK", "2025-09-05"),
    ("ST_VEC_ODS", "2025-09-09"),
)
CLOSED = history(  # closed in the register, never legally final
    8,
    ("ZAHAJ_RIZ", "2022-02-01"),
    ("ST_VEC_ODS", "2022-03-10"),
    ("ST_VEC_VYR", "2022-03-14"),
)


def test_a_typical_case_goes_filed_hearing_decided_final():
    paths, visits, outcomes = run(TYPICAL)
    assert paths[1] == ["filed", "hearing", "decided", "final"]
    assert visits["events"].tolist() == [1, 1, 2, 1]  # the cancelled hearing isn't counted
    assert visits["date"].tolist() == [
        date(2025, 11, 18),
        date(2026, 5, 21),
        date(2026, 5, 21),
        date(2026, 6, 20),
    ]
    case = outcomes.loc[1]
    assert (case.filed, case.disposed, case.end, case.how, case.until) == (
        date(2025, 11, 18),
        date(2026, 5, 21),
        date(2026, 6, 20),
        "final",
        date(2026, 6, 20),
    )


def test_repeated_hearings_are_one_visit_and_cases_can_go_back():
    paths, visits, outcomes = run(APPEALED_TWICE)
    assert paths[2] == [
        "filed",
        "hearing",
        "decided",
        "appeal",
        "revived",
        "hearing",
        "decided",
        "appeal",
        "final",
    ]
    assert visits["events"].tolist() == [1, 4, 1, 5, 1, 1, 2, 5, 1]
    assert visits["date"].iloc[1] == date(2024, 3, 18)  # a visit starts with its first event
    assert outcomes.loc[2, "disposed"] == date(2024, 11, 21)
    assert outcomes.loc[2, "end"] == date(2025, 6, 12)


def test_a_decision_with_no_disposal_still_puts_a_case_in_decided():
    paths, _, outcomes = run(REVIVED)
    assert paths[3] == ["filed", "decided", "revived", "hearing", "decided", "final"]
    assert outcomes.loc[3, "disposed"] == date(2022, 4, 29)


def test_a_case_revived_and_not_decided_again_is_open_and_not_disposed():
    paths, _, outcomes = run(STILL_REVIVED)
    assert paths[4] == ["filed", "decided", "appeal", "revived", "hearing"]
    case = outcomes.loc[4]
    assert (case.disposed, case.end, case.how, case.until) == (None, None, None, VALID_TO)


def test_the_path_stops_at_the_first_legally_final():
    paths, _, outcomes = run(APPEAL_AFTER_FINAL)
    assert paths[5] == ["filed", "hearing", "decided", "appeal", "final"]
    assert outcomes.loc[5, "end"] == date(2020, 12, 16)


def test_a_suspended_case_is_open_until_its_record_ends():
    paths, _, outcomes = run(SUSPENDED, RESUMED)
    assert paths[6] == ["filed", "suspended"]
    assert outcomes.loc[6, "until"] == VALID_TO and outcomes.loc[6, "end"] is None
    assert paths[7] == ["filed", "suspended", "hearing", "decided", "final"]  # "resumed" isn't a stage


def test_a_case_closed_without_legal_force_ends_at_its_closing():
    paths, _, outcomes = run(CLOSED)
    assert paths[8] == ["filed", "decided"]  # closing isn't a stage
    case = outcomes.loc[8]
    assert (case.end, case.how) == (date(2022, 3, 10), "closed")
    assert case.disposed == date(2022, 3, 10)  # its disposal is after its end, so it's capped


def test_a_case_that_ends_with_no_disposal_counts_as_disposed_when_it_ends():
    final_after_revival = history(
        9,
        ("ZAHAJ_RIZ", "2023-01-02"),
        ("NAR_JED", "2023-05-02"),
        ("VYD_ROZH", "2023-05-02"),
        ("ST_VEC_VYR", "2023-05-02"),
        ("ST_VEC_OBZ", "2023-06-01"),
        ("ST_VEC_PUK", "2023-06-20"),
    )
    no_disposal = history(
        10, ("ZAHAJ_RIZ", "2023-01-02"), ("VYD_ROZH", "2023-02-01"), ("ST_VEC_PUK", "2023-03-01")
    )
    _, _, outcomes = run(final_after_revival, no_disposal)
    assert outcomes.loc[9, "disposed"] == date(2023, 5, 2)  # revived, but it has ended since
    assert outcomes.loc[10, "disposed"] == date(2023, 3, 1)


def test_events_before_the_filing_are_left_off_and_the_filing_comes_first_on_its_day():
    odd = history(
        11,
        ("NAR_JED", "1021-01-11"),  # a typo for 2021
        ("ST_VEC_PUK", "2020-06-01"),
        ("VYD_ROZH", "2021-01-04"),
        ("ZAHAJ_RIZ", "2021-01-04"),
        ("ST_VEC_VYR", "2021-01-04"),
        ("ST_VEC_PUK", "2021-02-15"),
    )
    paths, _, outcomes = run(odd)
    assert paths[11] == ["filed", "decided", "final"]
    assert outcomes.loc[11, "filed"] == date(2021, 1, 4)
    assert outcomes.loc[11, "end"] == date(2021, 2, 15)


def test_a_case_with_no_filing_is_left_out():
    paths, _, outcomes = run(TYPICAL, history(12, ("NAR_JED", "2022-05-01"), ("VYD_ROZH", "2022-05-01")))
    assert 12 not in paths and 12 not in outcomes.index


def test_the_path_ends_where_the_case_does():
    histories = [
        TYPICAL,
        APPEALED_TWICE,
        REVIVED,
        STILL_REVIVED,
        APPEAL_AFTER_FINAL,
        SUSPENDED,
        RESUMED,
        CLOSED,
    ]
    paths, visits, outcomes = run(*histories)
    last = visits.groupby("number").last()
    for number, case in outcomes.iterrows():
        assert (last.loc[number, "stage"] == "final") == (case.how == "final")
        if case.how == "final":
            assert last.loc[number, "date"] == case.end


@pytest.mark.parametrize("code", sorted(events.STAGE))
def test_every_mapped_code_is_a_known_event(code):
    codes = {row["code"] for row in reference.events() if row["kind"] == "event"}
    assert code in codes
    assert events.STAGE[code] in events.STAGES
