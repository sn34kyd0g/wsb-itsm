# ai-generated: 90% - Claude wrote it from CI-SPEC.md section 3 and tested it on the practice set and on edge-case fixtures; I read it, ran it and own it
"""bakeoff.py - scanner SARIF + a labels file -> a per-tool confusion matrix (CI-SPEC.md P-23).

    python3 bakeoff.py --labels labels.json a.sarif b.sarif > bakeoff.json
    python3 bakeoff.py --labels labels.json bakeoff/sarif/*.sarif --output bakeoff.json

Standard library only: it runs as `python3 -S -E bakeoff.py`. Rule ids (P-nn) are those of CI-SPEC.md.
`--output` writes UTF-8 without a BOM, which a plain `>` in Windows PowerShell 5.1 does not (it writes UTF-16).
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from urllib.parse import unquote

# P-19: the ten course classes and the CWE numbers of each.
CLASS_CWES = {
    "secret": (259, 260, 321, 798),
    "injection": (74, 77, 78, 79, 80, 88, 89, 90, 91, 94, 95, 96, 611, 776, 917, 943, 1336),
    "deserialization": (502,),
    "weak-crypto": (261, 326, 327, 328, 330, 331, 338, 759, 760, 916),
    "insecure-transport": (295, 297, 319, 322, 757),
    "path-traversal": (22, 23, 35, 36, 73),
    "ssrf": (918,),
    "vulnerable-dependency": (937, 1035, 1104, 1395),
    "misconfiguration": (16, 215, 250, 489, 668, 732, 1188),
    "access-control": (284, 285, 639, 862, 863),
}
CLASSES = frozenset(CLASS_CWES)
# keyed by the decimal text, so a huge run of digits never goes through int()
CWE_CLASS = {str(n): cls for cls, numbers in CLASS_CWES.items() for n in numbers}

# P-15
FIXED_TOOLS = frozenset({"trivy", "grype", "osv-scanner", "gitleaks"})
SEMGREP_NAMES = frozenset({"semgrep", "semgrep oss", "semgrep ce", "semgrep community edition", "semgrep pro"})

# P-19 (c): `CWE-<n>`, CWE in any case, not preceded by an ASCII letter or digit, <n> the whole run of ASCII digits.
CWE_RE = re.compile(r"(?<![A-Za-z0-9])[Cc][Ww][Ee]-([0-9]+)")
# P-20: a token is a maximal run of A-Z a-z 0-9 . _ -  (its dots, underscores and hyphens at both ends are dropped).
TOKEN_RE = re.compile(r"[A-Za-z0-9._-]+")
PEP503_RE = re.compile(r"[-_.]+")


def tool_id(run: dict) -> str:
    """P-15: the tool id of a run, from tool.driver.name."""
    tool = run.get("tool")
    driver = tool.get("driver") if isinstance(tool, dict) else None
    name = driver.get("name") if isinstance(driver, dict) else None
    if not isinstance(name, str):
        return "unknown"
    lowered = name.strip().lower()
    if lowered in FIXED_TOOLS:
        return lowered
    if lowered in SEMGREP_NAMES:
        return "semgrep"
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-") or "unknown"


def first_location(result: dict):
    """P-16: (physicalLocation, uri) of the FIRST location, or None when the result is ignored."""
    locations = result.get("locations")
    if not isinstance(locations, list) or not locations:
        return None
    first = locations[0]
    physical = first.get("physicalLocation") if isinstance(first, dict) else None
    artifact = physical.get("artifactLocation") if isinstance(physical, dict) else None
    uri = artifact.get("uri") if isinstance(artifact, dict) else None
    if not isinstance(uri, str) or uri == "":
        return None
    return physical, uri


def file_in_set(uri: str, root: str):
    """P-17: the file of a result inside the set (from the LAST component equal to the root), else None."""
    path = unquote(uri)
    if path[:7].lower() == "file://":
        path = path[7:]
    if path.startswith("./"):
        path = path[2:]
    parts = path.split("/")
    for i in range(len(parts) - 1, -1, -1):
        if parts[i] == root:
            return "/".join(parts[i:])
    return None


def lines_of(physical: dict):
    """P-18: (start, end), or None when the result has no lines."""
    region = physical.get("region")
    if not isinstance(region, dict):
        return None
    start = region.get("startLine")
    if type(start) is not int or start < 1:  # not a bool, not 7.0, not "7"
        return None
    end = region.get("endLine")
    if type(end) is not int or end < start:
        end = start
    return start, end


def string_tags(obj) -> list[str]:
    """The string entries of obj.properties.tags (obj is a result or a rule)."""
    properties = obj.get("properties") if isinstance(obj, dict) else None
    tags = properties.get("tags") if isinstance(properties, dict) else None
    if not isinstance(tags, list):
        return []
    return [tag for tag in tags if isinstance(tag, str)]


def classes_of(tool: str, result: dict, rule) -> set[str]:
    """P-19: the classes of a result - the first of (a) properties.class, (b) by tool, (c) CWE tags, (d) other."""
    properties = result.get("properties")
    own = properties.get("class") if isinstance(properties, dict) else None
    if isinstance(own, str) and own in CLASSES:  # (a)
        return {own}
    if tool == "gitleaks":  # (b)
        return {"secret"}
    if tool in ("grype", "osv-scanner"):
        return {"vulnerable-dependency"}
    if tool == "trivy":
        found = set()
        for tag in string_tags(rule):
            lowered = tag.lower()
            if lowered == "vulnerability":
                found.add("vulnerable-dependency")
            elif lowered == "secret":
                found.add("secret")
            elif lowered == "misconfiguration":
                found.add("misconfiguration")
        if found:
            return found
    found = set()  # (c)
    for tag in string_tags(result) + string_tags(rule):
        for match in CWE_RE.finditer(tag):
            cls = CWE_CLASS.get(match.group(1).lstrip("0") or "0")
            if cls:
                found.add(cls)
    return found or {"other"}  # (d)


def pep503(text: str) -> str:
    return PEP503_RE.sub("-", text.lower())


def names_package(result: dict, package) -> bool:
    """P-20: some token of message.text equals the package name (PEP 503)."""
    message = result.get("message")
    text = message.get("text") if isinstance(message, dict) else None
    if not isinstance(text, str) or not isinstance(package, str):
        return False
    wanted = pep503(package)
    for token in TOKEN_RE.findall(text):
        token = token.strip("._-")
        if token and pep503(token) == wanted:
            return True
    return False


def matches(defect: dict, file: str, classes: set[str], lines, result: dict) -> bool:
    """P-20: does this result (in the set) match this defect?"""
    if not isinstance(defect, dict) or defect.get("file") != file:
        return False
    cls = defect.get("class")
    if cls not in classes:
        return False
    if cls == "vulnerable-dependency":
        return names_package(result, defect.get("package"))  # lines are not compared
    if lines is None:
        return False
    start, end = lines
    d_start, d_end = defect.get("start_line"), defect.get("end_line")
    if type(d_start) is not int or type(d_end) is not int:
        return False
    return start <= d_end and d_start <= end


def ratio(numerator: int, denominator: int):
    return None if denominator == 0 else round(numerator / denominator, 4)


def confusion_matrix(labels: dict, sarif_documents: list) -> dict:
    """The matrix of P-21 and P-22 for the labels (P-14) and the parsed SARIF documents."""
    root = labels["set"]
    defects = labels["defects"]
    found: dict[str, dict] = {}  # tool id -> {"hit": defect indexes, "fp": distinct FP keys}
    for document in sarif_documents:
        runs = document.get("runs") if isinstance(document, dict) else None
        if not isinstance(runs, list):
            continue
        for run in runs:
            if not isinstance(run, dict):
                continue
            tool = tool_id(run)
            entry = found.setdefault(tool, {"hit": set(), "fp": set()})
            driver = run["tool"]["driver"] if isinstance(run.get("tool"), dict) and isinstance(run["tool"].get("driver"), dict) else {}
            rules = driver.get("rules")
            first_rule: dict = {}
            if isinstance(rules, list):  # P-19: the FIRST rule with that id; ruleIndex is never read
                for rule in rules:
                    if isinstance(rule, dict) and isinstance(rule.get("id"), str):
                        first_rule.setdefault(rule["id"], rule)
            results = run.get("results")
            if not isinstance(results, list):
                continue
            for result in results:
                if not isinstance(result, dict):  # P-16
                    continue
                kind = result.get("kind")
                if kind is not None and kind != "fail":
                    continue
                if result.get("suppressions"):  # absent, null, [], {}, false, 0 and "" are empty
                    continue
                located = first_location(result)
                if located is None:
                    continue
                physical, uri = located
                file = file_in_set(uri, root)
                if file is None:  # outside the set: triage material, not part of the matrix
                    continue
                lines = lines_of(physical)
                rule_id = result.get("ruleId")
                rule_id = rule_id if isinstance(rule_id, str) else None
                classes = classes_of(tool, result, first_rule.get(rule_id) if rule_id is not None else None)
                hit = {i for i, defect in enumerate(defects) if matches(defect, file, classes, lines, result)}
                if hit:
                    entry["hit"] |= hit
                else:  # P-21: distinct (ruleId, file, start line, end line)
                    entry["fp"].add((rule_id, file, lines[0] if lines else None, lines[1] if lines else None))
    tools = {}
    for tool in sorted(found):
        tp = len(found[tool]["hit"])
        fp = len(found[tool]["fp"])
        fn = len(defects) - tp
        tools[tool] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": ratio(tp, tp + fp),
            "recall": ratio(tp, tp + fn),
            "f1": ratio(2 * tp, 2 * tp + fp + fn),  # from the counts, never from rounded scores
        }
    return {"set": labels["set"], "defects": len(defects), "tools": tools}


def expand(paths: list[str]) -> list[str]:
    """Windows PowerShell does not expand `*` for a native program: do it here when a path does not exist."""
    out: list[str] = []
    for path in paths:
        if any(ch in path for ch in "*?[") and not glob.glob(glob.escape(path)):
            matched = sorted(glob.glob(path))
            if not matched:
                raise FileNotFoundError(f"no file matches {path}")
            out.extend(matched)
        else:
            out.append(path)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="per-tool confusion matrix of SARIF against labels (CI-SPEC.md P-23)")
    parser.add_argument("--labels", required=True, help="the labels file (P-14)")
    parser.add_argument("-o", "--output", help="write the matrix to this file (UTF-8) instead of stdout")
    parser.add_argument("sarif", nargs="+", help="SARIF 2.1.0 files")
    args = parser.parse_args(argv)
    with open(args.labels, encoding="utf-8-sig") as fh:
        labels = json.load(fh)
    documents = []
    for path in expand(args.sarif):
        with open(path, encoding="utf-8-sig") as fh:
            documents.append(json.load(fh))
    text = json.dumps(confusion_matrix(labels, documents), indent=2) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
