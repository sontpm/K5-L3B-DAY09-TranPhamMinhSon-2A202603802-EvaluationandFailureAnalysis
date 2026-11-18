"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item
from lab9.graders import GRADERS


def _check_ratchet(spec: dict, base_spec: dict) -> list[str]:
    problems: list[str] = []
    pr_metrics = {m["id"]: m for m in (spec.get("metrics") or [])}
    for bm in base_spec.get("metrics") or []:
        mid = bm["id"]
        if mid not in pr_metrics:
            problems.append(f"ratchet: metric {mid} removed from spec")
            continue
        pm = pr_metrics[mid]
        if bm.get("blocking") and not pm.get("blocking"):
            problems.append(f"ratchet: blocking metric {mid} made non-blocking")
        bth, pth = bm.get("threshold") or {}, pm.get("threshold") or {}
        if "min" in bth and (pth.get("min") is None or pth["min"] < bth["min"]):
            problems.append(f"ratchet: metric {mid} min loosened ({pth.get('min')} < {bth['min']})")
        if "max" in bth and (pth.get("max") is None or pth["max"] > bth["max"]):
            problems.append(f"ratchet: metric {mid} max loosened ({pth.get('max')} > {bth['max']})")
        if "max_increase" in bth and (pth.get("max_increase") is None or pth["max_increase"] > bth["max_increase"]):
            problems.append(f"ratchet: metric {mid} max_increase loosened")
        if bth.get("no_significant_drop") and not pth.get("no_significant_drop"):
            problems.append(f"ratchet: metric {mid} dropped no_significant_drop")

    pr_slices = {(s["name"], s["metric"]): s for s in (spec.get("slices") or [])}
    for bs in base_spec.get("slices") or []:
        key = (bs["name"], bs["metric"])
        if key not in pr_slices:
            problems.append(f"ratchet: slice {bs['name']}/{bs['metric']} removed from spec")
            continue
        ps = pr_slices[key]
        if bs.get("blocking") and not ps.get("blocking"):
            problems.append(f"ratchet: blocking slice {bs['name']}/{bs['metric']} made non-blocking")
        if "min" in bs and (ps.get("min") is None or ps["min"] < bs["min"]):
            problems.append(f"ratchet: slice {bs['name']}/{bs['metric']} min loosened")
        if "max" in bs and (ps.get("max") is None or ps["max"] > bs["max"]):
            problems.append(f"ratchet: slice {bs['name']}/{bs['metric']} max loosened")
        if bs.get("no_significant_drop") and not ps.get("no_significant_drop"):
            problems.append(f"ratchet: slice {bs['name']}/{bs['metric']} dropped no_significant_drop")
    return problems


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted."""
    problems: list[str] = []
    for k, v in (pr.get("metrics") or {}).items():
        if isinstance(v, (int, float)) and not isinstance(v, bool) and not math.isfinite(v):
            problems.append(f"metric {k} is non-finite ({v})")

    manifest = pr.get("manifest") or {}
    rows = pr.get("rows") or []
    expected_n = int(manifest.get("items", 0)) * len(manifest.get("seeds") or [])
    if len(rows) != expected_n:
        problems.append(f"row count {len(rows)} != manifest {manifest.get('items')} x {len(manifest.get('seeds') or [])}")

    pr_keys_list = [(r.get("item_id"), r.get("seed")) for r in rows]
    if len(set(pr_keys_list)) != len(pr_keys_list):
        problems.append("duplicate (item_id, seed) rows in PR report")

    base_rows = base.get("rows") or []
    base_keys = {(r.get("item_id"), r.get("seed")) for r in base_rows}
    if set(pr_keys_list) != base_keys:
        problems.append("(item_id, seed) set in PR differs from baseline")

    if pr.get("evaluator_failures"):
        problems.append(f"{len(pr['evaluator_failures'])} evaluator failure(s) in PR")

    graded_ids = [
        m["id"]
        for m in (spec.get("metrics") or [])
        if m["id"] in GRADERS or (base_rows and m["id"] in base_rows[0])
    ]
    for r in rows:
        missing = [mid for mid in graded_ids if r.get(mid) is None]
        if missing:
            problems.append(f"row {r.get('item_id')}@{r.get('seed')} has None for graded metric(s) {missing}")
            break

    base_slices = {r.get("item_id"): tuple(sorted(r.get("slices") or [])) for r in base_rows}
    for r in rows:
        iid = r.get("item_id")
        pr_sl = tuple(sorted(r.get("slices") or []))
        if iid in base_slices and pr_sl != base_slices[iid]:
            problems.append(f"slice tags for {iid} differ from baseline ({list(pr_sl)} != {list(base_slices[iid])})")
            break

    if base_spec is not None:
        if spec.get("eval_set_version") == base_spec.get("eval_set_version"):
            problems.extend(_check_ratchet(spec, base_spec))
        elif (pr.get("manifest") or {}).get("eval_set_sha") == (base.get("manifest") or {}).get("eval_set_sha"):
            problems.append("ratchet: eval_set_version changed without changing eval_set_sha")

    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): per-slice floor and paired bootstrap check."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})
    for s in spec.get("slices") or []:
        name, mid = s["name"], s["metric"]
        a = per_item(pr, mid, slice_name=name)
        b = per_item(base, mid, slice_name=name)
        val = round(sum(a.values()) / len(a), 4) if a else None
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        else:
            if "min" in s and val < s["min"]:
                verdict = "fail"
            if "max" in s and val > s["max"]:
                verdict = "fail"
            if s.get("no_significant_drop"):
                keys = sorted(set(a) & set(b))
                if keys:
                    d, lo, hi = stats.paired_bootstrap(
                        [a[k] for k in keys],
                        [b[k] for k in keys],
                        n_resamples=bs.get("n_resamples", 1000),
                        rng=bs.get("rng", 2027),
                        confidence=bs.get("confidence", 0.95),
                    )
                    note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                    if hi < 0:
                        verdict = "fail"
        if verdict != "ok" and s.get("blocking"):
            blocked.append(f"slice:{name}/{mid}")
        th_view = {k: s[k] for k in ("min", "max", "no_significant_drop") if k in s}
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if s.get("blocking") else "warn")
        lines.append(f"  slice:{name}/{mid:<10} {val!s:<8} {json.dumps(th_view):<40} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
