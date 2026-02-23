<div align="center">

# 🍊 OCFL Bot

### Orange County FL Government Services

**AI-powered CLI and Telegram bot for Orange County, Florida county services**

50+ service guides · Live API integrations · PDF form filling · 155-entry directory

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## 📋 What is this?

OCFL Bot is a **CLI and Telegram bot** that gives citizens and AI agents structured access to **Orange County, Florida** government services — property records, tax lookups, permits, court services, elections, health inspections, and more.

- 🏛️ **For citizens** — Get answers about county services without navigating dozens of websites
- 🤖 **For AI agents** — Any agent (ChatGPT, Claude, OpenClaw, etc.) can use this CLI as a tool to help constituents
- 🔬 **Proof of concept** — Demonstrates how county governments can become AI-ready by exposing services as structured, machine-readable commands

Every command supports `--json` output, making OCFL Bot a bridge between government data and the AI ecosystem.

---

## ✨ Features

### 🗂️ 12 Command Groups

| Group | Examples |
|-------|---------|
| **property** | Parcel lookup, tax search, homestead exemption, flood zones |
| **vehicles** | Registration, title, boat, mobile home, DMV |
| **courts** | Marriage license, deeds, vital records, passport, jury duty |
| **elections** | Voter registration, vote-by-mail, polling lookup |
| **permits** | Permit lookup, business tax, short-term rental, inspections |
| **safety** | Hurricane prep, animal control, CCW, code enforcement |
| **health** | Restaurant inspections, mosquito control, clinics, crisis services |
| **utilities** | 311 requests, trash/recycling, pothole reports, drainage |
| **community** | Senior services, family services, Medicaid, workforce dev |
| **recreation** | Park reservations, library cards, hunting/fishing, arts grants |
| **government** | Budget transparency, procurement/bids |
| **forms** | PDF form filling (homestead exemption, building permits) |

### 🔌 Live API Integrations

```bash
ocfl property lookup "123 Main St, Orlando"    # Property Appraiser REST API
ocfl property tax "123 Main St"                # Tax Collector (Algolia)
ocfl gis flood "456 Oak Ave, Orlando"          # ArcGIS flood zone lookup
ocfl health inspections "Chili's"              # DBPR restaurant inspections
ocfl pets --ready --type dog --limit 5         # Animal Services adoptable pets
ocfl inmate "John Doe"                         # Corrections inmate search
```

### 📄 PDF Form Filling

```bash
ocfl forms fill homestead --name "Jane Doe" --address "123 Main St, Orlando, FL 32801"
ocfl forms fill building-permit --owner-name "John Smith" --description "Kitchen remodel"
```

### 📞 155-Entry County Directory

```bash
ocfl directory fire                # Fuzzy search → Fire Rescue, stations, chiefs
ocfl directory regex "^Animal"     # Regex search
ocfl phone "building permits"     # Quick phone lookup
```

### 🤖 Telegram Bot with Inline Menus

Interactive wizard with button-driven navigation — no typing required.

---

## 🚀 Quick Start

```bash
# Clone and install
git clone https://github.com/orange-county/ocfl-bot.git
cd ocfl-bot
uv sync
uv pip install -e . --python .venv/bin/python

# Run
.venv/bin/ocfl --help
.venv/bin/ocfl property lookup "123 Main St, Orlando"
.venv/bin/ocfl directory fire
.venv/bin/ocfl forms fill homestead --name "Jane Doe" --address "123 Main St"
```

---

## 📖 Command Reference

### `ocfl property` — Property & Tax

```
ocfl property lookup <addr>        Property info by address/parcel (live API)
ocfl property tax <addr>           Property tax info (live API)
ocfl property homestead            Homestead Exemption guide
ocfl property appraisal            TRIM / VAB Appraisal Appeal
ocfl property flood                Floodplain Determination
ocfl property domicile             Declaration of Domicile
```

### `ocfl vehicles` — Vehicles & DMV

```
ocfl vehicles registration         Vehicle Registration / Tag Renewal
ocfl vehicles title                Vehicle Title / Lien Release
ocfl vehicles boat                 Boat Registration / Titling
ocfl vehicles mobilehome           Mobile Home Titling
ocfl vehicles dmv                  Driver License Renewal
```

### `ocfl courts` — Courts & Records

