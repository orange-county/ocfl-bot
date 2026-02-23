#!/usr/bin/env python3
"""
OCFL Telegram Wizard - Interactive guide for Orange County FL services

This module provides conversation flows for Clawdbot's Telegram interface.
It uses inline buttons to guide users through common tasks.
"""

import json
import re
import subprocess
import sys
from typing import Optional

# ---------------------------------------------------------------------------
# Helper: linkify phone numbers for Telegram tel: links
# ---------------------------------------------------------------------------
_PHONE_RE = re.compile(
    r'(?<!\[)'                       # not already inside a markdown link
    r'(\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4})'
)

def linkify_phone(phone_str: str) -> str:
    """Convert a phone string like '(407) 836-6563' to clickable +1-407-836-6563 format."""
    digits = re.sub(r'\D', '', phone_str)
    if len(digits) == 10:
        return f'+1-{digits[:3]}-{digits[3:6]}-{digits[6:]}'
    if len(digits) == 11 and digits[0] == '1':
        return f'+{digits[0]}-{digits[1:4]}-{digits[4:7]}-{digits[7:]}'
    return phone_str

def linkify_phones_in_text(text: str) -> str:
    """Find all phone numbers in text and convert them to clickable format."""
    return _PHONE_RE.sub(lambda m: linkify_phone(m.group(1)), text)


def strip_rich_box(text: str) -> str:
    """Remove Rich panel/table box-drawing characters and clean up for Telegram."""
    # Remove box-drawing border lines (╭─╮, │, ╰─╯, ┌─┐, └─┘, etc.)
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        # Skip lines that are purely border (╭──╮, ╰──╯, ┌──┐, └──┘, ├──┤)
        stripped = line.strip()
        if stripped and all(c in '╭╮╰╯┌┐└┘─━═├┤┬┴┼╞╡╥╨╪▏▕│║╔╗╚╝╟╢╠╣' for c in stripped):
            continue
        # Remove leading/trailing box chars (│, ║)
        line = re.sub(r'^[\s]*[│║▏]', '', line)
        line = re.sub(r'[│║▕][\s]*$', '', line)
        # Remove Rich markup tags like [bold], [red], [/bold], etc.
        line = re.sub(r'\[/?[a-z_\s]+\]', '', line, flags=re.IGNORECASE)
        # Remove remaining box-drawing chars
        line = re.sub(r'[╭╮╰╯┌┐└┘─━═├┤┬┴┼╞╡╥╨╪│║╔╗╚╝╟╢╠╣▏▕]', '', line)
        cleaned.append(line.rstrip())
    # Remove excessive blank lines
    result = re.sub(r'\n{3,}', '\n\n', '\n'.join(cleaned))
    return result.strip()


def format_json_service(data: dict, emoji: str = "📋") -> str:
    """Format a JSON service guide for Telegram (from --json output of guide commands)."""
    lines = [f"{emoji} **{data.get('name', 'Service Info')}**\n"]

    for key, label in [('what', 'What'), ('why', 'Why'), ('how', 'How'),
                       ('requirements', 'Requirements'), ('hours', 'Hours'),
                       ('notes', 'Notes')]:
        val = data.get(key)
        if val:
            lines.append(f"**{label}:** {val}\n")

    if data.get('phone'):
        lines.append(f"📞 {data['phone']}")
    if data.get('url'):
        lines.append(f"🔗 {data['url']}")
    if data.get('contacts'):
        lines.append("\n**Contacts:**")
        for c in data['contacts']:
            lines.append(f"• {c}")

    return linkify_phones_in_text('\n'.join(lines))


def format_json_forms_list(data: dict) -> str:
    """Format forms list JSON for Telegram."""
    lines = ["📝 **Available PDF Forms**\n"]
    for fid, info in data.items():
        name = info.get('name', fid) if isinstance(info, dict) else info
        desc = info.get('description', '') if isinstance(info, dict) else ''
        lines.append(f"• **{fid}** — {name}")
        if desc:
            lines.append(f"  _{desc}_")
    lines.append("\n_Use: ocfl forms fields <form-id>_")
    return '\n'.join(lines)


def format_json_permit(data: dict) -> str:
    """Format permit JSON for Telegram."""
    lines = [f"📋 **{data.get('name', 'Permit Info')}**\n"]
    if data.get('fee'):
        lines.append(f"💰 **Fee:** {data['fee']}")
    if data.get('review_time'):
        lines.append(f"⏱️ **Review:** {data['review_time']}")
    if data.get('valid'):
        lines.append(f"📅 **Valid:** {data['valid']}")
    if data.get('submit'):
        lines.append(f"📤 **Submit:** {data['submit']}")
    if data.get('height'):
        lines.append(f"📏 **Height:** {data['height']}")
    if data.get('requirements'):
        lines.append("\n**Requirements:**")
        for req in data['requirements']:
            lines.append(f"☐ {req}")
    return linkify_phones_in_text('\n'.join(lines))


def format_json_directory_categories(data: dict) -> str:
    """Format directory categories JSON (category: count) for Telegram."""
    lines = ["📞 **County Directory**\n"]
    total = 0
    for cat, count in data.items():
        if isinstance(count, int):
            lines.append(f"• **{cat}** ({count})")
            total += count
        elif isinstance(count, list):
            lines.append(f"• **{cat}** ({len(count)})")
            total += len(count)
    lines.append(f"\n**Total:** {total} entries")
    lines.append("_Send a name or department to search._")
    return '\n'.join(lines)


