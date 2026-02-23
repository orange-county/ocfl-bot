#!/usr/bin/env python3
"""
OCFL CLI v3.0 — Orange County FL Government Services

Comprehensive CLI with grouped subcommands for property lookup, tax info,
GIS queries, pet adoption, inmate search, permits, directory, inspections,
50+ government service guides, and more.
"""

import json as json_mod
import math
import os
import re
import sys
import time
from pathlib import Path
from difflib import SequenceMatcher

import click
import requests
from thefuzz import fuzz
from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# ── API Constants ──────────────────────────────────────────────

OCPA_BASE = "https://ocpa-mainsite-afd-standard.azurefd.net/api"
ARCGIS_BASE = "https://ocgis4.ocfl.net/arcgis/rest/services"
GEOCODER = f"{ARCGIS_BASE}/PUBLIC_SITUS_ADDRESS_LOC/GeocodeServer/findAddressCandidates"
OPEN_DATA = f"{ARCGIS_BASE}/AGOL_Open_Data/MapServer"

ALGOLIA_URL = "https://0LWZO52LS2-dsn.algolia.net/1/indexes/*/queries"
ALGOLIA_KEY = "c0745578b56854a1b90ed57b63fbf0ba"
ALGOLIA_APP = "0LWZO52LS2"

BESTJAIL = "https://netapps.ocfl.net/BestJail"
PETS_URL = "https://www.ocnetpets.com/Adopt/AnimalsinShelter.aspx"
CATALOG_URL = "https://catalog.ocls.org/Search/Results"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "OCFL-CLI/3.0"})

# ── Helpers ────────────────────────────────────────────────────

def _json_opt(ctx):
    root = ctx.find_root()
    if root.obj and root.obj.get("json_output", False):
        return True
    # Also check if --json appears anywhere in argv (handles subcommand-level --json)
    return "--json" in sys.argv

def _api_get(url, params=None, timeout=15):
    try:
        r = SESSION.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        console.print(f"[red]API error:[/red] {e}")
        sys.exit(1)

