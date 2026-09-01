"""Why a camera is plausibly where it is, in a few sentences.

Claude writes each explanation once, from the facts the cameras table
already holds; the text is cached on the row and every later request is a
plain read. No key configured means the canned mock answers, same rule as
the other sources.

The prompt is deliberately fenced in: the model gets only verified fields
and general knowledge of how ALPR and speed cameras are deployed, and is
told to hedge rather than invent. An explanation that fabricates a school
or a crash statistic is worse than none.
"""

from concurrent.futures import ThreadPoolExecutor

from app import config, db, mock_data

# More width than this hammers the Anthropic API for a burst that is
# usually a handful of cameras anyway.
_MAX_CONCURRENT = 4

_SYSTEM = (
    "The app already shows this camera's usefulness score and its factor "
    "data as structured rows. You add ONE plain sentence, 20 words max, "
    "reading what the factors show together - repeat no numbers and no "
    "sources; the rows carry those. Examples of register: 'Among the "
    "lowest-scoring cameras in the data: modest local crime in one of "
    "the area's wealthiest tracts.' or 'The local crime and arrest "
    "figures here are among the highest recorded near any camera.' When "
    "there is no score, say the camera cannot be evaluated from public "
    "data, and you may add AT MOST one background fact: feed sharing "
    "for a commercial operator (describe them with the words the sheet "
    "gives, e.g. 'a shopping-mall landlord - not law enforcement'), the "
    "audit finding otherwise. Missing data is NOT zero: never claim low "
    "or no crime when no figure is given. Stay descriptive - no words "
    "like 'troubling', no advice, no questions, nothing beyond the fact "
    "sheet and background block, never an operator not in the facts. "
    "Plain prose, shown as-is in the app."
)

# Sourced, static context the note may cite verbatim. These are the two
# documented facts that make an otherwise unremarkable Flock camera worth
# a sentence, and the model is not allowed anything beyond them.
_BACKGROUND = (
    "Background facts, citable with these attributions:\n"
    "- Analyses of published Flock audit logs (Institute for Justice; "
    "404 Media, 2024-2025) found the overwhelming majority of plate "
    "scans are never linked to any investigation.\n"
    "- Flock retains scanned plates (typically 30 days) and private "
    "operators - retailers, property managers, HOAs - can share their "
    "camera feeds into police-searchable networks."
)


class ExplainError(Exception):
    """Anthropic is down, out of quota, or refused every request."""


class NeedsKeyError(Exception):
    """This install's free generations are spent and no user key came
    with the request. Cached explanations are still served before this
    is ever raised - only NEW generations are gated."""


class BadUserKeyError(Exception):
    """The Anthropic key the user supplied was rejected outright."""


def explanations_for(
    camera_ids: list[int], user_key: str = "", install_id: str = ""
) -> dict[int, str]:
    """Explanations keyed by camera id.

    Ids that are unknown, inactive, or whose generation failed are simply
    absent - one bad camera must not cost the driver the rest of the list.
    ExplainError only when nothing could be generated at all.

    Cached rows are always served; they cost nothing. Generating a new
    explanation bills someone: the user's own key when the request brings
    one, otherwise the server's key while the install's free allowance
    lasts (NeedsKeyError after that).
    """
    if config.USE_MOCK_EXPLAIN:
        return mock_data.camera_explanations(camera_ids)

    rows = db.fetch_cameras_for_explain(camera_ids)
    results = {row[0]: row[17] for row in rows if row[17]}
    missing = [row for row in rows if not row[17]]
    if not missing:
        return results

    api_key = user_key or _claim_server_key(install_id)

    import anthropic

    with ThreadPoolExecutor(max_workers=_MAX_CONCURRENT) as pool:
        try:
            generated = list(
                pool.map(lambda row: _generate_one(row, api_key), missing)
            )
        except anthropic.AuthenticationError:
            if user_key:
                raise BadUserKeyError()
            raise ExplainError("the server's Anthropic key was rejected")

    failures = 0
    for row, text in zip(missing, generated):
        if text is None:
            failures += 1
            continue
        results[row[0]] = text
        db.save_explanation(row[0], text)

    if failures and not results:
        raise ExplainError("every generation failed")
    return results


def _claim_server_key(install_id: str) -> str:
    """The server's key, if this install still has free generations.

    No install id means no way to count, which means no free tier: the
    app always sends one, so a request without it is not the app.
    """
    if not install_id or not db.claim_free_explain_use(
        install_id, config.FREE_EXPLAIN_BATCHES
    ):
        raise NeedsKeyError()
    return config.ANTHROPIC_API_KEY


