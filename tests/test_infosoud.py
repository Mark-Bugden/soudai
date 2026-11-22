"""infosoud's case lookup, court lists and event labels, on saved real responses."""

import pytest
from conftest import FIXTURES, FakeClient, load, make_response

from soudai import http, infosoud
from soudai.http import UnexpectedResponse

LOOKUP = infosoud.API + "rizeni/vyhledej"
NACHOD = ("KSVYCHK", "OSVYCNA", "C", 15)


def test_a_found_case_comes_back_with_its_timeline():
    _, response = load("infosoud/case_found.json")
    result = infosoud.parse_lookup(response)
    assert result.outcome == "found"
    assert (result.case["cislo"], result.case["druh"], result.case["bcVec"], result.case["rocnik"]) == (
        15,
        "C",
        384,
        2022,
    )
    assert result.case["platneK"].startswith("2026-11-21")


def test_a_missing_case_is_not_found():
    _, response = load("infosoud/case_not_found.json")
    result = infosoud.parse_lookup(response)
    assert result.outcome == "not_found"
    assert result.message == "RIZENI_0000#15 C 9999 / 2022#Okresní soud Náchod"


def test_the_apis_unexpected_error_is_an_error():
    response = make_response(LOOKUP, 400, {"message": "RIZENI_0001"})
    assert infosoud.parse_lookup(response).outcome == "error"


@pytest.mark.parametrize(
    "response",
    [
        make_response(LOOKUP, 400, {"message": "RIZENI_VALIDATION_0002"}),  # our request is wrong
        make_response(LOOKUP, 400, {"message": "ORGANIZACE_0000"}),
        make_response(LOOKUP, 404, {"message": "Not Found"}),
        make_response(LOOKUP, 200, text="<!doctype html>", content_type="text/html"),  # the app, not the API
        make_response(LOOKUP, 200, {"cislo": 15, "druh": "C"}),  # a case without its timeline
        make_response(LOOKUP, 200, [1, 2]),
        make_response(LOOKUP, 200, text="{not json"),  # JSON by its content type only
        make_response(LOOKUP, 400, ["RIZENI_0000"]),
        make_response(LOOKUP, 400, {"message": 404}),
    ],
)
def test_anything_else_raises(response):
    with pytest.raises(UnexpectedResponse):
        infosoud.parse_lookup(response)


def test_lookup_sends_the_case_number_as_the_app_does():
    record, response = load("infosoud/case_found.json")
    client = FakeClient([(("POST", LOOKUP, record["body"]), response)])
    assert infosoud.lookup(client, *NACHOD, 384, 2022).outcome == "found"
    assert client.requests == [("POST", LOOKUP, record["body"], False)]
    assert record["body"] == {
        "druhOrganizace": "KSVYCHK",
        "okresniSoud": "OSVYCNA",
        "druhVeci": "C",
        "cisloSenatu": 15,
        "bcVec": 384,
        "rocnik": 2022,
    }


def test_a_cached_error_is_fetched_again_once():
    body = infosoud.case_request(*NACHOD, 384, 2022)
    _, found = load("infosoud/case_found.json")
    cached_error = make_response(LOOKUP, 400, {"message": "RIZENI_0001"}, from_cache=True)
    client = FakeClient([(("POST", LOOKUP, body), cached_error), (("POST", LOOKUP, body), found)])
    assert infosoud.lookup(client, *NACHOD, 384, 2022).outcome == "found"
    assert [refresh for *_, refresh in client.requests] == [False, True]


def test_a_cached_answer_that_doesnt_parse_is_fetched_again_once():
    body = infosoud.case_request(*NACHOD, 384, 2022)
    _, found = load("infosoud/case_found.json")
    cached_page = make_response(
        LOOKUP, 200, text="<!doctype html>", content_type="text/html", from_cache=True
    )
    client = FakeClient([(("POST", LOOKUP, body), cached_page), (("POST", LOOKUP, body), found)])
    assert infosoud.lookup(client, *NACHOD, 384, 2022).outcome == "found"
    assert [refresh for *_, refresh in client.requests] == [False, True]


def test_case_numbers_from_numpy_become_plain_ints():
    import numpy

    body = infosoud.case_request(
        "KSVYCHK", "OSVYCNA", "C", numpy.int64(15), numpy.int64(384), numpy.int64(2022)
    )
    assert body == infosoud.case_request(*NACHOD, 384, 2022)
    assert all(type(body[key]) is int for key in ("cisloSenatu", "bcVec", "rocnik"))
    assert http.request_key("POST", LOOKUP, body)  # json can encode it


