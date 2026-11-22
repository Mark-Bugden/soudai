"""infosoud.gov.cz, the courts' public case-tracking service: court lists, case lookup and event labels.

Its JSON API (https://infosoud.gov.cz/api/v1) is undocumented and can change without notice. Every
request goes through the cached, paced client, and anything the API returns that this module doesn't
recognise raises UnexpectedResponse, so a run stops rather than recording nonsense.
"""

import re
from dataclasses import dataclass

from .http import UnexpectedResponse, parsed, with_params
from .http import expect_json as _json

SITE = "https://infosoud.gov.cz/"
API = SITE + "api/v1/"


@dataclass(frozen=True)
class Lookup:
    """The result of looking a case up: found (with `case`), not_found, or error (with `message`)."""

    outcome: str
    case: dict | None = None
    message: str | None = None


def backend_version(client):
    """The API's backend version, fetched afresh and recorded with the run, so an API change shows up."""
    response = client.get(API + "env", refresh=True)
    env = _json(response, 200)
    version = env.get("backendVerze") if isinstance(env, dict) else None
    if not version:
        raise UnexpectedResponse(f"env has no backendVerze: {response.text[:200]}")
    client.set_backend_version(version)
    return version


def regional_courts(client):
    """The regional, municipal and high courts, as [{"nazev": ..., "kod": ...}]."""
    return parsed(client, _courts, "GET", API + "organizace/lov")


def district_courts(client, regional_code):
    """The district courts under a regional court, as [{"nazev": ..., "kod": ...}]."""
    url = with_params(API + "organizace/podrizene/lov", {"idOrganizace": regional_code})
    return parsed(client, _courts, "GET", url)


def case_request(regional_code, district_code, register, senate, number, year):
    """The body of a case lookup: e.g. KSVYCHK, OSVYCNA, "C", 15, 384, 2022 for 15 C 384/2022 at Náchod.

    The numbers are made plain ints, so numpy's from a pandas table can't break the JSON or the cache key.
    """
    return {
        "druhOrganizace": str(regional_code),
        "okresniSoud": str(district_code),
        "druhVeci": str(register),
        "cisloSenatu": int(senate),
        "bcVec": int(number),
        "rocnik": int(year),
    }


def lookup(client, regional_code, district_code, register, senate, number, year):
    """Look one case up. A cached error, or a cached answer that doesn't parse, isn't trusted: it's
    fetched again once."""
    body = case_request(regional_code, district_code, register, senate, number, year)
    response = client.post(API + "rizeni/vyhledej", body)
    try:
        result = parse_lookup(response)
    except UnexpectedResponse:
        if not response.from_cache:
            raise
        result = None
    if response.from_cache and (result is None or result.outcome == "error"):
        result = parse_lookup(client.post(API + "rizeni/vyhledej", body, refresh=True))
    return result


class LookupFailed(Exception):
    """The API answered RIZENI_0001, "unexpected error", every time it was asked."""


def exists(client, regional_code, district_code, register, senate, number, year, attempts=3):
    """Whether a case number exists. An error answer is asked again, up to `attempts` times in all.
    A found case must be the one asked for."""
    for _ in range(attempts):
        result = lookup(client, regional_code, district_code, register, senate, number, year)
        if result.outcome == "not_found":
            return False
        if result.outcome == "found":
            case = result.case
            if (case["cislo"], case["druh"].upper(), case["bcVec"], case["rocnik"]) != (
                senate,
                register.upper(),
                number,
                year,
            ):
                raise UnexpectedResponse(f"asked for {senate} {register} {number}/{year}, got {case}"[:300])
            return True
    raise LookupFailed(f"{district_code} {senate} {register} {number}/{year}: {result.message}")


def parse_lookup(response):
    """found: HTTP 200 with the case. not_found: a 400 with RIZENI_0000. error: a 400 with RIZENI_0001,
    the API's "unexpected error, repeat the query". Anything else raises UnexpectedResponse."""
    if response.status == 200:
        case = _json(response, 200)
        if not isinstance(case, dict):
            raise UnexpectedResponse(f"a found case that isn't an object: {response.text[:200]}")
        missing = {"cislo", "druh", "rocnik", "bcVec", "stav", "udalosti", "platneK"} - set(case)
        if missing:
            raise UnexpectedResponse(f"a found case lacks {sorted(missing)}: {response.text[:200]}")
        return Lookup("found", case=case)
    error = _json(response, 400)
    message = error.get("message") if isinstance(error, dict) else None
    if not isinstance(message, str):
        raise UnexpectedResponse(f"HTTP 400 without a message: {response.text[:200]}")
    code = message.split("#", 1)[0]
    if code == "RIZENI_0000":
        return Lookup("not_found", message=message)
    if code == "RIZENI_0001":
        return Lookup("error", message=message)
    raise UnexpectedResponse(f"HTTP 400 with {message!r}")


