"""The official statistics: InfoData's S_AS_40 report, on the real 2022 report and its search results."""

import gzip

import pytest
from conftest import FIXTURES

from soudai import http, official, reference

PAGE = (FIXTURES / "infodata" / "results_2022.html").read_text(encoding="utf-8")
REPORT = gzip.decompress((FIXTURES / "infodata" / "s_as_40_2022.xml.gz").read_bytes())


def test_the_search_results_give_the_one_xml_report_for_the_year():
    link = official.document_link(PAGE, 2022)
    assert link.startswith("/InfoData/servlet/FileServlet?id1=1&id2=obsah_dokumentu_xml&")
    assert "id_dokumentu=2049306" in link and "&amp;" not in link
    with pytest.raises(http.UnexpectedResponse, match="0 XML documents"):
        official.document_link(PAGE, 2021)


def test_the_report_parses_and_adds_up():
    rows, computed = official.parse(REPORT)
    assert computed.isoformat() == "2023-01-15"
    found, national = official.by_court(rows, reference.courts())
    assert len(found) == 86
    assert found["OSVYCNA"] == {"napad": 2309, "revived": 108, "disposed": 2388, "pending": 333}
    assert found["OSJIMBM"]["napad"] == 11891  # "Brno": Městský soud v Brně
    assert national == {"napad": 295311, "revived": 16862, "disposed": 319050, "pending": 111588}


def test_a_court_missing_or_twice_or_totals_that_dont_add_up_are_refused():
    rows, _ = official.parse(REPORT)
    courts = reference.courts()
    nachod = next(i for i, (name, _) in enumerate(rows) if name == "Náchod")
    with pytest.raises(http.UnexpectedResponse, match="not in the report: náchod"):
        official.by_court(rows[:nachod] + rows[nachod + 1 :], courts)
    with pytest.raises(http.UnexpectedResponse, match="Náchod appears twice"):
        official.by_court(rows + [rows[nachod]], courts)
    changed = list(rows)
    changed[nachod] = ("Náchod", [rows[nachod][1][0], 2310.0] + rows[nachod][1][2:])
    with pytest.raises(http.UnexpectedResponse, match="napad doesn't add up"):
        official.by_court(changed, courts)


class StubClient:
    """Answers the form's search and the report from the fixtures, and records what's asked."""

    def __init__(self, cached):
        self.cached_keys = cached
        self.asked = []

    def cached(self, method, url, body=None, form=False):
        return True if (method, form) in self.cached_keys else None

    def post(self, url, body, form=False):
        self.asked.append(("POST", form))
        return http.Response(url, 200, PAGE.encode("utf-8"), "text/html", "", False)

    def get(self, url, refresh=False):
        self.asked.append(("GET", url))
        return http.Response(url, 200, REPORT, "text/xml;charset=utf-8", "", False)


@pytest.mark.parametrize(
    "cached, sessions", [(set(), 1), ({("POST", True)}, 1), ({("POST", True), ("GET", False)}, 0)]
)
def test_the_form_page_is_loaded_only_when_something_isnt_cached(cached, sessions):
    client, loaded = StubClient(cached), []
    content = official.fetch(client, 2022, lambda: loaded.append(1) if not loaded else None)
    assert content == REPORT
    assert len(loaded) == sessions
    assert client.asked[0] == ("POST", True)  # the search goes as a web form