def test_a_fresh_error_is_returned_as_it_is():
    body = infosoud.case_request(*NACHOD, 384, 2022)
    client = FakeClient([(("POST", LOOKUP, body), make_response(LOOKUP, 400, {"message": "RIZENI_0001"}))])
    assert infosoud.lookup(client, *NACHOD, 384, 2022).outcome == "error"
    assert len(client.requests) == 1


def test_events_sort_by_date_then_poradi():
    _, response = load("infosoud/case_found.json")
    events = infosoud.sorted_events(response.json())
    assert [event["udalost"] for event in events] == [
        "ZAHAJ_RIZ",
        "NAR_JED",
        "VYD_ROZH",
        "ST_VEC_VYR",
        "ST_VEC_PUK",
        "ST_VEC_ODS",
    ]


def test_cancelled_events_are_marked():
    _, response = load("infosoud/case_cancelled_hearing.json")
    cancelled = {event["udalost"] for event in response.json()["udalosti"] if event["zruseno"]}
    assert cancelled == {"NAR_JED", "ZRUS_JED"}


def test_court_lists(fixture_client):
    regional = infosoud.regional_courts(fixture_client)
    assert len(regional) == 10
    assert {"nazev": "Městský soud Praha", "kod": "MSPHAAB"} in regional
    district = infosoud.district_courts(fixture_client, "KSVYCHK")
    assert len(district) == 11
    assert {"nazev": "Okresní soud Náchod", "kod": "OSVYCNA"} in district


def test_the_backend_version_is_fetched_afresh_and_recorded(fixture_client):
    assert infosoud.backend_version(fixture_client) == "2.0.0.10"
    assert fixture_client.backend_version == "2.0.0.10"
    assert fixture_client.requests[-1] == ("GET", infosoud.API + "env", None, True)


@pytest.fixture(scope="module")
def chunk():
    return (FIXTURES / "infosoud" / "labels_chunk.js").read_text(encoding="utf-8")


def test_event_labels_are_the_district_courts_not_the_supreme_courts(chunk):
    labels = infosoud.event_labels(chunk)
    assert len(labels) == 28
    assert (
        labels["ZAHAJ_RIZ"]["label"] == "Zahájení řízení"
    )  # the Supreme Court's reads "Došlo Nejvyššímu soudu"
    assert (
        labels["ZAHAJ_RIZ"]["tooltip"] == "Zahájení řízení je zápis spisové značky do příslušného rejstříku"
    )
    assert labels["ST_VEC_ODS"]["label"] == "Skončení věci"
    assert labels["ST_VEC_ODS"]["description"].startswith("Skončení věci a uložení na spisovnu")
    assert "ns" not in labels and "tooltip" not in labels


def test_error_messages_name_the_lookup_outcomes(chunk):
    messages = infosoud.error_messages(chunk)
    assert messages["RIZENI_0000"] == "Hledaná spisová značka {} pro {} neexistuje."
    assert messages["RIZENI_0001"].startswith("Při načítání řízení se vyskytla neočekávaná chyba")
    assert {code for code in messages if code.startswith("RIZENI_VALIDATION")} == {
        f"RIZENI_VALIDATION_000{n}" for n in range(7)
    }


def test_js_object_literals_parse_with_their_escapes():
    text = """x={a:"\\u0158\\xEDzen\\xED",'b c':{d:'it\\'s',e:"say \\"hi\\""},f:"line\\nbreak"};"""
    assert infosoud.parse_js_object(text, 2) == {
        "a": "Řízení",
        "b c": {"d": "it's", "e": 'say "hi"'},
        "f": "line\nbreak",
    }


def test_the_labels_chunk_is_found_from_the_front_page_and_the_search_stops_there():
    site = infosoud.SITE
    client = FakeClient(
        [
            (("GET", site, None), make_response(site, 200, text='<script src="main-AB12.js" type="module">')),
            (("GET", site + "main-AB12.js", None), make_response("", 200, text='import("./chunk-ONE.js")')),
            (("GET", site + "chunk-ONE.js", None), make_response("", 200, text='import"./chunk-TWO.js";')),
            (
                ("GET", site + "chunk-TWO.js", None),
                make_response("", 200, text='udalost:{ns:{},ZAHAJ_RIZ:"x"}'),
            ),
        ]
    )
    assert infosoud.labels_chunk(client)[0] == "chunk-TWO.js"
    assert client.requests[0] == ("GET", site, None, True)  # the front page is always fetched afresh
    assert len(client.requests) == 4
