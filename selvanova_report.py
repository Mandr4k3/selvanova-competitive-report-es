from __future__ import annotations

import base64
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape, unescape
from pathlib import Path
from typing import Any

import jinja2
import numpy as np
import pandas as pd
import requests
import urllib3


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
ARTIFACTS_DIR = OUTPUT_DIR / "artifacts"
LISTING_HTML_DIR = ARTIFACTS_DIR / "listing_html"
SEARCH_HTML_DIR = ARTIFACTS_DIR / "search_html"
AIRDNA_SNAPSHOT_ARTIFACT = ARTIFACTS_DIR / "airdna_submarket_snapshot.json"

CHECK_IN = "2026-04-25"
CHECK_OUT = "2026-04-27"
PRIMARY_ROOM_ID = "1614163423009452086"
PRIMARY_URL = (
    f"https://www.airbnb.mx/rooms/{PRIMARY_ROOM_ID}"
    f"?check_in={CHECK_IN}&check_out={CHECK_OUT}&adults=1&guests=1&enable_auto_translate=false"
)
PRIMARY_SEARCH_PRICE_FALLBACK = {
    "search_price_total_mxn": 5703.0,
    "search_base_nightly_mxn": 2851.23,
    "search_base_total_mxn": 5702.45,
    "search_fee_total_mxn": 0.55,
    "search_price_qualifier": "por 2 noches",
    "search_price_accessibility": "$5,703 MXN por 2 noches",
}
AIRDNA_URL = (
    "https://app.airdna.co/data/mx/24/146170/overview"
    "?lat=20.658186&lng=-87.087405&zoom=14.66"
)
PRIMARY_LAT = 20.6559
PRIMARY_LNG = -87.0983
PRIMARY_COORDS = (PRIMARY_LAT, PRIMARY_LNG)

SEARCH_URLS = {
    "selvanova_q1": (
        "https://www.airbnb.mx/s/Playa-del-Carmen--Quintana-Roo--Mexico/homes"
        f"?check_in={CHECK_IN}&check_out={CHECK_OUT}&adults=1"
        "&room_types%5B%5D=Entire%20home%2Fapt"
        "&query=Selvanova%20Residencial%20Playa%20del%20Carmen"
    ),
    "selvanova_q6": (
        "https://www.airbnb.mx/s/Playa-del-Carmen--Quintana-Roo--Mexico/homes"
        f"?check_in={CHECK_IN}&check_out={CHECK_OUT}&adults=6"
        "&room_types%5B%5D=Entire%20home%2Fapt"
        "&query=Selvanova%20Residencial%20Playa%20del%20Carmen"
    ),
    "selvanova_q6_bed3": (
        "https://www.airbnb.mx/s/Playa-del-Carmen--Quintana-Roo--Mexico/homes"
        f"?check_in={CHECK_IN}&check_out={CHECK_OUT}&adults=6"
        "&room_types%5B%5D=Entire%20home%2Fapt"
        "&min_bedrooms=3"
        "&query=Selvanova%20Residencial%20Playa%20del%20Carmen"
    ),
    "selvanova_path": (
        "https://www.airbnb.mx/s/Selvanova-Residencial--Playa-del-Carmen--Quintana-Roo--Mexico/homes"
        f"?check_in={CHECK_IN}&check_out={CHECK_OUT}&adults=6"
        "&room_types%5B%5D=Entire%20home%2Fapt"
    ),
}

MUST_HAVE_FLAGS = [
    "kitchen",
    "wifi",
    "workspace",
    "parking",
    "pool",
    "ac",
    "washer",
    "dryer",
    "self_checkin",
    "family_cues",
]

PREFERRED_FLAGS = [
    "gym",
    "bbq",
    "smart_tv",
    "security",
    "elevator",
    "kids_club",
    "terrace",
    "laundry",
]

PHOTO_CATEGORY_KEYWORDS = {
    "pool": ["alberca", "pool", "rooftop pool", "swimming"],
    "living": ["sala", "living", "sofa", "tv room", "cinema"],
    "bedroom": ["recámara", "recamara", "bedroom", "cama", "dormitorio"],
    "kitchen": ["cocina", "kitchen"],
    "bathroom": ["baño", "bano", "bathroom", "regadera", "ducha"],
    "terrace": ["terraza", "balcón", "balcon", "patio", "outdoor dining"],
    "dining": ["comedor", "dining"],
    "workspace": ["workspace", "trabajo", "desk", "escritorio"],
    "parking": ["parking", "estacionamiento", "garage"],
    "exterior": ["fachada", "exterior", "building", "residencial", "entrada"],
}

STOP_WORDS = {
    "de",
    "del",
    "en",
    "con",
    "la",
    "el",
    "and",
    "to",
    "the",
    "a",
    "y",
    "for",
    "w",
    "mxn",
    "playa",
    "carmen",
    "selvanova",
}


@dataclass
class FetchResult:
    url: str
    html: str
    artifact_path: str
    status_code: int


def ensure_dirs() -> None:
    for path in [OUTPUT_DIR, ARTIFACTS_DIR, LISTING_HTML_DIR, SEARCH_HTML_DIR]:
        path.mkdir(parents=True, exist_ok=True)
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def session_factory() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "accept-language": "es-MX,es;q=0.9,en;q=0.8",
        }
    )
    return session


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "artifact"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def report_href(path_str: str) -> str:
    path = Path(path_str)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    try:
        return str(path.relative_to(OUTPUT_DIR))
    except ValueError:
        return path.as_uri()


def fetch_html(session: requests.Session, url: str, artifact_path: Path) -> FetchResult:
    if artifact_path.exists() and artifact_path.stat().st_size > 0:
        return FetchResult(
            url=url,
            html=artifact_path.read_text(encoding="utf-8"),
            artifact_path=str(artifact_path.relative_to(ROOT)),
            status_code=200,
        )
    response = session.get(url, timeout=60, verify=False)
    response.raise_for_status()
    write_text(artifact_path, response.text)
    return FetchResult(
        url=url,
        html=response.text,
        artifact_path=str(artifact_path.relative_to(ROOT)),
        status_code=response.status_code,
    )


def extract_script_json(html: str, script_id: str) -> Any | None:
    match = re.search(
        rf'<script[^>]*id="{re.escape(script_id)}"[^>]*>(.*?)</script>',
        html,
        flags=re.S,
    )
    if not match:
        return None
    return json.loads(match.group(1))


def extract_ld_json_objects(html: str) -> list[dict[str, Any]]:
    matches = re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        flags=re.S,
    )
    objects: list[dict[str, Any]] = []
    for raw in matches:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            objects.extend([obj for obj in parsed if isinstance(obj, dict)])
        elif isinstance(parsed, dict):
            objects.append(parsed)
    return objects


def decode_airbnb_room_id(encoded_id: str | None) -> str | None:
    if not encoded_id:
        return None
    try:
        decoded = base64.b64decode(encoded_id).decode("utf-8", errors="ignore")
        return decoded.split(":")[-1]
    except Exception:
        return None


def strip_html(raw: str | None) -> str | None:
    if not raw:
        return None
    text = raw.replace("<br />", "\n").replace("<br/>", "\n").replace("<br>", "\n")
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    return str(value)


