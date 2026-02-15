"""Knowledge Foundry — Input Sanitization & Prompt Injection Detection.

Defence Layer 1 per phase-3.1 spec: length validation, regex injection detection,
typoglycemia normalisation, and entropy analysis for encoded payloads.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum

# ──────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────

MAX_QUERY_LENGTH = 10_000  # characters
MAX_PROMPT_TOKENS = 100_000  # approximate token limit
ENTROPY_THRESHOLD = 7.0  # Shannon entropy > this → suspicious

# ──────────────────────────────────────────────────────────────
# Injection Patterns  (from phase-3.1 spec §2.1)
# ──────────────────────────────────────────────────────────────

INJECTION_PATTERNS: list[tuple[str, str]] = [
    (r"ignore\s+(?:(?:previous|all|prior|above)\s*)+instructions?", "ignore_instructions"),
    (r"system\s*:\s*you\s+are", "system_role_override"),
    (r"<\|im_start\|>", "chat_ml_injection"),
    (r"<\|im_end\|>", "chat_ml_injection"),
    (r"forget\s+(everything|all)", "memory_wipe"),
    (r"disregard\s+(all|previous)", "disregard_instructions"),
    (r"new\s+instructions?", "new_instructions"),
    (r"override\s+instructions?", "override_instructions"),
    (r"you\s+are\s+now", "role_reassignment"),
    (r"act\s+as\s+(if|a|an)", "role_play"),
    (r"pretend\s+(you|to\s+be)", "impersonation"),
    (r"role\s*:\s*system", "system_role_injection"),
    (r"<system_instruction>", "xml_system_injection"),
    (r"</system_instruction>", "xml_system_injection"),
    (r"reveal\s+(your|the)\s+(system|instructions?|prompt)", "prompt_extraction"),
    (r"repeat\s+the\s+text\s+above", "prompt_extraction"),
    (r"print\s+your\s+system\s+prompt", "prompt_extraction"),
    (r"what\s+are\s+your\s+instructions", "prompt_extraction"),
    (r"translate\s+.*\s+to\s+base64", "encoding_attack"),
    (r"you\s+are\s+in\s+debug\s+mode", "debug_mode"),
]

# Compiled for performance
_COMPILED_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE), label)
    for pattern, label in INJECTION_PATTERNS
]

# ──────────────────────────────────────────────────────────────
# Leet-speak expansion table
# ──────────────────────────────────────────────────────────────

_LEET_MAP: dict[str, str] = {
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s",
    "7": "t", "8": "b", "@": "a", "$": "s", "!": "i",
}

# Unicode confusable → ASCII normalisation
_CONFUSABLES: dict[str, str] = {
    "\u0430": "a",  # Cyrillic а
    "\u0435": "e",  # Cyrillic е
    "\u043e": "o",  # Cyrillic о
    "\u0440": "p",  # Cyrillic р
    "\u0441": "c",  # Cyrillic с
    "\u0443": "y",  # Cyrillic у
    "\u0445": "x",  # Cyrillic х
    "\u0456": "i",  # Ukrainian і
    "\u0458": "j",  # Cyrillic ј
    "\u04bb": "h",  # Cyrillic һ
    "\u2010": "-",  # Hyphen
    "\u2011": "-",  # Non-breaking hyphen
    "\u2013": "-",  # En dash
    "\u2014": "-",  # Em dash
    "\u00a0": " ",  # NBSP
    "\u200b": "",   # Zero-width space
    "\u200c": "",   # Zero-width non-joiner
    "\u200d": "",   # Zero-width joiner
    "\ufeff": "",   # BOM
}


# ──────────────────────────────────────────────────────────────
# Result types
# ──────────────────────────────────────────────────────────────

class ThreatSeverity(str, Enum):
    """Severity levels for detected threats."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SanitizationAction(str, Enum):
    """Action to take on a threat."""
    BLOCK = "block"
    FLAG = "flag"
    ALLOW = "allow"


@dataclass
class ThreatDetection:
    """A single detected threat in user input."""
    pattern_label: str
    severity: ThreatSeverity
    action: SanitizationAction
    matched_text: str = ""
    detail: str = ""


@dataclass
class SanitizationResult:
    """Result of input sanitisation."""
    is_safe: bool
    action: SanitizationAction
    threats: list[ThreatDetection] = field(default_factory=list)
    normalized_text: str = ""


# ──────────────────────────────────────────────────────────────
# Text normalisation (typoglycemia defence)
# ──────────────────────────────────────────────────────────────

def remove_unicode_confusables(text: str) -> str:
    """Replace Unicode look-alike characters with ASCII equivalents."""
    result = []
    for ch in text:
        if ch in _CONFUSABLES:
            result.append(_CONFUSABLES[ch])
        else:
            # NFKD decomposition to strip accents
            decomposed = unicodedata.normalize("NFKD", ch)
            ascii_ch = decomposed.encode("ascii", "ignore").decode("ascii")
            result.append(ascii_ch if ascii_ch else ch)
    return "".join(result)


def expand_leet_speak(text: str) -> str:
    """Convert leet-speak characters to plain letters."""
    return "".join(_LEET_MAP.get(ch, ch) for ch in text)


