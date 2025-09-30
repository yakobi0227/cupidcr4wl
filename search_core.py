"""Shared search logic for the cupidcr4wl command line interface and web app."""
from __future__ import annotations

import json
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

import requests


@dataclass
class SiteResult:
    """Represents the outcome of checking a single site."""

    name: str
    url: Optional[str]
    status: str
    response_code: Optional[int] = None
    message: Optional[str] = None
    matched_check_texts: List[str] = field(default_factory=list)
    matched_not_found_texts: List[str] = field(default_factory=list)


@dataclass
class CategoryResult:
    """Groups site results by category for a single target."""

    name: str
    sites: List[SiteResult]


@dataclass
class TargetResult:
    """Collects category results for a username or phone number."""

    target: str
    categories: List[CategoryResult]


def load_websites(file_path: str) -> Dict[str, Dict[str, dict]]:
    """Load website information from a JSON file and organise it by category."""
    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if "websites" in data:
        raw_sites = data["websites"]
    elif "phone_numbers" in data:
        raw_sites = data["phone_numbers"]
    else:
        raise ValueError("Unrecognised JSON schema: expected 'websites' or 'phone_numbers'.")

    categorised_websites: Dict[str, Dict[str, dict]] = defaultdict(dict)
    for site_name, info in raw_sites.items():
        category = info.get("category", "Other")
        categorised_websites[category][site_name] = info
    return categorised_websites


def load_user_agents(file_path: str) -> List[str]:
    """Load user agents from a text file."""
    with open(file_path, "r", encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip()]


def _check_single_site(
    target: str,
    site_name: str,
    info: dict,
    user_agents: Iterable[str],
    *,
    debug: bool = False,
) -> SiteResult:
    """Check a single site for the provided target and return a structured result."""
    url_template: Optional[str] = info.get("url")
    url = url_template.format(username=target) if url_template else None
    check_texts = info.get("check_text", []) or []
    not_found_texts = info.get("not_found_text", []) or []

    if not url or not check_texts:
        return SiteResult(
            name=site_name,
            url=url,
            status="skipped",
            message="URL or check text missing.",
        )

    headers = {"User-Agent": random.choice(list(user_agents))}

    try:
        response = requests.get(url, headers=headers, timeout=5)
    except requests.Timeout:
        return SiteResult(
            name=site_name,
            url=url,
            status="timeout",
            message="Timeout while checking site.",
        )
    except requests.RequestException as exc:
        return SiteResult(
            name=site_name,
            url=url,
            status="error",
            message=f"Network error: {exc}",
        )

    lower_text = response.text.lower()
    matching_check_texts = [text for text in check_texts if text.lower() in lower_text]
    matching_not_found_texts = [text for text in not_found_texts if text.lower() in lower_text]

    if response.status_code == 200:
        if matching_check_texts:
            status = "found"
            message = "Account found."
        elif matching_not_found_texts:
            status = "not_found"
            message = "No account found."
        else:
            status = "possible"
            message = "Possible account found."
    else:
        status = "not_found"
        message = "No account found."

    return SiteResult(
        name=site_name,
        url=url,
        status=status,
        response_code=response.status_code,
        message=message,
        matched_check_texts=matching_check_texts if debug else [],
        matched_not_found_texts=matching_not_found_texts if debug else [],
    )


def search_targets(
    targets: Iterable[str],
    *,
    user_agents: Iterable[str],
    websites_by_category: Dict[str, Dict[str, dict]],
    debug: bool = False,
) -> List[TargetResult]:
    """Search usernames or phone numbers across the configured websites."""
    cleaned_targets = [target.strip() for target in targets if target.strip()]
    results: List[TargetResult] = []

    for target in cleaned_targets:
        category_results: List[CategoryResult] = []
        for category, sites in websites_by_category.items():
            site_results: List[SiteResult] = []
            with ThreadPoolExecutor(max_workers=8) as executor:
                future_to_site = {
                    executor.submit(
                        _check_single_site,
                        target,
                        site_name,
                        info,
                        user_agents,
                        debug=debug,
                    ): site_name
                    for site_name, info in sites.items()
                }
                for future in as_completed(future_to_site):
                    site_results.append(future.result())

            # Sort results alphabetically for deterministic output
            site_results.sort(key=lambda result: result.name.lower())
            category_results.append(CategoryResult(name=category, sites=site_results))

        results.append(TargetResult(target=target, categories=category_results))

    return results


__all__ = [
    "CategoryResult",
    "SiteResult",
    "TargetResult",
    "load_user_agents",
    "load_websites",
    "search_targets",
]
