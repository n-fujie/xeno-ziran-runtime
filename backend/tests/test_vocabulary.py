"""Anti-regression: the runtime and shape layers carry no domain vocabulary (identifiers or string
literals). Docstrings may explain the rule, so they are exempt. Ported from ziran-xeno-simulator's
Layer-0 check."""

from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "xzr"
LAYERS = ("runtime", "shapes", "lod", "compare")
# domain-neutral modules of the experiment layer (the reasoning experiments legitimately use practice terms)
EXTRA = ("experiments/runs.py", "experiments/reduction.py", "experiments/reduction_rules.py")
FORBIDDEN = re.compile(
    r"(human|person|people|bank|market|institution|capital|societ|social|politic|agent|organi[sz]ation|"
    r"financ|econom|credit|nation|government|ideolog|citizen|\bleft\b|\bright\b|owner|worker|firm|"
    r"commit|entitle|brandom|wolfendale|responsib|claim)",
    re.IGNORECASE,
)


def _hits(path: Path) -> list[str]:
    out = []
    prev = None
    toks = tokenize.generate_tokens(io.StringIO(path.read_text()).readline)
    for tok in toks:
        if tok.type in (tokenize.COMMENT, tokenize.NL):
            continue
        is_doc = tok.type == tokenize.STRING and prev in (None, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT)
        if tok.type in (tokenize.NAME, tokenize.STRING) and not is_doc and FORBIDDEN.search(tok.string):
            out.append(f"{path.relative_to(ROOT)}:{tok.start[0]}: {tok.string[:60]}")
        if tok.type not in (tokenize.NL, tokenize.COMMENT):
            prev = tok.type
    return out


def test_core_layers_are_domain_neutral():
    files = [p for layer in LAYERS for p in sorted((ROOT / layer).glob("*.py"))] + [ROOT / f for f in EXTRA]
    bad = [h for p in files for h in _hits(p)]
    assert bad == [], "\n".join(bad)


def test_reasoning_terms_stay_out_of_the_core_even_in_docstrings():
    """Stricter for reasoning vocabulary: not even docstrings/comments of the core layers may use it."""
    words = re.compile(r"commitment|entitlement|brandom|wolfendale", re.IGNORECASE)
    bad = [f"{p.relative_to(ROOT)}" for layer in LAYERS for p in sorted((ROOT / layer).glob("*.py"))
           if words.search(p.read_text())]
    assert bad == [], bad


def test_scanner_would_catch_a_label(tmp_path):
    p = tmp_path / "x.py"
    p.write_text('"""doc mentions market freely."""\nmarket_share = 1\nlabel = "institution"\n')
    global ROOT
    old, ROOT = ROOT, tmp_path
    try:
        assert len(_hits(p)) == 2
    finally:
        ROOT = old