def _api_post(url, json_data=None, params=None, headers=None, timeout=15):
    try:
        r = SESSION.post(url, json=json_data, params=params, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        console.print(f"[red]API error:[/red] {e}")
        sys.exit(1)

OC_CITIES = ["Orlando", "Maitland", "Winter Park", "Apopka", "Ocoee", "Winter Garden",
             "Windermere", "Belle Isle", "Eatonville", "Oakland", "Bay Lake", "Lake Buena Vista"]

def geocode_address(address):
    """Geocode an address via OCFL ArcGIS. Returns dict with lat/lon/score or None."""
    data = _api_get(GEOCODER, {"Street": address, "outFields": "*", "f": "json", "maxLocations": 5, "outSR": 4326})
    candidates = data.get("candidates", [])
    # If no results and no city in address, retry with OC cities
    if not candidates:
        addr_lower = address.lower()
        has_city = any(c.lower() in addr_lower for c in OC_CITIES)
        if not has_city:
            for city in OC_CITIES:
                data = _api_get(GEOCODER, {"Street": f"{address}, {city}", "outFields": "*", "f": "json", "maxLocations": 5, "outSR": 4326})
                candidates = data.get("candidates", [])
                if candidates:
                    break
    if not candidates:
        return None
    best = candidates[0]
    loc = best["location"]
    return {
        "lat": loc["y"],
        "lon": loc["x"],
        "score": best.get("score", 0),
        "address": best.get("address", ""),
        "attributes": best.get("attributes", {}),
    }

def is_parcel_id(s):
    cleaned = s.replace("-", "").replace(" ", "")
    return cleaned.isdigit() and len(cleaned) >= 12

def parcel_to_api_format(pid):
    cleaned = pid.replace("-", "").replace(" ", "")
    return cleaned

def resolve_parcel(address_or_parcel):
    if is_parcel_id(address_or_parcel):
        pid = parcel_to_api_format(address_or_parcel)
        info = _api_get(f"{OCPA_BASE}/PRC/GetPRCGeneralInfo", {"pid": pid})
        if info and info.get("parcelId"):
            return [info]
        return []
    results = _api_get(f"{OCPA_BASE}/QuickSearch/GetSearchInfoByAddress", {
        "address": address_or_parcel, "page": 1, "size": 10,
        "sortBy": "ParcelID", "sortDir": "ASC"
    })
    return results if results else []

def fmt_currency(val):
    if val is None:
        return "N/A"
    try:
        return f"${float(val):,.2f}"
    except (ValueError, TypeError):
        return str(val)

def fmt_number(val):
    if val is None:
        return "N/A"
    try:
        return f"{float(val):,.0f}"
    except (ValueError, TypeError):
        return str(val)

# ── Directory Data ─────────────────────────────────────────────

DIRECTORY_FILE = Path(__file__).parent / "DIRECTORY.md"

def _load_directory():
    """Load flat list of directory entries (for search/phone)."""
    cache_path = CACHE_DIR / "directory.json"
    if cache_path.exists() and (time.time() - cache_path.stat().st_mtime < 86400):
        return json_mod.loads(cache_path.read_text())
    if not DIRECTORY_FILE.exists():
        return []
    text = DIRECTORY_FILE.read_text()
    entries = []
    in_phone_table = False
    for line in text.split("\n"):
        if "Complete Phone Directory" in line:
            in_phone_table = True
            continue
        if in_phone_table and line.startswith("|") and "---" not in line and "Department" not in line:
            parts = [p.strip().strip("*") for p in line.split("|")[1:-1]]
            if len(parts) >= 2:
                entries.append({"name": parts[0], "phone": parts[1]})
    sections = re.findall(r'### (.+?)(?=\n###|\n---|\Z)', text, re.DOTALL)
    for section in sections:
        lines = section.strip().split("\n")
        title = lines[0].strip()
        body = "\n".join(lines[1:])
        phones = re.findall(r'\((\d{3})\)\s*(\d{3})-(\d{4})', body)
        emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', body)
        urls = re.findall(r'https?://[^\s\)]+', body)
        for phone in phones:
            ph = f"({phone[0]}) {phone[1]}-{phone[2]}"
            if not any(e["phone"] == ph and e["name"] == title for e in entries):
                entries.append({"name": title, "phone": ph, "email": emails[0] if emails else "", "url": urls[0] if urls else ""})
    try:
        cache_path.write_text(json_mod.dumps(entries))
    except Exception:
        pass
    return entries


def _load_directory_by_category():
    """Load directory entries grouped by top-level category from DIRECTORY.md."""
    cache_path = CACHE_DIR / "directory_categories.json"
    if cache_path.exists() and (time.time() - cache_path.stat().st_mtime < 86400):
        return json_mod.loads(cache_path.read_text())
    if not DIRECTORY_FILE.exists():
        return {}
    text = DIRECTORY_FILE.read_text()
    categories = {}
    current_category = None

    # Top-level sections we care about (## headings)
    SKIP_SECTIONS = {"Table of Contents", "Overview & Main Sites", "Complete Phone Directory"}

    for line in text.split("\n"):
        # Detect ## headings (top-level categories)
        h2_match = re.match(r'^## (.+)$', line)
        if h2_match:
            cat_name = h2_match.group(1).strip()
            if cat_name in SKIP_SECTIONS:
                current_category = None
            else:
                current_category = cat_name
                if current_category not in categories:
                    categories[current_category] = []
            continue

        # Detect ### headings (entries within a category)
        h3_match = re.match(r'^### (.+)$', line)
        if h3_match and current_category:
            entry_name = h3_match.group(1).strip()
            categories[current_category].append({"name": entry_name, "phone": "", "email": "", "url": "", "address": ""})
            continue

        # For BCC, parse table rows as entries
        if current_category == "Board of County Commissioners" and line.startswith("|") and "---" not in line and "Position" not in line:
            parts = [p.strip().strip("*") for p in line.split("|")[1:-1]]
            if len(parts) >= 2 and parts[1]:
                categories[current_category].append({"name": f"{parts[0]} — {parts[1]}", "phone": "", "email": "", "url": "", "address": ""})
            continue

        # Enrich current entry with phone/email/url/address
        if current_category and categories.get(current_category):
            entry = categories[current_category][-1] if categories[current_category] else None
            if entry:
                phone_match = re.search(r'\((\d{3})\)\s*(\d{3})-(\d{4})', line)
                email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', line)
                url_match = re.search(r'https?://[^\s\)\]]+', line)
                addr_match = re.match(r'.*\*\*Address:\*\*\s*(.+)', line)
                if phone_match and not entry["phone"]:
                    entry["phone"] = f"({phone_match.group(1)}) {phone_match.group(2)}-{phone_match.group(3)}"
                if email_match and not entry["email"]:
                    entry["email"] = email_match.group(0)
                if url_match and not entry["url"]:
                    entry["url"] = url_match.group(0)
                if addr_match and not entry["address"]:
                    entry["address"] = addr_match.group(1).strip()

    # Also parse Special Districts, Linked Subsites etc. which use bullet points not ###
    # Re-parse for categories that might have entries as bullet items instead of ### headings
    for cat_name in list(categories.keys()):
        if not categories[cat_name]:
            # Try to find bullet-point entries
            cat_pattern = re.escape(cat_name)
            match = re.search(rf'^## {cat_pattern}\s*\n(.*?)(?=\n## |\Z)', text, re.DOTALL | re.MULTILINE)
            if match:
                block = match.group(1)
                for bline in block.split("\n"):
                    # Match lines like "| Name | URL |" or "- **Name** ..."
                    # Match markdown links: - [Name](url) or plain bullets: - **Name** — ...
                    link_match = re.match(r'^[-*]\s+\[(.+?)\]\((.+?)\)', bline)
                    if link_match:
                        name = link_match.group(1).strip()
                        url = link_match.group(2).strip()
                        phone = ""
                        ph = re.search(r'\((\d{3})\)\s*(\d{3})-(\d{4})', bline)
                        if ph:
                            phone = f"({ph.group(1)}) {ph.group(2)}-{ph.group(3)}"
                        categories[cat_name].append({"name": name, "phone": phone, "email": "", "url": url, "address": ""})
                        continue
                    bullet_match = re.match(r'^[-*]\s+\*?\*?(.+?)(?:\*\*|\s*[—–-]\s)', bline)
                    table_match = None
                    if bline.startswith("|") and "---" not in bline and "Name" not in bline and "Site" not in bline:
                        parts = [p.strip().strip("*") for p in bline.split("|")[1:-1]]
                        if len(parts) >= 1 and parts[0]:
                            phone = ""
                            url = ""
                            ph = re.search(r'\((\d{3})\)\s*(\d{3})-(\d{4})', bline)
                            um = re.search(r'https?://[^\s\)\|]+', bline)
                            if ph:
                                phone = f"({ph.group(1)}) {ph.group(2)}-{ph.group(3)}"
                            if um:
                                url = um.group(0)
                            categories[cat_name].append({"name": parts[0], "phone": phone, "email": "", "url": url, "address": ""})
                    elif bullet_match:
                        name = bullet_match.group(1).strip().strip("*")
                        phone = ""
                        url = ""
                        ph = re.search(r'\((\d{3})\)\s*(\d{3})-(\d{4})', bline)
                        um = re.search(r'https?://[^\s\)\]]+', bline)
                        if ph:
                            phone = f"({ph.group(1)}) {ph.group(2)}-{ph.group(3)}"
                        if um:
                            url = um.group(0)
                        categories[cat_name].append({"name": name, "phone": phone, "email": "", "url": url, "address": ""})

    # Add Complete Phone Directory as a category
    phone_dir_match = re.search(r'^## Complete Phone Directory\s*\n(.*?)(?=\n## |\Z)', text, re.DOTALL | re.MULTILINE)
    if phone_dir_match:
        phone_entries = []
        for pline in phone_dir_match.group(1).split("\n"):
            if pline.startswith("|") and "---" not in pline and "Department" not in pline:
                parts = [p.strip().strip("*") for p in pline.split("|")[1:-1]]
                if len(parts) >= 2 and parts[0]:
                    phone_entries.append({"name": parts[0], "phone": parts[1], "email": "", "url": "", "address": ""})
        if phone_entries:
            categories["Complete Phone Directory"] = phone_entries

    # Remove empty categories
    categories = {k: v for k, v in categories.items() if v}

    try:
        cache_path.write_text(json_mod.dumps(categories))
    except Exception:
        pass
    return categories

def _fuzzy_search(entries, query):
    query_lower = query.lower()
    query_tokens = set(query_lower.split())
    scored = []
    for e in entries:
        name_lower = e["name"].lower()
        # 1. Exact substring match → highest score
        if query_lower in name_lower:
            scored.append((100, e))
            continue
        # 2. Token match — how many query words appear in the name
        name_tokens = set(name_lower.split())
        token_hits = sum(1 for qt in query_tokens if any(qt in nt for nt in name_tokens))
        token_score = (token_hits / len(query_tokens)) * 80 if query_tokens else 0
        # 3. thefuzz — token_set_ratio handles word order & partial
        fuzz_score = fuzz.token_set_ratio(query_lower, name_lower) * 0.7
        # 4. Also check phone/email/url fields
        field_bonus = 0
        for field in ["phone", "email", "url"]:
            if query_lower in str(e.get(field, "")).lower():
                field_bonus = 80
                break
        best = max(token_score, fuzz_score, field_bonus)
        if best > 40:
            scored.append((best, e))
    scored.sort(key=lambda x: -x[0])
    return [e for _, e in scored[:15]]


def _regex_search(entries, pattern):
    """Search directory entries by regex pattern."""
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error as err:
        return None, str(err)
    results = []
    for e in entries:
        searchable = f"{e['name']} {e.get('phone','')} {e.get('email','')} {e.get('url','')} {e.get('address','')}"
        if rx.search(searchable):
            results.append(e)
    return results, None

# ── Permits Database ───────────────────────────────────────────

PERMITS_DB = {
    "fence": {
        "name": "Fence Permit (Residential)",
        "fee": "$38 base (+$40 if code enforcement violation)",
        "review_time": "4 business days",
        "valid": "180 days from approval",
        "submit": "Fast Track Online — fasttrack.ocfl.net",
        "requirements": [
            "Dimensioned site plan or survey with fence location",
            "Easement Acknowledgement Form (if in easement)",
            "PDF named: A100-Siteplan-Fence",
        ],
        "height": "Front: 4 ft max | Side/Rear: 6 ft max (check zoning district)",
    },
    "pool": {
        "name": "Pool/Spa Permit",
        "fee": "Varies by valuation",
        "review_time": "5-10 business days",
        "valid": "180 days",
        "submit": "Fast Track Online — fasttrack.ocfl.net",
        "requirements": [
            "Site plan with pool location & setbacks",
            "Barrier/fence plan (safety code)",
            "Equipment location",
            "Separate electrical permit required",
        ],
    },
    "roof": {
        "name": "Roofing Permit",
        "fee": "Based on valuation (min ~$82)",
        "review_time": "1-3 business days",
        "valid": "180 days",
        "submit": "Fast Track Online — fasttrack.ocfl.net",
        "requirements": [
            "Product approval documentation",
            "Contractor license info",
            "Roof plan if structural changes",
        ],
    },
    "adu": {
        "name": "Accessory Dwelling Unit (ADU)",
        "fee": "Varies (impact fees + permit fees)",
        "review_time": "15-30 business days",
        "valid": "180 days",
        "submit": "Fast Track Online — fasttrack.ocfl.net",
        "requirements": [
            "Site plan",
            "Floor plan",
            "Elevations",
            "Impact fee calculations",
            "Check Vision 2050 current status",
        ],
    },
    "garage_sale": {
        "name": "Garage/Yard Sale Permit",
        "fee": "Free",
        "review_time": "Same day (email)",
        "valid": "Duration of sale",
        "submit": "Email zoning@ocfl.net",
        "requirements": [
            "Property address",
            "Date(s) of sale",
            "Max 3 sales per year",
        ],
    },
    "tree": {
        "name": "Tree Removal Permit",
        "fee": "$25-$50",
        "review_time": "5-10 business days",
        "valid": "90 days",
        "submit": "Fast Track or in-person",
        "requirements": [
            "Site plan showing tree location",
            "Tree species and diameter (DBH)",
            "Reason for removal",
            "Replacement plan if protected species",
        ],
    },
    "window": {
        "name": "Window/Door Replacement Permit",
        "fee": "Based on valuation",
        "review_time": "1-3 business days",
        "valid": "180 days",
        "submit": "Fast Track Online — fasttrack.ocfl.net",
        "requirements": [
            "Product approval (FL approval number or Miami-Dade NOA)",
            "Installation details",
            "Impact-rated if in wind-borne debris region",
        ],
    },
    "ac": {
        "name": "AC Changeout Permit",
        "fee": "~$82",
        "review_time": "1-2 business days",
        "valid": "180 days",
        "submit": "Fast Track Online — fasttrack.ocfl.net",
        "requirements": [
            "Manual J load calculation (if upsizing)",
            "Equipment specifications",
            "Contractor license",
        ],
    },
}

# ── GIS Layer Names ────────────────────────────────────────────

GIS_KNOWN_LAYERS = {
    0: "Address Points", 1: "Address Range", 3: "Airport Noise Contours",
    6: "Boat Ramps", 9: "Code Enforcement Officer Zones",
    10: "Colleges and Universities", 11: "Commission Districts",
    12: "Community Development Districts", 15: "Conservation",
    16: "County Boundary", 19: "FEMA Flood Zones",
    20: "Fire Stations Countywide", 21: "Future Land Use",
    25: "Hospitals", 28: "Hydrology", 31: "Jurisdictions",
    32: "Law Enforcement Agencies", 33: "Major Drainage Basins",
    34: "Neighborhood Organizations", 60: "Water Service Provider",
}

def _get_gis_layers():
    cache_path = CACHE_DIR / "gis_layers.json"
    if cache_path.exists() and (time.time() - cache_path.stat().st_mtime < 86400):
        return json_mod.loads(cache_path.read_text())
    data = _api_get(f"{OPEN_DATA}", {"f": "json"})
    layers = {}
    for layer in data.get("layers", []):
        layers[layer["id"]] = layer["name"]
    for layer in data.get("tables", []):
        layers[layer["id"]] = layer["name"]
    try:
        cache_path.write_text(json_mod.dumps(layers))
    except Exception:
        pass
    return layers

def _find_layer(name_query):
    layers = _get_gis_layers()
    query = name_query.lower()
    best = None
    best_score = 0
    for lid, lname in layers.items():
        lname_lower = lname.lower()
        if query == lname_lower:
            return (int(lid), lname)
        if query in lname_lower:
            score = len(query) / len(lname_lower)
            if score > best_score:
                best_score = score
                best = (int(lid), lname)
        else:
            ratio = SequenceMatcher(None, query, lname_lower).ratio()
            if ratio > best_score and ratio > 0.4:
                best_score = ratio
                best = (int(lid), lname)
    return best

def _gis_point_query(layer_id, lon, lat, out_fields="*"):
    return _api_get(f"{OPEN_DATA}/{layer_id}/query", {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": out_fields,
        "f": "json",
        "inSR": "4326",
    })

def _gis_nearby_query(layer_id, lon, lat, radius=5000, out_fields="*", limit=10):
    return _api_get(f"{OPEN_DATA}/{layer_id}/query", {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": out_fields,
        "f": "json",
        "inSR": "4326",
        "distance": radius,
        "units": "esriSRUnit_Meter",
        "resultRecordCount": limit,
    })

# ── SERVICE INFO DATABASE ─────────────────────────────────────

SERVICES_DB = {
    "homestead": {
        "name": "Homestead Exemption Application",
        "category": "Property",
        "url": "https://www.ocpafl.org/Exemptions/Homestead.aspx",
        "phone": "(407) 836-5044",
        "department": "Orange County Property Appraiser",
        "what": "Reduces your property's taxable value by up to $50,000 if it's your primary residence. Save $750-$1,000+/yr on property taxes.",
        "why": "You bought a home in Orange County and want to lower your property tax bill. Required annually for new homeowners; auto-renews after.",
        "how": "1. Apply online at ocpafl.org by March 1\n2. Or visit 200 S Orange Ave, Suite 1700, Orlando\n3. Or mail completed DR-501 form\n4. First-time applicants must apply by March 1 of the year after purchase",
        "requirements": "FL Driver License or ID (with property address), Social Security number, proof of FL residency, recorded deed. If not US citizen: Permanent Resident Card.",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM",
        "notes": "⚠️ DEADLINE: March 1 each year for new applications. Late filing accepted through Sept but may not get full exemption. Must be your permanent residence as of Jan 1.",
        "contacts": ["Property Appraiser: (407) 836-5044", "https://www.ocpafl.org/"],
    },
    "appraisal": {
        "name": "Real Estate Appraisal Appeal (TRIM / VAB)",
        "category": "Property",
        "url": "http://www.ocpafl.org/",
        "phone": "(407) 836-5044",
        "department": "Orange County Property Appraiser / Value Adjustment Board",
        "what": "Challenge your property's assessed value if you believe it's too high. File a petition with the Value Adjustment Board.",
        "why": "Your TRIM notice shows a value you disagree with, you have evidence of lower market value.",
        "how": "1. Review TRIM notice (mailed August)\n2. Contact Property Appraiser first: (407) 836-5044\n3. File VAB petition by deadline (25 days after TRIM)\n4. Hearing before Special Magistrate",
        "requirements": "TRIM notice, comparable sales data or appraisal, $15 filing fee per parcel.",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM",
        "notes": "⚠️ STRICT DEADLINE: Must file within 25 days of TRIM notice (usually mid-September). Informal meeting with Appraiser first recommended. Bring comparable sales.",
        "contacts": ["Property Appraiser: (407) 836-5044", "VAB/Clerk: (407) 836-2000", "http://www.ocpafl.org/"],
    },
    "flood": {
        "name": "Floodplain Determination",
        "category": "Property",
        "url": "https://orangecountyfl.net/Environment.aspx",
        "phone": "(407) 836-1400",
        "department": "Environmental Protection Division",
        "what": "Determine if a property is in a FEMA flood zone. Affects insurance requirements, building permits, and property value.",
        "why": "Buying property, applying for a mortgage, building permit, or checking flood risk after map updates.",
        "how": "1. CLI: ocfl gis flood \"<address>\"\n2. FEMA Map: msc.fema.gov/portal\n3. OCFL GIS: ocgis4.ocfl.net\n4. In person: Environmental Protection, 3165 McCrory Place, Suite 200",
        "requirements": "Property address or parcel ID.",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM",
        "notes": "Flood insurance may be required even outside high-risk zones. FEMA maps update periodically. LOMA/LOMR process can remove you from flood zone. Also try: ocfl gis flood <address>",
        "contacts": ["EPD: (407) 836-1400", "FEMA Flood Map: msc.fema.gov", "NFIP: (800) 427-4661"],
    },
    "domicile": {
        "name": "Declaration of Domicile",
        "category": "Property",
        "url": "http://www.myorangeclerk.com/",
        "phone": "(407) 836-2000",
        "department": "Orange County Clerk of Courts",
        "what": "File a Declaration of Domicile to legally establish Florida as your permanent home. Supports homestead exemption and residency.",
        "why": "New FL resident wanting to establish legal domicile, support homestead exemption application, or prove FL residency.",
        "how": "1. In person: Clerk's office, 425 N Orange Ave\n2. Complete the declaration form\n3. Recorded in Official Records\n4. Fee: ~$10",
        "requirements": "Valid ID, FL address, declaration form. Must be signed in presence of Clerk or notary.",
        "hours": "Mon-Fri 7:30 AM - 4:00 PM",
        "notes": "Declaration of Domicile alone doesn't grant homestead exemption — you must also apply with the Property Appraiser. Useful for tax, voting, and legal residency purposes.",
        "contacts": ["Clerk: (407) 836-2000", "Property Appraiser: (407) 836-5044"],
    },
    "vehicle": {
        "name": "Vehicle Registration / Tag / Title Renewal",
        "category": "Vehicles",
        "url": "https://www.octaxcol.com/",
        "phone": "(407) 845-6200",
        "department": "Orange County Tax Collector",
        "what": "Renew vehicle registration, get new tags, transfer titles, or register a new vehicle in Florida.",
        "why": "Annual registration renewal, new vehicle purchase, moved to FL (must register within 30 days), or title transfer.",
        "how": "1. Online: octaxcol.com (renewals only)\n2. In-person: Any Tax Collector branch\n3. By mail: See octaxcol.com for forms\n4. FL DHSMV GoRenew: gorv.flhsmv.gov",
        "requirements": "Current registration or VIN, FL insurance, valid ID. New to FL: out-of-state title, FL insurance, VIN inspection.",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM (branch locations vary)",
        "notes": "Late fees apply after expiration. New FL residents must register within 30 days. $225 initial registration fee for new-to-FL vehicles.",
        "contacts": ["Tax Collector: (407) 845-6200", "FLHSMV: (850) 617-2000", "https://www.octaxcol.com/"],
    },
    "titles": {
        "name": "Vehicle Title / Lien Release",
        "category": "Vehicles",
        "url": "https://www.octaxcol.com/",
        "phone": "(407) 845-6200",
        "department": "Orange County Tax Collector",
        "what": "Apply for a new title, transfer title, obtain duplicate title, or process lien release on a motor vehicle.",
        "why": "Bought/sold a vehicle, paid off your car loan, lost your title, or need to add/remove a name.",
        "how": "1. In person: Any Tax Collector branch\n2. By mail for some services\n3. Lien release: lender sends electronically or you bring paper release",
        "requirements": "Title or application (HSMV 82040), valid ID, FL insurance, applicable fees ($75.25 new title, $2.50 lien fee).",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM",
        "notes": "Title must be transferred within 30 days of sale. Seller must have title notarized. Electronic liens are standard since 2013.",
        "contacts": ["Tax Collector: (407) 845-6200", "FLHSMV: (850) 617-2000"],
    },
    "boat": {
        "name": "Boat Registration / Titling",
        "category": "Vehicles",
        "url": "https://www.octaxcol.com/",
        "phone": "(407) 845-6200",
        "department": "Orange County Tax Collector",
        "what": "Register or title a boat, personal watercraft, or vessel in Florida.",
        "why": "New boat purchase, annual renewal, transfer of ownership, or new to Florida.",
        "how": "1. In person: Tax Collector branch\n2. Online renewal: octaxcol.com\n3. New registration requires in-person visit",
        "requirements": "Manufacturer's Statement of Origin or title, bill of sale, valid ID, sales tax (6%), registration fees vary by vessel length.",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM",
        "notes": "All motorized vessels and sailboats 16ft+ must be registered. Decal valid for 1-2 years. Must carry registration on board.",
        "contacts": ["Tax Collector: (407) 845-6200", "FWC: (850) 488-4676"],
    },
    "mobilehome": {
        "name": "Mobile Home Titling / Registration",
        "category": "Vehicles",
        "url": "https://www.octaxcol.com/",
        "phone": "(407) 845-6200",
        "department": "Orange County Tax Collector / FL DHSMV",
        "what": "Title and register mobile homes. Convert from real property to personal property (or vice versa).",
        "why": "Bought a mobile home, need to transfer title, converting to real property for mortgage, annual registration.",
        "how": "1. In person: Tax Collector branch\n2. Real property conversion: Comptroller + Tax Collector\n3. Title: HSMV 82040 form",
        "requirements": "Title or MSO, bill of sale, valid ID, applicable fees. Real property conversion: recorded deed + retirement of title.",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM",
        "notes": "Mobile homes on owned land can be converted to real property ('retired title'). This affects taxes and financing options. Annual decal required.",
        "contacts": ["Tax Collector: (407) 845-6200", "FLHSMV: (850) 617-2000"],
    },
    "dmv": {
        "name": "Driver License Renewal",
        "category": "Vehicles",
        "url": "https://www.flhsmv.gov/",
        "phone": "(850) 617-2000",
        "department": "FL Dept of Highway Safety & Motor Vehicles (FLHSMV)",
        "what": "Renew or replace a Florida driver license or ID card.",
        "why": "License expiring, lost/stolen, need to update address or name, or new FL resident needing to transfer.",
        "how": "1. Online: flhsmv.gov/GoRenew (eligible renewals)\n2. In person: Tax Collector office (acts as DMV)\n3. By mail (limited renewals)\n4. Main office: 200 S Orange Ave",
        "requirements": "Current DL or ID, proof of identity (for new/transfer), proof of SSN, 2 proofs of FL address, $48 (Class E, 8-year).",
        "hours": "Tax Collector/DMV: Mon-Fri 8:00 AM - 5:00 PM",
        "notes": "In FL, the Tax Collector IS the DMV for most services. REAL ID deadline: May 7, 2025. Bring documents for REAL ID upgrade at renewal.",
        "contacts": ["Tax Collector/DMV: (407) 845-6200", "FLHSMV: (850) 617-2000", "flhsmv.gov/GoRenew"],
    },
    "marriage": {
        "name": "Marriage License Issuance",
        "category": "Courts & Records",
        "url": "http://www.myorangeclerk.com/",
        "phone": "(407) 836-2000",
        "department": "Orange County Clerk of Courts",
        "what": "Obtain a Florida marriage license. Valid in any FL county. No waiting period if you complete a premarital course.",
        "why": "Getting married in Florida. License must be obtained before ceremony.",
        "how": "1. Both parties appear in person at Clerk's office\n2. 425 N Orange Ave, Suite 100, Orlando\n3. Apply online to save time: myorangeclerk.com\n4. License issued same day",
        "requirements": "Valid photo ID (both parties), Social Security numbers, $93.50 fee ($32.50 discount with FL premarital course). If previously married: date marriage ended.",
        "hours": "Mon-Fri 7:30 AM - 4:00 PM",
        "notes": "3-day waiting period WAIVED with approved premarital course. No blood test required. License valid for 60 days. No residency requirement.",
        "contacts": ["Clerk of Courts: (407) 836-2000", "http://www.myorangeclerk.com/"],
    },
    "deeds": {
        "name": "Deed / Lien / Mortgage Recording",
        "category": "Courts & Records",
        "url": "http://www.occompt.com/",
        "phone": "(407) 836-5690",
        "department": "Orange County Comptroller — Official Records",
        "what": "Record deeds, mortgages, liens, satisfactions, and other real property documents in the Official Records.",
        "why": "Real estate closing, adding/removing name from deed, filing a lien, recording a satisfaction of mortgage.",
        "how": "1. In person: 109 E Church St, Suite 300, Orlando\n2. E-recording via approved vendors\n3. By mail: PO Box 38, Orlando FL 32802",
        "requirements": "Original document, recording fees ($10 first page + $8.50 each additional), documentary stamp tax (deeds: $0.70/$100 of consideration).",
        "hours": "Mon-Fri 7:30 AM - 4:30 PM",
        "notes": "Official Records search free online at occompt.com. Documentary stamp tax and intangible tax apply to most deed transfers.",
        "contacts": ["Comptroller: (407) 836-5690", "http://www.occompt.com/"],
    },
    "vitals": {
        "name": "Birth / Death / Marriage Certificate",
        "category": "Courts & Records",
        "url": "http://www.myorangeclerk.com/",
        "phone": "(407) 836-2000",
        "department": "Orange County Clerk of Courts / FL Dept of Health",
        "what": "Obtain certified copies of birth certificates, death certificates, and marriage certificates for events that occurred in Florida.",
        "why": "Passport application, legal name change, estate settlement, genealogy, school enrollment.",
        "how": "1. In person: Clerk's office, 425 N Orange Ave\n2. Online: myorangeclerk.com or VitalChek.com\n3. FL Dept of Health: floridahealth.gov (statewide records)",
        "requirements": "Valid photo ID, relationship to person on certificate, $5 search fee + $9/certified copy. For birth certs: parent, child, or legal representative.",
        "hours": "Mon-Fri 7:30 AM - 4:00 PM",
        "notes": "Marriage certificates from Comptroller (recorded after 2005). Older birth/death records may need FL Dept of Health. Processing time varies.",
        "contacts": ["Clerk: (407) 836-2000", "Comptroller: (407) 836-5690", "FL Vital Records: (904) 359-6900"],
    },
    "passport": {
        "name": "Passport Application Acceptance",
        "category": "Courts & Records",
        "url": "http://www.myorangeclerk.com/",
        "phone": "(407) 836-2000",
        "department": "Orange County Clerk of Courts",
        "what": "Submit a new passport application (first-time, minor, lost/stolen, or expired 5+ years). The Clerk acts as a passport acceptance agent.",
        "why": "Need a US passport for international travel. New applications and renewals of long-expired passports must be done in person.",
        "how": "1. Download Form DS-11 from travel.state.gov (DO NOT SIGN)\n2. Gather documents\n3. Visit Clerk's office: 425 N Orange Ave\n4. Appointment recommended: myorangeclerk.com",
        "requirements": "Form DS-11 (unsigned), proof of citizenship (birth cert or naturalization), valid photo ID, passport photo (2x2), fees ($130 adult book + $35 execution fee).",
        "hours": "Mon-Fri 7:30 AM - 4:00 PM (appointment recommended)",
        "notes": "Renewals (within 15 years, adult, undamaged) can be done BY MAIL — no Clerk visit needed. Processing: 6-8 weeks routine, 2-3 weeks expedited (+$60).",
        "contacts": ["Clerk: (407) 836-2000", "State Dept: (877) 487-2778", "travel.state.gov"],
    },
    "notary": {
        "name": "Notary Public Services",
        "category": "Courts & Records",
        "url": "http://www.myorangeclerk.com/",
        "phone": "(407) 836-2000",
        "department": "Orange County Clerk of Courts",
        "what": "Free notary services at the Clerk's office. Also: apostille information, notary bond filing.",
        "why": "Need a document notarized (affidavits, POA, real estate docs, etc.).",
        "how": "1. Visit Clerk's office with unsigned document and valid photo ID\n2. Many banks and UPS stores also offer notary\n3. Mobile notaries available privately",
        "requirements": "Valid photo ID, document to be notarized (do NOT sign in advance), all signers present.",
        "hours": "Mon-Fri 7:30 AM - 4:00 PM",
        "notes": "Clerk provides notary free of charge. Private notaries may charge up to $10/signature (FL max). Remote Online Notarization (RON) also available in FL.",
        "contacts": ["Clerk: (407) 836-2000"],
    },
    "probate": {
        "name": "Probate / Estate / Name Change",
        "category": "Courts & Records",
        "url": "http://www.ninthcircuit.org/",
        "phone": "(407) 836-2050",
        "department": "9th Judicial Circuit Court — Probate Division",
        "what": "Probate of estates, guardianship, adult/minor name changes, and estate administration through the courts.",
        "why": "Someone passed away (probate), need a legal name change, or establishing guardianship.",
        "how": "1. File petition at Clerk's office: 425 N Orange Ave\n2. Self-help: flcourts.gov for forms\n3. Probate: file within 10 days of death for testate estates\n4. Name change: petition + hearing required",
        "requirements": "Probate: death certificate, original will, petition. Name change: petition, fingerprints, background check, $401 filing fee. Guardianship: petition, examining committee.",
        "hours": "Mon-Fri 7:30 AM - 4:00 PM",
        "notes": "Small estates (<$75K, no real property) may use Summary Administration. Name changes require FBI background check and newspaper publication. Free self-help center at courthouse.",
        "contacts": ["Circuit Court: (407) 836-2050", "Clerk: (407) 836-2000", "Self-Help: flcourts.gov"],
    },
    "jury": {
        "name": "Jury Duty Response",
        "category": "Courts & Records",
        "url": "http://www.myorangeclerk.com/",
        "phone": "(407) 836-2000",
        "department": "Orange County Clerk of Courts — Jury Services",
        "what": "Respond to jury summons, request postponement, claim exemption, or check reporting status.",
        "why": "Received a jury summons and need to respond, postpone, or get information about your service.",
        "how": "1. Online: myorangeclerk.com → Jury Services\n2. Phone: (407) 836-2000\n3. Check reporting status the evening before on website or phone\n4. Report to: 425 N Orange Ave, Orlando",
        "requirements": "Juror ID number (from summons), valid photo ID on day of service.",
        "hours": "Report by 8:00 AM on scheduled day. Check-in starts 7:30 AM.",
        "notes": "Juror pay: $15/day (first 3 days), $30/day (day 4+). Employers cannot fire you for jury service (FL law). One postponement usually granted automatically.",
        "contacts": ["Jury Services: (407) 836-2000", "http://www.myorangeclerk.com/"],
    },
    "records": {
        "name": "Public Records / Sunshine Law Request",
        "category": "Government",
        "url": "https://orangecountyfl.net/OpenGovernment/PublicRecords.aspx",
        "phone": "(407) 836-3111",
        "department": "Office of Professional Standards — Public Records Unit",
        "what": "Request government documents under Florida's broad public records law (Chapter 119). Almost all government records are public.",
        "why": "Researching government decisions, requesting emails/contracts/reports, journalism, legal discovery.",
        "how": "1. Email: PublicRecordRequest@ocfl.net\n2. In person: 450 E South St, Suite 360\n3. Sheriff records: ocso-fl.nextrequest.com\n4. Clerk records: myorangeclerk.com",
        "requirements": "Written request describing records sought. No ID required. No reason needed. Fees: $0.15/page copies, actual cost for extensive requests.",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM (excluding holidays)",
        "notes": "FL Sunshine Law is one of the strongest in the US. Agencies must respond 'promptly.' Exemptions exist for SSN, medical records, active investigations, etc.",
        "contacts": ["Public Records: PublicRecordRequest@ocfl.net", "311: (407) 836-3111", "Sheriff Records: ocso-fl.nextrequest.com"],
    },
    "pd": {
        "name": "Public Defender Application",
        "category": "Courts & Records",
        "url": "http://www.myfloridapd.com",
        "phone": "(407) 836-4800",
        "department": "Office of the Public Defender, 9th Judicial Circuit",
        "what": "Apply for court-appointed legal representation if you cannot afford an attorney for criminal charges.",
        "why": "You've been charged with a crime and cannot afford a private attorney.",
        "how": "1. Request at first court appearance (judge will inquire)\n2. Apply: 435 N Orange Ave, Suite 400, Orlando\n3. Phone: (407) 836-4800\n4. Application reviewed for financial eligibility",
        "requirements": "Financial affidavit showing inability to hire private counsel. Income, assets, and expenses reviewed. $50 application fee (may be waived).",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM",
        "notes": "Right to counsel guaranteed by 6th Amendment. PD handles felonies, misdemeanors, juvenile, and some civil cases. If found not indigent, may be referred to private attorney.",
        "contacts": ["Public Defender: (407) 836-4800", "435 N Orange Ave, Suite 400, Orlando 32801", "http://www.myfloridapd.com"],
    },
    "voter": {
        "name": "Voter Registration / Update",
        "category": "Elections",
        "url": "http://www.ocfelections.com/",
        "phone": "(407) 836-2070",
        "department": "Supervisor of Elections",
        "what": "Register to vote, update your registration (name, address, party), check registration status.",
        "why": "New resident, turned 18, changed name/address/party, or want to verify you're registered before election.",
        "how": "1. Online: registertovoteflorida.gov\n2. In person: 119 W Kaley St, Orlando\n3. By mail: voter registration application\n4. At Tax Collector offices, libraries, DMV",
        "requirements": "FL Driver License or last 4 SSN, date of birth, US citizen, FL resident, 18+ (can pre-register at 16).",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM. Extended hours before elections.",
        "notes": "Registration closes 29 days before each election. Party affiliation required for primary elections. Book closes differ — check ocfelections.com.",
        "contacts": ["Elections: (407) 836-2070", "119 W Kaley St, Orlando 32806", "http://www.ocfelections.com/"],
    },
    "ballot": {
        "name": "Absentee / Vote-by-Mail Ballot Request",
        "category": "Elections",
        "url": "http://www.ocfelections.com/",
        "phone": "(407) 836-2070",
        "department": "Supervisor of Elections",
        "what": "Request a vote-by-mail ballot for upcoming elections. Good for 2 general election cycles.",
        "why": "Can't make it to the polls, prefer voting from home, or will be away on Election Day.",
        "how": "1. Online: ocfelections.com\n2. Phone: (407) 836-2070\n3. In person: 119 W Kaley St\n4. By mail/email/fax request",
        "requirements": "Name, DOB, address, last 4 SSN or FL DL number. Must be registered voter.",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM",
        "notes": "Ballot must be RECEIVED by 7:00 PM on Election Day (not postmarked). Drop boxes available at early voting sites. Track your ballot at ocfelections.com.",
        "contacts": ["Elections: (407) 836-2070", "http://www.ocfelections.com/"],
    },
    "elections_info": {
        "name": "Election Info & Polling Place Lookup",
        "category": "Elections",
        "url": "http://www.ocfelections.com/",
        "phone": "(407) 836-2070",
        "department": "Supervisor of Elections",
        "what": "Find your polling place, view sample ballots, see upcoming election dates, early voting locations and times.",
        "why": "Need to know where to vote, what's on your ballot, or when early voting starts.",
        "how": "1. Polling lookup: ocfelections.com (enter address)\n2. Sample ballot: ocfelections.com\n3. Early voting: locations listed on website before each election",
        "requirements": "Registered voter address for lookup.",
        "hours": "Office: Mon-Fri 8-5. Polls: 7 AM - 7 PM on Election Day",
        "notes": "Bring valid photo ID to vote. FL accepts: FL DL, FL ID, US passport, debit/credit card with photo, military ID, student ID, retirement center ID, neighborhood association ID, public assistance ID.",
        "contacts": ["Elections: (407) 836-2070", "FL Voter Hotline: (866) 308-6739"],
    },
    "biztax": {
        "name": "Business Tax Receipt (Occupational License)",
        "category": "Permits",
        "url": "https://orangecountyfl.net/PermitsLicenses.aspx",
        "phone": "(407) 836-5650",
        "department": "Business Tax Department",
        "what": "Obtain a Business Tax Receipt (formerly Occupational License) required to operate a business in unincorporated Orange County.",
        "why": "Starting or renewing a business in unincorporated Orange County. Required for all businesses.",
        "how": "1. Online: octaxcol.com (renewals)\n2. In person: Tax Collector office\n3. New businesses: apply at Business Tax Dept, 201 S Rosalind Ave, 1st Floor",
        "requirements": "Business name, address, type of business, zoning approval, state license (if applicable), $25-$250+ depending on business type.",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM",
        "notes": "Renews annually Oct 1. Home-based businesses also need a BTR. City businesses get BTR from their city, not the county.",
        "contacts": ["Business Tax: (407) 836-5650", "Tax Collector: (407) 845-6200"],
    },
    "str": {
        "name": "Short-Term Rental Permit",
        "category": "Permits",
        "url": "https://orangecountyfl.net/PermitsLicenses.aspx",
        "phone": "(407) 836-8181",
        "department": "One Stop Permitting / Zoning Division",
        "what": "Register and obtain permits for short-term vacation rentals (Airbnb, VRBO, etc.) in unincorporated Orange County.",
        "why": "Renting your property on Airbnb/VRBO or other platforms for less than 30 days at a time.",
        "how": "1. County registration: Contact Zoning Division\n2. State license: DBPR (Hotels & Restaurants Division)\n3. Business Tax Receipt required\n4. Tourist Development Tax registration",
        "requirements": "DBPR vacation rental license, county BTR, tourist tax registration, fire inspection, liability insurance, local contact person.",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM",
        "notes": "FL law limits local STR regulations but Orange County has registration requirements. Must collect and remit 6% tourist development tax + 6% state sales tax. State license required.",
        "contacts": ["Zoning: (407) 836-3111", "Permits: (407) 836-8181", "DBPR: (850) 487-1395", "Tax Collector (tourist tax): (407) 845-6200"],
    },
    "inspection": {
        "name": "On-Site Building Inspection",
        "category": "Permits",
        "url": "http://fasttrack.ocfl.net/",
        "phone": "(407) 836-5550",
        "department": "Division of Building Safety",
        "what": "Schedule or check status of building inspections for permitted work (electrical, plumbing, structural, final).",
        "why": "Your contractor pulled a permit and work is ready for inspection, or you need to schedule the next inspection phase.",
        "how": "1. Online: fasttrack.ocfl.net → Schedule Inspection\n2. Phone: (407) 836-5550\n3. Automated line for next-day inspection scheduling\n4. Results available online same day",
        "requirements": "Permit number, work must be accessible and ready for inspection. Contractor or owner of record can request.",
        "hours": "Inspections: Mon-Fri 7 AM - 4 PM. Scheduling: by 4 PM for next business day.",
        "notes": "Inspection results posted to Fast Track same day. Failed inspections require correction and re-inspection (re-inspection fee may apply after 2nd failure).",
        "contacts": ["Building Safety: (407) 836-5550", "Permits: (407) 836-8181", "http://fasttrack.ocfl.net/"],
    },
    "dba": {
        "name": "Fictitious Name / DBA Registration",
        "category": "Permits",
        "url": "https://dos.fl.gov/sunbiz/",
        "phone": "(850) 245-6058",
        "department": "FL Division of Corporations (Sunbiz)",
        "what": "Register a fictitious name (DBA — 'Doing Business As') with the State of Florida.",
        "why": "Operating a business under a name that isn't your legal name or your registered LLC/Corp name.",
        "how": "1. Online: sunbiz.org → Fictitious Name Registration\n2. Fee: $50 online\n3. Renew every 5 years",
        "requirements": "$50 registration fee, FEI/EIN number (or SSN for sole proprietor), owner name and address. Must advertise once in local newspaper within 30 days.",
        "hours": "Online: 24/7. Phone: Mon-Fri 8-5",
        "notes": "This is a STATE filing, not county. Must publish notice in a newspaper (Orange County: Orlando Sentinel or other qualified paper). Registration valid 5 years.",
        "contacts": ["Sunbiz: (850) 245-6058", "https://dos.fl.gov/sunbiz/"],
    },
    "hurricane": {
        "name": "Hurricane / Disaster Assistance",
        "category": "Safety",
        "url": "https://orangecountyfl.net/EmergencySafety.aspx",
        "phone": "(407) 836-9140",
        "department": "Office of Emergency Management",
        "what": "Hurricane preparedness info, shelter locations, disaster recovery assistance, sandbag distribution, debris cleanup updates.",
        "why": "Before, during, or after a hurricane or major storm. Shelter info, FEMA assistance, debris pickup.",
        "how": "1. Preparedness: orangecountyfl.net/EmergencySafety\n2. During storm: monitor AlertOrange.com\n3. After: Apply for FEMA aid at disasterassistance.gov or call (800) 621-3362\n4. Shelters: call 311 for locations",
        "requirements": "FEMA aid: SSN, address, insurance info, description of damage. Shelters: bring medications, water, snacks.",
        "hours": "Emergency Management: Mon-Fri 8-5. During emergencies: 24/7 EOC activation",
        "notes": "Sign up for AlertOrange (alertorange.com) for emergency notifications. Know your evacuation zone (ocfl.net/hurricane). Hurricane season: June 1 - Nov 30.",
        "contacts": ["OEM: (407) 836-9140", "FEMA: (800) 621-3362", "AlertOrange: alertorange.com", "Red Cross: (407) 894-4141"],
    },
    "stray": {
        "name": "Animal Control / Stray / Bite Report",
        "category": "Safety",
        "url": "https://orangecountyfl.net/EmergencySafety.aspx",
        "phone": "(407) 836-3111",
        "department": "Orange County Animal Services",
        "what": "Report stray animals, animal bites, animal cruelty, dangerous dogs, or noise complaints about barking dogs.",
        "why": "Stray animal in your neighborhood, bitten by an animal, witness animal cruelty or neglect.",
        "how": "1. Call 311: (407) 836-3111\n2. Emergency (aggressive animal): call 911\n3. Animal Services: 2769 Conroy Rd\n4. Online: 311 portal for non-emergency reports",
        "requirements": "Location of animal, description, nature of complaint. Bite reports: victim info, animal description, owner if known.",
        "hours": "Animal Services: Tue-Sun 10 AM - 6 PM. 311: Mon-Fri 8-5",
        "notes": "FL law requires 10-day quarantine for biting animals. Rabies vaccination required for all dogs/cats. See 'ocfl pets' for adoption.",
        "contacts": ["311: (407) 836-3111", "Animal Services: 2769 Conroy Rd, Orlando"],
    },
    "ccw": {
        "name": "Concealed Weapon License",
        "category": "Safety",
        "url": "https://www.fdacs.gov/Consumer-Resources/Concealed-Weapon-License",
        "phone": "(850) 245-5691",
        "department": "FL Dept of Agriculture & Consumer Services",
        "what": "Apply for or renew a Florida Concealed Weapon or Firearm License (CWFL).",
        "why": "Want to legally carry a concealed weapon or firearm in Florida.",
        "how": "1. Online application: licensing.freshfromflorida.com\n2. In person: Regional office or Tax Collector\n3. Orange County Tax Collector processes applications\n4. Complete approved firearms training course first",
        "requirements": "21+ years old, US citizen/permanent resident, firearms training certificate, passport photo, fingerprints, $97 fee (new), $50 renewal.",
        "hours": "Tax Collector: Mon-Fri 8-5",
        "notes": "Processing: 50-90 days. Valid 7 years. FL has reciprocity with 37+ states. Training must include live-fire component.",
        "contacts": ["FDACS: (850) 245-5691", "Tax Collector: (407) 845-6200"],
    },
    "fingerprint": {
        "name": "Live Scan Fingerprinting",
        "category": "Safety",
        "url": "https://www.octaxcol.com/",
        "phone": "(407) 845-6200",
        "department": "Orange County Tax Collector",
        "what": "Electronic (Live Scan) fingerprinting for background checks required by employers, licensing boards, or government agencies.",
        "why": "Job application, professional license (teacher, nurse, real estate), volunteer background check, immigration.",
        "how": "1. In person: Tax Collector branch locations\n2. Appointment recommended\n3. Also available at UPS stores and private providers",
        "requirements": "Valid photo ID, ORI number (from requesting agency), payment ($13.25 FDLE + $14.50 FBI + service fee).",
        "hours": "Mon-Fri 8:00 AM - 4:30 PM",
        "notes": "Results sent directly to requesting agency. Processing: 24-72 hours (FDLE), 3-5 days (FBI). Some agencies require specific vendors.",
        "contacts": ["Tax Collector: (407) 845-6200", "FDLE: (850) 410-8109"],
    },
    "dv": {
        "name": "Domestic Violence Services",
        "category": "Safety",
        "url": "https://orangecountyfl.net/CommunityFamilyServices.aspx",
        "phone": "(407) 886-2856",
        "department": "Harbor House of Central Florida / Community & Family Services",
        "what": "Emergency shelter, counseling, legal advocacy, and safety planning for domestic violence survivors.",
        "why": "You or someone you know is experiencing domestic violence and needs help, shelter, or a safety plan.",
        "how": "1. Hotline (24/7): (407) 886-2856 (Harbor House)\n2. National Hotline: (800) 799-7233\n3. Text START to 88788\n4. In danger NOW: call 911",
        "requirements": "None — services are free and confidential.",
        "hours": "Hotline: 24/7. Office services: Mon-Fri 8-5",
        "notes": "FL injunctions for protection can be filed at Clerk's office (no fee). Harbor House provides emergency shelter, counseling, children's programs, and legal advocacy.",
        "contacts": ["Harbor House: (407) 886-2856", "National DV Hotline: (800) 799-7233", "Sheriff: (407) 254-7000", "911 for emergencies"],
    },
    "code": {
        "name": "Code Enforcement Complaint",
        "category": "Safety",
        "url": "https://orangecountyfl.net/PermitsLicenses.aspx",
        "phone": "(407) 836-3111",
        "department": "Code Compliance Division",
        "what": "Report property maintenance violations, illegal construction, overgrown lots, junk vehicles, commercial vehicles in residential areas.",
        "why": "Neighbor's property is unkempt, illegal structure built, business operating in residential zone, too many vehicles.",
        "how": "1. Call 311: (407) 836-3111\n2. Online: 311 portal\n3. In person: 2450 W 33rd St, 2nd Floor\n4. OCFL 311 app",
        "requirements": "Address of violation, description, type of violation. Complaints can be anonymous.",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM. Inspections during business hours.",
        "notes": "Complaints are confidential under FL law. Allow 5-10 business days for initial inspection. Appeals go to Code Enforcement Board.",
        "contacts": ["Code Compliance: (407) 836-3111", "Email: OCNeighborhoods@ocfl.net", "Neighborhood Services: (407) 836-4200"],
    },
    "mosquito": {
        "name": "Mosquito Control / Standing Water Report",
        "category": "Health",
        "url": "https://orangecountyfl.net/FamiliesHealthSocialSvcs.aspx",
        "phone": "(407) 254-9120",
        "department": "Mosquito Control Division",
        "what": "Report mosquito problems, request spraying, report standing water breeding sites. Protects against Zika, West Nile, Dengue.",
        "why": "Excessive mosquitoes, standing water that won't drain, potential breeding sites on public or neighboring property.",
        "how": "1. Call: (407) 254-9120\n2. Call 311: (407) 836-3111\n3. Report online via 311 portal",
        "requirements": "Address/location of issue, description of standing water or mosquito activity.",
        "hours": "Mon-Fri 7:00 AM - 3:30 PM",
        "notes": "Mosquito Control performs routine aerial and ground spraying. Dump standing water on your property weekly. Free Gambusia (mosquito fish) available for ponds.",
        "contacts": ["Mosquito Control: (407) 254-9120", "311: (407) 836-3111", "2715 Conroy Rd, Bldg A, Orlando"],
    },
    "clinic": {
        "name": "Public Health Clinic Services",
        "category": "Health",
        "url": "https://orangecountyfl.net/FamiliesHealthSocialSvcs/OrangeCountyMedicalClinic.aspx",
        "phone": "(407) 836-7611",
        "department": "Health Services Division / FL Dept of Health in Orange County",
        "what": "Low-cost medical services: immunizations, STD testing, TB testing, WIC, family planning, dental, and primary care for uninsured.",
        "why": "No insurance, need vaccinations, STD screening, WIC enrollment, or affordable primary care.",
        "how": "1. Walk-in or appointment at county health centers\n2. FL DOH Orange: 6101 Lake Ellenor Dr, Orlando\n3. County clinic: See orangecountyfl.net for locations\n4. Call for appointment: (407) 858-1400",
        "requirements": "No insurance required. Sliding fee scale based on income. Bring: ID, proof of income, insurance card if any.",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM (varies by location)",
        "notes": "FL DOH provides immunizations, STD/HIV testing, TB services, WIC, and environmental health. County clinic provides primary care.",
        "contacts": ["Health Services: (407) 836-7611", "FL DOH Orange: (407) 858-1400", "6101 Lake Ellenor Dr, Orlando 32809"],
    },
    "crisis": {
        "name": "Mental Health / Crisis Services",
        "category": "Health",
        "url": "https://orangecountyfl.net/FamiliesHealthSocialSvcs.aspx",
        "phone": "(407) 836-7608",
        "department": "Mental Health & Homelessness Division",
        "what": "Crisis intervention, mental health referrals, Baker Act information, homeless services, substance abuse resources.",
        "why": "Mental health crisis, suicidal thoughts, substance abuse, homelessness, or need counseling referral.",
        "how": "1. Crisis: Call 988 (Suicide & Crisis Lifeline)\n2. County: (407) 836-7608\n3. Crisis Center: (407) 425-2624 (Heart of FL United Way)\n4. Text HOME to 741741 (Crisis Text Line)",
        "requirements": "None for crisis services. Walk-ins accepted at crisis centers.",
        "hours": "Crisis lines: 24/7. Office: Mon-Fri 8-5",
        "notes": "Baker Act (involuntary examination) requires specific criteria. Marchman Act for substance abuse. Orange County invests heavily in mental health diversion programs.",
        "contacts": ["988 Suicide Lifeline: Dial 988", "County Mental Health: (407) 836-7608", "Crisis Center: (407) 425-2624", "NAMI: (407) 253-1900"],
    },
    "vector": {
        "name": "Vector Control Request",
        "category": "Health",
        "url": "https://orangecountyfl.net/FamiliesHealthSocialSvcs.aspx",
        "phone": "(407) 254-9120",
        "department": "Mosquito Control / Vector Control",
        "what": "Request control of mosquitoes, rats, or other disease-carrying vectors. Report standing water, rat infestations, or vector-borne illness concerns.",
        "why": "Mosquito infestation, rat problem on public property, concern about disease vectors.",
        "how": "1. Mosquitoes: (407) 254-9120\n2. Rats/rodents (private property): hire pest control\n3. Rats on public property: call 311\n4. Report standing water via 311",
        "requirements": "Location and description of issue.",
        "hours": "Mon-Fri 7:00 AM - 3:30 PM",
        "notes": "County handles mosquito control on public areas. Private property pest control is owner's responsibility. Free mosquito fish available for ponds.",
        "contacts": ["Mosquito Control: (407) 254-9120", "311: (407) 836-3111"],
    },
    "cemetery": {
        "name": "Cemetery / Burial Permit",
        "category": "Health",
        "url": "https://orangecountyfl.net/FamiliesHealthSocialSvcs.aspx",
        "phone": "(407) 836-9400",
        "department": "Medical Examiner / FL Dept of Health",
        "what": "Obtain burial/cremation permits, death certificate processing, and cemetery information.",
        "why": "Arranging a burial or cremation, need a burial transit permit, or death certificate.",
        "how": "1. Funeral home typically handles permits\n2. Burial permit: FL DOH vital records office\n3. Medical Examiner cases: (407) 836-9400\n4. Death certificates: Clerk's office or FL DOH",
        "requirements": "Death certificate filed by physician/ME, burial transit permit, cemetery deed (if applicable).",
        "hours": "Medical Examiner: 24/7 (death investigations). Vital Records: Mon-Fri 8-5",
        "notes": "Funeral directors typically handle all permits. If death is under Medical Examiner jurisdiction, ME must release body before burial. Cremation requires 48-hour wait + ME authorization.",
        "contacts": ["Medical Examiner: (407) 836-9400", "FL DOH (vital records): (407) 858-1400"],
    },
    "311": {
        "name": "311 Non-Emergency Service Requests",
        "category": "Utilities",
        "url": "https://orangecountyfl.net/Home/311HelpInfo.aspx",
        "phone": "(407) 836-3111",
        "department": "Orange County Customer Service (311)",
        "what": "Central hub for reporting non-emergency issues: potholes, stray animals, trash pickup, code violations, noise, and general county questions.",
        "why": "You need to report a problem, ask a question about county services, or don't know which department to call.",
        "how": "1. Dial 311 (or 407-836-3111 from cell)\n2. Online: 311onlinerequests.ocfl.net\n3. OCFL 311 app (iOS/Android)\n4. Chat: ocachat.whoson.com",
        "requirements": "Location of issue, description. No ID needed for reporting.",
        "hours": "Phone: Mon-Fri 8:00 AM - 5:00 PM. Online portal: 24/7",
        "notes": "For EMERGENCIES always call 911. 311 is for non-emergency county services only. City of Orlando residents should call (407) 246-2121.",
        "contacts": ["311: (407) 836-3111", "Online: https://311onlinerequests.ocfl.net"],
    },
    "trash": {
        "name": "Trash / Recycling / Bulk Pickup",
        "category": "Utilities",
        "url": "https://orangecountyfl.net/WaterGarbageRecycling.aspx",
        "phone": "(407) 836-6601",
        "department": "Solid Waste Division",
        "what": "Curbside trash collection, single-stream recycling, yard waste, bulk/large item pickup, and roll cart services.",
        "why": "Missed pickup, need bulk pickup scheduled, roll cart repair/replacement, recycling questions, or landfill hours.",
        "how": "1. Call (407) 836-6601 for service issues\n2. Bulk pickup: call to schedule (2 pickups/year included)\n3. Roll cart issues: call for repair/replacement\n4. Landfill: 5901 Young Pine Rd (McLeod Road)",
        "requirements": "Must be in unincorporated Orange County. Address for service. Bulk items placed curbside.",
        "hours": "Collection: varies by zone (Mon-Fri). Office: Mon-Fri 8-5",
        "notes": "Recycling is single-stream (no sorting needed). No plastic bags in recycling. Hazardous waste has separate drop-off events.",
        "contacts": ["Solid Waste: (407) 836-6601", "Email: Solid.Waste@ocfl.net", "Landfill: 5901 Young Pine Rd"],
    },
    "pothole": {
        "name": "Pothole / Road / Sidewalk / Drainage Report",
        "category": "Utilities",
        "url": "https://orangecountyfl.net/TrafficTransportation.aspx",
        "phone": "(407) 836-7900",
        "department": "Public Works — Roads & Drainage",
        "what": "Report potholes, damaged roads, broken sidewalks, drainage problems, and traffic sign issues in unincorporated Orange County.",
        "why": "Hazardous road conditions, flooding, broken sidewalk, missing/damaged traffic signs.",
        "how": "1. Call 311: (407) 836-3111\n2. Online: 311 portal\n3. OCFL 311 app\n4. Direct: (407) 836-7900",
        "requirements": "Location (address or nearest intersection), description of issue.",
        "hours": "Reports: 24/7 via app/online. Office: Mon-Fri 8-5",
        "notes": "County maintains roads in unincorporated areas only. City roads → call your city. State roads (SR/US) → call FDOT (866) 374-3368.",
        "contacts": ["Public Works: (407) 836-7900", "311: (407) 836-3111", "FDOT: (866) 374-3368"],
    },
    "drainage": {
        "name": "Stormwater / Drainage Complaint",
        "category": "Utilities",
        "url": "https://orangecountyfl.net/TrafficTransportation.aspx",
        "phone": "(407) 836-7900",
        "department": "Public Works — Roads & Drainage / Stormwater Management",
        "what": "Report drainage problems, flooding, clogged storm drains, erosion, and stormwater issues.",
        "why": "Yard flooding, street flooding, clogged storm drain, erosion near your property, water not draining properly.",
        "how": "1. Call 311: (407) 836-3111\n2. Public Works: (407) 836-7900\n3. Online: 311 portal\n4. Emergency flooding: (407) 836-7900",
        "requirements": "Location, description of drainage issue, photos helpful.",
        "hours": "Mon-Fri 8-5. Emergency: 24/7 via 311",
        "notes": "County maintains public drainage infrastructure. Private property drainage is owner's responsibility. HOA/CDD areas may have separate drainage management.",
        "contacts": ["Public Works: (407) 836-7900", "311: (407) 836-3111", "EPD Stormwater: (407) 836-1400"],
    },
    "dumping": {
        "name": "Environmental / Illegal Dumping Complaint",
        "category": "Utilities",
        "url": "https://orangecountyfl.net/Environment.aspx",
        "phone": "(407) 836-1400",
        "department": "Environmental Protection Division",
        "what": "Report illegal dumping, hazardous waste, pollution, contaminated sites, or environmental violations.",
        "why": "Witnessed illegal dumping, smell/see pollution, concerned about contamination, illegal burn.",
        "how": "1. Call EPD: (407) 836-1400\n2. Call 311: (407) 836-3111\n3. Email: EPD@ocfl.net\n4. FDEP Complaint: fldep.dep.state.fl.us",
        "requirements": "Location, description, time observed, photos/video if safe to obtain.",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM",
        "notes": "Illegal dumping is a crime in FL (fines up to $50K). Hazardous waste: call FL DEP hotline (800) 320-0519. Used oil/electronics: free disposal at Hazardous Waste days.",
        "contacts": ["EPD: (407) 836-1400", "Email: EPD@ocfl.net", "FL DEP: (800) 320-0519"],
    },
    "seniors": {
        "name": "Senior / Disabled / Veterans Services",
        "category": "Community",
        "url": "https://orangecountyfl.net/CommunityFamilyServices.aspx",
        "phone": "(407) 836-6563",
        "department": "Community & Family Services — Office on Aging / Disability / Veterans",
        "what": "Services for seniors (60+), persons with disabilities, and veterans: meals, transportation, benefits counseling, respite care, employment.",
        "why": "Need help with meals, transportation, home care, VA benefits, disability services, or social activities.",
        "how": "1. Seniors: (407) 836-6563\n2. Veterans: (407) 836-8990\n3. Disability: (407) 836-7588\n4. In person: 2100 E Michigan St, Orlando",
        "requirements": "Age 60+ for senior services. DD-214 for veteran services. Disability documentation for disability services.",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM",
        "notes": "Senior centers offer free activities, meals, and social programs. Veterans' Services helps with VA claims at no cost. SHINE program for Medicare counseling.",
        "contacts": ["Aging: (407) 836-6563", "Veterans: (407) 836-8990", "Disability: (407) 836-7588", "2100 E Michigan St, Orlando 32806"],
    },
    "family": {
        "name": "Child Support / Family Services",
        "category": "Community",
        "url": "https://orangecountyfl.net/CommunityFamilyServices.aspx",
        "phone": "(407) 836-7600",
        "department": "Youth & Family Services Division",
        "what": "Family resource programs, child support enforcement (state), family counseling, parenting classes, Neighborhood Centers for Families.",
        "why": "Need family counseling, parenting support, child support help, after-school programs, or family crisis assistance.",
        "how": "1. County Family Services: (407) 836-7600\n2. Child Support (FL DOR): floridarevenue.com/childsupport\n3. Neighborhood Centers: various locations\n4. In person: 2100 E Michigan St",
        "requirements": "Varies by program. Child support: court order or DOR case number.",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM",
        "notes": "Child support is managed by FL Dept of Revenue, not the county. County provides family support, counseling, and youth programs. Great Oaks Village for foster youth.",
        "contacts": ["Youth & Family: (407) 836-7600", "FL Child Support: (800) 622-5437", "Citizens' Commission for Children: (407) 836-7610"],
    },
    "medicaid": {
        "name": "Medicaid / SNAP Screening",
        "category": "Community",
        "url": "https://www.myflfamilies.com/",
        "phone": "(866) 762-2237",
        "department": "FL Dept of Children & Families (DCF)",
        "what": "Screen for eligibility and apply for Medicaid, SNAP (food stamps), TANF (cash assistance), and other public benefits.",
        "why": "Low income, need health coverage, food assistance, or cash aid for your family.",
        "how": "1. Online: myflfamilies.com → ACCESS Florida\n2. Phone: (866) 762-2237\n3. In person: DCF service center\n4. Community Action can help: (407) 836-9333",
        "requirements": "SSN, proof of income, residency, household size. Apply online — no office visit required.",
        "hours": "ACCESS online: 24/7. Phone: Mon-Fri 8-5",
        "notes": "FL expanded Medicaid eligibility in 2024. SNAP benefits on EBT card. OC Community Action Division provides free application assistance.",
        "contacts": ["DCF ACCESS: (866) 762-2237", "Community Action: (407) 836-9333", "https://www.myflfamilies.com/"],
    },
    "workforce": {
        "name": "Workforce Development Programs",
        "category": "Community",
        "url": "https://www.careersourcecf.com/",
        "phone": "(407) 531-1222",
        "department": "CareerSource Central Florida / OC Economic Development",
        "what": "Job training, career counseling, resume help, job fairs, and employment programs for Orange County residents.",
        "why": "Looking for a job, need training/skills upgrade, career change, or employer looking to hire.",
        "how": "1. CareerSource CF: careersourcecf.com\n2. In person: career centers throughout OC\n3. County Employment: (407) 836-5661\n4. Community Action: (407) 836-9333",
        "requirements": "FL resident, work eligible. Some programs income-based. Veterans get priority.",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM",
        "notes": "Free services include: resume workshops, mock interviews, computer access, job referrals. WIOA-funded training grants available for eligible residents.",
        "contacts": ["CareerSource CF: (407) 531-1222", "County Employment: (407) 836-5661", "Community Action: (407) 836-9333"],
    },
    "extension": {
        "name": "UF/IFAS Extension Office / 4-H / Agriculture",
        "category": "Community",
        "url": "http://orange.ifas.ufl.edu",
        "phone": "(407) 254-9200",
        "department": "UF/IFAS Orange County Extension",
        "what": "Free gardening advice, Master Gardener programs, 4-H youth programs, agricultural resources, soil testing, pest identification.",
        "why": "Gardening help, pest ID, 4-H for your kids, soil testing, landscaping with FL native plants, food preservation.",
        "how": "1. Call: (407) 254-9200\n2. Visit: 6021 S Conway Rd, Orlando\n3. Online: orange.ifas.ufl.edu\n4. Ask a Master Gardener (walk-in or phone)",
        "requirements": "None for most services. Soil test: $7 through UF. 4-H: ages 5-18.",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM",
        "notes": "Master Gardener Plant Clinic is free. Extension services are a partnership between UF and Orange County. Great resource for FL-specific gardening (what grows here, when to plant).",
        "contacts": ["Extension: (407) 254-9200", "6021 S Conway Rd, Orlando 32812", "http://orange.ifas.ufl.edu"],
    },
    "reserve": {
        "name": "Park Pavilion / Facility Reservation",
        "category": "Recreation",
        "url": "http://www.orangecountyparks.net/",
        "phone": "(407) 836-6200",
        "department": "Parks & Recreation Division",
        "what": "Reserve park pavilions, shelters, recreation center rooms, athletic fields, and camping sites in Orange County parks.",
        "why": "Planning a birthday party, family reunion, sports event, corporate outing, or camping trip.",
        "how": "1. Online: orangecountyparks.net\n2. Phone: (407) 836-6200\n3. In person: Parks office, 4801 W Colonial Dr",
        "requirements": "Reservation form, applicable fees ($25-$500+ depending on facility), 14-day minimum advance notice for most facilities.",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM. Parks: dawn to dusk",
        "notes": "Popular pavilions book weeks in advance. Alcohol requires special permit. Some facilities have capacity limits. Camping at Moss Park, Magnolia Park.",
        "contacts": ["Parks: (407) 836-6200", "Email: parks@ocfl.net", "http://www.orangecountyparks.net/"],
    },
    "libcard": {
        "name": "Library Card Issuance",
        "category": "Recreation",
        "url": "http://www.ocls.info/",
        "phone": "(407) 835-7323",
        "department": "Orange County Library System (OCLS)",
        "what": "Get a free library card for access to books, ebooks, databases, WiFi, computers, and 15+ library branches.",
        "why": "Borrow books/media, access digital resources (Libby, Hoopla), use computers/WiFi, attend free programs.",
        "how": "1. In person: Any OCLS branch with valid ID and proof of address\n2. Online: ocls.info for digital-only card\n3. Main library: 101 E Central Blvd, Orlando",
        "requirements": "Photo ID + proof of Orange County address (utility bill, lease, etc.). Free for OC residents. Non-residents: $125/year.",
        "hours": "Main: Mon-Thu 9-9, Fri-Sat 9-6, Sun 1-6. Branches vary.",
        "notes": "Card also works for Libby (ebooks), Hoopla, Kanopy (movies), LinkedIn Learning, and many databases. Free events and classes weekly.",
        "contacts": ["OCLS: (407) 835-7323", "http://www.ocls.info/", "101 E Central Blvd, Orlando 32801"],
    },
    "hunting": {
        "name": "Hunting / Fishing License",
        "category": "Recreation",
        "url": "https://myfwc.com/license/",
        "phone": "(888) 486-8356",
        "department": "FL Fish & Wildlife Conservation Commission (FWC)",
        "what": "Purchase hunting and freshwater/saltwater fishing licenses for Florida.",
        "why": "Want to hunt or fish in Florida. Licenses required for ages 16+ (some exemptions).",
        "how": "1. Online: GoOutdoorsFlorida.com\n2. In person: Tax Collector, Walmart, Bass Pro, bait shops\n3. Phone: (888) 486-8356",
        "requirements": "Valid ID, SSN. Hunting: hunter safety course (if born after 6/1/1975). Fees: resident freshwater/saltwater $17/ea, combo $32.50, hunting $17.",
        "hours": "Online: 24/7. Tax Collector: Mon-Fri 8-5",
        "notes": "FL residents get much lower fees than non-residents. Free licenses for 65+ residents, military on leave, disabled veterans. License year: July 1 - June 30.",
        "contacts": ["FWC: (888) 486-8356", "GoOutdoorsFlorida.com", "Tax Collector: (407) 845-6200"],
    },
    "arts": {
        "name": "Arts / Cultural Grant Application",
        "category": "Recreation",
        "url": "https://orangecountyfl.net/CultureParks.aspx",
        "phone": "(407) 836-5540",
        "department": "Arts & Cultural Affairs Division",
        "what": "Apply for cultural grants, public art programs, cultural tourism support, and arts organization funding from Orange County.",
        "why": "You're an artist or cultural organization seeking funding, or want info about public art and cultural programs.",
        "how": "1. Grant applications: orangecountyfl.net → Arts & Cultural Affairs\n2. Contact: (407) 836-5540\n3. 450 E South St, 3rd Floor, Orlando\n4. United Arts of Central Florida also provides grants",
        "requirements": "501(c)(3) status for organizational grants. Individual artist grants: OC resident. Application deadlines vary by program.",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM",
        "notes": "Funded by Tourist Development Tax. Programs include: Cultural Tourism, Public Art, Organizational Support, Project Grants. FusionFest is a signature county cultural event.",
        "contacts": ["Arts & Cultural Affairs: (407) 836-5540", "United Arts: (407) 628-0333", "450 E South St, 3rd Fl, Orlando"],
    },
    "budget": {
        "name": "County Budget & Financial Transparency",
        "category": "Government",
        "url": "https://orangecountyfl.net/OpenGovernment.aspx",
        "phone": "(407) 836-5690",
        "department": "Office of Management & Budget / Comptroller",
        "what": "Access Orange County's annual budget, CAFR, financial reports, spending data, and budget hearing schedules.",
        "why": "Research county spending, prepare for budget hearings, understand where tax dollars go, civic transparency.",
        "how": "1. Budget documents: orangecountyfl.net/OpenGovernment\n2. Comptroller reports: occompt.com\n3. Budget hearings: September (public comment welcome)\n4. Checkbook: online spending transparency tool",
        "requirements": "None — all budget documents are public.",
        "hours": "Online: 24/7. Offices: Mon-Fri 8-5",
        "notes": "Budget hearings in September are open to public comment. Fiscal year: Oct 1 - Sept 30. Millage rate set annually by BCC.",
        "contacts": ["Budget Office: (407) 836-5690", "Comptroller: (407) 836-5690", "http://www.occompt.com/"],
    },
    "bids": {
        "name": "Procurement / Bid Opportunities",
        "category": "Government",
        "url": "https://orangecountyfl.net/PermitsLicenses.aspx",
        "phone": "(407) 836-5635",
        "department": "Procurement Division",
        "what": "Find and respond to Orange County government bid opportunities, RFPs, ITBs, and vendor registration.",
        "why": "Want to sell goods/services to the county, respond to an open bid, or register as a vendor.",
        "how": "1. BidSync: register at bidsync.com (OC posts all bids)\n2. Procurement: (407) 836-5635\n3. Vendor registration: orangecountyfl.net → Vendor Services\n4. Business Development: (407) 836-7317",
        "requirements": "Vendor registration, applicable licenses, insurance. Small/minority business certifications available.",
        "hours": "Mon-Fri 8:00 AM - 5:00 PM",
        "notes": "Most bids posted on BidSync. Small Business BOOST program for local/small businesses. Check orangecountyfl.net for upcoming solicitations.",
        "contacts": ["Procurement: (407) 836-5635", "Email: Procurement@ocfl.net", "Business Development: (407) 836-7317"],
    },
}

# ── Service rendering helper ───────────────────────────────────

def _render_service(key):
    svc = SERVICES_DB[key]
    lines = []
    lines.append(f"[bold bright_cyan]🔗 URL:[/bold bright_cyan] {svc['url']}")
    lines.append(f"[bold bright_cyan]📞 Phone:[/bold bright_cyan] {svc['phone']}")
    lines.append(f"[bold bright_cyan]📋 Department:[/bold bright_cyan] {svc['department']}")
    lines.append("")
    lines.append(f"[bold]WHAT:[/bold] {svc['what']}")
    lines.append(f"[bold]WHY:[/bold] {svc['why']}")
    lines.append(f"[bold]HOW:[/bold]\n{svc['how']}")
    lines.append(f"[bold]REQUIREMENTS:[/bold] {svc['requirements']}")
    lines.append(f"[bold]HOURS:[/bold] {svc['hours']}")
    lines.append(f"[bold]NOTES:[/bold] {svc['notes']}")
    if svc.get("contacts"):
        lines.append("")
        lines.append("[bold]Additional Contacts:[/bold]")
        for c in svc["contacts"]:
            lines.append(f"  • {c}")
    content = "\n".join(lines)
    console.print(Panel(content, title=f"🍊 {svc['name']}", border_style="bright_yellow", padding=(1, 2)))


def _make_info_cmd(key):
    """Create a click command for a service info entry."""
    svc = SERVICES_DB[key]
    @click.option("--json", "as_json", is_flag=True, hidden=True, help="Output as JSON")
    @click.pass_context
    def cmd(ctx, as_json):
        if as_json:
            root = ctx.find_root()
            if root.obj is None:
                root.obj = {}
            root.obj["json_output"] = True
        if _json_opt(ctx):
            click.echo(json_mod.dumps(svc, indent=2))
            return
        _render_service(key)
    cmd.__doc__ = svc["name"]
    return cmd


# ── CLI ROOT ───────────────────────────────────────────────────

@click.group()
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.version_option("3.0.0", prog_name="ocfl")
@click.pass_context
def cli(ctx, json_output):
    """🍊 OCFL CLI v3 — Orange County FL Government Services

    \b
    Groups:
      property    Property lookup, tax, homestead, appraisal
      vehicles    Registration, titles, boat, mobile home, DMV
      courts      Marriage, deeds, vitals, passport, notary, probate
      elections   Voter registration, ballots, polling info
      permits     Permit database, business tax, STR, inspections
      safety      Hurricane, animal control, CCW, code enforcement
      health      Restaurant inspections, clinics, crisis services
      utilities   311, trash, pothole, drainage reports
      community   Seniors, family services, Medicaid, workforce
      recreation  Parks, library card, hunting, arts
      government  Budget, procurement/bids

    \b
    Top-level:
      gis         ArcGIS data layers, flood zones, zoning
      geocode     Geocode an address
      pets        Search adoptable pets
      inmate      Search inmates / booking reports
      phone       Department phone lookup
      directory   Government directory search
      library     Library catalog search
      services    List all commands
    """
    ctx.ensure_object(dict)
    ctx.obj["json_output"] = json_output


# ════════════════════════════════════════════════════════════════
# GROUP: property
# ════════════════════════════════════════════════════════════════

@cli.group()
@click.pass_context
def property(ctx):
    """🏠 Property lookup, tax, homestead, appraisal, flood, domicile."""
    pass

@property.command("lookup")
@click.argument("address_or_parcel")
@click.pass_context
def property_lookup(ctx, address_or_parcel):
    """Look up property info by address or parcel ID.

    \b
    Examples:
      ocfl property lookup "1321 Apopka Airport Rd, Apopka"
      ocfl property lookup 272035664500001
    """
    results = resolve_parcel(address_or_parcel)
    if not results:
        console.print("[red]No properties found.[/red]")
        sys.exit(1)

    if _json_opt(ctx):
        pid = results[0].get("parcelId")
        if pid:
            info = _api_get(f"{OCPA_BASE}/PRC/GetPRCGeneralInfo", {"pid": pid})
            values = _api_get(f"{OCPA_BASE}/PRC/GetPRCPropertyValues", {"PID": pid, "TaxYear": 0, "ShowAllFlag": 1})
            click.echo(json_mod.dumps({"info": info, "values": values}, indent=2))
        else:
            click.echo(json_mod.dumps(results, indent=2))
        return

    if not is_parcel_id(address_or_parcel) and len(results) > 1:
        console.print(f"[bold]Found {len(results)} properties:[/bold]\n")

    for i, res in enumerate(results[:5]):
        pid = res.get("parcelId", "")
        if not pid:
            continue
        info = _api_get(f"{OCPA_BASE}/PRC/GetPRCGeneralInfo", {"pid": pid})
        values_data = _api_get(f"{OCPA_BASE}/PRC/GetPRCPropertyValues", {"PID": pid, "TaxYear": 0, "ShowAllFlag": 1})

        table = Table(title=f"🏠 Property: {pid}", box=box.ROUNDED, show_header=False, title_style="bold cyan")
        table.add_column("Field", style="bold")
        table.add_column("Value")
        table.add_row("Owner", info.get("ownerName", "N/A").strip())
        table.add_row("Address", info.get("propertyAddress", "N/A"))
        table.add_row("City", f"{info.get('propertyCity', '')} {info.get('propertyState', '')} {info.get('propertyZip', '')}")
        table.add_row("Mailing", f"{info.get('mailAddress', '')} {info.get('mailCity', '')}, {info.get('mailState', '')} {info.get('mailZip', '')}")
        table.add_row("DOR Code", f"{info.get('dorCode', '')} — {info.get('dorDescription', '')}")
        table.add_row("Homestead", "✅ Yes" if res.get("isHomestead") == "True" else "❌ No")
        table.add_row("Tax Year", str(info.get("prcTaxYear", "")))
        if isinstance(values_data, list) and values_data:
            table.add_row("", "")
            table.add_row("[bold]Values[/bold]", "")
            for v in values_data:
                yr = v.get("taxYear", "")
                table.add_row(f"  {yr} Just Value", fmt_currency(v.get("justValue")))
                table.add_row(f"  {yr} Assessed", fmt_currency(v.get("assessedValue")))
                table.add_row(f"  {yr} Taxable", fmt_currency(v.get("taxableValue")))
        table.add_row("", "")
        table.add_row("Web", f"https://ocpaweb.ocpafl.org/parcelsearch/Parcel%20ID/{pid}")
        console.print(table)
        if i < len(results[:5]) - 1:
            console.print()

@property.command("tax")
@click.argument("address_or_parcel")
@click.pass_context
def property_tax(ctx, address_or_parcel):
    """Look up property tax info by address or parcel ID.

    \b
    Examples:
      ocfl property tax "1321 Apopka Airport Rd, Apopka"
      ocfl property tax 272035664500001
    """
    algolia_data = _api_post(
        ALGOLIA_URL,
        json_data={"requests": [{"indexName": "fl-orange.property_tax", "params": f"query={address_or_parcel}&hitsPerPage=5"}]},
        params={"x-algolia-api-key": ALGOLIA_KEY, "x-algolia-application-id": ALGOLIA_APP},
    )
    hits = []
    if algolia_data and "results" in algolia_data:
        hits = algolia_data["results"][0].get("hits", [])

    parcels = resolve_parcel(address_or_parcel)
    pid = parcels[0].get("parcelId") if parcels else None

    ocpa_taxes = ocpa_total = ocpa_nav = None
    if pid:
        try:
            ocpa_taxes = _api_get(f"{OCPA_BASE}/PRC/GetPRCCertifiedTaxes", {"PID": pid, "TaxYear": 0})
        except SystemExit:
            pass
        try:
            ocpa_total = _api_get(f"{OCPA_BASE}/PRC/GetPRCTotalTaxes", {"PID": pid, "TaxYear": 0})
        except SystemExit:
            pass
        try:
            ocpa_nav = _api_get(f"{OCPA_BASE}/PRC/GetPRCNonAdValorem", {"PID": pid, "TaxYear": 0})
        except SystemExit:
            pass

    if _json_opt(ctx):
        click.echo(json_mod.dumps({
            "algolia_hits": hits, "certified_taxes": ocpa_taxes,
            "total_taxes": ocpa_total, "non_ad_valorem": ocpa_nav,
        }, indent=2))
        return

    if not hits and not ocpa_taxes:
        console.print("[red]No tax records found.[/red]")
        sys.exit(1)

    if hits:
        for hit in hits[:3]:
            name = hit.get("display_name", "Unknown")
            cp = hit.get("custom_parameters", {})
            public_url = cp.get("public_url", "")
            entities = cp.get("entities", [])
            table = Table(title=f"💰 Tax Record: {name}", box=box.ROUNDED, show_header=False, title_style="bold green")
            table.add_column("Field", style="bold")
            table.add_column("Value")
            if entities:
                ent = entities[0]
                table.add_row("Owner", ent.get("name", ""))
                table.add_row("Address", f"{ent.get('address', '')} {ent.get('city', '')}, {ent.get('state', '')} {ent.get('zip', '')}")
            children = []
            for cg in hit.get("child_groups", []):
                children.extend(cg.get("children", []))
            for child in children[:3]:
                ccp = child.get("custom_parameters", {})
                table.add_row("Account", child.get("external_id", ""))
                table.add_row("Roll Year", ccp.get("roll_year", ""))
            if public_url:
                table.add_row("Bill URL", f"https://county-taxes.net{public_url}")
            console.print(table)
            console.print()

    if ocpa_taxes and isinstance(ocpa_taxes, list) and ocpa_taxes:
        table = Table(title="📋 Certified Taxes (OCPA)", box=box.ROUNDED)
        table.add_column("Authority", style="bold")
        table.add_column("Millage", justify="right")
        table.add_column("Tax Amount", justify="right", style="green")
        for t in ocpa_taxes:
            table.add_row(str(t.get("authorityName", "")), str(t.get("millageRate", "")), fmt_currency(t.get("certifiedTax")))
        console.print(table)

    if ocpa_total and isinstance(ocpa_total, list) and ocpa_total:
        for t in ocpa_total:
            console.print(f"\n[bold]Total Taxes ({t.get('taxYear', '')}):[/bold] {fmt_currency(t.get('totalTax'))}")

    if ocpa_nav and isinstance(ocpa_nav, list) and ocpa_nav:
        table = Table(title="📋 Non-Ad Valorem Assessments", box=box.ROUNDED)
        table.add_column("Assessment", style="bold")
        table.add_column("Amount", justify="right", style="yellow")
        for n in ocpa_nav:
            table.add_row(str(n.get("levyDescription", "")), fmt_currency(n.get("levyAmount")))
        console.print(table)

@property.command("homestead")
@click.argument("address_or_parcel", required=False)
@click.pass_context
def property_homestead(ctx, address_or_parcel):
    """Homestead Exemption — check status or view guide.

    \b
    With address/parcel: checks homestead status via OCPA API.
    Without argument: shows the application guide.

    \b
    Examples:
      ocfl property homestead
      ocfl property homestead "123 Main St, Orlando"
      ocfl property homestead 272035664500001
    """
    if not address_or_parcel:
        if _json_opt(ctx):
            click.echo(json_mod.dumps(SERVICES_DB["homestead"], indent=2))
            return
        _render_service("homestead")
        return

    results = resolve_parcel(address_or_parcel)
    if not results:
        console.print("[red]No properties found.[/red]")
        sys.exit(1)

    for res in results[:5]:
        pid = res.get("parcelId", "")
        if not pid:
            continue
        info = _api_get(f"{OCPA_BASE}/PRC/GetPRCGeneralInfo", {"pid": pid})

        if _json_opt(ctx):
            click.echo(json_mod.dumps({"parcelId": pid, "info": info, "isHomestead": res.get("isHomestead")}, indent=2))
            return

        hs = res.get("isHomestead") == "True"

        # Fetch property values for market vs assessed comparison
        values_data = _api_get(f"{OCPA_BASE}/PRC/GetPRCPropertyValues", {"PID": pid, "TaxYear": 0, "ShowAllFlag": 1})

        table = Table(title=f"🏠 Homestead Status: {pid}", box=box.ROUNDED, show_header=False, title_style="bold cyan")
        table.add_column("Field", style="bold")
        table.add_column("Value")
        table.add_row("Owner", info.get("ownerName", "N/A").strip())
        table.add_row("Address", info.get("propertyAddress", "N/A"))
        table.add_row("Parcel ID", pid)
        table.add_row("Homestead", "[bold green]✅ Homestead exemption is active[/bold green]" if hs else "[bold red]❌ No homestead exemption[/bold red]")
        table.add_row("DOR Code", f"{info.get('dorCode', '')} — {info.get('dorDescription', '')}")

        # Show current assessed vs market value
        if isinstance(values_data, list) and values_data:
            latest = sorted(values_data, key=lambda x: x.get("taxYear", 0), reverse=True)[0]
            jv = latest.get("justValue")
            av = latest.get("assessedValue")
            tv = latest.get("taxableValue")
            yr = latest.get("taxYear", "")
            table.add_row("", "")
            table.add_row(f"[bold]Values ({yr})[/bold]", "")
            table.add_row("  Market (Just) Value", fmt_currency(jv))
            table.add_row("  Assessed Value", fmt_currency(av))
            table.add_row("  Taxable Value", fmt_currency(tv))
            if jv and av:
                try:
                    soh_savings = float(jv) - float(av)
                    if soh_savings > 0:
                        table.add_row("  SOH Cap Savings", f"[green]{fmt_currency(soh_savings)}[/green]")
                except (ValueError, TypeError):
                    pass

        if not hs:
            table.add_row("", "")
            table.add_row("[yellow]Eligibility[/yellow]", "")
            table.add_row("  Deadline", "March 1 each year")
            table.add_row("  Savings", "Up to $50,000 off taxable value ($750-$1,000+/yr)")
            table.add_row("  Apply", "https://www.ocpafl.org/Exemptions/Homestead.aspx")
            table.add_row("  Phone", "(407) 836-5044")

        console.print(table)
        console.print()


@property.command("appraisal")
@click.argument("address_or_parcel", required=False)
@click.pass_context
def property_appraisal(ctx, address_or_parcel):
    """Appraisal Appeal (TRIM/VAB) — view values or guide.

    \b
    With address/parcel: shows assessment history to evaluate appeal.
    Without argument: shows the TRIM/VAB appeal guide.

    \b
    Examples:
      ocfl property appraisal
      ocfl property appraisal "123 Main St, Orlando"
    """
    if not address_or_parcel:
        if _json_opt(ctx):
            click.echo(json_mod.dumps(SERVICES_DB["appraisal"], indent=2))
            return
        _render_service("appraisal")
        return

    results = resolve_parcel(address_or_parcel)
    if not results:
        console.print("[red]No properties found.[/red]")
        sys.exit(1)

    for res in results[:3]:
        pid = res.get("parcelId", "")
        if not pid:
            continue
        info = _api_get(f"{OCPA_BASE}/PRC/GetPRCGeneralInfo", {"pid": pid})
        values_data = _api_get(f"{OCPA_BASE}/PRC/GetPRCPropertyValues", {"PID": pid, "TaxYear": 0, "ShowAllFlag": 1})

        if _json_opt(ctx):
            click.echo(json_mod.dumps({"parcelId": pid, "info": info, "values": values_data}, indent=2))
            return

        console.print(f"\n[bold cyan]📊 Appraisal History: {pid}[/bold cyan]")
        console.print(f"[bold]Owner:[/bold] {info.get('ownerName', 'N/A').strip()}")
        console.print(f"[bold]Address:[/bold] {info.get('propertyAddress', 'N/A')}")
        console.print(f"[bold]DOR Code:[/bold] {info.get('dorCode', '')} — {info.get('dorDescription', '')}\n")

        if isinstance(values_data, list) and values_data:
            table = Table(title="Assessment History", box=box.ROUNDED)
            table.add_column("Year", style="cyan", justify="right")
            table.add_column("Market Value", justify="right")
            table.add_column("Assessed", justify="right")
            table.add_column("SOH Cap", justify="right")
            table.add_column("Taxable", justify="right")
            table.add_column("Assessed YoY", justify="right")

            prev_assessed = None
            rows = []
            cap_warning = False
            for v in sorted(values_data, key=lambda x: x.get("taxYear", 0)):
                yr = v.get("taxYear", "")
                jv = v.get("justValue")
                av = v.get("assessedValue")
                tv = v.get("taxableValue")
                # SOH cap savings = just value - assessed value
                soh = ""
                if jv and av:
                    try:
                        diff = float(jv) - float(av)
                        soh = fmt_currency(diff) if diff > 0 else "—"
                    except (ValueError, TypeError):
                        pass
                change = ""
                if prev_assessed and av and prev_assessed > 0:
                    try:
                        pct = (float(av) - float(prev_assessed)) / float(prev_assessed) * 100
                        if pct > 3:
                            color = "red"
                            cap_warning = True
                        elif pct < 0:
                            color = "green"
                        else:
                            color = "yellow"
                        change = f"[{color}]{pct:+.1f}%[/{color}]"
                    except (ValueError, TypeError):
                        pass
                if av:
                    try:
                        if float(av) > 0:
                            prev_assessed = float(av)
                    except (ValueError, TypeError):
                        pass
                rows.append((str(yr), fmt_currency(jv), fmt_currency(av), soh, fmt_currency(tv), change))

            for row in rows:
                table.add_row(*row)
            console.print(table)

            if cap_warning:
                console.print("\n[bold red]⚠️  Assessed value grew faster than 3% (CPI cap) in some years.[/bold red]")

        console.print(f"\n[bold yellow]💡 If you believe market value is too high, you can file a TRIM petition by September 15.[/bold yellow]")
        console.print(f"[dim]Deadline: 25 days after TRIM notice (usually mid-September).[/dim]")
        console.print(f"[dim]Info: ocfl property appraisal (no argument) | Phone: (407) 836-5044[/dim]\n")

property.command("flood")(_make_info_cmd("flood"))
property.command("domicile")(_make_info_cmd("domicile"))


# ════════════════════════════════════════════════════════════════
# GROUP: vehicles
# ════════════════════════════════════════════════════════════════

@cli.group()
@click.pass_context
def vehicles(ctx):
    """🚗 Vehicle registration, titles, boat, mobile home, DMV."""
    pass

vehicles.command("registration")(_make_info_cmd("vehicle"))
vehicles.command("title")(_make_info_cmd("titles"))
vehicles.command("boat")(_make_info_cmd("boat"))
vehicles.command("mobilehome")(_make_info_cmd("mobilehome"))
vehicles.command("dmv")(_make_info_cmd("dmv"))


# ════════════════════════════════════════════════════════════════
# GROUP: courts
# ════════════════════════════════════════════════════════════════

@cli.group()
@click.pass_context
def courts(ctx):
    """⚖️ Marriage, deeds, vitals, passport, notary, probate, jury, records, PD."""
    pass

courts.command("marriage")(_make_info_cmd("marriage"))
courts.command("deeds")(_make_info_cmd("deeds"))
courts.command("vitals")(_make_info_cmd("vitals"))
courts.command("passport")(_make_info_cmd("passport"))
courts.command("notary")(_make_info_cmd("notary"))
courts.command("probate")(_make_info_cmd("probate"))
courts.command("jury")(_make_info_cmd("jury"))
@courts.command("records")
@click.argument("query", required=False)
@click.pass_context
def courts_records(ctx, query):
    """Public Records / Sunshine Law Request — info or search tip.

    \b
    Without argument: shows public records request guide.
    With query: provides direct links to search Official Records.

    \b
    Examples:
      ocfl courts records
      ocfl courts records "deed Smith"
    """
    if not query:
        if _json_opt(ctx):
            click.echo(json_mod.dumps(SERVICES_DB["records"], indent=2))
            return
        _render_service("records")
        return

    if _json_opt(ctx):
        click.echo(json_mod.dumps({
            "query": query,
            "search_urls": {
                "comptroller_official_records": "https://www.occompt.com/services/official-records/",
                "clerk_case_search": "https://myorangeclerk.com/",
                "sheriff_records": "https://ocso-fl.nextrequest.com/",
                "public_records_email": "PublicRecordRequest@ocfl.net",
            },
        }, indent=2))
        return

    console.print(f"[bold]📋 Public Records Search: '{query}'[/bold]\n")
    console.print("[yellow]Official Records search requires browser interaction.[/yellow]\n")
    console.print("[bold]Search these resources:[/bold]")
    console.print(f"  📄 [cyan]Comptroller Official Records[/cyan] (deeds, liens, mortgages):")
    console.print(f"     https://www.occompt.com/services/official-records/")
    console.print(f"  ⚖️  [cyan]Clerk Case Search[/cyan] (court cases):")
    console.print(f"     https://myorangeclerk.com/")
    console.print(f"  🔫 [cyan]Sheriff Records[/cyan] (incident reports, arrests):")
    console.print(f"     https://ocso-fl.nextrequest.com/")
    console.print(f"\n[bold]Or submit a formal request:[/bold]")
    console.print(f"  📧 PublicRecordRequest@ocfl.net")
    console.print(f"  📞 (407) 836-3111")
    console.print(f"\n[dim]FL Sunshine Law: No ID or reason required. Agencies must respond promptly.[/dim]")
courts.command("pd")(_make_info_cmd("pd"))


# ════════════════════════════════════════════════════════════════
# GROUP: elections
# ════════════════════════════════════════════════════════════════

@cli.group()
@click.pass_context
def elections(ctx):
    """🗳️ Voter registration, ballots, election info."""
    pass

@elections.command("voter")
@click.argument("name", required=False)
@click.pass_context
def elections_voter(ctx, name):
    """Voter Registration — info and lookup.

    \b
    Without argument: shows registration guide.
    With name: shows how to check your status online
    (FL voter lookup requires reCAPTCHA, cannot be automated).

    \b
    Examples:
      ocfl elections voter
      ocfl elections voter "Jane Doe"
    """
    if not name:
        if _json_opt(ctx):
            click.echo(json_mod.dumps(SERVICES_DB["voter"], indent=2))
            return
        _render_service("voter")
        return

    # Can't automate due to reCAPTCHA - provide direct link
    if _json_opt(ctx):
        click.echo(json_mod.dumps({
            "note": "FL voter lookup requires reCAPTCHA",
            "url": "https://registration.elections.myflorida.com/CheckVoterStatus",
            "local_url": "https://www.ocfelections.com/",
            "phone": "(407) 836-2070",
        }, indent=2))
        return

    console.print(f"[bold]🗳️  Voter Lookup: {name}[/bold]\n")
    console.print("[yellow]FL voter status lookup requires reCAPTCHA and cannot be automated.[/yellow]\n")
    console.print("[bold]Check your status online:[/bold]")
    console.print("  🔗 https://registration.elections.myflorida.com/CheckVoterStatus")
    console.print("     Enter: First Name, Last Name, Date of Birth\n")
    console.print("[bold]Orange County Elections:[/bold]")
    console.print("  🔗 https://www.ocfelections.com/")
    console.print("  📞 (407) 836-2070")
    console.print("  📍 119 W Kaley St, Orlando 32806")
elections.command("ballot")(_make_info_cmd("ballot"))
elections.command("info")(_make_info_cmd("elections_info"))


# ════════════════════════════════════════════════════════════════
# GROUP: permits
# ════════════════════════════════════════════════════════════════

@cli.group()
@click.pass_context
def permits(ctx):
    """📋 Permit database, business tax, STR, building inspections, DBA."""
    pass

@permits.command("lookup")
@click.argument("permit_type", required=False)
@click.pass_context
def permits_lookup(ctx, permit_type):
    """Look up permit requirements, fees, and submission info.

    \b
    Examples:
      ocfl permits lookup
      ocfl permits lookup fence
      ocfl permits lookup pool
    """
    if not permit_type or permit_type == "list":
        if _json_opt(ctx):
            click.echo(json_mod.dumps({k: v["name"] for k, v in PERMITS_DB.items()}, indent=2))
            return
        table = Table(title="📋 Available Permit Types", box=box.ROUNDED)
        table.add_column("Code", style="cyan bold")
        table.add_column("Name")
        table.add_column("Fee")
        table.add_column("Review Time")
        for code, info in PERMITS_DB.items():
            table.add_row(code, info["name"], info["fee"], info["review_time"])
        console.print(table)
        console.print("\nRun: [bold]ocfl permits lookup <code>[/bold] for details")
        console.print(f"🔗 Fast Track Portal: https://fasttrack.ocfl.net")
        return

    key = permit_type.lower().replace("-", "_").replace(" ", "_")
    if key not in PERMITS_DB:
        best = None
        best_score = 0
        for k in PERMITS_DB:
            ratio = SequenceMatcher(None, key, k).ratio()
            if ratio > best_score:
                best_score = ratio
                best = k
        if best and best_score > 0.5:
            key = best
        else:
            console.print(f"[red]Unknown permit type '{permit_type}'.[/red]")
            console.print(f"Available: {', '.join(PERMITS_DB.keys())}")
            sys.exit(1)

    p = PERMITS_DB[key]
    if _json_opt(ctx):
        click.echo(json_mod.dumps(p, indent=2))
        return

    panel_text = f"""[bold]{p['name']}[/bold]

[bold]Fee:[/bold] {p['fee']}
[bold]Review Time:[/bold] {p['review_time']}
[bold]Valid:[/bold] {p.get('valid', 'N/A')}
[bold]Submit Via:[/bold] {p['submit']}
"""
    if p.get("height"):
        panel_text += f"[bold]Height Limits:[/bold] {p['height']}\n"
    panel_text += "\n[bold]Requirements:[/bold]\n"
    for req in p["requirements"]:
        panel_text += f"  ☐ {req}\n"
    console.print(Panel(panel_text, title=f"📋 {key.upper()}", border_style="blue"))

@permits.command("biztax")
@click.argument("name", required=False)
@click.option("--limit", default=10, help="Max results")
@click.pass_context
def permits_biztax(ctx, name, limit):
    """Business Tax Receipt — search by name or view guide.

    \b
    With business name: searches Algolia for BTR records.
    Without argument: shows the BTR application guide.

    \b
    Examples:
      ocfl permits biztax
      ocfl permits biztax "McDonalds"
      ocfl permits biztax "nail salon" --limit 5
    """
    if not name:
        if _json_opt(ctx):
            click.echo(json_mod.dumps(SERVICES_DB["biztax"], indent=2))
            return
        _render_service("biztax")
        return

    algolia_data = _api_post(
        ALGOLIA_URL,
        json_data={"requests": [{"indexName": "fl-orange.business_tax", "params": f"query={name}&hitsPerPage={limit}"}]},
        params={"x-algolia-api-key": ALGOLIA_KEY, "x-algolia-application-id": ALGOLIA_APP},
    )
    hits = []
    if algolia_data and "results" in algolia_data:
        hits = algolia_data["results"][0].get("hits", [])

    if _json_opt(ctx):
        click.echo(json_mod.dumps(hits, indent=2))
        return

    if not hits:
        console.print(f"[yellow]No business tax records for '{name}'.[/yellow]")
        return

    table = Table(title=f"💼 Business Tax: '{name}' — {len(hits)} result(s)", box=box.ROUNDED)
    table.add_column("Business", style="bold", max_width=35)
    table.add_column("Account #", style="cyan")
    table.add_column("Address", max_width=40)
    table.add_column("Receipt", style="dim")

    for hit in hits:
        biz_name = hit.get("display_name", "")
        acct = hit.get("external_id", "")
        cp = hit.get("custom_parameters", {})
        entities = cp.get("entities", [])
        addr = ""
        for ent in entities:
            if ent.get("external_type") == "Business Address":
                addr = f"{ent.get('address', '')} {ent.get('city', '')}, {ent.get('state', '')} {ent.get('zip', '')}"
                break

        receipt = ""
        for cg in hit.get("child_groups", []):
            for child in cg.get("children", []):
                ccp = child.get("custom_parameters", {})
                receipt = f"{child.get('external_id', '')} ({ccp.get('year', '')})"
                break

        public_url = cp.get("public_url", "")
        table.add_row(biz_name, acct, addr, receipt)

    console.print(table)
    console.print(f"\n🔗 https://county-taxes.net/public/business_tax")

permits.command("str")(_make_info_cmd("str"))
permits.command("inspection")(_make_info_cmd("inspection"))
permits.command("dba")(_make_info_cmd("dba"))


# ════════════════════════════════════════════════════════════════
# GROUP: safety
# ════════════════════════════════════════════════════════════════

@cli.group()
@click.pass_context
def safety(ctx):
    """🛡️ Hurricane, animal control, CCW, fingerprinting, DV, code enforcement."""
    pass

safety.command("hurricane")(_make_info_cmd("hurricane"))
safety.command("stray")(_make_info_cmd("stray"))
safety.command("ccw")(_make_info_cmd("ccw"))
safety.command("fingerprint")(_make_info_cmd("fingerprint"))
safety.command("dv")(_make_info_cmd("dv"))
safety.command("code")(_make_info_cmd("code"))


# ════════════════════════════════════════════════════════════════
# GROUP: health
# ════════════════════════════════════════════════════════════════

@cli.group()
@click.pass_context
def health(ctx):
    """🏥 Restaurant inspections, clinics, mosquito control, crisis services."""
    pass

@health.command("inspections")
@click.argument("name")
@click.option("--limit", default=20, help="Max results to show")
@click.pass_context
def health_inspections(ctx, name, limit):
    """Search FL DBPR for restaurant/hotel inspections in Orange County.

    \b
    Examples:
      ocfl health inspections "McDonalds"
      ocfl health inspections "Hilton" --limit 5
    """
    DBPR_BASE = "https://www.myfloridalicense.com"

    try:
        r = SESSION.get(f"{DBPR_BASE}/wl11.asp?mode=0&SID=&brd=H", timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        console.print(f"[red]Could not reach DBPR:[/red] {e}")
        sys.exit(1)

    soup = BeautifulSoup(r.text, "html.parser")
    sid_field = soup.find("input", {"name": "hSID"})
    sid = sid_field["value"] if sid_field and sid_field.get("value") else ""

    form_data = {
        "hSID": sid, "hSearchType": "", "hLastName": "", "hFirstName": "",
        "hMiddleName": "", "hOrgName": "", "hSearchOpt": "", "hSearchOpt2": "",
        "hSearchAltName": "", "hSearchPartName": "", "hSearchFuzzy": "",
        "hDivision": "", "hBoard": "", "hLicenseType": "", "hSpecQual": "",
        "hAddrType": "", "hCity": "", "hCounty": "", "hState": "",
        "hLicNbr": "", "hAction": "", "hCurrPage": "", "hTotalPages": "",
        "hTotalRecords": "", "hPageAction": "", "hDDChange": "",
        "hBoardType": "", "hLicTyp": "", "hSearchHistoric": "",
        "hRecsPerPage": "",
        "OrgName": name, "LastName": "", "FirstName": "", "MiddleName": "",
        "Board": "200", "LicenseType": "", "SpecQual": "",
        "City": "", "County": "58", "State": "FL",
        "RecsPerPage": "50", "SearchPartName": "Part",
    }

    try:
        r2 = SESSION.post(
            f"{DBPR_BASE}/wl11.asp?mode=2&search=Name&SID={sid}&brd=H&typ=N",
            data=form_data, timeout=20,
        )
        r2.raise_for_status()
    except requests.RequestException as e:
        console.print(f"[red]Search failed:[/red] {e}")
        sys.exit(1)

    html = r2.text
    soup2 = BeautifulSoup(r2.text, "html.parser")
    results = []

    total_match = re.search(r'(\d+)\s*Records?', html)
    total_records = int(total_match.group(1)) if total_match else 0

    addr_tables = [t for t in soup2.find_all("table") if len(t.find_all("tr")) == 3]
    addresses = []
    for t in addr_tables:
        first_row = t.find("tr")
        cells = first_row.find_all("td") if first_row else []
        if len(cells) == 2 and "Address" in cells[0].get_text():
            addresses.append(cells[1].get_text(strip=True))

    pattern = re.compile(
        r"<a\s+href='(inspectionDates\.asp\?[^']+)'[^>]*>([^<]+)</a></font></td>"
        r"<td[^>]*><font[^>]*>([^<]+)</font></td>"
        r"<td[^>]*><font[^>]*>([^<]+(?:<br/>[\w\s,/]+)*)</font></td>"
        r"<td[^>]*><font[^>]*>([^<]+(?:<br/>[\d/]+)*)</font></td>",
        re.IGNORECASE | re.DOTALL,
    )

    for i, m in enumerate(pattern.finditer(html)):
        detail_href = m.group(1)
        rname = m.group(2).strip()
        name_type = m.group(3).strip()
        license_info = re.sub(r'<br\s*/?>', ' / ', m.group(4)).strip()
        status_info = re.sub(r'<br\s*/?>', ' / ', m.group(5)).strip()
        detail_url = f"{DBPR_BASE}/{detail_href}"
        addr = addresses[i] if i < len(addresses) else ""

        results.append({
            "name": rname, "type": name_type, "license": license_info,
            "status": status_info, "address": addr, "url": detail_url,
        })

    if _json_opt(ctx):
        click.echo(json_mod.dumps(results[:limit], indent=2))
        return

    if not results:
        if "no record" in html.lower() or "0 record" in html.lower():
            console.print(f"[yellow]No results for '{name}' in Orange County.[/yellow]")
        else:
            console.print(f"[yellow]No results parsed for '{name}'. Try the web:[/yellow]")
            console.print(f"🔗 {DBPR_BASE}/wl11.asp?mode=0&SID=&brd=H")
        return

    table = Table(title=f"🍽️  DBPR: '{name}' — {total_records} total", box=box.ROUNDED)
    table.add_column("Name", style="bold", max_width=35)
    table.add_column("License #", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Address", max_width=40)

    for r in results[:limit]:
        table.add_row(r["name"], r["license"], r["status"], r["address"])

    console.print(table)
    console.print(f"\n[dim]Showing {min(limit, len(results))} of {total_records} results[/dim]")
    console.print(f"🔗 DBPR: {DBPR_BASE}/wl11.asp?mode=0&SID=&brd=H")

health.command("mosquito")(_make_info_cmd("mosquito"))
health.command("clinic")(_make_info_cmd("clinic"))
health.command("crisis")(_make_info_cmd("crisis"))
health.command("vector")(_make_info_cmd("vector"))
health.command("cemetery")(_make_info_cmd("cemetery"))


# ════════════════════════════════════════════════════════════════
# GROUP: utilities
# ════════════════════════════════════════════════════════════════

@cli.group()
@click.pass_context
def utilities(ctx):
    """🔧 311, trash/recycling, pothole reports, drainage, dumping."""
    pass

utilities.command("311")(_make_info_cmd("311"))
utilities.command("trash")(_make_info_cmd("trash"))
utilities.command("pothole")(_make_info_cmd("pothole"))
utilities.command("drainage")(_make_info_cmd("drainage"))
utilities.command("dumping")(_make_info_cmd("dumping"))


# ════════════════════════════════════════════════════════════════
# GROUP: community
# ════════════════════════════════════════════════════════════════

@cli.group()
@click.pass_context
def community(ctx):
    """🤝 Seniors, family services, Medicaid, workforce, UF extension."""
    pass

community.command("seniors")(_make_info_cmd("seniors"))
community.command("family")(_make_info_cmd("family"))
community.command("medicaid")(_make_info_cmd("medicaid"))
community.command("workforce")(_make_info_cmd("workforce"))
community.command("extension")(_make_info_cmd("extension"))


# ════════════════════════════════════════════════════════════════
# GROUP: recreation
# ════════════════════════════════════════════════════════════════

@cli.group()
@click.pass_context
def recreation(ctx):
    """🎾 Park reservations, library card, hunting/fishing, arts grants."""
    pass

recreation.command("reserve")(_make_info_cmd("reserve"))
recreation.command("libcard")(_make_info_cmd("libcard"))
recreation.command("hunting")(_make_info_cmd("hunting"))
recreation.command("arts")(_make_info_cmd("arts"))


# ════════════════════════════════════════════════════════════════
# GROUP: government
# ════════════════════════════════════════════════════════════════

@cli.group()
@click.pass_context
def government(ctx):
    """🏛️ Budget transparency, procurement/bid opportunities."""
    pass

government.command("budget")(_make_info_cmd("budget"))
government.command("bids")(_make_info_cmd("bids"))


# ════════════════════════════════════════════════════════════════
# TOP-LEVEL: gis
# ════════════════════════════════════════════════════════════════

@cli.group(invoke_without_command=True)
@click.option("--layer", help="Layer name to search")
@click.option("--near", help="Lat,Lon for proximity search")
@click.option("--radius", default=5000, help="Search radius in meters (default 5000)")
@click.option("--address", help="Address for spatial query")
@click.pass_context
def gis(ctx, layer, near, radius, address):
    """🗺️ Query OCFL ArcGIS data layers.

    \b
    Examples:
      ocfl gis layers
      ocfl gis flood "201 S Rosalind Ave, Orlando"
      ocfl gis --layer "Fire Stations" --near 28.54,-81.38
    """
    if ctx.invoked_subcommand:
        return
    if not layer:
        click.echo(ctx.get_help())
        return

    found = _find_layer(layer)
    if not found:
        console.print(f"[red]Layer '{layer}' not found.[/red]")
        sys.exit(1)
    lid, lname = found

    if near:
        parts = near.split(",")
        lat, lon = float(parts[0]), float(parts[1])
    elif address:
        geo = geocode_address(address)
        if not geo:
            console.print("[red]Could not geocode address.[/red]")
            sys.exit(1)
        lat, lon = geo["lat"], geo["lon"]
    else:
        console.print("[red]Provide --near or --address.[/red]")
        sys.exit(1)

    data = _gis_nearby_query(lid, lon, lat, radius)
    features = data.get("features", [])

    if _json_opt(ctx):
        click.echo(json_mod.dumps(features, indent=2))
        return

    if not features:
        console.print(f"[yellow]No features found in '{lname}' near that location.[/yellow]")
        return

    console.print(f"[bold cyan]{lname}[/bold cyan] — {len(features)} result(s)\n")
    for f in features[:20]:
        attrs = f.get("attributes", {})
        for k, v in attrs.items():
            if v is not None and v != "" and k not in ("OBJECTID", "Shape", "Shape.STArea()", "Shape.STLength()"):
                console.print(f"  [bold]{k}:[/bold] {v}")
        console.print()


@gis.command("layers")
@click.pass_context
def gis_layers(ctx):
    """List all available GIS data layers."""
    layers = _get_gis_layers()
    if _json_opt(ctx):
        click.echo(json_mod.dumps(layers, indent=2))
        return
    table = Table(title="🗺️  OCFL ArcGIS Open Data Layers", box=box.ROUNDED)
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Layer Name", style="bold")
    for lid in sorted(layers.keys(), key=lambda x: int(x)):
        table.add_row(str(lid), layers[lid])
    console.print(table)


@gis.command("flood")
@click.argument("address")
@click.pass_context
def gis_flood(ctx, address):
    """FEMA flood zone lookup for an address.

    \b
    Example:
      ocfl gis flood "201 S Rosalind Ave, Orlando"
    """
    geo = geocode_address(address)
    if not geo:
        console.print("[red]Could not geocode address.[/red]")
        sys.exit(1)

    data = _gis_point_query(19, geo["lon"], geo["lat"])
    features = data.get("features", [])

    if _json_opt(ctx):
        click.echo(json_mod.dumps({"geocode": geo, "flood_zones": features}, indent=2))
        return

    console.print(f"[bold]📍 {geo['address']}[/bold] (score: {geo['score']})\n")
    if not features:
        console.print("[green]✅ No FEMA flood zone found at this location.[/green]")
        return

    for f in features:
        attrs = f.get("attributes", {})
        zone = attrs.get("FLD_ZONE", attrs.get("ZONE_SUBTY", "Unknown"))
        panel = attrs.get("PANEL", "")
        firm = attrs.get("FIRM_PAN", "")
        console.print(f"[bold red]🌊 Flood Zone: {zone}[/bold red]")
        if panel:
            console.print(f"  Panel: {panel}")
        if firm:
            console.print(f"  FIRM Panel: {firm}")
        for k, v in attrs.items():
            if v and k not in ("FLD_ZONE", "PANEL", "FIRM_PAN", "OBJECTID", "Shape", "Shape.STArea()", "Shape.STLength()"):
                console.print(f"  {k}: {v}")


@gis.command("zoning")
@click.argument("address")
@click.pass_context
def gis_zoning(ctx, address):
    """Zoning lookup for an address."""
    geo = geocode_address(address)
    if not geo:
        console.print("[red]Could not geocode address.[/red]")
        sys.exit(1)
    data = _gis_point_query(21, geo["lon"], geo["lat"])
    features = data.get("features", [])
    if _json_opt(ctx):
        click.echo(json_mod.dumps({"geocode": geo, "zoning": features}, indent=2))
        return
    console.print(f"[bold]📍 {geo['address']}[/bold]\n")
    if not features:
        console.print("[yellow]No zoning/land use data found.[/yellow]")
        return
    for f in features:
        attrs = f.get("attributes", {})
        for k, v in attrs.items():
            if v is not None and v != "" and k not in ("OBJECTID", "Shape", "Shape.STArea()", "Shape.STLength()"):
                console.print(f"  [bold]{k}:[/bold] {v}")


@gis.command("fire-stations")
@click.option("--near", help="Lat,Lon (e.g. 28.54,-81.38)")
@click.option("--address", help="Address to search near")
@click.pass_context
def gis_fire_stations(ctx, near, address):
    """Find nearest fire stations."""
    if near:
        parts = near.split(",")
        lat, lon = float(parts[0]), float(parts[1])
    elif address:
        geo = geocode_address(address)
        if not geo:
            console.print("[red]Could not geocode.[/red]")
            sys.exit(1)
        lat, lon = geo["lat"], geo["lon"]
    else:
        lat, lon = 28.54, -81.38
    data = _gis_nearby_query(20, lon, lat, 20000, limit=20)
    features = data.get("features", [])
    if _json_opt(ctx):
        click.echo(json_mod.dumps(features, indent=2))
        return
    if not features:
        console.print("[yellow]No fire stations found.[/yellow]")
        return
    table = Table(title="🚒 Fire Stations", box=box.ROUNDED)
    table.add_column("Station", style="bold")
    table.add_column("Address")
    table.add_column("Jurisdiction")
    for f in features:
        a = f.get("attributes", {})
        table.add_row(str(a.get("STATION_NAME", a.get("STATION", ""))),
                      str(a.get("FULL_ADDRESS", a.get("ADDRESS", ""))),
                      str(a.get("JURISDICTION", a.get("AGENCY_ID", ""))))
    console.print(table)


@gis.command("hospitals")
@click.option("--near", help="Lat,Lon")
@click.option("--address", help="Address to search near")
@click.pass_context
def gis_hospitals(ctx, near, address):
    """Find nearest hospitals."""
    if near:
        parts = near.split(",")
        lat, lon = float(parts[0]), float(parts[1])
    elif address:
        geo = geocode_address(address)
        if not geo:
            console.print("[red]Could not geocode.[/red]")
            sys.exit(1)
        lat, lon = geo["lat"], geo["lon"]
    else:
        lat, lon = 28.54, -81.38
    data = _gis_nearby_query(25, lon, lat, 30000, limit=20)
    features = data.get("features", [])
    if _json_opt(ctx):
        click.echo(json_mod.dumps(features, indent=2))
        return
    if not features:
        console.print("[yellow]No hospitals found.[/yellow]")
        return
    table = Table(title="🏥 Hospitals", box=box.ROUNDED)
    table.add_column("Name", style="bold")
    table.add_column("Address")
    table.add_column("Type")
    for f in features:
        a = f.get("attributes", {})
        table.add_row(str(a.get("NAME", a.get("FACNAME", ""))),
                      str(a.get("ADDRESS", a.get("FULLADDR", ""))),
                      str(a.get("TYPE", a.get("FACTYPE", ""))))
    console.print(table)


# ════════════════════════════════════════════════════════════════
# TOP-LEVEL: geocode
# ════════════════════════════════════════════════════════════════

@cli.command("geocode")
@click.argument("address")
@click.pass_context
def geocode_cmd(ctx, address):
    """📍 Geocode an Orange County address.

    \b
    Examples:
      ocfl geocode "201 S Rosalind Ave, Orlando"
      ocfl geocode "1321 Apopka Airport Rd"
    """
    data = _api_get(GEOCODER, {"Street": address, "outFields": "*", "f": "json", "maxLocations": 5, "outSR": 4326})
    candidates = data.get("candidates", [])
    # Auto-retry with OC cities if no results
    if not candidates:
        addr_lower = address.lower()
        has_city = any(c.lower() in addr_lower for c in OC_CITIES)
        if not has_city:
            for city in OC_CITIES:
                data = _api_get(GEOCODER, {"Street": f"{address}, {city}", "outFields": "*", "f": "json", "maxLocations": 5, "outSR": 4326})
                candidates = data.get("candidates", [])
                if candidates:
                    break
    if _json_opt(ctx):
        click.echo(json_mod.dumps(candidates, indent=2))
        return
    if not candidates:
        console.print(f"[red]No matches for '{address}'[/red]")
        sys.exit(1)
    for c in candidates:
        loc = c["location"]
        score = c.get("score", 0)
        addr = c.get("address", "")
        color = "green" if score >= 90 else "yellow" if score >= 70 else "red"
        console.print(f"[bold]{addr}[/bold]")
        console.print(f"  Lat: {loc['y']:.6f}  Lon: {loc['x']:.6f}  Score: [{color}]{score}[/{color}]")
        attrs = c.get("attributes", {})
        if attrs:
            for k, v in attrs.items():
                if v and k not in ("Match_addr", "Addr_type", "Score"):
                    console.print(f"  {k}: {v}")
        console.print()


# ════════════════════════════════════════════════════════════════
# TOP-LEVEL: pets
# ════════════════════════════════════════════════════════════════

@cli.command()
@click.option("--type", "pet_type", type=click.Choice(["dog", "cat"], case_sensitive=False), help="Filter by animal type")
@click.option("--ready", is_flag=True, help="Only show animals ready to adopt")
@click.option("--age", help="Age filter (e.g. '<1', '1-3', '4-6')")
@click.option("--gender", type=click.Choice(["M", "F"], case_sensitive=False), help="Filter by gender")
@click.option("--limit", default=20, help="Max results (default 20)")
@click.pass_context
def pets(ctx, pet_type, ready, age, gender, limit):
    """🐾 Search adoptable pets at Orange County Animal Services.

    \b
    Examples:
      ocfl pets --ready --limit 10
      ocfl pets --type dog --gender F
    """
    try:
        r = SESSION.get(PETS_URL, params={"page": 1, "pagesize": 200}, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        console.print(f"[red]Could not reach Animal Services:[/red] {e}")
        sys.exit(1)

    soup = BeautifulSoup(r.text, "html.parser")
    animals = []
    cards = soup.select("a.LightBox_Box")
    for card in cards:
        aid = card.get("id", "")
        if not aid or not re.match(r'A\d+', aid):
            continue
        h2 = card.select_one("h2")
        name = ""
        location = ""
        if h2:
            spans = h2.select("span")
            if len(spans) >= 2:
                name = spans[1].get_text(strip=True)
            if len(spans) >= 3:
                location = spans[2].get_text(strip=True)
        status = ""
        ribbon = card.select_one(".ribbon-status")
        if ribbon:
            status_text = ribbon.get_text(strip=True)
            if "READY" in status_text.upper():
                status = "Ready"
            elif "ADOPTED" in status_text.upper():
                status = "Adopted"
            else:
                status = status_text
        atype = ""
        if location:
            if location.startswith("WD") or location.startswith("D"):
                atype = "Dog"
            elif location.startswith("WC") or location.startswith("C") or location.startswith("ESAT"):
                atype = "Cat"
        animals.append({"name": name, "id": aid, "type": atype, "location": location,
                        "age": "", "gender": "", "status": status})

    if pet_type:
        animals = [a for a in animals if a["type"] == pet_type.capitalize()]
    if ready:
        animals = [a for a in animals if a["status"] == "Ready"]
    if gender:
        animals = [a for a in animals if a["gender"].upper() == gender.upper()]
    animals = animals[:limit]

    if _json_opt(ctx):
        click.echo(json_mod.dumps(animals, indent=2))
        return

    if not animals:
        console.print("[yellow]No matching animals found. Try different filters.[/yellow]")
        console.print(f"Browse directly: {PETS_URL}")
        return

    table = Table(title="🐾 Adoptable Pets", box=box.ROUNDED)
    table.add_column("Name", style="bold")
    table.add_column("ID", style="cyan")
    table.add_column("Type")
    table.add_column("Location")
    table.add_column("Status", style="green")
    for a in animals:
        table.add_row(a["name"], a["id"], a["type"], a.get("location", ""), a["status"])
    console.print(table)
    console.print(f"\n🔗 Browse all: {PETS_URL}")


# ════════════════════════════════════════════════════════════════
# TOP-LEVEL: inmate
# ════════════════════════════════════════════════════════════════

@cli.command()
@click.argument("name", required=False)
@click.option("--bookings", is_flag=True, help="Download daily bookings PDF")
@click.option("--first-appearance", is_flag=True, help="Show first appearances")
@click.pass_context
def inmate(ctx, name, bookings, first_appearance):
    """🔍 Search inmates or download booking reports.

    \b
    Examples:
      ocfl inmate "John Smith"
      ocfl inmate --bookings
    """
    if bookings:
        url = f"{BESTJAIL}/PDF/bookings.pdf"
        console.print(f"[bold]📥 Bookings PDF:[/bold] {url}")
        try:
            r = SESSION.head(url, timeout=10)
            if r.status_code == 200:
                size = r.headers.get("Content-Length", "unknown")
                console.print(f"  Status: [green]Available[/green] ({size} bytes)")
                console.print(f"  Download: curl -o bookings.pdf '{url}'")
            else:
                console.print(f"  Status: [red]{r.status_code}[/red]")
        except requests.RequestException as e:
            console.print(f"  [red]Error checking:[/red] {e}")
        return

    if first_appearance:
        url = f"{BESTJAIL}/Home/FirstAppearance"
        try:
            r = SESSION.get(url, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            if _json_opt(ctx):
                rows = []
                for tr in soup.select("table tr"):
                    cells = [td.get_text(strip=True) for td in tr.select("td, th")]
                    if cells:
                        rows.append(cells)
                click.echo(json_mod.dumps(rows, indent=2))
                return
            console.print("[bold]⚖️  First Appearances[/bold]\n")
            tables = soup.select("table")
            for table_el in tables[:3]:
                for tr in table_el.select("tr"):
                    cells = [td.get_text(strip=True) for td in tr.select("td, th")]
                    if cells:
                        console.print("  " + " | ".join(cells))
            if not tables:
                console.print(soup.get_text()[:2000])
            console.print(f"\n🔗 {url}")
        except requests.RequestException as e:
            console.print(f"[red]Error:[/red] {e}")
        return

    if not name:
        console.print("[yellow]Provide a name to search, or use --bookings / --first-appearance[/yellow]")
        sys.exit(1)

    url = f"{BESTJAIL}/Home/Inmates"
    try:
        r = SESSION.get(url, timeout=15)
        r.raise_for_status()
        r2 = SESSION.post(url, data={"SearchString": name}, timeout=15, allow_redirects=True)
        soup2 = BeautifulSoup(r2.text, "html.parser")
        results = []
        rows = soup2.select("table tr, .inmate-row, .result-row")
        for tr in rows:
            cells = [td.get_text(strip=True) for td in tr.select("td, th")]
            text = tr.get_text(strip=True)
            if name.lower().split()[0].lower() in text.lower():
                results.append({"cells": cells, "text": text[:200]})
        if _json_opt(ctx):
            click.echo(json_mod.dumps(results, indent=2))
            return
        if results:
            console.print(f"[bold]🔍 Inmate search: '{name}'[/bold]\n")
            for res in results[:20]:
                if res["cells"]:
                    console.print("  " + " | ".join(res["cells"]))
                else:
                    console.print(f"  {res['text']}")
        else:
            console.print(f"[yellow]No results for '{name}'. Try the web interface:[/yellow]")
            console.print(f"  {url}")
    except requests.RequestException as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print(f"Try directly: {url}")


# ════════════════════════════════════════════════════════════════
# TOP-LEVEL: phone, directory, library
# ════════════════════════════════════════════════════════════════

@cli.command()
@click.argument("query")
@click.pass_context
def phone(ctx, query):
    """📞 Look up a department phone number.

    \b
    Examples:
      ocfl phone 311
      ocfl phone "fire rescue"
    """
    if query.strip() == "311":
        if _json_opt(ctx):
            click.echo(json_mod.dumps({"department": "311 Customer Service", "phone": "(407) 836-3111"}))
            return
        console.print("[bold]📞 311 Customer Service:[/bold] (407) 836-3111")
        return
    entries = _load_directory()
    results = _fuzzy_search(entries, query)
    if _json_opt(ctx):
        click.echo(json_mod.dumps(results, indent=2))
        return
    if not results:
        console.print(f"[yellow]No results for '{query}'. Try 'ocfl directory {query}'.[/yellow]")
        return
    for e in results[:10]:
        console.print(f"[bold]{e['name']}:[/bold] {e['phone']}", end="")
        if e.get("email"):
            console.print(f" | {e['email']}", end="")
        console.print()


class DirectoryGroup(click.Group):
    """Custom group that treats unknown subcommands as search queries."""

    def get_command(self, ctx, cmd_name):
        # Try real subcommands first
        rv = super().get_command(ctx, cmd_name)
        if rv is not None:
            return rv
        # Treat unknown subcommand as a search query
        return self._make_search_cmd(cmd_name)

    def _make_search_cmd(self, query):
        @click.command(hidden=True)
        @click.argument("extra_words", nargs=-1)
        @click.option("--json", "json_output", is_flag=True, hidden=True)
        @click.pass_context
        def _search(ctx, extra_words, json_output):
            if json_output:
                root = ctx.find_root()
                if root.obj is None:
                    root.obj = {}
                root.obj["json_output"] = True
            full_query = query + (" " + " ".join(extra_words) if extra_words else "")
            _directory_search(ctx, full_query)
        return _search

    def resolve_command(self, ctx, args):
        # Override to prevent Click from erroring on unknown subcommands
        cmd_name, cmd, args = super().resolve_command(ctx, args)
        return cmd_name, cmd, args


def _directory_browse(ctx):
    """Show directory categories with entry counts."""
    categories = _load_directory_by_category()
    if _json_opt(ctx):
        click.echo(json_mod.dumps({k: len(v) for k, v in categories.items()}, indent=2))
        return
    if not categories:
        console.print("[yellow]No directory data available.[/yellow]")
        return
    table = Table(title="📒 Orange County Government Directory", box=box.ROUNDED)
    table.add_column("Category", style="bold")
    table.add_column("Entries", justify="right", style="cyan")
    total = 0
    for cat, entries in categories.items():
        table.add_row(cat, str(len(entries)))
        total += len(entries)
    table.add_row("", "")
    table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]")
    console.print(table)
    console.print("\n[dim]Commands: ocfl directory list | ocfl directory search <query> | ocfl directory <query>[/dim]")


def _directory_search(ctx, query):
    """Search directory entries by fuzzy match."""
    entries = _load_directory()
    results = _fuzzy_search(entries, query)
    if _json_opt(ctx):
        click.echo(json_mod.dumps(results, indent=2))
        return
    if not results:
        console.print(f"[yellow]No results for '{query}'.[/yellow]")
        console.print("General Customer Service: (407) 836-3111")
        return
    table = Table(title=f"📒 Directory: '{query}'", box=box.ROUNDED)
    table.add_column("Department", style="bold")
    table.add_column("Phone", style="cyan")
    table.add_column("Email")
    table.add_column("URL")
    for e in results[:15]:
        table.add_row(e["name"], e.get("phone", ""), e.get("email", ""), e.get("url", ""))
    console.print(table)


@cli.group(cls=DirectoryGroup, invoke_without_command=True)
@click.option("--json", "json_output", is_flag=True, hidden=True, help="Output as JSON")
@click.pass_context
def directory(ctx, json_output):
    """📒 Orange County government directory.

    \b
    Usage:
      ocfl directory              Browse categories
      ocfl directory browse       Browse categories
      ocfl directory list         Full directory listing
      ocfl directory search <q>   Search directory
      ocfl directory <query>      Search (shortcut)

    \b
    Examples:
      ocfl directory
      ocfl directory fire
      ocfl directory search "property appraiser"
    """
    # Propagate --json from subcommand level to root context
    if json_output:
        root = ctx.find_root()
        if root.obj is None:
            root.obj = {}
        root.obj["json_output"] = True
    if ctx.invoked_subcommand is None:
        _directory_browse(ctx)


_json_flag = click.option("--json", "json_output", is_flag=True, hidden=True)

@directory.command("browse")
@_json_flag
@click.pass_context
def directory_browse(ctx, json_output):
    """Browse directory categories with entry counts."""
    _directory_browse(ctx)


@directory.command("list")
@_json_flag
@click.pass_context
def directory_list(ctx, json_output):
    """Full directory listing grouped by category."""
    categories = _load_directory_by_category()
    if _json_opt(ctx):
        click.echo(json_mod.dumps(categories, indent=2))
        return
    if not categories:
        console.print("[yellow]No directory data available.[/yellow]")
        return
    for cat, entries in categories.items():
        table = Table(title=f"📒 {cat}", box=box.ROUNDED, show_header=True)
        table.add_column("Department/Office", style="bold", max_width=40)
        table.add_column("Phone", style="cyan")
        table.add_column("Email", max_width=30)
        table.add_column("URL", max_width=40)
        table.add_column("Address", max_width=40)
        for e in entries:
            table.add_row(
                e.get("name", ""),
                e.get("phone", ""),
                e.get("email", ""),
                e.get("url", ""),
                e.get("address", ""),
            )
        console.print(table)
        console.print()


@directory.command("search")
@click.argument("query")
@_json_flag
@click.pass_context
def directory_search_cmd(ctx, query, json_output):
    """Search the directory by keyword (fuzzy + token matching).

    \b
    Examples:
      ocfl directory search fire
      ocfl directory search "property appraiser"
      ocfl directory search 836-9000
    """
    _directory_search(ctx, query)


@directory.command("regex")
@click.argument("pattern")
@_json_flag
@click.pass_context
def directory_regex_cmd(ctx, pattern, json_output):
    """Search the directory by regex pattern.

    \b
    Examples:
      ocfl directory regex "fire|rescue"
      ocfl directory regex "836-\\d{4}"
      ocfl directory regex "^(tax|clerk)"
    """
    entries = _load_directory()
    results, err = _regex_search(entries, pattern)
    if err:
        console.print(f"[red]Invalid regex: {err}[/red]")
        return
    if _json_opt(ctx):
        click.echo(json_mod.dumps(results, indent=2))
        return
    if not results:
        console.print(f"[yellow]No results for regex '{pattern}'.[/yellow]")
        return
    table = Table(title=f"📒 Directory regex: '{pattern}' ({len(results)} matches)", box=box.ROUNDED)
    table.add_column("Department", style="bold")
    table.add_column("Phone", style="cyan")
    table.add_column("Email")
    table.add_column("URL")
    for e in results:
        table.add_row(e["name"], e.get("phone", ""), e.get("email", ""), e.get("url", ""))
    console.print(table)


@cli.command()
@click.argument("query")
@click.option("--limit", default=10, help="Max results")
@click.pass_context
def library(ctx, query, limit):
    """📚 Search the Orange County Library System catalog.

    \b
    Examples:
      ocfl library "python programming"
      ocfl library "orlando history"
    """
    try:
        r = SESSION.get(CATALOG_URL, params={"lookfor": query, "type": "AllFields"}, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        console.print(f"[red]Error searching catalog:[/red] {e}")
        sys.exit(1)

    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    items = soup.select(".result, .resultitem, .record, .result-body, .media, article")
    if not items:
        items = soup.select("[class*='result']")
    for item in items[:limit]:
        title_el = item.select_one(".result-title, .title, h3, h2, a[class*='title']")
        author_el = item.select_one(".result-author, .author, .authorName, [class*='author']")
        format_el = item.select_one(".result-format, .format, .mediaType, [class*='format'], .icon-format")
        avail_el = item.select_one(".result-availability, .availability, [class*='avail']")
        title = title_el.get_text(strip=True) if title_el else ""
        author = author_el.get_text(strip=True) if author_el else ""
        fmt = format_el.get_text(strip=True) if format_el else ""
        avail = avail_el.get_text(strip=True) if avail_el else ""
        link = ""
        if title_el and title_el.name == "a":
            link = title_el.get("href", "")
        elif title_el:
            a = title_el.find("a")
            if a:
                link = a.get("href", "")
        if link and not link.startswith("http"):
            link = f"https://catalog.ocls.org{link}"
        if title:
            results.append({"title": title, "author": author, "format": fmt, "availability": avail, "url": link})

    if _json_opt(ctx):
        click.echo(json_mod.dumps(results, indent=2))
        return
    if not results:
        console.print(f"[yellow]No results for '{query}'.[/yellow]")
        console.print(f"🔗 Search directly: {CATALOG_URL}?lookfor={query}&type=AllFields")
        return
    table = Table(title=f"📚 Library Search: '{query}'", box=box.ROUNDED)
    table.add_column("Title", style="bold", max_width=50)
    table.add_column("Author", max_width=25)
    table.add_column("Format")
    table.add_column("Availability", style="green")
    for r in results:
        table.add_row(r["title"][:50], r["author"][:25], r["format"], r["availability"][:30])
    console.print(table)
    if results and results[0].get("url"):
        console.print(f"\n🔗 {results[0]['url']}")


# ════════════════════════════════════════════════════════════════
# TOP-LEVEL: services
# ════════════════════════════════════════════════════════════════

# Grouped structure for services listing
SERVICE_GROUPS = {
    "property": {
        "desc": "Property lookup, tax, homestead, appraisal",
        "commands": {
            "property lookup <addr>": "Property info by address/parcel (live API)",
            "property tax <addr>": "Property tax info (live API)",
            "property homestead": "Homestead Exemption Application",
            "property appraisal": "TRIM / VAB Appraisal Appeal",
            "property flood": "Floodplain Determination",
            "property domicile": "Declaration of Domicile",
        },
    },
    "vehicles": {
        "desc": "Registration, titles, boat, mobile home, DMV",
        "commands": {
            "vehicles registration": "Vehicle Registration / Tag Renewal",
            "vehicles title": "Vehicle Title / Lien Release",
            "vehicles boat": "Boat Registration / Titling",
            "vehicles mobilehome": "Mobile Home Titling",
            "vehicles dmv": "Driver License Renewal",
        },
    },
    "courts": {
        "desc": "Marriage, deeds, vitals, passport, notary, probate",
        "commands": {
            "courts marriage": "Marriage License",
            "courts deeds": "Deed / Lien / Mortgage Recording",
            "courts vitals": "Birth / Death / Marriage Certificate",
            "courts passport": "Passport Application",
            "courts notary": "Notary Public Services",
            "courts probate": "Probate / Estate / Name Change",
            "courts jury": "Jury Duty Response",
            "courts records": "Public Records / Sunshine Request",
            "courts pd": "Public Defender Application",
        },
    },
    "elections": {
        "desc": "Voter registration, ballots, polling info",
        "commands": {
            "elections voter": "Voter Registration / Update",
            "elections ballot": "Vote-by-Mail Ballot Request",
            "elections info": "Election Info & Polling Lookup",
        },
    },
    "permits": {
        "desc": "Permit database, business tax, STR, inspections",
        "commands": {
            "permits lookup [type]": "Permit requirements & fees (offline DB)",
            "permits biztax": "Business Tax Receipt",
            "permits str": "Short-Term Rental Permit",
            "permits inspection": "On-Site Building Inspection",
            "permits dba": "Fictitious Name / DBA Registration",
        },
    },
    "safety": {
        "desc": "Hurricane, animal control, CCW, code enforcement",
        "commands": {
            "safety hurricane": "Hurricane / Disaster Assistance",
            "safety stray": "Animal Control / Stray / Bite Report",
            "safety ccw": "Concealed Weapon License",
            "safety fingerprint": "Live Scan Fingerprinting",
            "safety dv": "Domestic Violence Services",
            "safety code": "Code Enforcement Complaint",
        },
    },
    "health": {
        "desc": "Restaurant inspections, clinics, crisis services",
        "commands": {
            "health inspections <name>": "DBPR Restaurant Inspections (live)",
            "health mosquito": "Mosquito Control",
            "health clinic": "Public Health Clinic Services",
            "health crisis": "Mental Health / Crisis Services",
            "health vector": "Vector Control Request",
            "health cemetery": "Cemetery / Burial Permit",
        },
    },
    "utilities": {
        "desc": "311, trash, pothole, drainage, dumping",
        "commands": {
            "utilities 311": "311 Non-Emergency Requests",
            "utilities trash": "Trash / Recycling / Bulk Pickup",
            "utilities pothole": "Pothole / Road Report",
            "utilities drainage": "Stormwater / Drainage Complaint",
            "utilities dumping": "Illegal Dumping Complaint",
        },
    },
    "community": {
        "desc": "Seniors, family, Medicaid, workforce, extension",
        "commands": {
            "community seniors": "Senior / Disabled / Veterans",
            "community family": "Child Support / Family Services",
            "community medicaid": "Medicaid / SNAP Screening",
            "community workforce": "Workforce Development",
            "community extension": "UF/IFAS Extension / 4-H",
        },
    },
    "recreation": {
        "desc": "Parks, library card, hunting, arts",
        "commands": {
            "recreation reserve": "Park Pavilion / Facility Reservation",
            "recreation libcard": "Library Card Issuance",
            "recreation hunting": "Hunting / Fishing License",
            "recreation arts": "Arts / Cultural Grant",
        },
    },
    "government": {
        "desc": "Budget, procurement/bids",
        "commands": {
            "government budget": "County Budget & Transparency",
            "government bids": "Procurement / Bid Opportunities",
        },
    },
}

@cli.command()
@click.pass_context
def services(ctx):
    """📋 List all available OCFL service commands by category."""
    if _json_opt(ctx):
        click.echo(json_mod.dumps(SERVICE_GROUPS, indent=2))
        return

    console.print(Panel("[bold]🍊 OCFL CLI v3 — All Government Service Commands[/bold]\n\nRun any command for full details: [cyan]ocfl <group> <command>[/cyan]", border_style="bright_yellow"))
    console.print()

    for group_name, group_info in SERVICE_GROUPS.items():
        table = Table(title=f"  {group_name} — {group_info['desc']}", box=box.SIMPLE, show_header=True, title_style="bold bright_cyan")
        table.add_column("Command", style="cyan bold", min_width=30)
        table.add_column("Description")
        for cmd, desc in group_info["commands"].items():
            table.add_row(f"ocfl {cmd}", desc)
        console.print(table)
        console.print()

    console.print("[bold]Top-level commands:[/bold]")
    console.print("  [cyan]ocfl gis[/cyan]              — ArcGIS data layers, flood, zoning")
    console.print("  [cyan]ocfl geocode <addr>[/cyan]   — Geocode an address")
    console.print("  [cyan]ocfl pets[/cyan]             — Search adoptable pets")
    console.print("  [cyan]ocfl inmate[/cyan]           — Search inmates / bookings")
    console.print("  [cyan]ocfl phone <query>[/cyan]    — Department phone lookup")
    console.print("  [cyan]ocfl directory <query>[/cyan] — Government directory search")
    console.print("  [cyan]ocfl library <query>[/cyan]  — Library catalog search")
    console.print()


# ── Skill MD Generator ─────────────────────────────────────────

def _generate_skill_md():
    """Generate a complete SKILL.md with OpenClaw frontmatter."""
    lines = []
    # Frontmatter
    lines.append("---")
    lines.append("name: ocfl")
    lines.append('description: "Orange County FL Government Services CLI v3.0 — grouped subcommands for property, tax, GIS, permits, pets, inmates, library, directory, inspections, 50+ service guides"')
    lines.append("metadata:")
    lines.append('  {"openclaw": {"emoji": "🍊", "requires": {"bins": ["ocfl"]}, "install": [{"id": "uv", "kind": "uv", "package": ".", "bins": ["ocfl"], "label": "Install OCFL CLI (uv pip install)"}]}}')
    lines.append("---")
    lines.append("")
    lines.append("# OCFL CLI v3.0 — Orange County FL Government Services")
    lines.append("")
    lines.append("Comprehensive CLI for interacting with Orange County, Florida government data and services.")
    lines.append("Commands are organized into logical groups.")
    lines.append("")

    # Installation
    lines.append("## Installation")
    lines.append("")
    lines.append("```bash")
    lines.append("cd {baseDir}")
    lines.append("uv pip install -e . --python .venv/bin/python")
    lines.append("ln -sf {baseDir}/.venv/bin/ocfl ~/bin/ocfl")
    lines.append("```")
    lines.append("")

    # Command groups from SERVICE_GROUPS
    lines.append("## Command Groups")
    lines.append("")
    for group_name, group_info in SERVICE_GROUPS.items():
        lines.append(f"### `ocfl {group_name.split()[0].lower()}` — {group_name}")
        lines.append("")
        lines.append("```bash")
        for cmd, desc in group_info["commands"].items():
            lines.append(f"ocfl {cmd:<50} # {desc}")
        lines.append("```")
        lines.append("")

    # Top-level commands
    lines.append("## Top-Level Commands")
    lines.append("")
    top_cmds = {
        "gis layers": "List available ArcGIS layers",
        "gis flood <address>": "Flood zone lookup",
        "gis zoning <address>": "Zoning lookup",
        "gis --layer <name> --near lat,lon": "Query any layer by proximity",
        "geocode <address>": "Geocode an Orange County address",
        "pets --ready --limit 10": "Search adoptable pets",
        "pets --type dog --gender F": "Filter pets by type/gender",
        "inmate <name>": "Search inmates by name",
        "inmate --bookings": "Download recent booking reports",
        "phone <query>": "Department phone lookup",
        "directory": "Browse department categories",
        "directory list": "Full directory dump",
        "directory <query>": "Fuzzy search directory",
        "directory regex <pattern>": "Regex search directory",
        "library <query>": "Search OCLS catalog",
        "services": "List all commands by category",
    }
    lines.append("```bash")
    for cmd, desc in top_cmds.items():
        lines.append(f"ocfl {cmd:<45} # {desc}")
    lines.append("```")
    lines.append("")

    # Global options
    lines.append("## Global Options")
    lines.append("")
    lines.append("- `--json` — Machine-readable JSON output on all commands")
    lines.append("- `--version` — Show version")
    lines.append("- `--help` — Help on any command or group")
    lines.append("")

    # Data sources
    lines.append("## Data Sources")
    lines.append("")
    lines.append("| Source | API Type | Auth |")
    lines.append("|--------|----------|------|")
    lines.append("| OCPA (Property Appraiser) | REST/JSON | None |")
    lines.append("| Tax Collector (Algolia) | Algolia search | Public key |")
    lines.append("| OCFL ArcGIS (ocgis4) | REST/JSON | None |")
    lines.append("| FL DBPR (Inspections) | HTML scrape | None |")
    lines.append("| Animal Services (ocnetpets) | HTML scrape | None |")
    lines.append("| BestJail (Corrections) | HTML scrape + PDF | None |")
    lines.append("| OCLS Library | HTML scrape | None |")
    lines.append("| Directory | Local (DIRECTORY.md) | N/A |")
    lines.append("| Permits | Local database | N/A |")
    lines.append("| Service Guides | Local database | N/A |")
    lines.append("")

    # Key API endpoints (reference for agent)
    lines.append("## Key API Endpoints (Reference)")
    lines.append("")
    lines.append("- OCPA REST: `https://ocpa-mainsite-afd-standard.azurefd.net/api/`")
    lines.append("- Tax Collector Algolia: app=`0LWZO52LS2`, indexes: `fl-orange.property_tax`, `fl-orange.business_tax`")
    lines.append("- ArcGIS: `https://ocgis4.ocfl.net/arcgis/rest/services/` (60+ layers)")
    lines.append("- OCPA ArcGIS: `https://vgispublic.ocpafl.org/server/rest/services/`")
    lines.append("- Parcel ID format: display `35-20-27-6645-00-550` → API `272035664500550`")
    lines.append("")

    return "\n".join(lines)


@cli.command("skill-md")
@click.option("--write", is_flag=True, help="Write SKILL.md to current directory instead of stdout")
@click.pass_context
def skill_md_cmd(ctx, write):
    """📝 Generate a SKILL.md for the OCFL skill.

    \b
    Without --write: prints to stdout
    With --write: writes SKILL.md to the current directory

    \b
    Examples:
      ocfl skill-md              # Print to stdout
      ocfl skill-md --write      # Write ./SKILL.md
      ocfl skill-md > SKILL.md   # Redirect to file
    """
    content = _generate_skill_md()
    if write:
        out_path = Path.cwd() / "SKILL.md"
        out_path.write_text(content)
        console.print(f"[green]✅ Wrote SKILL.md to {out_path}[/green]")
    else:
        click.echo(content)


# ════════════════════════════════════════════════════════════════
# GROUP: forms
# ════════════════════════════════════════════════════════════════

from forms.forms import forms as forms_group
cli.add_command(forms_group, "forms")


# ── Entry point ────────────────────────────────────────────────

if __name__ == "__main__":
    cli()