def _generate_one(row: tuple, api_key: str) -> str | None:
    """One Claude call. None on failure, so the batch can go on without
    it - except a rejected key, which no retry in this batch will fix."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key, timeout=config.EXPLAIN_TIMEOUT_S)
    try:
        response = client.messages.create(
            model=config.EXPLAIN_MODEL,
            # Room to finish every sentence without truncating a citation;
            # the word cap lives in the prompt.
            max_tokens=250,
            system=_SYSTEM,
            messages=[
                {"role": "user", "content": _facts(row) + "\n\n" + _BACKGROUND}
            ],
        )
    except anthropic.AuthenticationError:
        # A bad key fails the whole batch identically; let the caller
        # name the problem instead of eating it camera by camera.
        raise
    except anthropic.APIError:
        return None
    text = "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()
    # A note cut off by the token ceiling must not be served as-is: keep
    # whole sentences only, and treat a fragment with none as a failure.
    if response.stop_reason == "max_tokens":
        text = text[: text.rfind(".") + 1] if "." in text else ""
    return text or None


def _facts(row: tuple) -> str:
    """The row as Key: value lines. Unknown fields are omitted entirely,
    because a line saying "Operator: None" invites the model to fill it."""
    (_, ctype, facing_deg, operator, brand, road_name, road_ref,
     road_class, maxspeed, crime_count, crime_desc,
     tract_income, county_income, arrest_count, arrest_desc,
     usefulness_score, score_desc, _) = row

    lines = ["Camera type: " + (
        "fixed speed camera" if ctype == "speed_camera"
        else "license plate reader (ALPR)"
    )]
    if brand:
        lines.append(f"Brand: {brand}")
    if operator:
        lines.append(f"Operator: {operator}")
        if not _looks_governmental(operator):
            lines.append(
                f"Operator type: {_operator_kind(operator)} - not a "
                "law-enforcement agency"
            )
    if road_name or road_ref:
        road = road_name or road_ref
        ref = f" ({road_ref})" if road_name and road_ref else ""
        lines.append(f"Road it watches: {road}{ref}")
    if road_class:
        lines.append(f"Road class (OSM highway tag): {road_class}")
    if maxspeed:
        lines.append(f"Posted speed limit: {maxspeed}")
    # Public-records ground truth, when the enrichment job has run. This
    # is what lets the sentence say whether the placement matches the
    # local crime picture instead of assuming it does.
    if usefulness_score is not None and score_desc:
        lines.append(
            f"Computed usefulness score: {usefulness_score}/100 ({score_desc})"
        )
    if crime_count is not None and crime_desc:
        lines.append(f"Crime near this camera: {crime_count} {crime_desc}")
    if arrest_count is not None and arrest_desc:
        lines.append(f"Arrests: {arrest_count} {arrest_desc}")
    # Income near the county median is filler, not evidence, so it only
    # reaches the model when it diverges enough to say something.
    if (
        tract_income is not None
        and county_income
        and abs(tract_income - county_income) / county_income >= 0.20
    ):
        lines.append(
            f"Neighborhood median household income: {_dollars(tract_income)}"
            f" (county median {_dollars(county_income)}) - source: US Census ACS"
        )
    # No region line: the table spans states, and naming the wrong one
    # here made Claude confidently misplace a Delaware camera in Virginia.
    # The operator and road name carry the locale when anything does.
    return "\n".join(lines)


# What the recurring commercial operators in the table actually are, so
# a note can say "a shopping-mall landlord" instead of the bureaucratic
# "private/commercial operator". Substring match, lowercase.
_OPERATOR_KINDS = {
    "brookfield": "a shopping-mall landlord",
    "simon property": "a shopping-mall landlord",
    "lowe's": "a hardware retailer",
    "lowes": "a hardware retailer",
    "home depot": "a hardware retailer",
    "ted britt": "a car dealership",
    "homeowners": "a homeowners' association",
    "hoa": "a homeowners' association",
}


def _operator_kind(operator: str) -> str:
    lowered = operator.lower()
    for needle, kind in _OPERATOR_KINDS.items():
        if needle in lowered:
            return kind
    return "a private/commercial operator"


def _looks_governmental(operator: str) -> bool:
    """Police departments and towns write their names in recognizable
    shapes; anything else - Lowe's, a mall REIT, an HOA - is private."""
    needles = (
        "police", "sheriff", " pd", "pd)", "public safety", "patrol",
        "city of", "town of", "county", "department", "state", "federal",
    )
    lowered = f" {operator.lower()}"
    return any(needle in lowered for needle in needles)


def _dollars(income: int) -> str:
    """ACS top-codes high tracts as 250001, meaning "$250,000 or more"."""
    if income >= 250001:
        return "$250,000+"
    return f"${income:,}"