def format_json_directory_list(data) -> str:
    """Format directory list JSON for Telegram."""
    if isinstance(data, list):
        # Flat list of entries
        lines = ["📞 **Directory Results**\n"]
        for e in data[:15]:
            name = e.get('name', '?')
            phone = e.get('phone', '')
            if phone:
                lines.append(f"• **{name}** — {linkify_phone(phone)}")
            else:
                lines.append(f"• **{name}**")
        if len(data) > 15:
            lines.append(f"\n_...and {len(data) - 15} more_")
        return linkify_phones_in_text('\n'.join(lines))
    elif isinstance(data, dict):
        # Category -> entries dict
        lines = ["📞 **County Directory**\n"]
        total = 0
        for cat, entries in data.items():
            if isinstance(entries, list):
                lines.append(f"**{cat}** ({len(entries)} entries)")
                for e in entries[:5]:
                    name = e.get('name', '?')
                    phone = e.get('phone', '')
                    if phone:
                        lines.append(f"  • {name} — {linkify_phone(phone)}")
                    else:
                        lines.append(f"  • {name}")
                if len(entries) > 5:
                    lines.append(f"  _...and {len(entries) - 5} more_")
                lines.append("")
                total += len(entries)
        lines.append(f"**Total:** {total} entries")
        return linkify_phones_in_text('\n'.join(lines))
    return "📞 No directory data available."

# ---------------------------------------------------------------------------
# Helper: build a back-button row
# ---------------------------------------------------------------------------
def _back(target="main"):
    return [{"text": "« Back", "callback_data": f"ocfl:{target}"}]


