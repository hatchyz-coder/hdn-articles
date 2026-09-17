#!/usr/bin/env python3
"""Fail-closed completion state machine for canonical and social publication."""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class State(IntEnum):
    GENERATED = 1
    CANONICAL_COMMITTED = 2
    CANONICAL_LIVE = 3
    SOCIAL_SCHEDULED = 4
    SOCIAL_LIVE = 5


@dataclass(frozen=True)
class Evidence:
    jp_exists: bool = False
    en_exists: bool = False
    canonical_live: bool = False
    social_provider_id: str = ""
    social_status: str = ""
    social_live_evidence: bool = False
    social_evidence_source: str = ""
    duplicate_free: bool = False
    facebook_chars: int = 0


def resolve_state(e: Evidence) -> State:
    if not e.jp_exists:
        return State.GENERATED
    if not e.en_exists:
        return State.CANONICAL_COMMITTED
    if not e.canonical_live:
        return State.CANONICAL_COMMITTED
    if not e.social_provider_id:
        return State.CANONICAL_LIVE
    if e.social_status.upper() not in {"PUBLISHED", "LIVE"}:
        return State.SOCIAL_SCHEDULED
    if not e.social_live_evidence:
        return State.SOCIAL_SCHEDULED
    if e.social_evidence_source not in {"direct_network", "provider_published_retrieval"}:
        return State.SOCIAL_SCHEDULED
    if not e.duplicate_free:
        return State.SOCIAL_SCHEDULED
    return State.SOCIAL_LIVE


def facebook_copy_valid(chars: int, explicit_exception: bool = False) -> bool:
    return explicit_exception or 1200 <= chars <= 1500


def may_claim_canonical_published(e: Evidence) -> bool:
    return resolve_state(e) >= State.CANONICAL_LIVE


def may_claim_social_published(e: Evidence) -> bool:
    return resolve_state(e) == State.SOCIAL_LIVE


def completion_label(e: Evidence) -> str:
    state = resolve_state(e)
    return {
        State.GENERATED: "GENERATED",
        State.CANONICAL_COMMITTED: "CANONICAL_COMMITTED",
        State.CANONICAL_LIVE: "CANONICAL_LIVE",
        State.SOCIAL_SCHEDULED: "SOCIAL_SCHEDULED",
        State.SOCIAL_LIVE: "COMPLETED",
    }[state]
