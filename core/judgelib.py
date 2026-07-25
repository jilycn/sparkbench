"""Snapshot-local answer parsing shared by SparkBench judges.

Judges grade from the transcript on disk rather than from a runner-reported
parse, so that a bug in a runner cannot inflate a score. That makes parsing
correctness load-bearing here: a defect in this module is indistinguishable,
in the scorecard, from a model deficiency.

Suite 2.2 shipped a parser that accepted a final answer object only when the
whole object fitted on the last physical line. Models that pretty-printed an
otherwise compliant answer were graded wrong. The contract the phase system
prompts actually state is that the answer object is TERMINAL, meaning nothing
may follow it, which is what `terminal_answer` enforces. See CHANGELOG 2.2.1.

Parsing never collapses distinct failures into a bare `None`. Every result
carries an envelope category so the judges can report why an answer was not
graded, and so that format compliance can be measured as itself instead of
being charged silently against a reasoning axis.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

#: Envelope categories, ordered from most to least compliant.
#: Only the first two satisfy the terminal-answer contract and are graded.
ENVELOPES: tuple[str, ...] = (
    "strict_single_line",
    "multiline_terminal",
    "fenced_terminal",
    "trailing_content",
    "non_dict_json",
    "no_json",
    "missing_transcript",
)

#: Envelopes that satisfy the contract. Widening this set is a scoring-policy
#: change, not a parser repair, and must ship with its own suite version note.
GRADABLE_ENVELOPES: frozenset[str] = frozenset({"strict_single_line", "multiline_terminal"})

#: Categories that describe a broken or absent transcript rather than a model
#: formatting choice. Reported separately so they cannot be read as a model
#: compliance failure.
TRANSPORT_ENVELOPES: frozenset[str] = frozenset({"missing_transcript"})

_DECODER = json.JSONDecoder()

# A closing code fence, optionally tagged, at the very end of a reply.
_TRAILING_FENCE = re.compile(r"\n?[ \t]*```[a-zA-Z0-9_+-]*[ \t]*\Z")


@dataclass(frozen=True)
class ParsedAnswer:
    """One transcript's answer, with the reason it is or is not gradable.

    Attributes:
        value: The decoded JSON value when one was found, else None. Populated
            even for non-gradable envelopes so judges can report what the model
            actually produced, but never used for scoring unless `is_gradable`.
        envelope: One of `ENVELOPES`.
        detail: Human-readable explanation, empty when the answer is compliant.
    """

    value: object | None
    envelope: str
    detail: str = ""

    @property
    def is_gradable(self) -> bool:
        """True when the answer met the terminal-object contract."""
        return self.envelope in GRADABLE_ENVELOPES and isinstance(self.value, dict)

    @property
    def graded_value(self) -> dict | None:
        """The answer object to score, or None when the contract was not met."""
        return self.value if self.is_gradable else None


def _candidate_starts(text: str):
    """Yield ascending indices where a JSON value could begin.

    Ascending order matters: for a nested object only the outermost start can
    consume through the end of the text, so the first accepted candidate is the
    outermost object rather than an inner fragment.
    """
    for index, char in enumerate(text):
        if char in "{[":
            yield index
        elif char not in " \t\r\n" and (index == 0 or text[index - 1] == "\n"):
            yield index


def _terminal_json(text: str) -> tuple[object, int] | None:
    """Decode the JSON value that ends exactly at the end of `text`.

    Requiring the decode to consume through the final character is what makes
    this quote-safe and non-exploitable: braces inside string literals cannot
    fake a match, and an earlier object followed by further content can never
    be selected over a later contradictory one.
    """
    end = len(text)
    for start in _candidate_starts(text):
        try:
            value, consumed = _DECODER.raw_decode(text, start)
        except ValueError:
            continue
        if consumed == end:
            return value, start
    return None


def _last_json_object(text: str) -> dict | None:
    """Return the last decodable object anywhere in `text`, for diagnostics.

    Never used for scoring. It exists so a non-compliant reply can be reported
    as "answered, but with content after the object" instead of "no answer".
    """
    best: dict | None = None
    best_end = -1
    for start in _candidate_starts(text):
        try:
            value, consumed = _DECODER.raw_decode(text, start)
        except ValueError:
            continue
        if isinstance(value, dict) and consumed > best_end:
            best, best_end = value, consumed
    return best


def terminal_answer(text: str) -> ParsedAnswer:
    """Classify a transcript against the terminal-answer contract."""
    stripped = text.rstrip()
    if not stripped:
        return ParsedAnswer(None, "no_json", "transcript is empty")

    found = _terminal_json(stripped)
    if found is not None:
        value, start = found
        if not isinstance(value, dict):
            return ParsedAnswer(
                value, "non_dict_json",
                f"terminal JSON is {type(value).__name__}, expected an object",
            )
        multiline = "\n" in stripped[start:]
        return ParsedAnswer(value, "multiline_terminal" if multiline else "strict_single_line")

    unfenced = _TRAILING_FENCE.sub("", stripped).rstrip()
    if unfenced != stripped:
        fenced = _terminal_json(unfenced)
        if fenced is not None and isinstance(fenced[0], dict):
            return ParsedAnswer(
                fenced[0], "fenced_terminal",
                "answer object is followed by a closing code fence",
            )

    anywhere = _last_json_object(stripped)
    if anywhere is not None:
        return ParsedAnswer(anywhere, "trailing_content", "content follows the answer object")
    return ParsedAnswer(None, "no_json", "no JSON object found in transcript")


def final_json_object(text: str) -> dict | None:
    """Answer object when the transcript met the contract, else None."""
    return terminal_answer(text).graded_value


def normalized_equal(actual, expected, *, casefold=False, numeric=False, tolerance=0.0) -> bool:
    if numeric:
        if not isinstance(actual, (int, float)) or isinstance(actual, bool):
            return False
        return abs(float(actual) - float(expected)) <= tolerance
    # Python treats True == 1, so a boolean and an integer would compare equal
    # in the scalar fallback below. Suites carry both (boolean logic answers,
    # integer assignment answers), so the types must agree before the values do.
    if isinstance(actual, bool) != isinstance(expected, bool):
        return False
    if isinstance(actual, str) and isinstance(expected, str):
        actual, expected = actual.strip(), expected.strip()
        if casefold:
            actual, expected = actual.casefold(), expected.casefold()
        return actual == expected
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(normalized_equal(a, b, casefold=casefold) for a, b in zip(actual, expected))
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(normalized_equal(actual[key], expected[key], casefold=casefold) for key in actual)
    return actual == expected


def raw_parsed_answer(run_dir: Path, record: dict) -> ParsedAnswer:
    """Parse one record's stored transcript, reporting why it is not gradable.

    `run_dir` is the trial directory that owns the `raw/` transcript folder.
    """
    request_id = record.get("request_id")
    if not request_id:
        return ParsedAnswer(None, "missing_transcript", "record has no request_id")
    path = run_dir / "raw" / f"{request_id}.txt"
    if not path.is_file():
        return ParsedAnswer(None, "missing_transcript", f"no transcript file for {request_id}")
    return terminal_answer(path.read_text())


def raw_answer(run_dir: Path, record: dict) -> dict | None:
    """Gradable answer object for one record, or None when the contract failed."""
    return raw_parsed_answer(run_dir, record).graded_value