# ---------------------------------------------------------------------------
# Wizard state machine
# ---------------------------------------------------------------------------
FLOWS = {
    # ── Main menu ──────────────────────────────────────────────────────────
    "main": {
        "text": "🍊 **Welcome to OCFL Services**\n\nOrange County Mayor Jerry L. Demings welcomes you to the OCFL Bot — your AI-powered guide to county services.\n\nUse the menu below or just tell me what you need help with!\n\n_\"Orange County, Florida — where community, innovation, and opportunity come together in the heart of the Sunshine State.\"_",
        "buttons": [
            [
                {"text": "🏠 Property", "callback_data": "ocfl:property"},
                {"text": "🚗 Vehicles", "callback_data": "ocfl:vehicles"},
            ],
            [
                {"text": "⚖️ Courts", "callback_data": "ocfl:courts"},
                {"text": "🗳️ Elections", "callback_data": "ocfl:elections"},
            ],
            [
                {"text": "📋 Permits", "callback_data": "ocfl:permit"},
                {"text": "🛡️ Safety", "callback_data": "ocfl:safety"},
            ],
            [
                {"text": "🏥 Health", "callback_data": "ocfl:health"},
                {"text": "🔧 Utilities", "callback_data": "ocfl:utilities"},
            ],
            [
                {"text": "👥 Community", "callback_data": "ocfl:community"},
                {"text": "🎾 Recreation", "callback_data": "ocfl:recreation"},
            ],
            [
                {"text": "🏛️ Government", "callback_data": "ocfl:government"},
                {"text": "📝 Forms", "callback_data": "ocfl:forms"},
            ],
            [
                {"text": "🐕 Find a Pet", "callback_data": "ocfl:pets"},
                {"text": "👮 Inmate Search", "callback_data": "ocfl:inmate"},
            ],
            [
                {"text": "📞 Phone Directory", "callback_data": "ocfl:directory"},
                {"text": "📚 Library Search", "callback_data": "ocfl:library"},
            ],
        ],
    },

    # ── Property ───────────────────────────────────────────────────────────
    "property": {
        "text": (
            "🏠 **Property Lookup**\n\n"
            "I can look up property info by address or parcel ID.\n\n"
            "_Send me an address or parcel number, or tap below:_"
        ),
        "buttons": [
            [{"text": "📍 Use My Address", "callback_data": "ocfl:property:my_address"}],
            [{"text": "🔢 I Have a Parcel ID", "callback_data": "ocfl:property:parcel_prompt"}],
            [
                {"text": "🏡 Homestead", "callback_data": "ocfl:property:homestead"},
                {"text": "📊 Appraisal", "callback_data": "ocfl:property:appraisal"},
            ],
            [
                {"text": "🌊 Flood Zone", "callback_data": "ocfl:property:flood"},
                {"text": "📜 Domicile", "callback_data": "ocfl:property:domicile"},
            ],
            _back(),
        ],
        "expects_input": True,
        "input_handler": "property_lookup",
    },

    # ── Vehicles ───────────────────────────────────────────────────────────
    "vehicles": {
        "text": "🚗 **Vehicle & DMV Services**\n\nSelect a service for step-by-step info:",
        "buttons": [
            [
                {"text": "🏷️ Registration", "callback_data": "ocfl:vehicles:registration"},
                {"text": "📄 Title", "callback_data": "ocfl:vehicles:title"},
            ],
            [
                {"text": "⛵ Boat", "callback_data": "ocfl:vehicles:boat"},
                {"text": "🏠 Mobile Home", "callback_data": "ocfl:vehicles:mobilehome"},
            ],
            [{"text": "🪪 DMV / License", "callback_data": "ocfl:vehicles:dmv"}],
            _back(),
        ],
    },

    # ── Courts ─────────────────────────────────────────────────────────────
    "courts": {
        "text": "⚖️ **Clerk & Court Services**\n\nSelect a service:",
        "buttons": [
            [
                {"text": "💍 Marriage", "callback_data": "ocfl:courts:marriage"},
                {"text": "📜 Deeds", "callback_data": "ocfl:courts:deeds"},
            ],
            [
                {"text": "📋 Vitals", "callback_data": "ocfl:courts:vitals"},
                {"text": "🛂 Passport", "callback_data": "ocfl:courts:passport"},
            ],
            [
                {"text": "✒️ Notary", "callback_data": "ocfl:courts:notary"},
                {"text": "⚖️ Probate", "callback_data": "ocfl:courts:probate"},
            ],
            [
                {"text": "🏛️ Jury Duty", "callback_data": "ocfl:courts:jury"},
                {"text": "📂 Records", "callback_data": "ocfl:courts:records"},
            ],
            [{"text": "🛡️ Public Defender", "callback_data": "ocfl:courts:pd"}],
            _back(),
        ],
    },

    # ── Elections ──────────────────────────────────────────────────────────
    "elections": {
        "text": "🗳️ **Elections & Voting**\n\nSelect a service:",
        "buttons": [
            [{"text": "📝 Voter Registration", "callback_data": "ocfl:elections:voter"}],
            [{"text": "📬 Vote by Mail", "callback_data": "ocfl:elections:ballot"}],
            [{"text": "ℹ️ Election Info", "callback_data": "ocfl:elections:info"}],
            _back(),
        ],
    },

    # ── Permits (existing, extended) ──────────────────────────────────────
    "permit": {
        "text": "📋 **Permit Information**\n\nSelect a permit type for requirements and fees:",
        "buttons": [
            [
                {"text": "🏗️ Fence", "callback_data": "ocfl:permit:fence"},
                {"text": "🏊 Pool", "callback_data": "ocfl:permit:pool"},
            ],
            [
                {"text": "🏠 Roof", "callback_data": "ocfl:permit:roof"},
                {"text": "🏘️ ADU", "callback_data": "ocfl:permit:adu"},
            ],
            [
                {"text": "🛒 Garage Sale", "callback_data": "ocfl:permit:garage_sale"},
                {"text": "🌳 Tree Removal", "callback_data": "ocfl:permit:tree"},
            ],
            [
                {"text": "💼 Biz Tax", "callback_data": "ocfl:permit:biztax"},
                {"text": "🏖️ Short-Term Rental", "callback_data": "ocfl:permit:str"},
            ],
            [
                {"text": "🔍 Inspection", "callback_data": "ocfl:permit:inspection"},
                {"text": "📝 DBA / Fictitious Name", "callback_data": "ocfl:permit:dba"},
            ],
            _back(),
        ],
    },

    # ── Safety ─────────────────────────────────────────────────────────────
    "safety": {
        "text": "🛡️ **Public Safety**\n\nSelect a service:",
        "buttons": [
            [
                {"text": "🌀 Hurricane", "callback_data": "ocfl:safety:hurricane"},
                {"text": "🐕 Animal Control", "callback_data": "ocfl:safety:stray"},
            ],
            [
                {"text": "🔫 CCW", "callback_data": "ocfl:safety:ccw"},
                {"text": "🖐️ Fingerprinting", "callback_data": "ocfl:safety:fingerprint"},
            ],
            [
                {"text": "💜 DV Services", "callback_data": "ocfl:safety:dv"},
                {"text": "📋 Code Enforce", "callback_data": "ocfl:safety:code"},
            ],
            _back(),
        ],
    },

    # ── Health ─────────────────────────────────────────────────────────────
    "health": {
        "text": "🏥 **Health Services**\n\nSelect a service:",
        "buttons": [
            [{"text": "🍽️ Restaurant Inspections", "callback_data": "ocfl:health:inspections"}],
            [
                {"text": "🦟 Mosquito", "callback_data": "ocfl:health:mosquito"},
                {"text": "🏥 Clinic", "callback_data": "ocfl:health:clinic"},
            ],
            [
                {"text": "🆘 Crisis", "callback_data": "ocfl:health:crisis"},
                {"text": "🐛 Vector", "callback_data": "ocfl:health:vector"},
            ],
            [{"text": "⚰️ Cemetery", "callback_data": "ocfl:health:cemetery"}],
            _back(),
        ],
    },

    # ── Health: restaurant inspections sub-flow ───────────────────────────
    "health_inspections": {
        "text": "🍽️ **Restaurant Inspections**\n\nSend me a restaurant name to search:",
        "buttons": [_back("health")],
        "expects_input": True,
        "input_handler": "health_inspections",
    },

    # ── Utilities ──────────────────────────────────────────────────────────
    "utilities": {
        "text": "🔧 **Utilities & Public Works**\n\nSelect a service:",
        "buttons": [
            [
                {"text": "📞 311", "callback_data": "ocfl:utilities:311"},
                {"text": "🗑️ Trash/Recycling", "callback_data": "ocfl:utilities:trash"},
            ],
            [
                {"text": "🕳️ Pothole", "callback_data": "ocfl:utilities:pothole"},
                {"text": "🌧️ Drainage", "callback_data": "ocfl:utilities:drainage"},
            ],
            [{"text": "🚯 Illegal Dumping", "callback_data": "ocfl:utilities:dumping"}],
            _back(),
        ],
    },

    # ── Community ──────────────────────────────────────────────────────────
    "community": {
        "text": "👥 **Community & Social Services**\n\nSelect a service:",
        "buttons": [
            [{"text": "👴 Seniors/Vets", "callback_data": "ocfl:community:seniors"}],
            [{"text": "👨‍👩‍👧 Family Services", "callback_data": "ocfl:community:family"}],
            [{"text": "🏥 Medicaid/SNAP", "callback_data": "ocfl:community:medicaid"}],
            [{"text": "💼 Workforce", "callback_data": "ocfl:community:workforce"}],
            [{"text": "🌿 Extension/4-H", "callback_data": "ocfl:community:extension"}],
            _back(),
        ],
    },

    # ── Recreation ─────────────────────────────────────────────────────────
    "recreation": {
        "text": "🎾 **Parks & Recreation**\n\nSelect a service:",
        "buttons": [
            [
                {"text": "🏕️ Park Reservation", "callback_data": "ocfl:recreation:reserve"},
                {"text": "📚 Library Card", "callback_data": "ocfl:recreation:libcard"},
            ],
            [
                {"text": "🎣 Hunting/Fishing", "callback_data": "ocfl:recreation:hunting"},
                {"text": "🎨 Arts Grant", "callback_data": "ocfl:recreation:arts"},
            ],
            _back(),
        ],
    },

    # ── Government ─────────────────────────────────────────────────────────
    "government": {
        "text": "🏛️ **Government & Transparency**\n\nSelect a service:",
        "buttons": [
            [{"text": "💰 Budget", "callback_data": "ocfl:government:budget"}],
            [{"text": "📋 Bids/Procurement", "callback_data": "ocfl:government:bids"}],
            _back(),
        ],
    },

    # ── Forms (PDF filling) ───────────────────────────────────────────────
    "forms": {
        "text": "📝 **PDF Form Filling**\n\nFill out official forms right here!",
        "buttons": [
            [{"text": "🏡 Homestead Exemption", "callback_data": "ocfl:forms:homestead"}],
            [{"text": "🏗️ Building Permit", "callback_data": "ocfl:forms:building-permit"}],
            [{"text": "📋 List All Forms", "callback_data": "ocfl:forms:list"}],
            _back(),
        ],
    },

    # Forms sub-flows: homestead
    "forms_homestead": {
        "text": (
            "🏡 **Homestead Exemption (DR-501)**\n\n"
            "I'll need a few details. Send them in this format:\n\n"
            "`Name ; Address ; Parcel ID`\n\n"
            "Example:\n`Jane Doe ; 123 Main St, Orlando, FL 32801 ; 01-23-45-6789-00-100`"
        ),
        "buttons": [_back("forms")],
        "expects_input": True,
        "input_handler": "forms_homestead",
    },

    # Forms sub-flows: building permit
    "forms_building_permit": {
        "text": (
            "🏗️ **Building Permit Application**\n\n"
            "Send the details in this format:\n\n"
            "`Owner Name ; Address, City, ST ZIP ; Description ; Valuation`\n\n"
            "Example:\n`John Smith ; 456 Oak Ave, Orlando, FL 32803 ; Kitchen remodel ; 25000`"
        ),
        "buttons": [_back("forms")],
        "expects_input": True,
        "input_handler": "forms_building_permit",
    },

    # ── Pets (existing) ───────────────────────────────────────────────────
    "pets": {
        "text": (
            "🐕 **Pet Adoption**\n\n"
            "Orange County Animal Services has pets ready for adoption!\n\n"
            "What are you looking for?"
        ),
        "buttons": [
            [
                {"text": "🐕 Dogs", "callback_data": "ocfl:pets:dog"},
                {"text": "🐈 Cats", "callback_data": "ocfl:pets:cat"},
            ],
            [{"text": "✅ Ready to Adopt Now", "callback_data": "ocfl:pets:ready"}],
            [{"text": "📊 Shelter Stats", "callback_data": "ocfl:pets:stats"}],
            _back(),
        ],
    },

    # ── Inmate (existing) ─────────────────────────────────────────────────
    "inmate": {
        "text": (
            "👮 **Inmate Search**\n\n"
            "Search current inmates or view today's bookings.\n\n"
            "_Send a name to search, or tap below:_"
        ),
        "buttons": [
            [{"text": "📋 Today's Bookings (PDF)", "callback_data": "ocfl:inmate:bookings"}],
            [{"text": "⚖️ First Appearances", "callback_data": "ocfl:inmate:appearances"}],
            _back(),
        ],
        "expects_input": True,
        "input_handler": "inmate_search",
    },

    # ── Directory ──────────────────────────────────────────────────────────
    "directory": {
        "text": "📞 **County Phone Directory**\n\nSend a name or department to search, or tap below:",
        "buttons": [
            [{"text": "📂 Browse Categories", "callback_data": "ocfl:directory:categories"}],
            [{"text": "📋 Full List", "callback_data": "ocfl:directory:list"}],
            _back(),
        ],
        "expects_input": True,
        "input_handler": "directory_search",
    },

    # ── Library ────────────────────────────────────────────────────────────
    "library": {
        "text": "📚 **OCLS Library Search**\n\nSend me a title, author, or keyword to search the catalog:",
        "buttons": [_back()],
        "expects_input": True,
        "input_handler": "library_search",
    },
}


