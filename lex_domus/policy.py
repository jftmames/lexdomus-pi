"""Technical policy checks. Recorded approval is not verified legal approval."""
from datetime import date
from pathlib import Path
import re
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

import yaml


class PolicyError(ValueError):
    """A policy cannot authorize analysis; messages contain no file contents."""


class _UniqueLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        # Reject duplicate and merge keys rather than silently replacing rules.
        keys = [self.construct_object(key, deep=deep) for key, _ in node.value]
        if any(not isinstance(key, str) for key in keys) or len(keys) != len(set(keys)):
            raise PolicyError("Invalid policy keys")
        return super().construct_mapping(node, deep=deep)


def _fields(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise PolicyError("Invalid policy structure")


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _strings(value, *, empty=False):
    return (isinstance(value, list) and (empty or bool(value))
            and all(_text(item) for item in value) and len(value) == len(set(value)))


def _date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise PolicyError("Policy dates must be quoted ISO dates")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise PolicyError("Invalid policy date") from exc
    if parsed > date.today():
        raise PolicyError("Future policy reference or review date")
    return parsed


def validate_policy(policy: Any, jurisdiction: Optional[str] = None, *,
                    require_approved: bool = True) -> Dict[str, Any]:
    _fields(policy, ("schema_version", "policy_id", "revision", "jurisdiction",
                     "reference_date", "review", "sources"))
    if (type(policy["schema_version"]) is not int or policy["schema_version"] != 1
            or type(policy["revision"]) is not int or policy["revision"] < 1
            or not _text(policy["policy_id"]) or policy["jurisdiction"] != "ES"):
        raise PolicyError("Unsupported policy version or scope")
    if jurisdiction is not None and jurisdiction != policy["jurisdiction"]:
        raise PolicyError("Jurisdiction outside policy scope")
    reference_date = _date(policy["reference_date"])
    review = policy["review"]
    _fields(review, ("status", "reviewer", "reviewed_on", "record"))
    if review["status"] not in ("pending", "approved"):
        raise PolicyError("Invalid policy review status")
    approved = review["status"] == "approved"
    if approved:
        if not _text(review["reviewer"]) or not _text(review["record"]):
            raise PolicyError("Policy approval requires reviewer and record")
        if _date(review["reviewed_on"]) < reference_date:
            raise PolicyError("Policy review predates its reference date")
    elif any(review[key] is not None for key in ("reviewer", "reviewed_on", "record")):
        raise PolicyError("Pending policy must not claim approval")
    sources = policy["sources"]
    _fields(sources, ("allowed", "constraints"))
    if not _strings(sources["allowed"], empty=not approved):
        raise PolicyError("Invalid allowed sources")
    constraints = sources["constraints"]
    _fields(constraints, sources["allowed"])
    for rule in constraints.values():
        _fields(rule, ("jurisdictions", "url_hosts"))
        if not _strings(rule["jurisdictions"]) or not _strings(rule["url_hosts"]):
            raise PolicyError("Source constraints must be explicit")
        if any(item not in ("ES", "EU", "INT") for item in rule["jurisdictions"]):
            raise PolicyError("Source jurisdiction outside ES pilot")
        if any(not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*\.[a-z]{2,}", host)
               for host in rule["url_hosts"]):
            raise PolicyError("Source hosts must be exact hostnames")
    if require_approved and not approved:
        raise PolicyError("Policy awaiting professional review")
    return policy


def read_policy(path: Path) -> Dict[str, Any]:
    try:
        content = path.read_bytes()
        if len(content) > 65536:
            raise PolicyError("Policy exceeds size limit")
        policy = yaml.load(content.decode("utf-8"), Loader=_UniqueLoader)
        return validate_policy(policy)
    except PolicyError:
        raise
    except (OSError, UnicodeError, yaml.YAMLError, ValueError, TypeError, RecursionError) as exc:
        raise PolicyError("Policy missing or invalid") from exc


def source_is_allowed(policy: Dict[str, Any], meta: Dict[str, Any]) -> bool:
    try:
        validate_policy(policy)
        if not isinstance(meta, dict) or meta.get("source") not in policy["sources"]["allowed"]:
            return False
        rule = policy["sources"]["constraints"][meta["source"]]
        raw_url = meta.get("ref_url")
        if not isinstance(raw_url, str) or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in raw_url):
            return False
        url = urlsplit(raw_url)
        return (meta.get("jurisdiction") in rule["jurisdictions"]
                and url.scheme == "https" and url.hostname in rule["url_hosts"]
                and url.port in (None, 443) and url.username is None and url.password is None)
    except (PolicyError, ValueError, TypeError):
        return False
