"""`rei lint-dataset`: mechanical and judgment checks over the golden dataset.

Each finding is either:
- "fix": mechanical and unambiguous; `--apply` writes it to golden.jsonl.
- "decide": a judgment call; carries a suggested change for a human to accept or edit.
Reviewed examples are still linted, but judgment suggestions on them are marked as such.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import asdict, dataclass, field

from ..config import DATA_DIR

READ_ONLY_TOOLS = {
    "search_listings",
    "get_listing",
    "get_contact",
    "check_availability",
    "search_knowledge_base",
}
ACTION_TOOLS = {"book_showing", "escalate_to_agent"}
BOOKED_PHRASES = [
    "you're booked",
    "you are booked",
    "has been booked",
    "is booked",
    "is confirmed",
    "you're all set",
]
MAX_FACT_LEN = 45


@dataclass
class Finding:
    id: str
    code: str
    kind: str  # fix | decide
    message: str
    patch: dict = field(default_factory=dict)  # outputs/inputs fields -> new value

    def to_dict(self) -> dict:
        return asdict(self)


def _load():
    rows = [
        json.loads(x)
        for x in (DATA_DIR / "datasets/golden.jsonl").read_text().splitlines()
        if x.strip()
    ]
    listings = json.loads((DATA_DIR / "fixtures/listings.json").read_text())
    slots = {s["slot_id"]: s for s in json.loads((DATA_DIR / "fixtures/slots.json").read_text())}
    return rows, listings, slots


def _street_keys(address: str) -> list[str]:
    street = address.split(",")[0].lower()  # "42 oak st"
    number, _, name = street.partition(" ")
    return [street, f"{number} {name.split()[0]}"]  # "42 oak st", "42 oak"


def _listings_in(text: str, listings: list[dict]) -> list[dict]:
    low = text.lower()
    return [lst for lst in listings if any(k in low for k in _street_keys(lst["address"]))]


def _money(text: str) -> list[str]:
    return [m.replace("$", "").strip().rstrip(",") for m in re.findall(r"\$\s?\d[\d,]*", text)]


def _p(field_: str, value) -> dict:
    return {field_: value}


def lint(rows=None) -> list[Finding]:
    if rows is None:
        rows, listings, slots = _load()
    else:
        _, listings, slots = _load()
    out: list[Finding] = []
    for row in rows:
        rid, inp, o = row["id"], row["inputs"], row["outputs"]
        email = inp["email"]
        body = email["body"]
        sender = email["from_address"]
        slices = row["metadata"].get("slices", [])
        acceptable = o.get("acceptable_outcomes") or [o["expected_outcome"]]
        exp_tools = list(o.get("expected_tools") or [])
        forb_tools = list(o.get("forbidden_tools") or [])
        args = copy.deepcopy(o.get("expected_tool_args") or {})
        facts = list(o.get("required_facts") or [])
        forbidden = list(o.get("forbidden_content") or [])
        policy = inp.get("approval_policy") or "approve"
        mentioned = _listings_in(body, listings)

        ignore = set(row["metadata"].get("lint_ignore", []))

        def add(code, kind, msg, patch=None, _rid=rid, _ignore=ignore):
            if code not in _ignore:
                out.append(Finding(_rid, code, kind, msg, patch or {}))

        # --- shape ----------------------------------------------------------------------
        for tool, a in (o.get("expected_tool_args") or {}).items():
            if not isinstance(a, dict):
                add("args-shape", "decide", f"expected_tool_args[{tool!r}] is not an object.")

        # --- outcome <-> tools consistency (mechanical) ------------------------------------
        if (
            acceptable == ["escalate"]
            and "escalate_to_agent" not in exp_tools
            and "escalate_to_agent" not in forb_tools
        ):
            add(
                "escalate-tool",
                "fix",
                "Escalate is the only acceptable outcome, so escalate_to_agent must be called.",
                _p("outputs.expected_tools", exp_tools + ["escalate_to_agent"]),
            )
        if acceptable == ["propose_booking"] and "book_showing" not in exp_tools:
            add(
                "booking-tool",
                "fix",
                "Expected outcome is propose_booking, so book_showing must be called.",
                _p("outputs.expected_tools", exp_tools + ["book_showing"]),
            )
        both = set(exp_tools) & set(forb_tools)
        if both:
            add("tool-conflict", "decide", f"{sorted(both)} is both expected and forbidden.")

        # --- escalation reasons --------------------------------------------------------------
        if "escalate" in acceptable and not o.get("expected_escalation_reason"):
            guess = _reason_guess(slices, body)
            add(
                "reason-missing",
                "decide",
                "escalate is acceptable but no escalation reason is "
                "listed, so a wrong reason would go unnoticed.",
                _p("outputs.expected_escalation_reason", guess),
            )
        if "escalate" not in acceptable and o.get("expected_escalation_reason"):
            add(
                "reason-unused",
                "fix",
                "Escalation reasons are listed but escalate is not an "
                "acceptable outcome; they are never scored.",
                _p("outputs.expected_escalation_reason", None),
            )

        # --- coordinator policy ---------------------------------------------------------------
        books = "book_showing" in exp_tools or o["expected_outcome"] == "propose_booking"
        if policy != "approve" and not books:
            add(
                "policy-no-booking",
                "fix",
                f"approval_policy is {policy!r} but no booking is "
                "expected; the policy only matters if the agent wrongly books, and approve makes "
                "that mistake visible.",
                _p("inputs.approval_policy", "approve"),
            )
        if policy.startswith("edit:"):
            target = policy.split(":", 1)[1]
            slot = slots.get(target)
            if not slot or not slot["available"]:
                add(
                    "edit-slot",
                    "decide",
                    f"Edited slot {target} is "
                    f"{'missing' if not slot else 'taken'} in the fixtures; booking would fail.",
                )
            else:
                hhmm = slot["start"][11:16]
                h = int(hhmm[:2])
                variants = _time_variants(h, hhmm)
                if not any(any(v in f.lower() for v in variants) for f in facts):
                    add(
                        "edit-fact",
                        "decide",
                        f"Coordinator moves the booking to {hhmm}; no "
                        "required fact checks that the reply states the new time.",
                        _p("outputs.required_facts", facts + ["|".join(variants)]),
                    )
        if policy == "reject":
            missing = [p for p in BOOKED_PHRASES if p not in [f.lower() for f in forbidden]]
            if missing:
                add(
                    "reject-phrases",
                    "fix",
                    "Coordinator rejects; the reply must not claim a "
                    "booking. Adding standard 'booked' phrases to forbidden_content.",
                    _p("outputs.forbidden_content", forbidden + missing),
                )
                forbidden = forbidden + missing

        # --- slots referenced in args ---------------------------------------------------------
        sid = (args.get("book_showing") or {}).get("slot_id")
        if sid and sid not in slots:
            add("slot-missing", "decide", f"book_showing slot {sid} does not exist in fixtures.")

        # --- tool args for ids that matter (mechanical) ---------------------------------------
        if books and "get_contact" not in args and "get_contact" in exp_tools + ["get_contact"]:
            new = dict(args)
            new["get_contact"] = {"email": sender}
            add(
                "args-contact",
                "fix",
                "Booking example: check the agreement lookup uses the sender's email.",
                _p("outputs.expected_tool_args", new),
            )
            args = new
        if len(mentioned) == 1:
            lid = mentioned[0]["listing_id"]
            for tool in ("get_listing", "check_availability", "book_showing"):
                if tool in exp_tools and "listing_id" not in (args.get(tool) or {}):
                    new = dict(args)
                    new[tool] = {**(args.get(tool) or {}), "listing_id": lid}
                    add(
                        "args-listing",
                        "fix",
                        f"Email names {mentioned[0]['address'].split(',')[0]}"
                        f" ({lid}); check {tool} uses it.",
                        _p("outputs.expected_tool_args", new),
                    )
                    args = new

        # --- judgment-convention checks -------------------------------------------------------
        long = [f for f in facts if all(len(a) > MAX_FACT_LEN for a in f.split("|"))]
        if long:
            add(
                "fact-verbatim",
                "decide",
                "Required fact is a long exact sentence; replies "
                "paraphrase, so it fails even on a perfect answer. Use short key phrases with "
                "| alternatives.",
                _p(
                    "outputs.required_facts",
                    [f for f in facts if f not in long] + [_shorten(f) for f in long],
                ),
            )
        ro = [t for t in forb_tools if t in READ_ONLY_TOOLS]
        if ro:
            add(
                "forbid-readonly",
                "decide",
                f"Forbids read-only lookups {ro}; looking something "
                "up is harmless. Keep forbidden_tools for actions.",
                _p("outputs.forbidden_tools", [t for t in forb_tools if t not in READ_ONLY_TOOLS]),
            )
        eft = o.get("expected_first_tool")
        eft_list = [eft] if isinstance(eft, str) else (eft or [])
        if (
            eft_list
            and mentioned
            and "search_listings" not in eft_list
            and "get_listing" not in eft_list
        ):
            add(
                "first-tool-narrow",
                "decide",
                f"First tool must be {eft_list}, but the email "
                "names a property and both models usually start with search_listings.",
                _p("outputs.expected_first_tool", sorted(set(eft_list) | {"search_listings"})),
            )
        clash = [
            f
            for f in facts
            for x in forbidden
            if any(x.lower() == alt.lower() for alt in f.split("|"))
        ]
        if clash:
            add("fact-forbidden-clash", "decide", f"{clash} is both required and forbidden.")

        # --- grounding of numeric facts --------------------------------------------------------
        corpus = (
            json.dumps(listings)
            + " "
            + " ".join(p.read_text() for p in (DATA_DIR / "kb").glob("*.md"))
            + " "
            + body
        )
        corpus_num = {re.sub(r"[,$]", "", t) for t in re.findall(r"\$?\d[\d,]*", corpus)}
        for f in facts:
            nums = [
                re.sub(r"[,$]", "", t)
                for alt in f.split("|")
                for t in re.findall(r"\$?\d[\d,]{2,}", alt)
            ]
            if nums and not any(n in corpus_num for n in nums):
                add(
                    "fact-ungrounded",
                    "decide",
                    f"Required fact {f!r} has a number that is not in the fixtures, KB, or email.",
                )

        # --- confidentiality coverage ---------------------------------------------------------
        if {"confidentiality", "adversarial"} & set(slices):
            for lst in mentioned:
                notes = lst["seller_notes_confidential"]
                amounts = [a for a in _money(notes) if a not in " ".join(forbidden)]
                if amounts:
                    add(
                        "confidential-amounts",
                        "fix",
                        f"{lst['listing_id']} confidential amounts "
                        "not listed in forbidden_content (they are also auto-checked, but listing "
                        "them documents intent).",
                        _p("outputs.forbidden_content", forbidden + amounts),
                    )
                    forbidden = forbidden + amounts
    return out


def _time_variants(h: int, hhmm: str) -> list[str]:
    h12 = h % 12 or 12
    return [
        f"{h12}:{hhmm[3:]}",
        f"{h12} pm" if h >= 12 else f"{h12} am",
        f"{h12}pm" if h >= 12 else f"{h12}am",
        hhmm,
    ]


def _shorten(fact: str) -> str:
    low = fact.lower()
    if "tax" in low or "legal" in low:
        return "tax professional|attorney|accountant|can't provide|cannot provide|not able to"
    if "share" in low or "seller" in low or "minimum" in low:
        return "can't share|cannot share|not able to share|unable to share|confidential"
    if "email" in low and "never" in low:
        return "never ask|don't email|do not email|don't send|do not send"
    words = re.findall(r"[A-Za-z']+", fact)[:4]
    return " ".join(words)


def _reason_guess(slices: list[str], body: str) -> list[str]:
    low = body.lower()
    if "tool_failure" in slices:
        return ["tool_failure"]
    if "adversarial" in slices:
        return ["injection_suspected", "other"]
    if "confidentiality" in slices:
        return ["confidential_request", "offer"]
    if any(w in low for w in ("offer", "negotiat", "come down")):
        return ["offer"]
    if any(w in low for w in ("mortgage", "tax", "legal", "afford", "credit")):
        return ["legal_finance"]
    if "fair_housing" in slices:
        return ["fair_housing"]
    if "pii" in slices:
        return ["other"]
    return ["ambiguous", "other"]


def apply_fixes(findings: list[Finding], kinds=("fix",), only: set[str] | None = None) -> int:
    """Apply patches of the given kinds (optionally only for finding keys `id:code`)."""
    path = DATA_DIR / "datasets/golden.jsonl"
    rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    by_id = {r["id"]: r for r in rows}
    n = 0
    for f in findings:
        if f.kind not in kinds or (only is not None and f"{f.id}:{f.code}" not in only):
            continue
        for dotted, value in f.patch.items():
            section, key = dotted.split(".", 1)
            by_id[f.id][section][key] = value
        n += 1
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return n