```
ocfl courts marriage               Marriage License
ocfl courts deeds                  Deed / Lien / Mortgage Recording
ocfl courts vitals                 Birth / Death / Marriage Certificate
ocfl courts passport               Passport Application
ocfl courts notary                 Notary Public Services
ocfl courts probate                Probate / Estate / Name Change
ocfl courts jury                   Jury Duty Response
ocfl courts records                Public Records / Sunshine Request
ocfl courts pd                     Public Defender Application
```

### `ocfl elections` — Elections & Voting

```
ocfl elections voter               Voter Registration / Update
ocfl elections ballot              Vote-by-Mail Ballot Request
ocfl elections info                Election Info & Polling Lookup
```

### `ocfl permits` — Permits & Business

```
ocfl permits lookup [type]         Permit requirements & fees
ocfl permits biztax                Business Tax Receipt
ocfl permits str                   Short-Term Rental Permit
ocfl permits inspection            On-Site Building Inspection
ocfl permits dba                   Fictitious Name / DBA Registration
```

### `ocfl safety` — Safety & Emergency

```
ocfl safety hurricane              Hurricane / Disaster Assistance
ocfl safety stray                  Animal Control / Stray / Bite Report
ocfl safety ccw                    Concealed Weapon License
ocfl safety fingerprint            Live Scan Fingerprinting
ocfl safety dv                     Domestic Violence Services
ocfl safety code                   Code Enforcement Complaint
```

### `ocfl health` — Health & Inspections

```
ocfl health inspections <name>     DBPR Restaurant Inspections (live)
ocfl health mosquito               Mosquito Control
ocfl health clinic                 Public Health Clinic Services
ocfl health crisis                 Mental Health / Crisis Services
ocfl health vector                 Vector Control Request
ocfl health cemetery               Cemetery / Burial Permit
```

### `ocfl utilities` — Utilities & 311

```
ocfl utilities 311                 311 Non-Emergency Requests
ocfl utilities trash               Trash / Recycling / Bulk Pickup
ocfl utilities pothole             Pothole / Road Report
ocfl utilities drainage            Stormwater / Drainage Complaint
ocfl utilities dumping             Illegal Dumping Complaint
```

### `ocfl community` — Community Services

```
ocfl community seniors             Senior / Disabled / Veterans
ocfl community family              Child Support / Family Services
ocfl community medicaid            Medicaid / SNAP Screening
ocfl community workforce           Workforce Development
ocfl community extension           UF/IFAS Extension / 4-H
```

### `ocfl recreation` — Recreation & Culture

```
ocfl recreation reserve            Park Pavilion / Facility Reservation
ocfl recreation libcard            Library Card Issuance
ocfl recreation hunting            Hunting / Fishing License
ocfl recreation arts               Arts / Cultural Grant
```

### `ocfl government` — Budget & Procurement

```
ocfl government budget             County Budget & Transparency
ocfl government bids               Procurement / Bid Opportunities
```

### `ocfl forms` — PDF Form Filling

```
ocfl forms list                    List available fillable PDF forms
ocfl forms fields <form-id>        Show all fillable fields for a form
ocfl forms fill <form-id> [opts]   Fill a PDF form and open it
```

### Top-Level Commands

```
ocfl gis layers                    List available ArcGIS layers
ocfl gis flood <address>           Flood zone lookup
ocfl gis zoning <address>          Zoning lookup
ocfl gis --layer <n> --near x,y    Query any layer by proximity
ocfl geocode <address>             Geocode an Orange County address
ocfl pets [--ready] [--type X]     Search adoptable pets
ocfl inmate <name>                 Search inmates by name
ocfl inmate --bookings             Download recent booking reports
ocfl phone <query>                 Department phone lookup
ocfl directory [query]             Browse/search department directory
ocfl directory list                Full directory dump
ocfl directory regex <pattern>     Regex search directory
ocfl library <query>               Search OCLS catalog
ocfl services                      List all commands by category
```

### Global Options

| Flag | Description |
|------|-------------|
| `--json` | Machine-readable JSON output on all commands |
| `--version` | Show version |
| `--help` | Help on any command or group |

---

## 🤖 Telegram Bot Integration

The `wizard.py` module provides an interactive Telegram bot experience with **inline button menus**:

1. User sends `/start` or a question
2. Bot presents service categories as inline buttons
3. User taps through a guided flow — no typing required
4. Bot returns structured answers with phone numbers, URLs, hours, and next steps