def normalize_whitespace(text: str) -> str:
    """Collapse multiple whitespace chars into single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def normalize_text(text: str) -> str:
    """Full normalisation pipeline for obfuscation detection."""
    text = remove_unicode_confusables(text)
    text = expand_leet_speak(text)
    text = normalize_whitespace(text)
    return text.lower()


# ──────────────────────────────────────────────────────────────
# Entropy analysis
# ──────────────────────────────────────────────────────────────

def calculate_entropy(text: str) -> float:
    """Calculate Shannon entropy of a string.

    High entropy (> 7.0) indicates random/encoded content that may
    contain hidden payloads (e.g. base64-encoded instructions).
    """
    if not text:
        return 0.0
    freq = Counter(text)
    total = len(text)
    return -sum(
        (count / total) * math.log2(count / total)
        for count in freq.values()
    )


# ──────────────────────────────────────────────────────────────
# Core detection functions
# ──────────────────────────────────────────────────────────────

def detect_injection_patterns(text: str) -> list[ThreatDetection]:
    """Scan text for known prompt injection patterns."""
    threats = []
    for regex, label in _COMPILED_PATTERNS:
        match = regex.search(text)
        if match:
            threats.append(ThreatDetection(
                pattern_label=label,
                severity=ThreatSeverity.CRITICAL,
                action=SanitizationAction.BLOCK,
                matched_text=match.group(),
                detail=f"Injection pattern '{label}' detected",
            ))
    return threats


def detect_obfuscated_injection(text: str) -> list[ThreatDetection]:
    """Detect injection patterns hidden via typoglycemia / leet-speak."""
    normalized = normalize_text(text)
    threats = []
    for regex, label in _COMPILED_PATTERNS:
        match = regex.search(normalized)
        if match:
            threats.append(ThreatDetection(
                pattern_label=f"obfuscated_{label}",
                severity=ThreatSeverity.HIGH,
                action=SanitizationAction.BLOCK,
                matched_text=match.group(),
                detail=f"Obfuscated injection pattern '{label}' detected after normalisation",
            ))
    return threats


def detect_encoded_payload(text: str) -> list[ThreatDetection]:
    """Flag high-entropy text segments that may contain encoded payloads."""
    threats = []
    # Check overall entropy
    entropy = calculate_entropy(text)
    if entropy > ENTROPY_THRESHOLD:
        threats.append(ThreatDetection(
            pattern_label="high_entropy",
            severity=ThreatSeverity.MEDIUM,
            action=SanitizationAction.FLAG,
            detail=f"High entropy ({entropy:.2f}) suggests encoded payload",
        ))

    # Check for base64-like segments
    b64_pattern = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")
    for match in b64_pattern.finditer(text):
        threats.append(ThreatDetection(
            pattern_label="base64_segment",
            severity=ThreatSeverity.MEDIUM,
            action=SanitizationAction.FLAG,
            matched_text=match.group()[:50] + "...",
            detail="Possible base64-encoded content detected",
        ))
        break  # Report first only
    return threats


def validate_length(text: str) -> list[ThreatDetection]:
    """Validate input length constraints."""
    threats = []
    if len(text) > MAX_QUERY_LENGTH:
        threats.append(ThreatDetection(
            pattern_label="input_too_long",
            severity=ThreatSeverity.HIGH,
            action=SanitizationAction.BLOCK,
            detail=f"Input length {len(text)} exceeds maximum {MAX_QUERY_LENGTH}",
        ))
    return threats


# ──────────────────────────────────────────────────────────────
# Main public API
# ──────────────────────────────────────────────────────────────

def sanitize_input(text: str) -> SanitizationResult:
    """Run the full input sanitisation pipeline.

    Applies all defence layers:
    1. Length validation
    2. Direct injection pattern detection
    3. Obfuscated injection detection (typoglycemia)
    4. Encoded payload detection (entropy)

    Returns:
        SanitizationResult with aggregated threats and recommended action.
    """
    all_threats: list[ThreatDetection] = []

    # Layer 1: Length
    all_threats.extend(validate_length(text))

    # Layer 2: Direct injection
    all_threats.extend(detect_injection_patterns(text))

    # Layer 3: Obfuscated injection (only if no direct match, to avoid dupes)
    if not any(t.pattern_label.startswith("obfuscated_") is False
               and t.action == SanitizationAction.BLOCK for t in all_threats):
        obfuscated = detect_obfuscated_injection(text)
        # Deduplicate: only add obfuscated threats not already caught directly
        direct_labels = {t.pattern_label for t in all_threats}
        for t in obfuscated:
            base_label = t.pattern_label.removeprefix("obfuscated_")
            if base_label not in direct_labels:
                all_threats.append(t)

    # Layer 4: Entropy
    all_threats.extend(detect_encoded_payload(text))

    # Determine overall action
    if any(t.action == SanitizationAction.BLOCK for t in all_threats):
        action = SanitizationAction.BLOCK
    elif any(t.action == SanitizationAction.FLAG for t in all_threats):
        action = SanitizationAction.FLAG
    else:
        action = SanitizationAction.ALLOW

    return SanitizationResult(
        is_safe=(action == SanitizationAction.ALLOW),
        action=action,
        threats=all_threats,
        normalized_text=normalize_text(text),
    )