# ---------------------------------------------------------------------------
# CLI runner
# ---------------------------------------------------------------------------
def run_ocfl(*args) -> dict:
    """Run the ocfl CLI and return parsed JSON output"""
    import os
    ocfl_bin = os.path.expanduser("~/bin/ocfl")

    try:
        result = subprocess.run(
            [ocfl_bin] + list(args),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                # Non-JSON output (guide text) — wrap it
                return {"_raw": result.stdout.strip()}
        else:
            return {"error": result.stderr or "Command failed"}
    except Exception as e:
        return {"error": str(e)}


def run_ocfl_raw(*args) -> str:
    """Run the ocfl CLI and return raw stdout (for guide commands)."""
    import os
    ocfl_bin = os.path.expanduser("~/bin/ocfl")

    try:
        result = subprocess.run(
            [ocfl_bin] + list(args),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"❌ Error: {result.stderr or 'Command failed'}"
    except Exception as e:
        return f"❌ Error: {e}"


# ---------------------------------------------------------------------------
# Formatters — all apply linkify_phones_in_text before returning
# ---------------------------------------------------------------------------

def format_property_result(data: dict) -> str:
    """Format property lookup result for Telegram"""
    if data.get("_raw"):
        return strip_rich_box(linkify_phones_in_text(data["_raw"]))

    lines = ["🏠 **Property Lookup Result**\n"]

    if data.get("geocoding", {}).get("success"):
        lines.append(f"✅ **Address:** {data.get('matched_address')}")
        lines.append(f"📊 **Confidence:** {data.get('confidence')}%")
        lines.append("")
        if data.get("links"):
            lines.append("**Quick Links:**")
            if "property_search" in data["links"]:
                lines.append(f"• [Property Search]({data['links']['property_search']})")
            if "gis_hub" in data["links"]:
                lines.append(f"• [GIS Maps]({data['links']['gis_hub']})")
    elif data.get("parcel_id"):
        lines.append(f"📋 **Parcel ID:** {data['parcel_id']}")
        lines.append("")
        if data.get("links"):
            lines.append("**Quick Links:**")
            for name, url in data["links"].items():
                lines.append(f"• [{name.replace('_', ' ').title()}]({url})")
    else:
        lines.append("❌ Address not found in Orange County")
        lines.append("Try the property search manually.")

    return linkify_phones_in_text("\n".join(lines))


def format_pets_result(data: dict) -> str:
    """Format pet search result for Telegram"""
    if data.get("_raw"):
        return strip_rich_box(linkify_phones_in_text(data["_raw"]))

    lines = ["🐾 **Adoptable Pets**\n"]

    if data.get("success"):
        stats = data.get("stats", {})
        if stats:
            lines.append(f"📊 **Shelter Stats:** {stats.get('dogs', '?')} dogs, {stats.get('cats', '?')} cats")
            lines.append(f"✅ **Ready to adopt:** {stats.get('ready_to_adopt', '?')}")
            lines.append("")

        pets = data.get("pets", [])
        if pets:
            lines.append("**Available Now:**")
            for pet in pets[:10]:
                status = "✅" if pet.get("ready_to_adopt") else "⏳"
                lines.append(f"{status} **{pet['name']}** ({pet.get('animal_id', 'N/A')})")
            if len(pets) > 10:
                lines.append(f"_...and {len(pets) - 10} more_")

        lines.append("")
        lines.append(f"🏠 [Visit Shelter]({data.get('shelter_url', '')})")
        contact = data.get('contact', '407-836-3111')
        lines.append(f"📞 {linkify_phone(contact) if contact else ''}")
    else:
        lines.append("❌ Couldn't fetch shelter data")
        lines.append(f"[Try the website]({data.get('shelter_url', '')})")

    return linkify_phones_in_text("\n".join(lines))


def format_permit_result(data: dict) -> str:
    """Format permit info for Telegram"""
    if data.get("_raw"):
        return strip_rich_box(linkify_phones_in_text(data["_raw"]))
    if data.get("error"):
        return f"❌ {data['error']}\n\nAvailable: {', '.join(data.get('available_types', []))}"

    lines = [f"📋 **{data.get('name', 'Permit Info')}**\n"]

    if data.get("fee"):
        lines.append(f"💰 **Fee:** {data['fee']}")
    if data.get("review_time"):
        lines.append(f"⏱️ **Review:** {data['review_time']}")
    if data.get("expires"):
        lines.append(f"📅 **Expires:** {data['expires']}")
    if data.get("submit_via"):
        lines.append(f"📤 **Submit:** {data['submit_via']}")

    lines.append("")

    if data.get("requirements"):
        lines.append("**Requirements:**")
        for req in data["requirements"]:
            lines.append(f"• {req}")

    if data.get("height_limits"):
        lines.append("\n**Height Limits:**")
        for area, limit in data["height_limits"].items():
            lines.append(f"• {area.replace('_', ' ').title()}: {limit}")

    if data.get("contact"):
        lines.append(f"\n📞 {data['contact']}")

    return linkify_phones_in_text("\n".join(lines))


def format_bookings_result(data: dict) -> str:
    """Format booking info for Telegram"""
    if data.get("_raw"):
        return strip_rich_box(linkify_phones_in_text(data["_raw"]))

    lines = ["👮 **Daily Bookings**\n"]

    if data.get("pdf_available"):
        lines.append("✅ Today's booking list is available")
        lines.append(f"📄 [Download PDF]({data.get('bookings_pdf', '')})")
    else:
        lines.append("⏳ Booking list may not be ready yet")

    lines.append("")
    lines.append(f"📊 [Population Stats]({data.get('population_stats', '')})")
    lines.append(f"⚖️ [First Appearances]({data.get('first_appearances', '')})")
    lines.append("")
    lines.append(f"_{data.get('note', '')}_")

    return linkify_phones_in_text("\n".join(lines))


def format_guide_result(data: dict, emoji: str = "📋") -> str:
    """Format a service guide result (vehicles, courts, etc.)"""
    if data.get("_raw"):
        return strip_rich_box(linkify_phones_in_text(data["_raw"]))
    if data.get("error"):
        return f"❌ {data['error']}"

    lines = [f"{emoji} **{data.get('name', data.get('title', 'Service Guide'))}**\n"]

    for key in ("description", "summary"):
        if data.get(key):
            lines.append(data[key])
            lines.append("")

    if data.get("steps"):
        lines.append("**Steps:**")
        for i, step in enumerate(data["steps"], 1):
            lines.append(f"{i}. {step}")
        lines.append("")

    if data.get("requirements"):
        lines.append("**Requirements:**")
        for req in data["requirements"]:
            lines.append(f"• {req}")
        lines.append("")

    for key in ("fee", "cost"):
        if data.get(key):
            lines.append(f"💰 **Fee:** {data[key]}")
    if data.get("contact"):
        lines.append(f"📞 {data['contact']}")
    if data.get("url"):
        lines.append(f"🔗 [More info]({data['url']})")

    return linkify_phones_in_text("\n".join(lines))


def format_directory_result(data: dict) -> str:
    """Format directory search results"""
    if data.get("_raw"):
        return strip_rich_box(linkify_phones_in_text(data["_raw"]))
    if data.get("error"):
        return f"❌ {data['error']}"

    lines = ["📞 **Directory Results**\n"]
    results = data.get("results", data.get("entries", []))
    if not results:
        lines.append("No results found.")
        return "\n".join(lines)

    for entry in results[:15]:
        name = entry.get("name", entry.get("department", "?"))
        phone = entry.get("phone", "")
        if phone:
            lines.append(f"• **{name}** — {linkify_phone(phone)}")
        else:
            lines.append(f"• **{name}**")

    if len(results) > 15:
        lines.append(f"\n_...and {len(results) - 15} more_")

    return linkify_phones_in_text("\n".join(lines))


def format_directory_summary(data: dict) -> str:
    """Format directory as a category summary with counts"""
    if data.get("_raw"):
        return strip_rich_box(linkify_phones_in_text(data["_raw"]))
    if data.get("error"):
        return f"❌ {data['error']}"

    entries = data.get("results", data.get("entries", []))
    if not entries:
        return "📞 **Directory**\n\nNo entries found."

    # Group by category/department
    categories = {}
    for entry in entries:
        cat = entry.get("category", entry.get("department", "Other"))
        categories.setdefault(cat, []).append(entry)

    lines = [f"📞 **County Directory** — {len(entries)} entries\n"]
    for cat in sorted(categories.keys()):
        lines.append(f"• **{cat}** ({len(categories[cat])})")

    lines.append(f"\n_Send a name or department to search._")
    return "\n".join(lines)


def format_forms_result(data: dict) -> str:
    """Format form fill results (show path to PDF)"""
    if data.get("_raw"):
        return strip_rich_box(linkify_phones_in_text(data["_raw"]))
    if data.get("error"):
        return f"❌ {data['error']}"

    lines = ["📝 **Form Filled**\n"]
    if data.get("output_path"):
        lines.append(f"✅ PDF saved to: `{data['output_path']}`")
    if data.get("fields_filled"):
        lines.append(f"📋 Fields filled: {data['fields_filled']}")
    if data.get("forms"):
        lines.append("**Available forms:**")
        for f in data["forms"]:
            fid = f.get("id", "?")
            fname = f.get("name", fid)
            lines.append(f"• `{fid}` — {fname}")

    return linkify_phones_in_text("\n".join(lines))


def format_library_result(data: dict) -> str:
    """Format library search results"""
    if data.get("_raw"):
        return strip_rich_box(linkify_phones_in_text(data["_raw"]))
    if data.get("error"):
        return f"❌ {data['error']}"

    lines = ["📚 **Library Search Results**\n"]
    results = data.get("results", [])
    if not results:
        lines.append("No results found.")
        return "\n".join(lines)

    for item in results[:10]:
        title = item.get("title", "?")
        author = item.get("author", "")
        lines.append(f"• **{title}**" + (f" — {author}" if author else ""))

    if len(results) > 10:
        lines.append(f"\n_...and {len(results) - 10} more_")

    return linkify_phones_in_text("\n".join(lines))


def format_health_inspection_result(data: dict) -> str:
    """Format restaurant inspection results"""
    if data.get("_raw"):
        return strip_rich_box(linkify_phones_in_text(data["_raw"]))
    if data.get("error"):
        return f"❌ {data['error']}"

    lines = ["🍽️ **Restaurant Inspection Results**\n"]
    results = data.get("results", data.get("inspections", []))
    if not results:
        lines.append("No results found.")
        return "\n".join(lines)

    for r in results[:8]:
        name = r.get("name", r.get("establishment", "?"))
        date = r.get("date", "")
        violations = r.get("violations", r.get("violation_count", ""))
        line = f"• **{name}**"
        if date:
            line += f" ({date})"
        if violations:
            line += f" — {violations} violations"
        lines.append(line)

    return linkify_phones_in_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Guide-command mapping: group → {sub → (cli_args, emoji)}
# ---------------------------------------------------------------------------
GUIDE_COMMANDS = {
    "vehicles": {
        "registration": (["vehicles", "registration"], "🏷️"),
        "title":        (["vehicles", "title"], "📄"),
        "boat":         (["vehicles", "boat"], "⛵"),
        "mobilehome":   (["vehicles", "mobilehome"], "🏠"),
        "dmv":          (["vehicles", "dmv"], "🪪"),
    },
    "courts": {
        "marriage": (["courts", "marriage"], "💍"),
        "deeds":    (["courts", "deeds"], "📜"),
        "vitals":   (["courts", "vitals"], "📋"),
        "passport": (["courts", "passport"], "🛂"),
        "notary":   (["courts", "notary"], "✒️"),
        "probate":  (["courts", "probate"], "⚖️"),
        "jury":     (["courts", "jury"], "🏛️"),
        "records":  (["courts", "records"], "📂"),
        "pd":       (["courts", "pd"], "🛡️"),
    },
    "elections": {
        "voter":  (["elections", "voter"], "📝"),
        "ballot": (["elections", "ballot"], "📬"),
        "info":   (["elections", "info"], "ℹ️"),
    },
    "safety": {
        "hurricane":   (["safety", "hurricane"], "🌀"),
        "stray":       (["safety", "stray"], "🐕"),
        "ccw":         (["safety", "ccw"], "🔫"),
        "fingerprint": (["safety", "fingerprint"], "🖐️"),
        "dv":          (["safety", "dv"], "💜"),
        "code":        (["safety", "code"], "📋"),
    },
    "health": {
        "mosquito": (["health", "mosquito"], "🦟"),
        "clinic":   (["health", "clinic"], "🏥"),
        "crisis":   (["health", "crisis"], "🆘"),
        "vector":   (["health", "vector"], "🐛"),
        "cemetery": (["health", "cemetery"], "⚰️"),
    },
    "utilities": {
        "311":      (["utilities", "311"], "📞"),
        "trash":    (["utilities", "trash"], "🗑️"),
        "pothole":  (["utilities", "pothole"], "🕳️"),
        "drainage": (["utilities", "drainage"], "🌧️"),
        "dumping":  (["utilities", "dumping"], "🚯"),
    },
    "community": {
        "seniors":   (["community", "seniors"], "👴"),
        "family":    (["community", "family"], "👨‍👩‍👧"),
        "medicaid":  (["community", "medicaid"], "🏥"),
        "workforce": (["community", "workforce"], "💼"),
        "extension": (["community", "extension"], "🌿"),
    },
    "recreation": {
        "reserve": (["recreation", "reserve"], "🏕️"),
        "libcard": (["recreation", "libcard"], "📚"),
        "hunting": (["recreation", "hunting"], "🎣"),
        "arts":    (["recreation", "arts"], "🎨"),
    },
    "government": {
        "budget": (["government", "budget"], "💰"),
        "bids":   (["government", "bids"], "📋"),
    },
    "property_guides": {
        "homestead": (["property", "homestead"], "🏡"),
        "appraisal": (["property", "appraisal"], "📊"),
        "flood":     (["property", "flood"], "🌊"),
        "domicile":  (["property", "domicile"], "📜"),
    },
}

# Permit sub-commands that use `permits` group instead of `permit`
PERMIT_EXTRA = {
    "biztax":     ["permits", "biztax"],
    "str":        ["permits", "str"],
    "inspection": ["permits", "inspection"],
    "dba":        ["permits", "dba"],
}

# Property sub-actions that are guide commands (NOT property lookups)
PROPERTY_GUIDE_SUBS = {"homestead", "appraisal", "flood", "domicile"}


# ---------------------------------------------------------------------------
# Callback handler
# ---------------------------------------------------------------------------

def handle_callback(callback_data: str) -> dict:
    """
    Handle a callback from an inline button.
    Returns: {"text": str, "buttons": list} or {"text": str} for final responses
    """
    parts = callback_data.split(":")
    if len(parts) < 2 or parts[0] != "ocfl":
        return {"text": "Unknown action"}

    action = parts[1]
    sub_action = parts[2] if len(parts) > 2 else None

    # ── Navigation to flows ───────────────────────────────────────────────
    if action in FLOWS and not sub_action:
        flow = FLOWS[action]
        return {"text": flow["text"], "buttons": flow.get("buttons", [])}

    # ── Health: inspections needs a sub-flow ──────────────────────────────
    if action == "health" and sub_action == "inspections":
        flow = FLOWS["health_inspections"]
        return {"text": flow["text"], "buttons": flow.get("buttons", [])}

    # ── Forms sub-flows ───────────────────────────────────────────────────
    if action == "forms":
        if sub_action == "homestead":
            flow = FLOWS["forms_homestead"]
            return {"text": flow["text"], "buttons": flow.get("buttons", []),
                    "expects_input": True}
        elif sub_action == "building-permit":
            flow = FLOWS["forms_building_permit"]
            return {"text": flow["text"], "buttons": flow.get("buttons", []),
                    "expects_input": True}
        elif sub_action == "list":
            data = run_ocfl("forms", "list", "--json")
            if isinstance(data, dict) and not data.get("error") and not data.get("_raw"):
                return {"text": format_json_forms_list(data), "buttons": [_back("forms")]}
            raw = run_ocfl_raw("forms", "list")
            return {"text": strip_rich_box(linkify_phones_in_text(raw)), "buttons": [_back("forms")]}

    # ── Pets sub-actions (existing) ───────────────────────────────────────
    if action == "pets":
        if sub_action == "dog":
            data = run_ocfl("pets", "--type", "dog", "--limit", "10")
            return {"text": format_pets_result(data), "buttons": [_back("pets")]}
        elif sub_action == "cat":
            data = run_ocfl("pets", "--type", "cat", "--limit", "10")
            return {"text": format_pets_result(data), "buttons": [_back("pets")]}
        elif sub_action == "ready":
            data = run_ocfl("pets", "--ready", "--limit", "10")
            return {"text": format_pets_result(data), "buttons": [_back("pets")]}
        elif sub_action == "stats":
            data = run_ocfl("pets", "--limit", "1")
            return {"text": format_pets_result(data), "buttons": [_back("pets")]}

    # ── Permit sub-actions (existing + new) ───────────────────────────────
    if action == "permit" and sub_action:
        if sub_action in PERMIT_EXTRA:
            data = run_ocfl(*PERMIT_EXTRA[sub_action], "--json")
            if isinstance(data, dict) and not data.get("error") and not data.get("_raw"):
                return {"text": format_json_service(data, "📋"), "buttons": [_back("permit")]}
            raw = run_ocfl_raw(*PERMIT_EXTRA[sub_action])
            return {"text": strip_rich_box(linkify_phones_in_text(raw)), "buttons": [_back("permit")]}
        # Permit lookup from permits DB
        data = run_ocfl("permits", "lookup", sub_action, "--json")
        if isinstance(data, dict) and not data.get("error") and not data.get("_raw"):
            return {"text": format_json_permit(data), "buttons": [_back("permit")]}
        data = run_ocfl("permit", sub_action)
        return {"text": format_permit_result(data), "buttons": [_back("permit")]}

    # ── Inmate sub-actions (existing) ─────────────────────────────────────
    if action == "inmate":
        if sub_action == "bookings":
            data = run_ocfl("inmate", "--bookings")
            return {"text": format_bookings_result(data), "buttons": [_back("inmate")]}
        elif sub_action == "appearances":
            return {
                "text": "⚖️ **First Appearances**\n\n[View Schedule](https://netapps.ocfl.net/BestJail/Home/FirstAppearance)",
                "buttons": [_back("inmate")],
            }

    # ── Property sub-actions ──────────────────────────────────────────────
    if action == "property":
        # Guide commands (homestead, appraisal, flood, domicile)
        if sub_action in PROPERTY_GUIDE_SUBS:
            cli_args, emoji = GUIDE_COMMANDS["property_guides"][sub_action]
            data = run_ocfl(*cli_args, "--json")
            if isinstance(data, dict) and not data.get("error") and not data.get("_raw"):
                return {"text": format_json_service(data, emoji), "buttons": [_back("property")]}
            raw = run_ocfl_raw(*cli_args)
            return {"text": strip_rich_box(linkify_phones_in_text(raw)), "buttons": [_back("property")]}
        # Parcel ID prompt
        if sub_action == "parcel_prompt":
            return {
                "text": "🔢 Send me the parcel ID number (e.g., `292234916802030`)",
                "expects_input": True,
                "buttons": [_back("property")],
            }
        # My address — prompt user to type their address
        if sub_action == "my_address":
            return {
                "text": "📍 **Send me your address** and I'll look it up in the Orange County property records.\n\nExample: `123 Main St, Orlando, FL 32801`",
                "expects_input": True,
                "buttons": [_back("property")],
            }

    # ── Directory sub-actions ─────────────────────────────────────────────
    if action == "directory":
        if sub_action == "categories":
            data = run_ocfl("directory", "--json")
            if isinstance(data, dict) and not data.get("error") and not data.get("_raw"):
                return {"text": format_json_directory_categories(data), "buttons": [_back("directory")]}
            return {"text": format_directory_summary(data), "buttons": [_back("directory")]}
        elif sub_action == "list":
            data = run_ocfl("directory", "list", "--json")
            if isinstance(data, dict) and not data.get("error") and not data.get("_raw"):
                return {"text": format_json_directory_list(data), "buttons": [_back("directory")]}
            return {"text": format_directory_summary(data), "buttons": [_back("directory")]}

    # ── Guide commands (vehicles, courts, elections, safety, etc.) ────────
    if action in GUIDE_COMMANDS and sub_action:
        if sub_action in GUIDE_COMMANDS[action]:
            cli_args, emoji = GUIDE_COMMANDS[action][sub_action]
            # Try JSON first, fall back to raw (stripped)
            data = run_ocfl(*cli_args, "--json")
            if isinstance(data, dict) and not data.get("_raw") and not data.get("error"):
                return {"text": format_json_service(data, emoji), "buttons": [_back(action)]}
            if data.get("_raw"):
                return {"text": strip_rich_box(linkify_phones_in_text(data["_raw"])), "buttons": [_back(action)]}
            raw = run_ocfl_raw(*cli_args)
            return {"text": strip_rich_box(linkify_phones_in_text(raw)), "buttons": [_back(action)]}

    return {"text": "Action not implemented yet", "buttons": [_back()]}


# ---------------------------------------------------------------------------
# Text input handler
# ---------------------------------------------------------------------------

def handle_text_input(text: str, context: str = None) -> dict:
    """
    Handle free text input from user.
    Context tells us which flow we're in.
    """
    text = text.strip()

    # ── Health inspections ────────────────────────────────────────────────
    if context == "health_inspections":
        data = run_ocfl("health", "inspections", text, "--json")
        if data.get("_raw") or data.get("error"):
            raw = run_ocfl_raw("health", "inspections", text)
            return {"text": strip_rich_box(linkify_phones_in_text(raw)), "buttons": [_back("health")]}
        return {"text": format_health_inspection_result(data), "buttons": [_back("health")]}

    # ── Directory search ──────────────────────────────────────────────────
    if context == "directory_search":
        data = run_ocfl("directory", text, "--json")
        if data.get("_raw") or data.get("error"):
            raw = run_ocfl_raw("directory", text)
            return {"text": strip_rich_box(linkify_phones_in_text(raw)), "buttons": [_back("directory")]}
        return {"text": format_directory_result(data), "buttons": [_back("directory")]}

    # ── Library search ────────────────────────────────────────────────────
    if context == "library_search":
        data = run_ocfl("library", text, "--json")
        if data.get("_raw") or data.get("error"):
            raw = run_ocfl_raw("library", text)
            return {"text": strip_rich_box(linkify_phones_in_text(raw)), "buttons": [_back("library")]}
        return {"text": format_library_result(data), "buttons": [_back("library")]}

    # ── Inmate search ─────────────────────────────────────────────────────
    if context == "inmate_search":
        data = run_ocfl("inmate", text, "--json")
        if data.get("_raw"):
            return {"text": linkify_phones_in_text(data["_raw"]), "buttons": [_back("inmate")]}
        return {"text": format_bookings_result(data), "buttons": [_back("inmate")]}

    # ── Forms: homestead ──────────────────────────────────────────────────
    if context == "forms_homestead":
        parts = [p.strip() for p in text.split(";")]
        if len(parts) < 2:
            return {
                "text": "Please provide at least: `Name ; Address`\n\nOptionally: `Name ; Address ; Parcel ID`",
                "expects_input": True,
                "buttons": [_back("forms")],
            }
        name = parts[0]
        address = parts[1]
        cmd = ["forms", "fill", "homestead", "--name", name, "--address", address]
        if len(parts) >= 3 and parts[2]:
            cmd += ["--parcel", parts[2]]
        cmd.append("--json")
        data = run_ocfl(*cmd)
        result_text = format_forms_result(data)
        return {"text": result_text, "buttons": [_back("forms")],
                "file_path": data.get("output_path")}

    # ── Forms: building permit ────────────────────────────────────────────
    if context == "forms_building_permit":
        parts = [p.strip() for p in text.split(";")]
        if len(parts) < 4:
            return {
                "text": "Please provide: `Owner Name ; Address, City, ST ZIP ; Description ; Valuation`",
                "expects_input": True,
                "buttons": [_back("forms")],
            }
        owner, addr_full, desc, val = parts[0], parts[1], parts[2], parts[3]
        # Parse address parts
        addr_parts = [p.strip() for p in addr_full.split(",")]
        owner_addr = addr_parts[0] if len(addr_parts) > 0 else addr_full
        owner_city = addr_parts[1] if len(addr_parts) > 1 else "Orlando"
        state_zip = addr_parts[2].strip().split() if len(addr_parts) > 2 else ["FL", "32801"]
        owner_state = state_zip[0] if len(state_zip) > 0 else "FL"
        owner_zip = state_zip[1] if len(state_zip) > 1 else "32801"

        data = run_ocfl("forms", "fill", "building-permit",
                        "--owner-name", owner,
                        "--owner-address", owner_addr,
                        "--owner-city", owner_city,
                        "--owner-state", owner_state,
                        "--owner-zip", owner_zip,
                        "--description", desc,
                        "--valuation", val,
                        "--json")
        result_text = format_forms_result(data)
        return {"text": result_text, "buttons": [_back("forms")],
                "file_path": data.get("output_path")}

    # ── Default: property lookup (existing behavior) ──────────────────────
    clean = text.replace("-", "").replace(" ", "")
    if clean.isdigit() and len(clean) >= 12:
        data = run_ocfl("property", text)
        return {"text": format_property_result(data)}

    data = run_ocfl("property", text)
    return {"text": format_property_result(data)}


# ---------------------------------------------------------------------------
# CLI for testing
# ---------------------------------------------------------------------------

def main():
    """CLI interface for testing the wizard"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  wizard.py callback <callback_data>")
        print("  wizard.py input <text> [context]")
        print("  wizard.py start")
        sys.exit(1)

    action = sys.argv[1]

    if action == "start":
        result = {"text": FLOWS["main"]["text"], "buttons": FLOWS["main"]["buttons"]}
    elif action == "callback" and len(sys.argv) > 2:
        result = handle_callback(sys.argv[2])
    elif action == "input" and len(sys.argv) > 2:
        context = sys.argv[-1] if len(sys.argv) > 3 and sys.argv[-1] in (
            "health_inspections", "directory_search", "library_search",
            "inmate_search", "forms_homestead", "forms_building_permit",
        ) else None
        text_parts = sys.argv[2:] if context is None else sys.argv[2:-1]
        result = handle_text_input(" ".join(text_parts), context)
    else:
        print("Invalid arguments")
        sys.exit(1)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