**How it works with OpenClaw:** The wizard connects to [OpenClaw](https://github.com/nichochar/openclaw) as a skill. When a user asks about Orange County services, the AI agent invokes `ocfl` commands behind the scenes and returns formatted responses with action buttons.

---

## 📄 PDF Form Filling

Pre-fill official Orange County PDF forms from the command line.

### Available Forms

| Form ID | Name | Fields |
|---------|------|--------|
| `homestead` | DR-501 Homestead Exemption Application | 22 fillable fields |
| `building-permit` | Orange County Building Permit Application | 107 fields (24 mapped) |

### Example Usage

```bash
# Homestead Exemption
ocfl forms fill homestead \
  --name "Jane Doe" \
  --address "123 Main St, Orlando, FL 32801" \
  --parcel "01-23-45-6789-00-100" \
  --date-acquired "01/15/2025"
# → Saves to ~/Downloads/homestead_filled.pdf

# Building Permit
ocfl forms fill building-permit \
  --owner-name "John Smith" \
  --owner-address "456 Oak Ave" \
  --owner-city "Orlando" \
  --owner-state "FL" \
  --owner-zip "32803" \
  --description "Kitchen remodel" \
  --valuation "25000"
# → Saves to ~/Downloads/building_permit_filled.pdf
```

### Key Flags

**Homestead:** `--name`, `--co-applicant`, `--address`, `--parcel`, `--phone`, `--ssn`, `--dob`, `--date-acquired`, `--previous-homestead`, `--tax-year`

**Building Permit:** `--owner-name`, `--owner-address`, `--owner-city`, `--owner-state`, `--owner-zip`, `--owner-phone`, `--subdivision`, `--tenant`, `--business`, `--architect`, `--description`, `--valuation`

---

## 🗄️ Data Sources

| Source | API Type | Auth |
|--------|----------|------|
| OCPA (Property Appraiser) | REST/JSON | None |
| Tax Collector (Algolia) | Algolia search | Public key |
| OCFL ArcGIS (ocgis4) | REST/JSON | None |
| FL DBPR (Inspections) | HTML scrape | None |
| Animal Services (ocnetpets) | HTML scrape | None |
| BestJail (Corrections) | HTML scrape + PDF | None |
| OCLS Library | HTML scrape | None |
| Directory | Local (DIRECTORY.md) | N/A |
| Permits | Local database | N/A |
| Service Guides | Local database | N/A |

## 🔗 API Endpoints Reference

| Service | Endpoint |
|---------|----------|
| OCPA REST | `https://ocpa-mainsite-afd-standard.azurefd.net/api/` |
| Tax Collector (Algolia) | App `0LWZO52LS2` · Indexes: `fl-orange.property_tax`, `fl-orange.business_tax` |
| ArcGIS | `https://ocgis4.ocfl.net/arcgis/rest/services/` (60+ layers) |
| OCPA ArcGIS | `https://vgispublic.ocpafl.org/server/rest/services/` |

> **Parcel ID format:** Display `35-20-27-6645-00-550` → API `272035664500550`

---

## 🏗️ Architecture

```
ocfl-bot/
├── ocfl.py          # Main CLI entry point (Click-based)
├── wizard.py        # Telegram bot wizard with inline button menus
├── forms/           # PDF form filling module (pypdf)
├── DIRECTORY.md     # 155-entry county phone directory data
├── SKILL.md         # OpenClaw skill definition
├── config.toml      # Configuration
└── pyproject.toml   # Python package definition
```

---

## 🛠️ Built With

- **[Python](https://python.org)** — 3.11+
- **[Click](https://click.palletsprojects.com)** — CLI framework
- **[Rich](https://rich.readthedocs.io)** — Terminal formatting & tables
- **[pypdf](https://pypdf.readthedocs.io)** — PDF form filling
- **[OpenClaw](https://github.com/nichochar/openclaw)** — AI agent platform integration

---

## 🤝 Contributing

Contributions are welcome! This project is a proof-of-concept for AI-ready government services.

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/new-service`)
3. Commit your changes (`git commit -m 'Add new service guide'`)
4. Push and open a Pull Request

Ideas for contribution:
- Add more service guides
- Map additional PDF form fields
- Add new API integrations (e.g., building permit status tracking)
- Improve Telegram bot flows

---

## ⚠️ Scope Note

This bot covers **unincorporated Orange County, Florida** and county-level services. Municipalities within Orange County — including **Orlando, Winter Park, Maitland, Apopka**, and others — have their own separate government systems, websites, and service portals.

When in doubt, the bot will note whether a service is county-level or may require contacting a specific city.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.

---

<div align="center">

**🍊 Making Orange County government services accessible to humans and AI agents alike.**

</div>