def sorted_events(case):
    """A case's events in order. The API doesn't sort them: sort by date, then by `poradi`."""
    return sorted(case["udalosti"], key=lambda event: (event["datum"], event["poradi"]))


# The app's JS bundle: the Czech labels of event codes, and the API's error messages.


def labels_chunk(client):
    """The name and text of the bundle chunk holding the event labels.

    The front page is fetched afresh, since it names the current build. Chunks have content hashes in
    their names, so cached ones are reused. The chunks are searched breadth-first from main.js, and the
    search stops at the first that holds ZAHAJ_RIZ's label.
    """
    index = client.get(SITE, refresh=True).text
    main = re.search(r'<script src="(main-\w+\.js)"', index)
    if main is None:
        raise UnexpectedResponse("the front page names no main-*.js")
    queue, seen = [main.group(1)], set()
    while queue:
        name = queue.pop(0)
        if name in seen:
            continue
        seen.add(name)
        text = client.get(SITE + name).text
        if "udalost:{ns:{" in text and "ZAHAJ_RIZ:" in text:
            return name, text
        queue += re.findall(r"\./(chunk-\w+\.js)", text)
    raise UnexpectedResponse(f"none of the {len(seen)} chunks reachable from main.js holds the event labels")


def event_labels(chunk):
    """The event labels for the district, regional and high courts (not the Supreme Court's set, `ns`).

    Returns {code: {"label": ..., "tooltip": ..., "description": ...}}, with HTML tags taken out of
    the tooltips.
    """
    udalost = parse_js_object(chunk, _find(chunk, "udalost:{ns:{") + len("udalost:"))
    tooltips, descriptions = udalost.get("tooltip", {}), udalost.get("popis", {})
    return {
        code: {
            "label": label.strip(),
            "tooltip": _strip_tags(tooltips.get(code, "")),
            "description": descriptions.get(code, "").strip(),
        }
        for code, label in udalost.items()
        if isinstance(label, str)
    }


def error_messages(chunk):
    """The API's error codes with the app's Czech messages, e.g. RIZENI_0000."""
    return parse_js_object(chunk, _find(chunk, "messages:{RIZENI_0000") + len("messages:"))


_JS_KEY = re.compile(r"[A-Za-z_$][\w$]*")


def parse_js_object(text, start):
    """Parse the JS object literal at text[start], which holds only strings and further objects."""
    value, _ = _js_value(text, start)
    return value


def _js_value(text, i):
    if text[i] == "{":
        result, i = {}, i + 1
        while True:
            i = _skip_space(text, i)
            if text[i] == "}":
                return result, i + 1
            if text[i] in "\"'":
                key, i = _js_string(text, i)
            else:
                match = _JS_KEY.match(text, i)
                if match is None:
                    raise ValueError(f"expected a key at {i}: {text[i : i + 40]!r}")
                key, i = match.group(), match.end()
            i = _skip_space(text, i)
            if text[i] != ":":
                raise ValueError(f"expected ':' at {i}: {text[i : i + 40]!r}")
            result[key], i = _js_value(text, _skip_space(text, i + 1))
            i = _skip_space(text, i)
            if text[i] == ",":
                i += 1
    if text[i] in "\"'":
        return _js_string(text, i)
    raise ValueError(f"expected a string or an object at {i}: {text[i : i + 40]!r}")


def _js_string(text, i):
    quote, i, out = text[i], i + 1, []
    escapes = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}
    while text[i] != quote:
        if text[i] == "\\":
            kind = text[i + 1]
            if kind == "u":
                out.append(chr(int(text[i + 2 : i + 6], 16)))
                i += 6
            elif kind == "x":
                out.append(chr(int(text[i + 2 : i + 4], 16)))
                i += 4
            else:
                out.append(escapes.get(kind, kind))
                i += 2
        else:
            out.append(text[i])
            i += 1
    return "".join(out), i + 1


def _skip_space(text, i):
    while text[i].isspace():
        i += 1
    return i


def _find(text, needle):
    position = text.find(needle)
    if position < 0:
        raise UnexpectedResponse(f"the labels chunk has no {needle!r}")
    return position


def _strip_tags(html):
    return re.sub(r"<[^>]+>", "", html).strip()


def _courts(response):
    courts = _json(response, 200)
    if not isinstance(courts, list) or not all({"nazev", "kod"} <= set(court) for court in courts):
        raise UnexpectedResponse(f"not a court list: {response.text[:200]}")
    return courts