def parse_money(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = (
        value.replace("$", "")
        .replace("MXN", "")
        .replace("\xa0", "")
        .replace(",", "")
        .strip()
    )
    match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    return float(match.group(1)) if match else None


def parse_int_from_text(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"(\d+)", value.replace(",", ""))
    return int(match.group(1)) if match else None


def parse_float_from_text(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", value.replace(",", ""))
    return float(match.group(1)) if match else None


def haversine_km(lat1: float | None, lon1: float | None, lat2: float, lon2: float) -> float | None:
    if lat1 is None or lon1 is None:
        return None
    radius = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def classify_photo(label: str | None) -> str:
    label_l = (label or "").lower()
    for category, keywords in PHOTO_CATEGORY_KEYWORDS.items():
        if any(keyword in label_l for keyword in keywords):
            return category
    return "unknown"


def normalize_words(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9]+", text.lower())
    return [word for word in words if word not in STOP_WORDS and len(word) > 2]


def mean_or_none(values: list[float]) -> float | None:
    cleaned = [value for value in values if value is not None]
    return sum(cleaned) / len(cleaned) if cleaned else None


def safe_join(values: list[str], sep: str = ", ") -> str:
    return sep.join([value for value in values if value])


def recursive_find_values(obj: Any, key: str) -> list[Any]:
    found: list[Any] = []
    if isinstance(obj, dict):
        for k, value in obj.items():
            if k == key:
                found.append(value)
            found.extend(recursive_find_values(value, key))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(recursive_find_values(item, key))
    return found


def parse_review_rating_text(value: str | None) -> tuple[float | None, int | None, bool]:
    if not value:
        return None, None, False
    if "nuevo" in value.lower():
        return None, 0, True
    match = re.search(r"(\d+(?:\.\d+)?)\s*\(([\d,]+)\)", value)
    if not match:
        return parse_float_from_text(value), None, False
    return float(match.group(1)), int(match.group(2).replace(",", "")), False


def parse_search_result(result: dict[str, Any], source_name: str, source_url: str) -> dict[str, Any]:
    encoded_id = result.get("demandStayListing", {}).get("id")
    room_id = decode_airbnb_room_id(encoded_id)
    structured = result.get("structuredContent") or {}
    detail_bodies = [item.get("body") for item in structured.get("primaryLine") or [] if item.get("body")]
    rating_value, review_count, is_new = parse_review_rating_text(result.get("avgRatingLocalized"))
    badges = [badge.get("text") or badge.get("badgeText") or "" for badge in result.get("badges") or []]
    coord = result.get("demandStayListing", {}).get("location", {}).get("coordinate", {})
    primary_line = result.get("structuredDisplayPrice", {}).get("primaryLine") or {}
    explanation_data = result.get("structuredDisplayPrice", {}).get("explanationData") or {}
    base_nightly = None
    base_total = None
    fee_total = None
    for group in explanation_data.get("priceDetails") or []:
        for item in group.get("items") or []:
            description = item.get("description") or ""
            price_string = item.get("priceString") or ""
            if " x $" in description:
                nightly_match = re.search(r"x\s*\$([\d,]+(?:\.\d+)?)", description)
                if nightly_match:
                    base_nightly = float(nightly_match.group(1).replace(",", ""))
                base_total = parse_money(price_string)
                break
        if base_total is not None:
            break
    total_price = parse_money(primary_line.get("price"))
    if total_price is not None and base_total is not None:
        fee_total = round(total_price - base_total, 2)
    return {
        "room_id": room_id,
        "search_source": source_name,
        "search_source_url": source_url,
        "search_title": result.get("title"),
        "search_subtitle": result.get("subtitle"),
        "search_name": result.get("nameLocalized", {}).get("localizedStringWithTranslationPreference"),
        "search_rating_text": result.get("avgRatingLocalized"),
        "search_rating_value": rating_value,
        "search_review_count": review_count,
        "search_is_new": is_new,
        "search_badges": [badge for badge in badges if badge],
        "search_photo_url": (result.get("contextualPictures") or [{}])[0].get("picture"),
        "search_detail_bodies": detail_bodies,
        "search_price_total_mxn": total_price,
        "search_base_nightly_mxn": base_nightly,
        "search_base_total_mxn": base_total,
        "search_fee_total_mxn": fee_total,
        "search_price_qualifier": primary_line.get("qualifier"),
        "search_price_accessibility": primary_line.get("accessibilityLabel"),
        "lat": coord.get("latitude"),
        "lng": coord.get("longitude"),
    }


def merge_candidate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        room_id = row["room_id"]
        if not room_id:
            continue
        if room_id not in merged:
            merged[room_id] = row | {
                "search_sources": [row["search_source"]],
                "search_source_urls": [row["search_source_url"]],
            }
            continue
        current = merged[room_id]
        current["search_sources"] = sorted(set(current["search_sources"] + [row["search_source"]]))
        current["search_source_urls"] = sorted(set(current["search_source_urls"] + [row["search_source_url"]]))
        for key, value in row.items():
            if current.get(key) in (None, [], "", 0) and value not in (None, [], "", 0):
                current[key] = value
        if row.get("search_review_count") and (
            (current.get("search_review_count") or 0) < row.get("search_review_count", 0)
        ):
            current["search_review_count"] = row["search_review_count"]
            current["search_rating_value"] = row.get("search_rating_value")
            current["search_rating_text"] = row.get("search_rating_text")
        if row.get("search_base_nightly_mxn") and (
            current.get("search_base_nightly_mxn") is None
            or row["search_base_nightly_mxn"] < current["search_base_nightly_mxn"]
        ):
            current["search_base_nightly_mxn"] = row["search_base_nightly_mxn"]
            current["search_price_total_mxn"] = row.get("search_price_total_mxn")
            current["search_fee_total_mxn"] = row.get("search_fee_total_mxn")
            current["search_base_total_mxn"] = row.get("search_base_total_mxn")
    return list(merged.values())


def trim_candidate_pool(df: pd.DataFrame, keep_n: int = 34) -> pd.DataFrame:
    work = df.copy()
    work["distance_seed_km"] = work.apply(
        lambda row: haversine_km(row.get("lat"), row.get("lng"), PRIMARY_LAT, PRIMARY_LNG),
        axis=1,
    )
    work["search_review_count"] = work["search_review_count"].fillna(0)
    work["search_title_l"] = (
        work["search_title"].fillna("").astype(str).str.lower()
        + " "
        + work["search_subtitle"].fillna("").astype(str).str.lower()
    )
    work["search_seed_score"] = 0.0
    work.loc[work["distance_seed_km"].fillna(999).le(1.0), "search_seed_score"] += 5
    work.loc[work["distance_seed_km"].fillna(999).between(1.0, 2.0), "search_seed_score"] += 3
    work.loc[work["search_title_l"].str.contains("departamento|condominio|selvanova", regex=True), "search_seed_score"] += 3
    work.loc[work["search_title_l"].str.contains("villa|hotel", regex=True), "search_seed_score"] -= 4
    work["bedroom_seed"] = work["search_detail_bodies"].apply(
        lambda values: parse_int_from_text(next((item for item in values if "habit" in item.lower()), None))
        if isinstance(values, list)
        else None
    )
    work.loc[work["bedroom_seed"].fillna(0).between(2, 4), "search_seed_score"] += 2
    work = work[work["distance_seed_km"].fillna(999).le(4.0)].copy()
    work = work.sort_values(
        by=["search_seed_score", "search_review_count", "distance_seed_km"],
        ascending=[False, False, True],
    )
    must_keep = work[work["room_id"] == PRIMARY_ROOM_ID]
    trimmed = pd.concat([must_keep, work[work["room_id"] != PRIMARY_ROOM_ID].head(keep_n)])
    return trimmed.drop_duplicates(subset=["room_id"]).copy()


def flatten_amenities(section: dict[str, Any] | None) -> list[str]:
    amenities: list[str] = []
    if not section:
        return amenities
    for group in section.get("seeAllAmenitiesGroups") or []:
        for amenity in group.get("amenities") or []:
            title = amenity.get("title")
            if title:
                amenities.append(title)
    if not amenities:
        for group in section.get("previewAmenitiesGroups") or []:
            for amenity in group.get("amenities") or []:
                title = amenity.get("title")
                if title:
                    amenities.append(title)
    return sorted(set(amenities))


def amenity_flag_map(amenities: list[str], description: str, highlights: list[str], house_rules: list[str]) -> dict[str, int]:
    text_blob = " | ".join(amenities + [description] + highlights + house_rules).lower()
    return {
        "kitchen": int("cocina" in text_blob or "kitchen" in text_blob),
        "wifi": int("wifi" in text_blob or "wi-fi" in text_blob),
        "workspace": int("trabajar" in text_blob or "workspace" in text_blob or "escritorio" in text_blob),
        "parking": int("estacionamiento" in text_blob or "parking" in text_blob),
        "pool": int("alberca" in text_blob or "pool" in text_blob),
        "gym": int("gym" in text_blob or "gimnasio" in text_blob),
        "bbq": int("bbq" in text_blob or "asador" in text_blob or "grill" in text_blob),
        "ac": int("aire acondicionado" in text_blob or re.search(r"\bac\b", text_blob) is not None),
        "washer": int("lavadora" in text_blob or "washer" in text_blob),
        "dryer": int("secadora" in text_blob or "dryer" in text_blob),
        "laundry": int(("lavadora" in text_blob or "washer" in text_blob) and ("secadora" in text_blob or "dryer" in text_blob)),
        "self_checkin": int("llegada autónoma" in text_blob or "self check-in" in text_blob or "candado inteligente" in text_blob or "cerradura inteligente" in text_blob),
        "family_cues": int("kids club" in text_blob or "familiar" in text_blob or "teenagers club" in text_blob or "family" in text_blob),
        "security": int("seguridad" in text_blob or "security" in text_blob or "cámaras de seguridad" in text_blob or "surveillance" in text_blob),
        "smart_tv": int("smart tv" in text_blob or "cinema tv" in text_blob or "75" in text_blob and "tv" in text_blob),
        "elevator": int("elevador" in text_blob or "elevator" in text_blob),
        "kids_club": int("kids club" in text_blob or "teenagers club" in text_blob),
        "terrace": int("terraza" in text_blob or "terrace" in text_blob or "balcón" in text_blob or "balcon" in text_blob),
    }


def extract_description(section_lookup: dict[str, dict[str, Any]]) -> tuple[str, list[dict[str, str]]]:
    section = section_lookup.get("DESCRIPTION_MODAL") or section_lookup.get("DESCRIPTION_DEFAULT") or {}
    chunks: list[dict[str, str]] = []
    for item in section.get("items") or []:
        title = item.get("title") or ""
        html_block = (item.get("html") or {}).get("htmlText")
        text = strip_html(html_block)
        if text:
            chunks.append({"title": title, "text": text})
    full_text = "\n\n".join(
        [f"{chunk['title']}\n{chunk['text']}".strip() for chunk in chunks if chunk.get("text")]
    ).strip()
    return full_text, chunks


def extract_house_rules(section_lookup: dict[str, dict[str, Any]]) -> list[str]:
    policies = section_lookup.get("POLICIES_DEFAULT") or {}
    rules: list[str] = []
    for group in policies.get("houseRulesSections") or []:
        group_title = group.get("title") or ""
        for item in group.get("items") or []:
            title = item.get("title")
            if title:
                rules.append(f"{group_title}: {title}" if group_title else title)
    for item in policies.get("houseRules") or []:
        title = item.get("title")
        if title and title not in rules:
            rules.append(title)
    return rules


def extract_highlights(section_lookup: dict[str, dict[str, Any]]) -> list[str]:
    highlights = []
    section = section_lookup.get("HIGHLIGHTS_DEFAULT") or {}
    for item in section.get("highlights") or []:
        title = item.get("title")
        subtitle = item.get("subtitle")
        if title and subtitle:
            highlights.append(f"{title}: {subtitle}")
        elif title:
            highlights.append(title)
    return highlights


def parse_listing_payload(room_id: str, url: str, html: str) -> dict[str, Any]:
    deferred = extract_script_json(html, "data-deferred-state-0")
    if not deferred:
        raise ValueError(f"Missing deferred state for room {room_id}")
    entry = next(
        (item for item in deferred.get("niobeClientData", []) if str(item[0]).startswith("StaysPdpSections:")),
        None,
    )
    if entry is None:
        raise ValueError(f"Missing StaysPdpSections payload for room {room_id}")
    data = entry[1]["data"]
    presentation = data.get("node", {}).get("pdpPresentation") or {}
    sections = data.get("presentation", {}).get("stayProductDetailPage", {}).get("sections", {}).get("sections") or []
    section_lookup = {item.get("sectionId"): item.get("section") for item in sections if item.get("sectionId")}
    ld_objects = extract_ld_json_objects(html)

    overview = presentation.get("overview") or {}
    quality = presentation.get("quality") or {}
    title_section = section_lookup.get("TITLE_DEFAULT") or {}
    hero_section = section_lookup.get("HERO_DEFAULT") or {}
    photo_section = section_lookup.get("PHOTO_TOUR_SCROLLABLE_MODAL") or {}
    host_section = section_lookup.get("MEET_YOUR_HOST") or {}
    location_section = section_lookup.get("LOCATION_DEFAULT") or section_lookup.get("LOCATION_PDP") or {}
    reviews_section = section_lookup.get("REVIEWS_DEFAULT") or {}
    amenities_section = section_lookup.get("AMENITIES_DEFAULT") or presentation.get("amenities") or {}
    sleeping_section = section_lookup.get("SLEEPING_ARRANGEMENT_WITH_IMAGES") or {}
    policies_section = section_lookup.get("POLICIES_DEFAULT") or {}

    description_text, description_blocks = extract_description(section_lookup)
    house_rules = extract_house_rules(section_lookup)
    highlights = extract_highlights(section_lookup)

    hero_images = hero_section.get("previewImages") or []
    photo_items = photo_section.get("mediaItems") or []
    if photo_items:
        photo_labels = [item.get("accessibilityLabel") for item in photo_items]
        photo_urls = [item.get("baseUrl") for item in photo_items]
    else:
        photo_labels = [item.get("accessibilityLabel") for item in hero_images]
        photo_urls = [item.get("baseUrl") for item in hero_images]

    review_tags = reviews_section.get("reviewTags") or []
    category_ratings = reviews_section.get("ratings") or []
    rating_distribution = reviews_section.get("ratingDistribution") or []
    host_card = host_section.get("cardData") or {}
    host_stats = {item.get("type"): item.get("value") for item in host_card.get("stats") or []}
    amenities = flatten_amenities(amenities_section)
    amenity_flags = amenity_flag_map(amenities, description_text, highlights, house_rules)
    review_tag_names = [tag.get("localizedName") for tag in review_tags if tag.get("localizedName")]
    review_tag_counts = {tag.get("localizedName"): tag.get("count") for tag in review_tags if tag.get("localizedName")}
    photo_categories = [classify_photo(label) for label in photo_labels]
    overview_items = overview.get("items") or []
    guests = parse_int_from_text(next((item for item in overview_items if "huésped" in item.lower()), None))
    bedrooms = parse_int_from_text(next((item for item in overview_items if "habit" in item.lower()), None))
    beds = parse_int_from_text(next((item for item in overview_items if "cama" in item.lower()), None))
    baths = parse_float_from_text(next((item for item in overview_items if "bañ" in item.lower()), None))
    review_count = reviews_section.get("overallCount")
    overall_rating = reviews_section.get("overallRating")
    if overall_rating is None:
        overall_rating = (
            quality.get("listingRatingStats", {})
            .get("overallRatingStats", {})
            .get("ratingAverage")
        )
    if review_count is None:
        raw_count = (
            quality.get("listingRatingStats", {})
            .get("overallRatingStats", {})
            .get("ratingCount")
        )
        review_count = int(raw_count) if raw_count else None

    room_rows = []
    for detail in sleeping_section.get("arrangementDetails") or []:
        title = detail.get("title")
        subtitle = detail.get("subtitle")
        if title or subtitle:
            room_rows.append(f"{title}: {subtitle}".strip(": "))

    review_comment_candidates = recursive_find_values(reviews_section, "comment") + recursive_find_values(
        reviews_section, "localizedComment"
    )
    review_comments = [strip_html(text_or_none(item)) for item in review_comment_candidates if text_or_none(item)]

    ld_rating = None
    ld_review_count = None
    for obj in ld_objects:
        agg = obj.get("aggregateRating") or {}
        if agg:
            ld_rating = ld_rating or parse_float_from_text(text_or_none(agg.get("ratingValue")))
            ld_review_count = ld_review_count or parse_int_from_text(text_or_none(agg.get("reviewCount")))

    if overall_rating is None:
        overall_rating = ld_rating
    if review_count is None:
        review_count = ld_review_count

    return {
        "room_id": room_id,
        "listing_url": url,
        "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        "title": title_section.get("title") or next((obj.get("name") for obj in ld_objects if obj.get("name")), None),
        "overview_title": overview.get("title"),
        "guests": guests,
        "bedrooms": bedrooms,
        "beds": beds,
        "baths": baths,
        "photo_count": len(photo_urls),
        "photo_urls": photo_urls,
        "photo_labels": photo_labels,
        "hero_label": photo_labels[0] if photo_labels else None,
        "hero_category": photo_categories[0] if photo_categories else "unknown",
        "first_five_photo_categories": photo_categories[:5],
        "photo_category_diversity": len(set([category for category in photo_categories[:8] if category != "unknown"])),
        "amenities": amenities,
        "amenity_count": len(amenities),
        "amenity_flags": amenity_flags,
        "highlights": highlights,
        "description": description_text,
        "description_blocks": description_blocks,
        "location_subtitle": location_section.get("subtitle"),
        "lat": location_section.get("lat"),
        "lng": location_section.get("lng"),
        "location_verified": (location_section.get("listingLocationVerificationDetails") or {}).get("isVerified"),
        "rating": overall_rating,
        "review_count": review_count,
        "review_tags": review_tag_names,
        "review_tag_counts": review_tag_counts,
        "review_comments": review_comments,
        "category_ratings": {
            item.get("label"): parse_float_from_text(item.get("localizedRating"))
            for item in category_ratings
            if item.get("label")
        },
        "rating_distribution": {
            item.get("label"): item.get("localizedRating")
            for item in rating_distribution
            if item.get("label")
        },
        "host_name": host_card.get("name"),
        "host_verified": host_card.get("isVerified"),
        "is_superhost": host_card.get("isSuperhost"),
        "host_response_blurb": host_section.get("hostRespondTimeCopy"),
        "host_details": host_section.get("hostDetails") or [],
        "host_about": host_section.get("about"),
        "host_rating_average": host_card.get("ratingAverage"),
        "host_rating_count": host_card.get("ratingCount"),
        "host_review_count_stat": host_stats.get("REVIEW_COUNT"),
        "host_months_experience": host_card.get("timeAsHost", {}).get("months"),
        "host_years_experience": host_card.get("timeAsHost", {}).get("years"),
        "host_response_rate": next(
            (item for item in host_section.get("hostDetails") or [] if "respuesta" in item.lower()),
            None,
        ),
        "house_rules": house_rules,
        "checkin_checkout_rules": [rule for rule in house_rules if "llegada" in rule.lower() or "salida" in rule.lower()],
        "max_guests_rule": next((rule for rule in house_rules if "huésped" in rule.lower()), None),
        "safety_items": [
            item.get("title")
            for item in policies_section.get("previewSafetyAndProperties") or []
            if item.get("title")
        ],
        "sleeping_arrangements": room_rows,
        "cancellation_policy_exact": policies_section.get("cancellationPolicyForDisplay"),
        "cancellation_policy_title": policies_section.get("cancellationPolicyTitle"),
        "book_it_price_loaded": any(
            section_lookup.get(key, {}).get("structuredDisplayPrice") for key in ["BOOK_IT_SIDEBAR", "BOOK_IT_FLOATING_FOOTER"]
        ),
        "title_share_summary": ((title_section.get("shareSave") or {}).get("sharingConfig") or {}).get("title"),
        "search_badges_inline": [],
    }


def comp_similarity_seed(record: dict[str, Any]) -> float:
    score = 0.0
    distance = record.get("distance_km")
    bedrooms = record.get("bedrooms")
    guests = record.get("guests")
    type_line = (record.get("overview_title") or record.get("search_title") or "").lower()
    if distance is not None:
        if distance <= 0.8:
            score += 5
        elif distance <= 1.5:
            score += 3
        elif distance <= 3.0:
            score += 1
    if bedrooms is not None:
        score += max(0, 4 - abs(bedrooms - 3))
    if guests is not None:
        score += max(0, 3 - abs(guests - 6) * 0.5)
    if any(term in type_line for term in ["departamento", "condominio", "vivienda rentada"]):
        score += 3
    if "villa" in type_line or "hotel" in type_line:
        score -= 4
    if any(term in type_line for term in ["residencia", "casa"]):
        score -= 1
    return score


def build_scores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["distance_km"] = df.apply(
        lambda row: haversine_km(row.get("lat"), row.get("lng"), PRIMARY_LAT, PRIMARY_LNG),
        axis=1,
    )
    df["review_count_filled"] = df["review_count"].fillna(0)
    df["rating_filled"] = df["rating"].fillna(df["search_rating_value"]).fillna(0)
    df["nightly_price_mxn"] = df["search_base_nightly_mxn"].fillna(df["search_price_total_mxn"] / 2)
    df["fee_load_mxn"] = df["search_fee_total_mxn"]
    df["price_per_guest_mxn"] = df["nightly_price_mxn"] / df["guests"].replace(0, np.nan)
    df["amenity_completeness_score"] = df.apply(
        lambda row: round(
            100
            * (
                sum((row.get("amenity_flags") or {}).get(flag, 0) for flag in MUST_HAVE_FLAGS)
                + 0.5 * sum((row.get("amenity_flags") or {}).get(flag, 0) for flag in PREFERRED_FLAGS)
            )
            / (len(MUST_HAVE_FLAGS) + 0.5 * len(PREFERRED_FLAGS)),
            1,
        ),
        axis=1,
    )
    df["trust_review_strength_score"] = df.apply(
        lambda row: round(
            min(100, (row["rating_filled"] / 5) * 45 + math.log1p(row["review_count_filled"]) * 12
                + (8 if row.get("is_superhost") else 0)
                + (8 if "Favorito entre huéspedes" in safe_join(row.get("search_badges") or []) else 0)
                + (4 if row.get("host_verified") else 0)
                + (5 if (row.get("amenity_flags") or {}).get("self_checkin") else 0)),
            1,
        ),
        axis=1,
    )
    df["booking_friction_score"] = df.apply(
        lambda row: round(
            max(
                0,
                100
                - (12 if not (row.get("amenity_flags") or {}).get("self_checkin") else 0)
                - (10 if not (row.get("amenity_flags") or {}).get("parking") else 0)
                - (8 if not (row.get("amenity_flags") or {}).get("wifi") else 0)
                - (8 if row.get("fee_load_mxn") and row.get("fee_load_mxn") > 600 else 0)
                - (6 if row.get("search_is_new") else 0)
                - (10 if row.get("cancellation_policy_exact") in (None, "", "null") else 0),
            ),
            1,
        ),
        axis=1,
    )
    df["photo_storytelling_score"] = df.apply(
        lambda row: round(
            min(
                100,
                30
                + min(row.get("photo_count") or 0, 40)
                + min((row.get("photo_category_diversity") or 0) * 8, 24)
                + (8 if (row.get("hero_category") or "") in {"living", "pool", "terrace"} else 0)
                + (8 if "pool" in (row.get("first_five_photo_categories") or []) else 0)
                + (8 if "bedroom" in (row.get("first_five_photo_categories") or []) else 0),
            ),
            1,
        ),
        axis=1,
    )
    df["family_group_fit_score"] = df.apply(
        lambda row: round(
            min(
                100,
                (20 if (row.get("guests") or 0) >= 6 else 0)
                + (20 if (row.get("bedrooms") or 0) >= 3 else 0)
                + min((row.get("beds") or 0) * 6, 18)
                + (12 if (row.get("amenity_flags") or {}).get("pool") else 0)
                + (10 if (row.get("amenity_flags") or {}).get("parking") else 0)
                + (10 if (row.get("amenity_flags") or {}).get("laundry") else 0)
                + (10 if (row.get("amenity_flags") or {}).get("family_cues") else 0),
            ),
            1,
        ),
        axis=1,
    )
    df["location_framing_score"] = df.apply(
        lambda row: round(
            min(
                100,
                35
                + (20 if "10 minutos" in (row.get("description") or "").lower() else 0)
                + (15 if "quinta" in (row.get("description") or "").lower() or "5ta" in (row.get("description") or "").lower() else 0)
                + (10 if "carro" in (row.get("description") or "").lower() or "parking" in (row.get("description") or "").lower() else 0)
                + (10 if row.get("distance_km") is not None and row["distance_km"] <= 1.2 else 0)
                + (10 if "seguridad" in (row.get("description") or "").lower() or "quiet" in (row.get("description") or "").lower() else 0),
            ),
            1,
        ),
        axis=1,
    )
    price_series = df["nightly_price_mxn"].dropna()
    if not price_series.empty:
        min_price = price_series.min()
        max_price = price_series.max()
        if math.isclose(min_price, max_price):
            df["pricing_strength_score"] = 50.0
        else:
            df["pricing_strength_score"] = round(
                100 * (df["nightly_price_mxn"] - min_price) / (max_price - min_price),
                1,
            )
    else:
        df["pricing_strength_score"] = np.nan

    df["listing_appeal_score"] = (
        0.24 * df["amenity_completeness_score"]
        + 0.28 * df["trust_review_strength_score"]
        + 0.24 * df["photo_storytelling_score"]
        + 0.12 * df["location_framing_score"]
        + 0.12 * df["family_group_fit_score"]
    ).round(1)
    df["value_for_money_score"] = (
        0.45 * (100 - df["pricing_strength_score"].fillna(50))
        + 0.30 * df["amenity_completeness_score"]
        + 0.25 * df["trust_review_strength_score"]
    ).round(1)
    df["occupancy_proxy_score"] = (
        0.42 * df["trust_review_strength_score"]
        + 0.20 * df["booking_friction_score"]
        + 0.18 * df["value_for_money_score"]
        + 0.20 * df["listing_appeal_score"]
    ).round(1)
    df["revenue_strength_proxy_score"] = (
        0.25 * df["pricing_strength_score"].fillna(50)
        + 0.75 * df["occupancy_proxy_score"]
    ).round(1)
    df["comp_similarity_seed"] = df.apply(lambda row: comp_similarity_seed(row.to_dict()), axis=1)
    return df


def select_comp_sets(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    candidates = df[df["room_id"] != PRIMARY_ROOM_ID].copy()
    apartment_like = candidates["overview_title"].fillna(candidates["search_title"]).str.lower().str.contains(
        "departamento|condominio|vivienda rentada",
        regex=True,
    )
    not_villa = ~candidates["overview_title"].fillna(candidates["search_title"]).str.lower().str.contains(
        "villa|hotel",
        regex=True,
    )
    strict_direct = candidates[
        apartment_like
        & not_villa
        & candidates["distance_km"].fillna(999).le(1.2)
        & candidates["bedrooms"].fillna(0).between(2, 4)
        & candidates["guests"].fillna(0).between(4, 8)
    ].copy()
    if len(strict_direct) < 10:
        expanded_direct = candidates[
            not_villa
            & candidates["distance_km"].fillna(999).le(1.8)
            & candidates["bedrooms"].fillna(0).between(2, 4)
            & candidates["guests"].fillna(0).between(4, 10)
        ].copy()
        expanded_direct = expanded_direct.sort_values(
            by=["comp_similarity_seed", "trust_review_strength_score", "listing_appeal_score"],
            ascending=[False, False, False],
        )
        direct = expanded_direct.head(10).copy()
    else:
        direct = strict_direct.sort_values(
            by=["comp_similarity_seed", "trust_review_strength_score", "listing_appeal_score"],
            ascending=[False, False, False],
        ).head(10)

    secondary = candidates[
        not_villa
        & ~candidates["room_id"].isin(direct["room_id"])
        & candidates["distance_km"].fillna(999).between(0.8, 3.2)
        & candidates["guests"].fillna(0).between(4, 10)
        & candidates["bedrooms"].fillna(0).between(2, 4)
    ].copy()
    secondary = secondary.sort_values(
        by=["value_for_money_score", "trust_review_strength_score", "listing_appeal_score"],
        ascending=[False, False, False],
    ).head(8)

    aspirational_pool = pd.concat([direct, secondary]).drop_duplicates(subset=["room_id"])
    aspirational = aspirational_pool[
        aspirational_pool["guests"].fillna(0).le(10)
    ].sort_values(
        by=["revenue_strength_proxy_score", "trust_review_strength_score", "photo_storytelling_score"],
        ascending=[False, False, False],
    ).head(5)
    return direct, secondary, aspirational


def scorecard_columns() -> list[str]:
    return [
        "title",
        "nightly_price_mxn",
        "rating",
        "review_count",
        "distance_km",
        "guests",
        "bedrooms",
        "beds",
        "revenue_strength_proxy_score",
        "pricing_strength_score",
        "occupancy_proxy_score",
        "listing_appeal_score",
        "amenity_completeness_score",
        "trust_review_strength_score",
        "booking_friction_score",
        "photo_storytelling_score",
        "family_group_fit_score",
        "location_framing_score",
        "value_for_money_score",
    ]


def compute_market_summary(primary: pd.Series, direct: pd.DataFrame, aspirational: pd.DataFrame) -> dict[str, Any]:
    direct_median_price = direct["nightly_price_mxn"].median()
    aspirational_median_price = aspirational["nightly_price_mxn"].median()
    primary_price = primary["nightly_price_mxn"]
    direct_review_median = direct["review_count"].median()
    direct_rating_median = direct["rating"].median()
    premium_pct = None
    if pd.notna(primary_price) and pd.notna(direct_median_price) and direct_median_price:
        premium_pct = round((primary_price / direct_median_price - 1) * 100, 1)
    return {
        "direct_median_price": direct_median_price,
        "aspirational_median_price": aspirational_median_price,
        "direct_review_median": direct_review_median,
        "direct_rating_median": direct_rating_median,
        "primary_price_premium_pct_vs_direct": premium_pct,
        "primary_review_gap_vs_direct_median": round((direct_review_median or 0) - (primary["review_count"] or 0), 1),
        "primary_appeal_gap_vs_aspirational": round(
            (aspirational["listing_appeal_score"].median() or 0) - (primary["listing_appeal_score"] or 0), 1
        ),
    }


def recommended_titles() -> list[str]:
    return [
        "Selvanova 3BR for Families | Pools, parking, 10 min beach",
        "Spacious Selvanova 3BR | 4 pools, gym, private parking",
        "Quiet 3BR in Selvanova | Family-ready, self check-in",
        "3BR Playa base in Selvanova | Pools, AC, parking",
        "Family condo in Selvanova | 3BR, terrace, 10 min beach",
        "Selvanova 3BR retreat | 4 pools, kids club, parking",
        "Spacious Playa del Carmen 3BR | Selvanova, pools, gym",
        "Secure Selvanova 3BR | Terrace, pools, easy beach access",
        "3BR for groups in Selvanova | Parking, pools, AC",
        "Quiet family stay in Selvanova | 3BR, pools, 5th Ave by car",
    ]


def description_variants() -> list[dict[str, str]]:
    return [
        {
            "label": "Family-first",
            "en": (
                "Spacious 3-bedroom apartment in Selvanova Residencial, built for families who want a calmer Playa del Carmen base. "
                "You get 4 pools, gym access, private parking, self check-in, full kitchen, laundry, AC in every bedroom, and a private terrace. "
                "Best for guests with a car or rideshare budget who want more space, more comfort, and easier logistics than a small tourist-zone condo."
            ),
            "es": (
                "Departamento amplio de 3 recámaras en Selvanova Residencial, ideal para familias que buscan una base más tranquila en Playa del Carmen. "
                "Tienes acceso a 4 albercas, gimnasio, estacionamiento privado, llegada autónoma, cocina completa, lavandería, aire acondicionado en cada recámara y terraza privada. "
                "Es ideal para huéspedes con auto o presupuesto para rideshare que quieren más espacio, más comodidad y menos estrés que en un estudio turístico."
            ),
        },
        {
            "label": "Friends and group stays",
            "en": (
                "Traveling with friends or another couple? This Selvanova 3BR gives your group real separation, shared living space, pools, parking, and easy car access to the beach, Quinta Avenida, restaurants, and day trips."
            ),
            "es": (
                "¿Viajas con amigos o con otra pareja? Este 3BR en Selvanova ofrece privacidad real, áreas comunes cómodas, albercas, estacionamiento y acceso práctico en auto a la playa, Quinta Avenida, restaurantes y tours."
            ),
        },
        {
            "label": "Long-stay and practical base",
            "en": (
                "A practical Riviera Maya launchpad for longer stays: reliable self check-in, workspace, strong comfort cues, laundry, kitchen, AC, parking, and a residential setting that feels calmer after beach or park days."
            ),
            "es": (
                "Una base práctica en la Riviera Maya para estancias más largas: llegada autónoma, área de trabajo, lavandería, cocina, aire acondicionado, estacionamiento y un entorno residencial que se siente más tranquilo después de un día de playa o parques."
            ),
        },
    ]


def first_10_seconds_bullets() -> list[str]:
    return [
        "3 bedrooms, 2 baths, up to 6 guests: clear fit for families and friend groups.",
        "Quiet Selvanova residential setting with 4 pools, gym, kids club, BBQ areas, and private parking.",
        "10 minutes by car to the beach and Quinta Avenida: honest location framing, not a beach-strip promise.",
        "Self check-in, full kitchen, laundry, AC in every bedroom, and large TV room reduce booking anxiety fast.",
        "Best for guests who want more space, calmer nights, and easier logistics than a compact downtown condo.",
    ]


def guest_segments() -> list[dict[str, str]]:
    return [
        {
            "segment": "Families",
            "positioning": "Lead with 3BR layout, pools, kids club, private parking, kitchen, and sleep comfort.",
            "objections": "Clarify that the beach is about 10 minutes by car, not walkable beachfront.",
            "must_show": "Beds by room, pools, terrace, dining table, parking, self check-in.",
        },
        {
            "segment": "Friend groups",
            "positioning": "Sell private bedrooms plus shared living and easy rides to Quinta.",
            "objections": "Remove uncertainty around parking, ride-share ease, and sleeping layout.",
            "must_show": "Living room, bedroom separation, pool, outdoor dining, smart TV.",
        },
        {
            "segment": "Longer stays",
            "positioning": "Promote kitchen, laundry, workspace, AC, calm residential setting, nearby shopping.",
            "objections": "Publish Wi-Fi speed and remote-work-ready surface.",
            "must_show": "Workspace, Wi-Fi speed screenshot, washer/dryer, kitchen storage, parking.",
        },
        {
            "segment": "Park and mobility travelers",
            "positioning": "Frame the unit as a practical launchpad for beach days, parks, cenotes, and town nights.",
            "objections": "Be explicit that a car or rideshare is the easiest fit.",
            "must_show": "Parking, self check-in, calm arrival, practical location copy.",
        },
        {
            "segment": "Value-seeking space buyers",
            "positioning": "Compare implicitly against paying for multiple hotel rooms or a cramped 2BR.",
            "objections": "Demonstrate why the inland location is worth the trade for space and amenities.",
            "must_show": "Square-meter feel, terrace, bed plan, pools, family amenities.",
        },
    ]


def photo_shot_list() -> list[str]:
    return [
        "Bright living room plus terrace hero shot with the apartment feeling open, not cropped.",
        "One clean pool lifestyle image that feels family-ready, not just generic amenities.",
        "Primary bedroom with bed size and natural light clearly visible.",
        "Second and third bedroom shots that prove the group sleeping plan immediately.",
        "Kitchen plus dining setup ready for a real meal, not a detail close-up.",
        "Private parking and controlled-access entry shot to reduce mobility and safety anxiety.",
        "Workspace/Wi-Fi proof image, ideally with a speed-test screen.",
        "A practical local-context image or caption card: 10 min by car to beach and Quinta, shopping nearby.",
    ]


def pricing_recommendations(primary: pd.Series, direct: pd.DataFrame) -> list[dict[str, str]]:
    direct_median = direct["nightly_price_mxn"].median()
    premium_pct = None
    if pd.notna(primary["nightly_price_mxn"]) and pd.notna(direct_median) and direct_median:
        premium_pct = round((primary["nightly_price_mxn"] / direct_median - 1) * 100, 1)
    nightly_note = (
        f"Observed 2-night search pricing puts the listing about {premium_pct}% above the direct-comp median."
        if premium_pct is not None
        else "Observed nightly-price comparison is limited; use live host dashboard pricing before changing rates."
    )
    return [
        {
            "change": "Hold a premium only when trust improves",
            "why": nightly_note + " With only 4 reviews, premium pricing needs stronger photo and trust proof than higher-social-proof Selvanova rivals.",
            "impact": "ADR and conversion",
        },
        {
            "change": "Test a lower weekend entry point until review count reaches double digits",
            "why": "A slightly more compelling first-booking price can reduce review-count drag and accelerate ranking-safe social proof.",
            "impact": "Occupancy, ranking, reviews",
        },
        {
            "change": "Audit fee load inside the host dashboard",
            "why": "Search results show fee-inclusive totals, but exact fee lines were not exposed in the listing payload. If the all-in total feels high versus nearby 3BRs, conversion will suffer before guests even click.",
            "impact": "Conversion and occupancy",
        },
        {
            "change": "Keep self check-in and clarify it visually",
            "why": "This is already a conversion asset. It reduces arrival friction and matters more in a car-based residential location.",
            "impact": "Conversion, reviews",
        },
        {
            "change": "Review cancellation setting for competitiveness",
            "why": "Exact cancellation terms were not exposed publicly here. If your setting is stricter than nearby family-group comps, a more flexible option can help a low-review listing compete.",
            "impact": "Conversion and ranking competitiveness",
        },
    ]


def action_plan(primary: pd.Series, market_summary: dict[str, Any]) -> list[dict[str, Any]]:
    premium_note = (
        f"Search pricing is roughly {market_summary['primary_price_premium_pct_vs_direct']}% above the direct-comp median."
        if market_summary.get("primary_price_premium_pct_vs_direct") is not None
        else "Observed pricing suggests the listing is competing for a premium slot without deep social proof yet."
    )
    return [
        {
            "window": "0-7 days",
            "change": "Verify and remove any inaccurate amenity, especially 'Frente al agua', if it is not literally true.",
            "why": "An inland Selvanova apartment should not risk guest disappointment with a waterfront-type amenity signal.",
            "evidence": "Observed on the public Airbnb amenity list.",
            "impact": "Reviews, conversion, policy safety",
            "confidence": "High",
            "difficulty": "Low",
        },
        {
            "window": "0-7 days",
            "change": "Replace the headline and first-screen copy with a fit-led version: 3BR, pools, parking, self check-in, 10 min by car.",
            "why": "Current title is more generic and less trust-building than the best Selvanova messaging patterns.",
            "evidence": "Observed title plus nearby comp positioning.",
            "impact": "Conversion",
            "confidence": "High",
            "difficulty": "Low",
        },
        {
            "window": "0-7 days",
            "change": "Reorder the first 8 photos to show space, pool, primary bedroom, kitchen, second/third bedroom, parking/security, terrace, lifestyle.",
            "why": "The apartment needs to win the 'will my group fit comfortably?' decision in seconds.",
            "evidence": "Photo-order patterns and search-result hero signals.",
            "impact": "Conversion, CTR",
            "confidence": "High",
            "difficulty": "Medium",
        },
        {
            "window": "0-7 days",
            "change": "Add Wi-Fi speed proof and workspace proof to the gallery and description.",
            "why": "Selvanova also competes for longer stays and remote/hybrid travelers. Right now the Wi-Fi benefit is underspecified.",
            "evidence": "Workspace amenity is present; speed proof is not visible.",
            "impact": "Occupancy, conversion",
            "confidence": "Medium",
            "difficulty": "Low",
        },
        {
            "window": "8-30 days",
            "change": "Push for the next 8-12 high-quality reviews with a tighter arrival guide, local guidebook, and post-stay feedback loop.",
            "why": premium_note,
            "evidence": "4 reviews versus stronger Selvanova rivals with far deeper social proof.",
            "impact": "Conversion, ranking, ADR",
            "confidence": "High",
            "difficulty": "Medium",
        },
        {
            "window": "8-30 days",
            "change": "Tune the price ladder to earn more clicks before raising back to premium.",
            "why": "A newer listing can monetise more effectively by trading a small amount of ADR for review momentum and occupancy proof.",
            "evidence": "Observed direct-comp price and review spread.",
            "impact": "Occupancy, reviews, ranking",
            "confidence": "Medium",
            "difficulty": "Medium",
        },
        {
            "window": "8-30 days",
            "change": "Build a family-ready trust stack: crib/high chair only if real, beach towels/cooler, kitchen starter kit, arrival video.",
            "why": "This listing naturally fits families and groups. Small operational touches create the next wave of review tags.",
            "evidence": "Review tags already lean toward hospitality, comfort, family, sleep, and amenities.",
            "impact": "Reviews, conversion",
            "confidence": "Medium",
            "difficulty": "Medium",
        },
        {
            "window": "31-90 days",
            "change": "A/B test cover-photo concepts between interior-space hero and pool-lifestyle hero.",
            "why": "The winning image should improve click-through rate in search without discounting.",
            "evidence": "Observed competitive cover-photo patterns and the listing's current premium position.",
            "impact": "CTR, conversion, ranking",
            "confidence": "Medium",
            "difficulty": "Medium",
        },
        {
            "window": "31-90 days",
            "change": "Strengthen authority cues around hosting consistency: guidebook polish, repeated review themes, cohost responsiveness, and cleaner operational scripts.",
            "why": "Trust is the main gap versus established Selvanova winners, not raw amenity count.",
            "evidence": "Observed host age/review count gap versus aspirational comps.",
            "impact": "Reviews, ADR, conversion",
            "confidence": "High",
            "difficulty": "Medium",
        },
        {
            "window": "31-90 days",
            "change": "Re-check cancellation, minimum-night, and fee settings against live competitors inside the host dashboard.",
            "why": "AirDNA metrics and exact public cancellation text were blocked, so the final monetisation edge must be tuned with dashboard-side settings.",
            "evidence": "Public extraction gap plus search-result total-price spread.",
            "impact": "Conversion, occupancy, ADR",
            "confidence": "Medium",
            "difficulty": "Low",
        },
    ]


def quick_wins() -> list[str]:
    return [
        "Verify the 'Frente al agua' amenity immediately; remove it if inaccurate.",
        "Change the title from generic luxury language to fit-led Selvanova positioning.",
        "Move pool, living room, and bedroom proof into the first 5 photos.",
        "Publish a Wi-Fi speed screenshot and workspace photo.",
        "State '10 minutes by car to the beach and Quinta' exactly and early.",
        "Lead with private parking and self check-in in the first screen.",
        "Add room-by-room bed labels to captions or description.",
        "Use review themes like comfort, hospitality, family, and sleep in copy without copying guest text.",
        "Sharpen family/group positioning instead of trying to sound beachfront.",
        "Audit fee load and weekend entry pricing before pushing ADR higher.",
    ]


def build_findings(
    primary: pd.Series,
    direct: pd.DataFrame,
    aspirational: pd.DataFrame,
    market_summary: dict[str, Any],
    airdna_snapshot: dict[str, Any] | None = None,
) -> list[str]:
    findings = []
    if market_summary.get("primary_price_premium_pct_vs_direct") is not None:
        findings.append(
            f"Your observed nightly search price sits about {market_summary['primary_price_premium_pct_vs_direct']}% above the direct-comp median, but the listing has only {int(primary['review_count'] or 0)} reviews."
        )
    if airdna_snapshot:
        top_listings = airdna_snapshot.get("top_listings") or []
        if top_listings:
            top5 = top_listings[:5]
            top_rev_avg = statistics.mean(item["annual_revenue_mxn"] for item in top5)
            top_occ_avg = statistics.mean(item["occupancy_pct"] for item in top5)
            top_adr_avg = statistics.mean(item["adr_mxn"] for item in top5)
            findings.append(
                "AirDNA confirms the micro-market gap is real: the top Selvanova / Mision de las Flores 3BR listings average roughly "
                f"{compact_currency(top_rev_avg)} annual revenue with about {top_occ_avg:.0f}% occupancy and {compact_currency(top_adr_avg)} ADR."
            )
        overview = airdna_snapshot.get("overview_metrics") or {}
        if overview:
            findings.append(
                "The submarket itself is middling, not weak: score 59, average annual revenue about "
                f"{compact_currency(overview.get('annual_revenue_mxn'))}, ADR about {compact_currency(overview.get('adr_mxn'))}, and occupancy {overview.get('occupancy_pct')}%."
            )
    findings.append(
        "Trust, not amenity count, is the main monetisation gap: nearby Selvanova winners pair stronger review depth with clearer fit messaging."
    )
    findings.append(
        "The listing already has major conversion assets: 3 bedrooms, 4 pools, gym, parking, self check-in, and family-group sleep fit."
    )
    findings.append(
        "The public amenity list currently shows 'Frente al agua', which looks mismatched for an inland Selvanova apartment and should be verified."
    )
    aspirational_pattern = Counter()
    for _, row in aspirational.iterrows():
        for word in normalize_words((row.get("title") or "") + " " + (row.get("description") or "")):
            aspirational_pattern[word] += 1
    words = [word for word, _ in aspirational_pattern.most_common(6)]
    findings.append(
        "Aspirational nearby winners repeatedly anchor around comfort, pools, family fit, parking, and calm practical access instead of pretending to be beachfront."
        + (f" Common keyword pattern: {', '.join(words)}." if words else "")
    )
    return findings


def build_blocked_data(airdna_available: bool) -> list[str]:
    base = [
        "Exact Airbnb cancellation-policy text was not exposed in the public listing payload.",
        "Exact cleaning-fee and tax line items were not consistently exposed on public listing pages; search results showed fee-inclusive totals only.",
        "Public review payloads exposed review tags and category ratings more reliably than full review text.",
        "No host-dashboard-only signals were available: impression share, click-through rate, conversion rate, or booking lead-time data.",
    ]
    if airdna_available:
        return [
            "AirDNA submarket overview pages were accessible, but the listing-specific AirDNA page and raw API response bodies were not exported directly from the browser session.",
            "Some AirDNA panels show abbreviated currency displays; values are cited as observed from the interface rather than treated as fully normalized exports unless otherwise noted.",
        ] + base
    return [
        "AirDNA market/listing metrics were blocked by an authentication wall in the available browser session.",
    ] + base


def html_metric(value: Any, suffix: str = "", decimals: int = 1) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "Unavailable"
    if isinstance(value, (int, np.integer)):
        return f"{value}{suffix}"
    if isinstance(value, (float, np.floating)):
        return f"{value:.{decimals}f}{suffix}"
    return f"{value}{suffix}"


def currency(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "Unavailable"
    return f"${value:,.0f} MXN"


def compact_currency(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "Unavailable"
    value = float(value)
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        whole = value / 1_000
        return f"${whole:.0f}K" if whole >= 100 else f"${whole:.1f}K"
    return f"${value:,.0f}"


def pct_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "Unavailable"
    value = float(value)
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"


def pill(label: str, tone: str = "neutral") -> str:
    return f'<span class="pill pill-{tone}">{escape(label)}</span>'


def dataframe_to_html(df: pd.DataFrame, columns: list[str], money_cols: set[str], score_cols: set[str]) -> str:
    header = "".join(f"<th>{escape(col.replace('_', ' ').title())}</th>" for col in columns)
    rows = []
    for _, row in df.iterrows():
        cells = []
        for col in columns:
            value = row.get(col)
            if col in money_cols:
                display = currency(value)
            elif col in score_cols:
                display = html_metric(value)
            elif col == "distance_km":
                display = html_metric(value, " km")
            elif isinstance(value, list):
                display = escape(", ".join([str(item) for item in value]))
            else:
                display = escape(str(value)) if value not in (None, np.nan) else "Unavailable"
            cells.append(f"<td>{display}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table class='report-table'><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def scatter_svg(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    label_col: str,
    highlight_room_id: str,
    title: str,
    x_label: str,
    y_label: str,
) -> str:
    plot_df = df[[x_col, y_col, label_col, "room_id", "role"]].dropna().copy()
    if plot_df.empty:
        return "<div class='empty-chart'>Chart unavailable</div>"

    width = 760
    height = 360
    margin = {"left": 70, "right": 20, "top": 30, "bottom": 50}
    plot_width = width - margin["left"] - margin["right"]
    plot_height = height - margin["top"] - margin["bottom"]
    x_min = float(plot_df[x_col].min())
    x_max = float(plot_df[x_col].max())
    y_min = float(plot_df[y_col].min())
    y_max = float(plot_df[y_col].max())
    if math.isclose(x_min, x_max):
        x_max += 1
    if math.isclose(y_min, y_max):
        y_max += 1

    def sx(value: float) -> float:
        return margin["left"] + (value - x_min) / (x_max - x_min) * plot_width

    def sy(value: float) -> float:
        return margin["top"] + plot_height - (value - y_min) / (y_max - y_min) * plot_height

    palette = {
        "primary": "#b07a00",
        "direct": "#0b7a75",
        "secondary": "#5b6470",
        "aspirational": "#d1495b",
    }
    points = []
    for _, row in plot_df.iterrows():
        role = row["role"]
        color = palette.get(role, "#5b6470")
        radius = 7 if row["room_id"] == highlight_room_id else 5
        stroke = "#111111" if row["room_id"] == highlight_room_id else "white"
        stroke_width = 2 if row["room_id"] == highlight_room_id else 1
        label = escape(str(row[label_col]))
        points.append(
            f'<g><circle cx="{sx(row[x_col]):.1f}" cy="{sy(row[y_col]):.1f}" r="{radius}" fill="{color}" '
            f'stroke="{stroke}" stroke-width="{stroke_width}"></circle>'
            f'<title>{label}</title></g>'
        )

    x_ticks = []
    for idx in range(5):
        value = x_min + (x_max - x_min) * idx / 4
        x = sx(value)
        x_ticks.append(
            f'<line x1="{x:.1f}" y1="{margin["top"]}" x2="{x:.1f}" y2="{margin["top"] + plot_height}" stroke="#e0d8c8" stroke-dasharray="2 4"></line>'
            f'<text x="{x:.1f}" y="{height - 16}" text-anchor="middle" fill="#594c38" font-size="11">{value:.0f}</text>'
        )
    y_ticks = []
    for idx in range(5):
        value = y_min + (y_max - y_min) * idx / 4
        y = sy(value)
        y_ticks.append(
            f'<line x1="{margin["left"]}" y1="{y:.1f}" x2="{margin["left"] + plot_width}" y2="{y:.1f}" stroke="#e0d8c8" stroke-dasharray="2 4"></line>'
            f'<text x="18" y="{y + 4:.1f}" text-anchor="start" fill="#594c38" font-size="11">{value:.0f}</text>'
        )

    return f"""
    <svg viewBox="0 0 {width} {height}" class="chart-svg" role="img" aria-label="{escape(title)}">
      <rect x="0" y="0" width="{width}" height="{height}" rx="18" fill="#fffaf2"></rect>
      <text x="{margin['left']}" y="18" font-size="16" fill="#1f2933" font-weight="700">{escape(title)}</text>
      {''.join(x_ticks)}
      {''.join(y_ticks)}
      <line x1="{margin['left']}" y1="{margin['top'] + plot_height}" x2="{margin['left'] + plot_width}" y2="{margin['top'] + plot_height}" stroke="#574737"></line>
      <line x1="{margin['left']}" y1="{margin['top']}" x2="{margin['left']}" y2="{margin['top'] + plot_height}" stroke="#574737"></line>
      {''.join(points)}
      <text x="{margin['left'] + plot_width / 2}" y="{height - 2}" text-anchor="middle" fill="#594c38" font-size="12">{escape(x_label)}</text>
      <text x="16" y="{margin['top'] + plot_height / 2}" transform="rotate(-90 16 {margin['top'] + plot_height / 2})" text-anchor="middle" fill="#594c38" font-size="12">{escape(y_label)}</text>
    </svg>
    """


def bar_svg(df: pd.DataFrame, label_col: str, value_col: str, title: str, highlight_room_id: str) -> str:
    plot_df = df[[label_col, value_col, "room_id", "role"]].dropna().copy().head(12)
    if plot_df.empty:
        return "<div class='empty-chart'>Chart unavailable</div>"
    width = 760
    row_height = 26
    height = 60 + len(plot_df) * row_height
    max_value = float(plot_df[value_col].max()) or 1
    palette = {
        "primary": "#b07a00",
        "direct": "#0b7a75",
        "secondary": "#5b6470",
        "aspirational": "#d1495b",
    }
    rows = []
    for idx, (_, row) in enumerate(plot_df.iterrows()):
        y = 34 + idx * row_height
        label = escape(str(row[label_col])[:42])
        value = float(row[value_col])
        bar_width = 420 * value / max_value
        color = palette.get(row["role"], "#5b6470")
        stroke = "#111111" if row["room_id"] == highlight_room_id else "none"
        rows.append(
            f'<text x="18" y="{y + 11}" font-size="11" fill="#1f2933">{label}</text>'
            f'<rect x="300" y="{y}" width="{bar_width:.1f}" height="14" rx="7" fill="{color}" stroke="{stroke}" stroke-width="1.5"></rect>'
            f'<text x="{730}" y="{y + 11}" text-anchor="end" font-size="11" fill="#1f2933">{value:.1f}</text>'
        )
    return f"""
    <svg viewBox="0 0 {width} {height}" class="chart-svg" role="img" aria-label="{escape(title)}">
      <rect x="0" y="0" width="{width}" height="{height}" rx="18" fill="#fffaf2"></rect>
      <text x="18" y="20" font-size="16" fill="#1f2933" font-weight="700">{escape(title)}</text>
      {''.join(rows)}
    </svg>
    """


def insight_cards(
    primary: pd.Series,
    market_summary: dict[str, Any],
    airdna_snapshot: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    premium = market_summary.get("primary_price_premium_pct_vs_direct")
    premium_text = f"{premium}% vs direct median" if premium is not None else "Premium unclear"
    cards = [
        {
            "label": "Price Position",
            "value": premium_text,
            "detail": "Observed nightly search-rate proxy vs direct Selvanova-like comps.",
        },
        {
            "label": "Review Depth",
            "value": f"{int(primary['review_count'] or 0)} reviews",
            "detail": "Perfect 5.0 rating, but still early-stage social proof.",
        },
        {
            "label": "Trust Gap",
            "value": f"{market_summary['primary_review_gap_vs_direct_median']:.0f} reviews below direct median",
            "detail": "Main monetisation blocker relative to established nearby winners.",
        },
        {
            "label": "Core Strength",
            "value": "3BR + pools + parking",
            "detail": "The product fit is strong; the page has to communicate it faster and more credibly.",
        },
    ]
    if airdna_snapshot:
        overview = airdna_snapshot.get("overview_metrics") or {}
        cards.append(
            {
                "label": "Submarket Baseline",
                "value": f"{overview.get('occupancy_pct', 'NA')}% occ. / {compact_currency(overview.get('adr_mxn'))} ADR",
                "detail": "Observed AirDNA overview for Mision de las Flores.",
            }
        )
    return cards


def build_airdna_context(airdna_snapshot: dict[str, Any] | None, primary: pd.Series) -> dict[str, Any]:
    if not airdna_snapshot:
        return {"available": False}

    overview = airdna_snapshot.get("overview_metrics") or {}
    occupancy = airdna_snapshot.get("occupancy_metrics") or {}
    revenue = airdna_snapshot.get("revenue_metrics") or {}
    rates = airdna_snapshot.get("rate_metrics") or {}
    top_listings = airdna_snapshot.get("top_listings") or []
    ai = airdna_snapshot.get("ai_guest_insights") or {}
    top_five = top_listings[:5]
    top_revenue_avg = statistics.mean(item["annual_revenue_mxn"] for item in top_five) if top_five else None
    top_occ_avg = statistics.mean(item["occupancy_pct"] for item in top_five) if top_five else None
    top_adr_avg = statistics.mean(item["adr_mxn"] for item in top_five) if top_five else None
    primary_rate = primary.get("nightly_price_mxn")
    rate_vs_submarket = None
    if primary_rate and overview.get("adr_mxn"):
        rate_vs_submarket = round((primary_rate / overview["adr_mxn"] - 1) * 100, 1)

    strategy_bullets = [
        f"Mision de las Flores scores {overview.get('submarket_score')} overall, with very high seasonality ({overview.get('seasonality_score')}) and strong regulation ({overview.get('regulation_score')}), so execution quality matters more than raw market tailwind.",
        f"Average submarket revenue is {compact_currency(overview.get('annual_revenue_mxn'))}, but top nearby 3BR listings cluster around {compact_currency(top_revenue_avg)} when they pair stronger trust and clearer family-group fit." if top_revenue_avg else "Top-listing revenue data was unavailable.",
        f"Observed lead time is {occupancy.get('booking_lead_time_days')} days and average stay is {occupancy.get('length_of_stay_days')} days, which supports sharper pre-arrival trust cues and practical long-stay positioning.",
        f"Public AirDNA guest themes reinforce the same pattern seen on Airbnb: security, pools, family comfort, quiet, and convenience win; distance from the beach remains the main objection to neutralize.",
    ]
    return {
        "available": True,
        "overview": overview,
        "occupancy": occupancy,
        "revenue": revenue,
        "rates": rates,
        "top_listings": top_listings,
        "top_submarkets": airdna_snapshot.get("top_submarkets") or [],
        "ai": ai,
        "top_revenue_avg": top_revenue_avg,
        "top_occ_avg": top_occ_avg,
        "top_adr_avg": top_adr_avg,
        "rate_vs_submarket": rate_vs_submarket,
        "strategy_bullets": strategy_bullets,
        "screenshots": airdna_snapshot.get("screenshots") or {},
        "submarket_url": airdna_snapshot.get("submarket_url") or AIRDNA_URL,
    }


def render_report(context: dict[str, Any]) -> str:
    template = jinja2.Template(
        """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Selvanova Competitive Report</title>
  <style>
    :root {
      --paper: #f7f2e8;
      --paper-2: #fbf8f2;
      --panel: rgba(255, 250, 243, 0.92);
      --panel-strong: #fff9f1;
      --ink: #1d252d;
      --muted: #5d6773;
      --gold: #b97c12;
      --gold-soft: rgba(185, 124, 18, 0.14);
      --teal: #145f5a;
      --teal-soft: rgba(20, 95, 90, 0.12);
      --sand: #eadcc7;
      --line: rgba(88, 73, 49, 0.14);
      --rose: #b64a53;
      --rose-soft: rgba(182, 74, 83, 0.12);
      --navy: #213145;
      --shadow: 0 24px 60px rgba(46, 34, 18, 0.10);
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
      background:
        radial-gradient(circle at top right, rgba(185, 124, 18, 0.16), transparent 22%),
        radial-gradient(circle at top left, rgba(20, 95, 90, 0.10), transparent 26%),
        linear-gradient(180deg, #fdfbf7 0%, var(--paper) 24%, #efe5d3 100%);
      color: var(--ink);
      line-height: 1.55;
    }
    a { color: inherit; }
    .wrap {
      width: min(1660px, calc(100vw - 28px));
      margin: 0 auto;
      padding: 20px 0 56px;
    }
    .layout {
      display: grid;
      grid-template-columns: minmax(340px, 380px) minmax(0, 1fr);
      gap: 22px;
      align-items: start;
    }
    .sidebar {
      position: sticky;
      top: 18px;
      align-self: start;
      display: grid;
      gap: 14px;
    }
    .nav-card,
    .hero,
    .section,
    .metric-card,
    .card,
    .chart-card,
    .evidence-card {
      border: 1px solid var(--line);
      background: var(--panel);
      box-shadow: var(--shadow);
      backdrop-filter: blur(14px);
      border-radius: 24px;
    }
    .nav-card {
      padding: 22px;
    }
    .brand {
      display: grid;
      gap: 8px;
    }
    .brand .eyebrow,
    .section .eyebrow {
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.16em;
      color: var(--gold);
    }
    .brand h1 {
      margin: 0;
      font-size: clamp(30px, 2.8vw, 44px);
      line-height: 0.93;
      letter-spacing: -0.05em;
      color: var(--navy);
      text-wrap: balance;
      overflow-wrap: anywhere;
      max-width: 10ch;
    }
    .brand p,
    .muted {
      color: var(--muted);
      font-size: 14px;
      margin: 0;
    }
    .toc {
      display: grid;
      gap: 6px;
      margin-top: 8px;
    }
    .toc a {
      text-decoration: none;
      padding: 10px 12px;
      border-radius: 14px;
      color: var(--navy);
      font-size: 13px;
      font-weight: 650;
      transition: transform 120ms ease, background 120ms ease;
      background: transparent;
      border: 1px solid transparent;
    }
    .toc a:hover {
      transform: translateX(2px);
      background: rgba(255,255,255,0.55);
      border-color: var(--line);
    }
    .toc span {
      color: var(--gold);
      margin-right: 8px;
      font-variant-numeric: tabular-nums;
    }
    .badge-row,
    .pill-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .hero {
      padding: 34px;
      background:
        linear-gradient(135deg, rgba(16, 44, 55, 0.97), rgba(185, 124, 18, 0.93)),
        linear-gradient(120deg, rgba(255,255,255,0.12), transparent 40%);
      color: #fff;
      margin-bottom: 18px;
    }
    .hero-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.12fr) minmax(340px, 0.88fr);
      gap: 24px;
      align-items: end;
    }
    .hero-copy {
      display: grid;
      gap: 12px;
    }
    .hero h2 {
      margin: 10px 0 8px;
      font-size: clamp(42px, 4.6vw, 82px);
      line-height: 0.87;
      letter-spacing: -0.06em;
      color: white;
      text-wrap: balance;
      max-width: 12ch;
    }
    .hero p {
      margin: 0;
      color: rgba(255,255,255,0.87);
      font-size: 17px;
      max-width: 58ch;
    }
    .hero-meta {
      display: grid;
      gap: 10px;
    }
    .hero-panel {
      background: rgba(255,255,255,0.12);
      border: 1px solid rgba(255,255,255,0.18);
      border-radius: 22px;
      padding: 18px;
    }
    .hero-panel h3 {
      margin: 0 0 10px;
      font-size: 13px;
      letter-spacing: 0.10em;
      text-transform: uppercase;
      color: rgba(255,255,255,0.78);
    }
    .hero-panel .big {
      font-size: 30px;
      font-weight: 800;
      line-height: 1;
      margin-bottom: 8px;
    }
    .summary-grid,
    .grid-4,
    .grid-3,
    .grid-2,
    .chart-grid,
    .card-grid {
      display: grid;
      gap: 16px;
    }
    .summary-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .grid-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .grid-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .grid-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .card-grid { grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
    .metric-card,
    .card,
    .chart-card,
    .evidence-card {
      padding: 18px;
    }
    .section {
      padding: 24px;
      margin-bottom: 18px;
    }
    .section-head {
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 16px;
      margin-bottom: 14px;
    }
    .section h2 {
      margin: 4px 0 0;
      font-size: 30px;
      line-height: 0.98;
      letter-spacing: -0.05em;
      color: var(--navy);
      text-wrap: balance;
    }
    h3 {
      margin: 0 0 10px;
      font-size: 16px;
      letter-spacing: -0.03em;
      color: var(--navy);
    }
    p { margin: 10px 0; color: var(--muted); }
    .metric {
      font-size: 30px;
      font-weight: 800;
      color: var(--navy);
      line-height: 1.05;
      margin-bottom: 8px;
    }
    .metric-label {
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--gold);
      margin-bottom: 8px;
      font-weight: 700;
    }
    .subtle {
      color: var(--muted);
      font-size: 14px;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      padding: 7px 11px;
      font-size: 12px;
      font-weight: 700;
      background: rgba(255,255,255,0.78);
      color: var(--navy);
      border: 1px solid rgba(255,255,255,0.1);
    }
    .pill-good { background: var(--teal-soft); color: var(--teal); border-color: rgba(20,95,90,0.12); }
    .pill-warn { background: var(--gold-soft); color: var(--gold); border-color: rgba(185,124,18,0.12); }
    .pill-risk { background: var(--rose-soft); color: var(--rose); border-color: rgba(182,74,83,0.12); }
    .pill-neutral { background: rgba(33,49,69,0.06); color: var(--navy); border-color: rgba(33,49,69,0.08); }
    .callout {
      border-left: 4px solid var(--gold);
      padding: 16px 18px;
      background: linear-gradient(180deg, rgba(185,124,18,0.08), rgba(185,124,18,0.04));
      border-radius: 16px;
      margin-top: 12px;
      color: #4d3d24;
    }
    .risk {
      border-left-color: var(--rose);
      background: linear-gradient(180deg, rgba(182,74,83,0.10), rgba(182,74,83,0.04));
      color: #6d2731;
    }
    .good {
      border-left-color: var(--teal);
      background: linear-gradient(180deg, rgba(20,95,90,0.10), rgba(20,95,90,0.04));
      color: #0b5751;
    }
    .table-wrap {
      overflow-x: auto;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.55);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      min-width: 860px;
    }
    th, td {
      padding: 12px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }
    th {
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--gold);
      background: rgba(255,255,255,0.75);
      position: sticky;
      top: 0;
      z-index: 1;
    }
    .chart-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
      align-items: start;
    }
    .chart-svg {
      width: 100%;
      height: auto;
      display: block;
      border-radius: 20px;
    }
    ul.flat {
      margin: 10px 0 0 0;
      padding-left: 18px;
      color: var(--muted);
    }
    ul.flat li { margin: 7px 0; }
    .action-table td, .action-table th { font-size: 12px; }
    .sources a {
      color: var(--teal);
      text-decoration: none;
      border-bottom: 1px solid rgba(11,122,117,0.25);
    }
    .small {
      font-size: 12px;
      color: var(--muted);
    }
    .split {
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      margin-top: 10px;
    }
    .split > div {
      flex: 1 1 220px;
      background: rgba(255,255,255,0.54);
      border-radius: 16px;
      padding: 14px;
      border: 1px solid var(--line);
    }
    .evidence-strip {
      display: grid;
      gap: 10px;
    }
    .evidence-card a {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      text-decoration: none;
      color: var(--teal);
      font-weight: 700;
    }
    .anchor {
      scroll-margin-top: 22px;
    }
    .mono {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
    }
    .section-divider {
      height: 1px;
      background: linear-gradient(90deg, transparent, var(--line), transparent);
      margin: 18px 0;
    }
    .caption {
      font-size: 12px;
      color: var(--muted);
      margin-top: 8px;
    }
    @media (max-width: 1200px) {
      .layout {
        grid-template-columns: 1fr;
      }
      .sidebar {
        position: static;
      }
      .brand h1 {
        max-width: none;
      }
      .toc {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }
    @media (max-width: 960px) {
      .hero-grid,
      .summary-grid,
      .grid-4,
      .grid-3,
      .grid-2,
      .chart-grid {
        grid-template-columns: 1fr;
      }
      .wrap {
        width: min(100vw - 18px, 1520px);
      }
      .hero,
      .section,
      .nav-card {
        border-radius: 20px;
        padding: 18px;
      }
      .toc {
        grid-template-columns: 1fr;
      }
      .hero h2 {
        max-width: none;
      }
      .hero p {
        font-size: 15px;
      }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="layout">
      <aside class="sidebar">
        <div class="nav-card">
          <div class="brand">
            <div class="eyebrow">Selvanova Strategy File</div>
            <h1>Revenue-grade competitive report</h1>
            <p>Micro-market reverse-engineering for <strong>{{ primary.title }}</strong>.</p>
          </div>
          <div class="section-divider"></div>
          <div class="pill-row">
            <span class="pill pill-good">Airbnb live extraction</span>
            {% if airdna.available %}
            <span class="pill pill-good">AirDNA submarket evidence</span>
            {% else %}
            <span class="pill pill-warn">AirDNA blocked</span>
            {% endif %}
            <span class="pill pill-neutral">Generated {{ generated_at }}</span>
          </div>
          <div class="section-divider"></div>
          <nav class="toc">
            <a href="#exec-summary"><span>01</span>Executive summary</a>
            <a href="#property-snapshot"><span>02</span>Property snapshot</a>
            <a href="#selvanova-market"><span>03</span>Selvanova market overview</a>
            <a href="#direct-comps"><span>04</span>Direct competitors</a>
            <a href="#aspirational-comps"><span>05</span>Aspirational competitors</a>
            <a href="#pricing-visuals"><span>06</span>Revenue & pricing visuals</a>
            <a href="#frontier"><span>07</span>Occupancy / ADR frontier</a>
            <a href="#amenity-gaps"><span>08</span>Amenity gap analysis</a>
            <a href="#review-intel"><span>09</span>Review intelligence</a>
            <a href="#photo-copy"><span>10</span>Photo & copy audit</a>
            <a href="#friction"><span>11</span>Booking friction</a>
            <a href="#segments"><span>12</span>Guest segments</a>
            <a href="#titles-copy"><span>13</span>Titles & rewritten copy</a>
            <a href="#photo-order"><span>14</span>Photo order & shot list</a>
            <a href="#pricing"><span>15</span>Pricing recommendations</a>
            <a href="#action-plan"><span>16</span>30/60/90 plan</a>
            <a href="#quick-wins"><span>17</span>Quick wins</a>
            <a href="#appendix"><span>18</span>Appendix</a>
          </nav>
        </div>

        <div class="evidence-card">
          <div class="eyebrow">Evidence quality</div>
          <h3>What this report can defend</h3>
          <ul class="flat">
            <li>Observed Airbnb listing attributes and search-price proxies</li>
            <li>Observed AirDNA submarket metrics for Mision de las Flores</li>
            <li>Explicitly labeled proxy scores where first-party revenue data is missing</li>
          </ul>
        </div>

        <div class="evidence-card">
          <div class="eyebrow">Artifact links</div>
          <div class="evidence-strip sources">
            {% for artifact in artifacts[:8] %}
            <a href="{{ artifact.href }}">{{ artifact.label }}</a>
            {% endfor %}
          </div>
        </div>
      </aside>

      <main>
        <section class="hero anchor" id="exec-summary">
          <div class="badge-row">
            <span class="pill pill-warn">Primary listing: {{ primary.title }}</span>
            {% if airdna.available %}
            <span class="pill pill-good">AirDNA submarket: {{ airdna.overview.submarket_score if airdna.overview.submarket_score else 'Observed' }} score</span>
            {% endif %}
          </div>
          <div class="hero-grid">
            <div class="hero-copy">
              <div class="eyebrow" style="color:rgba(255,255,255,0.72);">Executive readout</div>
              <h2>Top Selvanova winners are beating the market with trust, clarity, and practical family-group fit.</h2>
              <p>Your product is strong enough to compete. The monetisation gap is mostly page execution: your observed ask is premium, but your social proof is still thin and some benefits are under-sold while one visible amenity may be inaccurate.</p>
            </div>
            <div class="hero-meta">
              <div class="hero-panel">
                <h3>Primary tension</h3>
                <div class="big">{{ primary.nightly_price_display }}</div>
                <div class="small">Observed nightly search-price proxy with only {{ primary.review_count }} reviews.</div>
              </div>
              <div class="hero-panel">
                <h3>What top winners show</h3>
                <div class="big">{% if airdna.available %}{{ compact_currency(airdna.top_revenue_avg) }}{% else %}Unavailable{% endif %}</div>
                <div class="small">Average annual revenue across the top AirDNA 5 in this micro-market{% if airdna.available %}, with about {{ "%.0f"|format(airdna.top_occ_avg) }}% occupancy{% endif %}.</div>
              </div>
            </div>
          </div>
        </section>

        <section class="summary-grid">
          {% for card in insight_cards %}
          <div class="metric-card">
            <div class="metric-label">{{ card.label }}</div>
            <div class="metric">{{ card.value }}</div>
            <div class="subtle">{{ card.detail }}</div>
          </div>
          {% endfor %}
        </section>

        <section class="section anchor" id="property-snapshot">
          <div class="section-head">
            <div>
              <div class="eyebrow">2. Property snapshot</div>
              <h2>What the listing is selling today</h2>
            </div>
            <div class="small mono">{{ primary.listing_url }}</div>
          </div>
          <div class="grid-3">
            <div class="card">
              <h3>Observed core facts</h3>
              <ul class="flat">
                <li>{{ primary.guests }} guests, {{ primary.bedrooms }} bedrooms, {{ primary.beds }} beds, {{ primary.baths }} baths</li>
                <li>{{ primary.rating }} rating from {{ primary.review_count }} reviews</li>
                <li>{{ "Verified host profile" if primary.host_verified else "Host verification unavailable" }}; {{ primary.host_response_rate or "response-rate blurb unavailable" }}</li>
                <li>{{ "Self check-in visible" if primary.amenity_flags.self_checkin else "Self check-in weakly communicated" }}</li>
                <li>Observed location framing: {{ primary.location_subtitle }}</li>
              </ul>
            </div>
            <div class="card">
              <h3>What already works</h3>
              <div class="pill-row">
                {% for label in primary.good_pills %}
                  {{ label|safe }}
                {% endfor %}
              </div>
              <p>{{ primary.description_excerpt }}</p>
            </div>
            <div class="card">
              <h3>Trust and friction snapshot</h3>
              <ul class="flat">
                <li>Observed nightly search-price proxy: {{ primary.nightly_price_display }}</li>
                <li>Review themes: {{ primary.review_tags_display }}</li>
                <li>Check-in/out rules: {{ primary.checkin_checkout_display }}</li>
                <li>Cancellation visibility: {{ primary.cancellation_policy_display }}</li>
                <li>Fee visibility: {{ primary.fee_visibility_note }}</li>
              </ul>
            </div>
          </div>
        </section>

        <section class="section anchor" id="selvanova-market">
          <div class="section-head">
            <div>
              <div class="eyebrow">3. Selvanova market overview</div>
              <h2>AirDNA confirms this is a practical residential base, not a beach-strip market</h2>
            </div>
            <div class="small">Primary submarket: Mision de las Flores / Selvanova area</div>
          </div>
          {% if airdna.available %}
          <div class="grid-4">
            <div class="metric-card">
              <div class="metric-label">Submarket score</div>
              <div class="metric">{{ airdna.overview.submarket_score }}</div>
              <div class="subtle">Rental demand {{ airdna.overview.rental_demand_score }}, revenue growth {{ airdna.overview.revenue_growth_score }}, seasonality {{ airdna.overview.seasonality_score }}, regulation {{ airdna.overview.regulation_score }}.</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">Average revenue</div>
              <div class="metric">{{ compact_currency(airdna.overview.annual_revenue_mxn) }}</div>
              <div class="subtle">{{ pct_text(airdna.overview.annual_revenue_yoy_pct) }} past year</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">Average ADR</div>
              <div class="metric">{{ compact_currency(airdna.overview.adr_mxn) }}</div>
              <div class="subtle">{{ pct_text(airdna.overview.adr_yoy_pct) }} past year</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">Average occupancy</div>
              <div class="metric">{{ airdna.overview.occupancy_pct }}%</div>
              <div class="subtle">{{ pct_text(airdna.overview.occupancy_yoy_pct) }} past year across {{ airdna.overview.active_listings }} active listings</div>
            </div>
          </div>
          <div class="split">
            <div>
              <h3>AirDNA guest insight summary</h3>
              <p>{{ airdna.ai.overview }}</p>
            </div>
            <div>
              <h3>Strategic read</h3>
              <ul class="flat">
                {% for item in airdna.strategy_bullets %}
                <li>{{ item }}</li>
                {% endfor %}
              </ul>
            </div>
          </div>
          <div class="grid-3" style="margin-top:14px;">
            <div class="card">
              <h3>What guests love</h3>
              <ul class="flat">
                {% for item in airdna.ai.what_guests_love %}
                <li>{{ item }}</li>
                {% endfor %}
              </ul>
            </div>
            <div class="card">
              <h3>Expected amenities</h3>
              <ul class="flat">
                {% for item in airdna.ai.amenities %}
                <li>{{ item }}</li>
                {% endfor %}
              </ul>
            </div>
            <div class="card">
              <h3>Common objections</h3>
              <ul class="flat">
                {% for item in airdna.ai.complaints %}
                <li>{{ item }}</li>
                {% endfor %}
              </ul>
            </div>
          </div>
          <div class="grid-2" style="margin-top:16px;">
            <div class="card">
              <h3>Top submarkets in Playa del Carmen</h3>
              <div class="table-wrap">{{ airdna_top_submarkets_table|safe }}</div>
              <div class="caption">These are AirDNA interface values as displayed on the submarket overview page.</div>
            </div>
            <div class="card">
              <h3>Top-performing Selvanova / Mision listings</h3>
              <div class="table-wrap">{{ airdna_top_listings_table|safe }}</div>
              <div class="caption">These top performers are the closest evidence for the revenue frontier you are trying to join.</div>
            </div>
          </div>
          <p class="small sources">Observed AirDNA pages: <a href="artifacts/airdna_submarket_overview.png">overview screenshot</a>, <a href="artifacts/airdna_submarket_occupancy.png">occupancy screenshot</a>, and the browser-observed metric snapshot saved in <span class="mono">artifacts/airdna_submarket_snapshot.json</span>. Source URL: <a class="mono" href="{{ airdna.submarket_url }}">{{ airdna.submarket_url }}</a>.</p>
          {% else %}
          <div class="callout">AirDNA submarket data was not available in this run, so this section falls back to Airbnb-only evidence.</div>
          {% endif %}
        </section>

        <section class="section anchor" id="direct-comps">
          <div class="section-head">
            <div>
              <div class="eyebrow">4. Direct competitor table</div>
              <h2>Closest apartment / condo competition for the same booking mission</h2>
            </div>
          </div>
          <p>These direct comps prioritize Selvanova-like proximity, 3-bedroom family-group fit, and apartment/condo-style inventory. When strict apartment-only supply was too thin, the set widened to nearby residential equivalents and is flagged in the appendix.</p>
          <div class="table-wrap">{{ direct_table|safe }}</div>
        </section>

        <section class="section anchor" id="aspirational-comps">
          <div class="section-head">
            <div>
              <div class="eyebrow">5. Aspirational competitor table</div>
              <h2>Listings setting the bar for trust, clarity, and monetisation</h2>
            </div>
          </div>
          <p>Aspirational comps stay grounded in the same guest mission. They are useful because they show what stronger execution looks like without drifting into unrealistic luxury-villa inventory.</p>
          <div class="table-wrap">{{ aspirational_table|safe }}</div>
        </section>

        <section class="section anchor" id="pricing-visuals">
          <div class="section-head">
            <div>
              <div class="eyebrow">6. Revenue and pricing visuals</div>
              <h2>Where the current pricing story is vulnerable</h2>
            </div>
          </div>
          <p class="small">These plots combine observed Airbnb price points with review/trust and value scores. They are not substitutes for true host-dashboard conversion data, but they are directionally useful.</p>
          <div class="chart-grid">
            <div class="chart-card">{{ price_vs_trust_chart|safe }}</div>
            <div class="chart-card">{{ price_vs_value_chart|safe }}</div>
          </div>
        </section>

        <section class="section anchor" id="frontier">
          <div class="section-head">
            <div>
              <div class="eyebrow">7. Occupancy / ADR frontier</div>
              <h2>The report’s best estimate of the revenue frontier</h2>
            </div>
          </div>
          <div class="callout good">High-confidence interpretation: your listing is already priced like a stronger incumbent, but the trust stack still looks like a newer listing. That mismatch is the core frontier problem to fix.</div>
          <div class="chart-grid">
            <div class="chart-card">{{ occ_vs_price_chart|safe }}</div>
            <div class="chart-card">{{ direct_rank_chart|safe }}</div>
          </div>
        </section>

        <section class="section anchor" id="amenity-gaps">
          <div class="section-head">
            <div>
              <div class="eyebrow">8. Amenity gap analysis</div>
              <h2>What matters is not just having amenities, but proving the right ones quickly</h2>
            </div>
          </div>
          <div class="grid-2">
            <div class="card">
              <h3>Already strong</h3>
              <div class="pill-row">
                {% for label in primary.good_pills %}
                  {{ label|safe }}
                {% endfor %}
              </div>
            </div>
            <div class="card">
              <h3>Under-sold or risky</h3>
              <div class="pill-row">
                {% for label in primary.gap_pills %}
                  {{ label|safe }}
                {% endfor %}
              </div>
            </div>
          </div>
          <div class="split">
            <div>
              <h3>Must-have communication gaps</h3>
              <ul class="flat">
                <li>Wi‑Fi speed proof and workspace proof</li>
                <li>Parking clarity and arrival clarity</li>
                <li>Room-by-room sleeping fit</li>
                <li>Earlier explanation of who this place is best for</li>
              </ul>
            </div>
            <div>
              <h3>Low-cost perceived-value upgrades</h3>
              <ul class="flat">
                <li>Arrival guide with parking and route guidance</li>
                <li>Beach towels / cooler only if real and consistently stocked</li>
                <li>Family convenience kit if you can operationalize it cleanly</li>
                <li>Wi‑Fi screenshot, workspace image, and amenity captions</li>
              </ul>
            </div>
          </div>
        </section>

        <section class="section anchor" id="review-intel">
          <div class="section-head">
            <div>
              <div class="eyebrow">9. Review intelligence</div>
              <h2>What guests already reward, and what future complaints will probably be about</h2>
            </div>
          </div>
          <div class="grid-2">
            <div class="card">
              <h3>Recurring praise themes</h3>
              <ul class="flat">
                {% for item in primary.review_tag_lines %}
                <li>{{ item }}</li>
                {% endfor %}
              </ul>
            </div>
            <div class="card">
              <h3>Likely complaint themes to prevent</h3>
              <ul class="flat">
                {% if airdna.available %}
                  {% for item in airdna.ai.complaints %}
                  <li>{{ item }}</li>
                  {% endfor %}
                {% else %}
                  <li>Distance-to-beach expectation mismatch</li>
                  <li>Arrival uncertainty</li>
                  <li>Amenity proof gaps</li>
                {% endif %}
              </ul>
            </div>
          </div>
        </section>

        <section class="section anchor" id="photo-copy">
          <div class="section-head">
            <div>
              <div class="eyebrow">10. Photo and listing-copy audit</div>
              <h2>The listing needs to sell calm, spacious group comfort in the first 10 seconds</h2>
            </div>
          </div>
          <div class="grid-2">
            <div class="card">
              <h3>Observed photo story</h3>
              <p>The current gallery sells <strong>{{ primary.photo_story }}</strong>. Nearby winners hit a clearer emotional promise: more space, calmer nights, easier parking, and a practical family/group base.</p>
              <p class="small">Observed first five categories: {{ primary.first_five_categories }}</p>
            </div>
            <div class="card">
              <h3>Recommended visual promise</h3>
              <ul class="flat">
                <li><strong>Cover:</strong> bright, spacious living + terrace or living + dining frame</li>
                <li><strong>First sequence:</strong> space, pool, primary bedroom, kitchen, sleeping plan, parking/security</li>
                <li><strong>Caption theme:</strong> "3BR for families and groups, 4 pools, private parking, self check-in, 10 min by car."</li>
              </ul>
            </div>
          </div>
        </section>

        <section class="section anchor" id="friction">
          <div class="section-head">
            <div>
              <div class="eyebrow">11. Booking-friction audit</div>
              <h2>Where a guest could hesitate before pressing book</h2>
            </div>
          </div>
          <div class="callout {% if primary.risky_amenity %}risk{% else %}good{% endif %}">
            <strong>Primary friction callout:</strong> {{ primary.friction_callout }}
          </div>
          <ul class="flat">
            <li><strong>Fee friction:</strong> exact line-item fees were not exposed publicly, so compare your all-in total against nearby 3BR totals before trying to defend a premium.</li>
            <li><strong>Trust friction:</strong> 4 reviews is still light social proof for a premium-priced Selvanova option.</li>
            <li><strong>Location friction:</strong> the page should say "10 minutes by car" early, not just later in the description.</li>
            <li><strong>Amenity friction:</strong> prove Wi‑Fi, parking, sleeping fit, and security visually.</li>
          </ul>
        </section>

        <section class="section anchor" id="segments">
          <div class="section-head">
            <div>
              <div class="eyebrow">12. Guest-segment playbook</div>
              <h2>Sell to the guests Selvanova naturally fits best</h2>
            </div>
          </div>
          <div class="grid-3">
            {% for segment in guest_segments %}
            <div class="card">
              <h3>{{ segment.segment }}</h3>
              <p><strong>Positioning:</strong> {{ segment.positioning }}</p>
              <p><strong>Objection to remove:</strong> {{ segment.objections }}</p>
              <p><strong>Must show:</strong> {{ segment.must_show }}</p>
            </div>
            {% endfor %}
          </div>
        </section>

        <section class="section anchor" id="titles-copy">
          <div class="section-head">
            <div>
              <div class="eyebrow">13. Recommended listing titles and rewritten copy</div>
              <h2>Lead with fit, not generic luxury language</h2>
            </div>
          </div>
          <div class="grid-2">
            <div class="card">
              <h3>Title options</h3>
              <ul class="flat">
                {% for title in titles %}
                <li>{{ title }}</li>
                {% endfor %}
              </ul>
            </div>
            <div class="card">
              <h3>What guests should understand in 10 seconds</h3>
              <ul class="flat">
                {% for bullet in first_screen_bullets %}
                <li>{{ bullet }}</li>
                {% endfor %}
              </ul>
            </div>
          </div>
          <div class="grid-3" style="margin-top:14px;">
            {% for variant in description_variants %}
            <div class="card">
              <h3>{{ variant.label }}</h3>
              <p><strong>EN:</strong> {{ variant.en }}</p>
              <p><strong>ES:</strong> {{ variant.es }}</p>
            </div>
            {% endfor %}
          </div>
        </section>

        <section class="section anchor" id="photo-order">
          <div class="section-head">
            <div>
              <div class="eyebrow">14. Recommended photo order and missing shots</div>
              <h2>Build the click and the conversion in the same sequence</h2>
            </div>
          </div>
          <ul class="flat">
            {% for shot in photo_shot_list %}
            <li>{{ shot }}</li>
            {% endfor %}
          </ul>
        </section>

        <section class="section anchor" id="pricing">
          <div class="section-head">
            <div>
              <div class="eyebrow">15. Pricing / minimum-night / fee / cancellation recommendations</div>
              <h2>Monetise like a strong incumbent only after earning incumbent-level trust</h2>
            </div>
          </div>
          <ul class="flat">
            {% for item in pricing_recommendations %}
            <li><strong>{{ item.change }}:</strong> {{ item.why }} <em>Impact:</em> {{ item.impact }}.</li>
            {% endfor %}
          </ul>
        </section>

        <section class="section anchor" id="action-plan">
          <div class="section-head">
            <div>
              <div class="eyebrow">16. 30/60/90 day action plan</div>
              <h2>What to do now, next, and after the next review wave lands</h2>
            </div>
          </div>
          <div class="table-wrap">
            <table class="report-table action-table">
              <thead>
                <tr>
                  <th>Window</th>
                  <th>What to change</th>
                  <th>Why it matters</th>
                  <th>Evidence</th>
                  <th>Impact</th>
                  <th>Confidence</th>
                  <th>Difficulty</th>
                </tr>
              </thead>
              <tbody>
                {% for item in action_plan %}
                <tr>
                  <td>{{ item.window }}</td>
                  <td>{{ item.change }}</td>
                  <td>{{ item.why }}</td>
                  <td>{{ item.evidence }}</td>
                  <td>{{ item.impact }}</td>
                  <td>{{ item.confidence }}</td>
                  <td>{{ item.difficulty }}</td>
                </tr>
                {% endfor %}
              </tbody>
            </table>
          </div>
        </section>

        <section class="section anchor" id="quick-wins">
          <div class="section-head">
            <div>
              <div class="eyebrow">17. High-confidence quick wins</div>
              <h2>No-regret changes that should improve conversion quality fast</h2>
            </div>
          </div>
          <div class="grid-2">
            <div class="card">
              <ul class="flat">
                {% for item in quick_wins[:5] %}
                <li>{{ item }}</li>
                {% endfor %}
              </ul>
            </div>
            <div class="card">
              <ul class="flat">
                {% for item in quick_wins[5:] %}
                <li>{{ item }}</li>
                {% endfor %}
              </ul>
            </div>
          </div>
        </section>

        <section class="section anchor" id="appendix">
          <div class="section-head">
            <div>
              <div class="eyebrow">18. Appendix with raw data, assumptions, and data-quality notes</div>
              <h2>What was observed directly, what was inferred, and what remained blocked</h2>
            </div>
          </div>
          <div class="grid-2">
            <div class="card">
              <h3>Blocked or unavailable fields</h3>
              <ul class="flat">
                {% for item in blocked_data %}
                <li>{{ item }}</li>
                {% endfor %}
              </ul>
            </div>
            <div class="card">
              <h3>Observed artifacts</h3>
              <ul class="flat sources">
                {% for artifact in artifacts %}
                <li><a href="{{ artifact.href }}">{{ artifact.label }}</a></li>
                {% endfor %}
              </ul>
            </div>
          </div>
          <p class="small sources">Structured outputs: <span class="mono">output/selvanova_comps.csv</span>, <span class="mono">output/selvanova_comps.json</span>, <span class="mono">output/notes.md</span>. AirDNA submarket observations are saved in <span class="mono">output/artifacts/airdna_submarket_snapshot.json</span>.</p>
        </section>
      </main>
    </div>
  </div>
</body>
</html>
        """
    )
    return template.render(
        compact_currency=compact_currency,
        pct_text=pct_text,
        **context,
    )


def build_notes(
    primary: pd.Series,
    direct: pd.DataFrame,
    secondary: pd.DataFrame,
    aspirational: pd.DataFrame,
    blocked_data: list[str],
    search_urls: dict[str, str],
    airdna_snapshot: dict[str, Any] | None,
) -> str:
    lines = [
        "# Selvanova competitive report notes",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- Primary listing: {PRIMARY_URL}",
        f"- AirDNA target URL: {AIRDNA_URL}",
        "",
        "## Search URLs fetched",
    ]
    for name, url in search_urls.items():
        lines.append(f"- `{name}`: {url}")
    lines.extend(
        [
            "",
            "## Blocked data",
            *[f"- {item}" for item in blocked_data],
            "",
            "## AirDNA submarket snapshot",
        ]
    )
    if airdna_snapshot:
        overview = airdna_snapshot.get("overview_metrics") or {}
        lines.extend(
            [
                f"- Submarket: {airdna_snapshot.get('submarket_name')} / {airdna_snapshot.get('market_name')}",
                f"- Score: {overview.get('submarket_score')}",
                f"- Average revenue: {compact_currency(overview.get('annual_revenue_mxn'))} ({pct_text(overview.get('annual_revenue_yoy_pct'))})",
                f"- Average ADR: {compact_currency(overview.get('adr_mxn'))} ({pct_text(overview.get('adr_yoy_pct'))})",
                f"- Average occupancy: {overview.get('occupancy_pct')}% ({pct_text(overview.get('occupancy_yoy_pct'))})",
                f"- Active listings: {overview.get('active_listings')} ({pct_text(overview.get('active_listings_yoy_pct'))})",
            ]
        )
    else:
        lines.append("- AirDNA submarket snapshot unavailable")
    lines.extend(
        [
            "",
            "## Primary listing summary",
            f"- Title: {primary['title']}",
            f"- Layout: {primary['guests']} guests / {primary['bedrooms']} bedrooms / {primary['beds']} beds / {primary['baths']} baths",
            f"- Rating: {primary['rating']} from {primary['review_count']} reviews",
            f"- Nightly search-price proxy: {currency(primary['nightly_price_mxn'])}",
            f"- Review tags: {', '.join(primary['review_tags'] or [])}",
            "",
            "## Direct comp room IDs",
            *[f"- {row.room_id}: {row.title}" for row in direct.itertuples()],
            "",
            "## Secondary comp room IDs",
            *[f"- {row.room_id}: {row.title}" for row in secondary.itertuples()],
            "",
            "## Aspirational comp room IDs",
            *[f"- {row.room_id}: {row.title}" for row in aspirational.itertuples()],
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    ensure_dirs()
    session = session_factory()
    airdna_snapshot = read_json_if_exists(AIRDNA_SNAPSHOT_ARTIFACT)

    search_candidate_rows: list[dict[str, Any]] = []
    fetched_search_artifacts = []

    for name, url in SEARCH_URLS.items():
        artifact_path = SEARCH_HTML_DIR / f"{name}.html"
        fetch_result = fetch_html(session, url, artifact_path)
        fetched_search_artifacts.append(fetch_result)
        deferred = extract_script_json(fetch_result.html, "data-deferred-state-0")
        if not deferred:
            continue
        entry = next(
            (item for item in deferred.get("niobeClientData", []) if str(item[0]).startswith("StaysSearch:")),
            None,
        )
        if entry is None:
            continue
        search_root = entry[1]["data"]["presentation"]["staysSearch"]
        result_sets = [
            search_root.get("results", {}).get("searchResults") or [],
            search_root.get("mapResults", {}).get("mapSearchResults") or [],
        ]
        for result_set in result_sets:
            for result in result_set:
                parsed = parse_search_result(result, name, url)
                if parsed.get("room_id"):
                    search_candidate_rows.append(parsed)

    merged_candidates = merge_candidate_rows(search_candidate_rows)
    candidate_df = pd.DataFrame(merged_candidates)
    if candidate_df.empty:
        raise SystemExit("No Airbnb candidates were extracted from search pages.")
    candidate_df = trim_candidate_pool(candidate_df)

    room_ids = sorted(set(candidate_df["room_id"].dropna().tolist() + [PRIMARY_ROOM_ID]))
    listing_rows = []
    fetched_listing_artifacts = []
    for room_id in room_ids:
        url = (
            f"https://www.airbnb.mx/rooms/{room_id}"
            f"?check_in={CHECK_IN}&check_out={CHECK_OUT}&adults=1&guests=1&enable_auto_translate=false"
        )
        artifact_path = LISTING_HTML_DIR / f"{room_id}.html"
        fetch_result = fetch_html(session, url, artifact_path)
        fetched_listing_artifacts.append(fetch_result)
        parsed_listing = parse_listing_payload(room_id, url, fetch_result.html)
        parsed_listing["listing_html_artifact"] = fetch_result.artifact_path
        listing_rows.append(parsed_listing)

    listing_df = pd.DataFrame(listing_rows)
    merged_df = listing_df.merge(candidate_df, how="left", on="room_id", suffixes=("", "_search"))
    primary_mask = merged_df["room_id"] == PRIMARY_ROOM_ID
    if primary_mask.any() and pd.isna(merged_df.loc[primary_mask, "search_base_nightly_mxn"]).all():
        for key, value in PRIMARY_SEARCH_PRICE_FALLBACK.items():
            merged_df.loc[primary_mask, key] = value

    merged_df["search_badges"] = merged_df["search_badges"].apply(
        lambda value: value if isinstance(value, list) else []
    )
    merged_df["distance_km"] = merged_df.apply(
        lambda row: haversine_km(row.get("lat"), row.get("lng"), PRIMARY_LAT, PRIMARY_LNG),
        axis=1,
    )
    merged_df = build_scores(merged_df)

    merged_df["title"] = merged_df["title"].fillna(merged_df["search_subtitle"]).fillna(merged_df["search_name"])
    merged_df["nightly_price_display"] = merged_df["nightly_price_mxn"].apply(currency)
    merged_df["distance_km"] = merged_df["distance_km"].round(2)

    direct, secondary, aspirational = select_comp_sets(merged_df)
    merged_df["role"] = "secondary"
    merged_df.loc[merged_df["room_id"] == PRIMARY_ROOM_ID, "role"] = "primary"
    merged_df.loc[merged_df["room_id"].isin(direct["room_id"]), "role"] = "direct"
    merged_df.loc[merged_df["room_id"].isin(aspirational["room_id"]), "role"] = "aspirational"

    primary = merged_df[merged_df["room_id"] == PRIMARY_ROOM_ID].iloc[0].copy()
    market_summary = compute_market_summary(primary, direct, aspirational)
    airdna_context = build_airdna_context(airdna_snapshot, primary)

    def with_role(df: pd.DataFrame) -> pd.DataFrame:
        return merged_df[merged_df["room_id"].isin(df["room_id"])][scorecard_columns()].sort_values(
            by=["revenue_strength_proxy_score", "trust_review_strength_score"],
            ascending=[False, False],
        )

    direct_table_df = with_role(direct)
    aspirational_table_df = with_role(aspirational)

    primary_amenity_flags = primary["amenity_flags"] or {}
    primary_good_pills = [
        pill("3 bedrooms", "good"),
        pill("4 pools", "good") if primary_amenity_flags.get("pool") else pill("Pool not visible", "warn"),
        pill("Private parking", "good") if primary_amenity_flags.get("parking") else pill("Parking unclear", "warn"),
        pill("Self check-in", "good") if primary_amenity_flags.get("self_checkin") else pill("Self check-in weak", "warn"),
        pill("Workspace", "good") if primary_amenity_flags.get("workspace") else pill("Workspace proof missing", "warn"),
        pill("Gym access", "good") if primary_amenity_flags.get("gym") else pill("Gym unclear", "warn"),
    ]
    primary_gap_pills = [
        pill("Verify waterfront amenity", "risk") if "Frente al agua" in (primary["amenities"] or []) else pill("Amenity accuracy audit", "warn"),
        pill("Publish Wi-Fi speed", "warn"),
        pill("More review depth needed", "warn"),
        pill("Rebuild first 5 photos", "warn"),
        pill("Lead with parking + 10 min by car", "warn"),
    ]
    primary["good_pills"] = primary_good_pills
    primary["gap_pills"] = primary_gap_pills
    primary["description_excerpt"] = (primary["description"] or "")[:340] + ("..." if len(primary["description"] or "") > 340 else "")
    primary["review_tags_display"] = ", ".join(primary["review_tags"] or []) if primary["review_tags"] else "Unavailable"
    primary["checkin_checkout_display"] = (
        "; ".join(primary["checkin_checkout_rules"]) if primary["checkin_checkout_rules"] else "Unavailable"
    )
    primary["cancellation_policy_display"] = (
        primary["cancellation_policy_exact"]
        or "Exact public cancellation text unavailable in extracted payload"
    )
    primary["fee_visibility_note"] = (
        "Search results showed fee-inclusive totals; exact fee line items were not consistently exposed."
    )
    primary["photo_story"] = {
        "living": "space and shared comfort",
        "pool": "amenity-led vacation feel",
        "bedroom": "sleep comfort",
        "terrace": "outdoor calm",
    }.get(primary["hero_category"], "a generic interior promise")
    primary["first_five_categories"] = ", ".join(primary["first_five_photo_categories"] or [])
    primary["review_tag_lines"] = [
        f"{name}: mentioned by {count} review(s)"
        for name, count in sorted((primary["review_tag_counts"] or {}).items(), key=lambda item: (-item[1], item[0]))
    ]
    primary["risky_amenity"] = "Frente al agua" in (primary["amenities"] or [])
    primary["friction_callout"] = (
        "Verify or remove the waterfront-style amenity, then make the first screen more explicit about parking, self check-in, and 10-minute-by-car access."
        if primary["risky_amenity"]
        else "The bigger friction is trust depth versus premium pricing: improve first-screen clarity and review momentum."
    )

    blocked_data = build_blocked_data(airdna_context["available"])
    findings = build_findings(primary, direct, aspirational, market_summary, airdna_snapshot)

    direct_rank_df = merged_df[
        merged_df["room_id"].isin([PRIMARY_ROOM_ID] + direct["room_id"].tolist())
    ][["room_id", "title", "revenue_strength_proxy_score", "role"]].drop_duplicates(subset=["room_id"])
    direct_rank_df = direct_rank_df.sort_values(by="revenue_strength_proxy_score", ascending=False)

    if airdna_context["available"]:
        airdna_top_listings_df = pd.DataFrame(airdna_context["top_listings"][:10]).rename(
            columns={
                "title": "title",
                "bedrooms": "bedrooms",
                "accommodates": "accommodates",
                "rating": "rating",
                "annual_revenue_mxn": "airdna_revenue",
                "occupancy_pct": "occupancy",
                "adr_mxn": "airdna_adr",
                "days_available": "days_available",
            }
        )
        airdna_top_listings_df["airdna_revenue"] = airdna_top_listings_df["airdna_revenue"].apply(compact_currency)
        airdna_top_listings_df["airdna_adr"] = airdna_top_listings_df["airdna_adr"].apply(compact_currency)
        airdna_top_listings_df["occupancy"] = airdna_top_listings_df["occupancy"].apply(lambda v: f"{int(v)}%")
        airdna_top_submarkets_df = pd.DataFrame(airdna_context["top_submarkets"][:10]).rename(
            columns={
                "name": "submarket",
                "score": "score",
                "revenue_mxn": "display_revenue",
                "occupancy_pct": "occupancy",
                "revpar_usd": "display_revpar",
                "adr_usd": "display_adr",
            }
        )
        airdna_top_submarkets_df["display_revenue"] = airdna_top_submarkets_df["display_revenue"].apply(compact_currency)
        airdna_top_submarkets_df["occupancy"] = airdna_top_submarkets_df["occupancy"].apply(lambda v: f"{int(v)}%")
        airdna_top_submarkets_df["display_revpar"] = airdna_top_submarkets_df["display_revpar"].apply(lambda v: f"${v}")
        airdna_top_submarkets_df["display_adr"] = airdna_top_submarkets_df["display_adr"].apply(lambda v: f"${v}")
        airdna_top_listings_table = dataframe_to_html(
            airdna_top_listings_df,
            columns=["title", "bedrooms", "accommodates", "rating", "airdna_revenue", "occupancy", "airdna_adr", "days_available"],
            money_cols=set(),
            score_cols={"rating"},
        )
        airdna_top_submarkets_table = dataframe_to_html(
            airdna_top_submarkets_df,
            columns=["submarket", "score", "display_revenue", "occupancy", "display_revpar", "display_adr"],
            money_cols=set(),
            score_cols={"score"},
        )
    else:
        airdna_top_listings_table = "<div class='small'>Unavailable</div>"
        airdna_top_submarkets_table = "<div class='small'>Unavailable</div>"

    artifacts = [
        {"label": "Primary listing screenshot", "href": report_href("output/artifacts/my_listing_airbnb_full.png")},
        {"label": "Selvanova Airbnb search screenshot", "href": report_href("output/artifacts/airbnb_search_selvanova.png")},
        {"label": "AirDNA submarket overview screenshot", "href": report_href("output/artifacts/airdna_submarket_overview.png")},
        {"label": "AirDNA occupancy screenshot", "href": report_href("output/artifacts/airdna_submarket_occupancy.png")},
        {"label": "AirDNA submarket snapshot JSON", "href": report_href("output/artifacts/airdna_submarket_snapshot.json")},
        {"label": "Primary Airbnb page snapshot", "href": report_href("output/artifacts/my_listing_snapshot.md")},
    ]
    if not airdna_context["available"]:
        artifacts.append(
            {"label": "AirDNA auth-block screenshot", "href": report_href("output/artifacts/airdna_auth_block.png")}
        )
    artifacts.extend(
        {
            "label": f"Search HTML: {Path(item.artifact_path).name}",
            "href": report_href(item.artifact_path),
        }
        for item in fetched_search_artifacts
    )
    artifacts.extend(
        {
            "label": f"Listing HTML: {Path(item.artifact_path).name}",
            "href": report_href(item.artifact_path),
        }
        for item in fetched_listing_artifacts[: min(len(fetched_listing_artifacts), 10)]
    )

    report_context = {
        "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "primary": primary,
        "airdna": airdna_context,
        "insight_cards": insight_cards(primary, market_summary, airdna_snapshot),
        "findings": findings,
        "airdna_top_listings_table": airdna_top_listings_table,
        "airdna_top_submarkets_table": airdna_top_submarkets_table,
        "direct_table": dataframe_to_html(
            direct_table_df,
            columns=scorecard_columns(),
            money_cols={"nightly_price_mxn"},
            score_cols={
                "rating",
                "review_count",
                "revenue_strength_proxy_score",
                "pricing_strength_score",
                "occupancy_proxy_score",
                "listing_appeal_score",
                "amenity_completeness_score",
                "trust_review_strength_score",
                "booking_friction_score",
                "photo_storytelling_score",
                "family_group_fit_score",
                "location_framing_score",
                "value_for_money_score",
            },
        ),
        "aspirational_table": dataframe_to_html(
            aspirational_table_df,
            columns=scorecard_columns(),
            money_cols={"nightly_price_mxn"},
            score_cols={
                "rating",
                "review_count",
                "revenue_strength_proxy_score",
                "pricing_strength_score",
                "occupancy_proxy_score",
                "listing_appeal_score",
                "amenity_completeness_score",
                "trust_review_strength_score",
                "booking_friction_score",
                "photo_storytelling_score",
                "family_group_fit_score",
                "location_framing_score",
                "value_for_money_score",
            },
        ),
        "price_vs_trust_chart": scatter_svg(
            merged_df[merged_df["role"].isin(["primary", "direct", "aspirational"])].copy(),
            "nightly_price_mxn",
            "trust_review_strength_score",
            "title",
            PRIMARY_ROOM_ID,
            "Nightly price vs trust strength",
            "Observed nightly search-price proxy (MXN)",
            "Trust / review strength score",
        ),
        "price_vs_value_chart": scatter_svg(
            merged_df[merged_df["role"].isin(["primary", "direct", "aspirational"])].copy(),
            "nightly_price_mxn",
            "value_for_money_score",
            "title",
            PRIMARY_ROOM_ID,
            "Nightly price vs value-for-money signal",
            "Observed nightly search-price proxy (MXN)",
            "Value-for-money score",
        ),
        "occ_vs_price_chart": scatter_svg(
            merged_df[merged_df["role"].isin(["primary", "direct", "aspirational"])].copy(),
            "nightly_price_mxn",
            "occupancy_proxy_score",
            "title",
            PRIMARY_ROOM_ID,
            "Price vs occupancy proxy",
            "Observed nightly search-price proxy (MXN)",
            "Occupancy proxy score",
        ),
        "direct_rank_chart": bar_svg(
            direct_rank_df,
            "title",
            "revenue_strength_proxy_score",
            "Revenue strength proxy ranking",
            PRIMARY_ROOM_ID,
        ),
        "guest_segments": guest_segments(),
        "titles": recommended_titles(),
        "description_variants": description_variants(),
        "first_screen_bullets": first_10_seconds_bullets(),
        "photo_shot_list": photo_shot_list(),
        "pricing_recommendations": pricing_recommendations(primary, direct),
        "action_plan": action_plan(primary, market_summary),
        "quick_wins": quick_wins(),
        "blocked_data": blocked_data,
        "artifacts": artifacts,
    }

    report_html = render_report(report_context)
    write_text(OUTPUT_DIR / "selvanova_competitive_report.html", report_html)

    export_df = merged_df.copy()
    export_df["search_badges"] = export_df["search_badges"].apply(json.dumps)
    export_df["amenities"] = export_df["amenities"].apply(json.dumps)
    export_df["amenity_flags"] = export_df["amenity_flags"].apply(json.dumps)
    export_df["highlights"] = export_df["highlights"].apply(json.dumps)
    export_df["description_blocks"] = export_df["description_blocks"].apply(json.dumps)
    export_df["photo_urls"] = export_df["photo_urls"].apply(json.dumps)
    export_df["photo_labels"] = export_df["photo_labels"].apply(json.dumps)
    export_df["review_tags"] = export_df["review_tags"].apply(json.dumps)
    export_df["review_tag_counts"] = export_df["review_tag_counts"].apply(json.dumps)
    export_df["review_comments"] = export_df["review_comments"].apply(json.dumps)
    export_df["category_ratings"] = export_df["category_ratings"].apply(json.dumps)
    export_df["rating_distribution"] = export_df["rating_distribution"].apply(json.dumps)
    export_df["host_details"] = export_df["host_details"].apply(json.dumps)
    export_df["house_rules"] = export_df["house_rules"].apply(json.dumps)
    export_df["checkin_checkout_rules"] = export_df["checkin_checkout_rules"].apply(json.dumps)
    export_df["safety_items"] = export_df["safety_items"].apply(json.dumps)
    export_df["sleeping_arrangements"] = export_df["sleeping_arrangements"].apply(json.dumps)
    export_df["search_sources"] = export_df["search_sources"].apply(json.dumps)
    export_df["search_source_urls"] = export_df["search_source_urls"].apply(json.dumps)
    export_df["first_five_photo_categories"] = export_df["first_five_photo_categories"].apply(json.dumps)

    export_df.to_csv(OUTPUT_DIR / "selvanova_comps.csv", index=False)
    export_df.to_json(OUTPUT_DIR / "selvanova_comps.json", orient="records", force_ascii=False, indent=2)
    notes_md = build_notes(primary, direct, secondary, aspirational, blocked_data, SEARCH_URLS, airdna_snapshot)
    write_text(OUTPUT_DIR / "notes.md", notes_md)


if __name__ == "__main__":
    main()
