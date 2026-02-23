---
name: ocfl
description: "Orange County FL Government Services CLI v3.0 — grouped subcommands for property, tax, GIS, permits, pets, inmates, library, directory, inspections, 50+ service guides"
metadata:
  {"openclaw": {"emoji": "🍊", "requires": {"bins": ["ocfl"]}, "install": [{"id": "uv", "kind": "uv", "package": ".", "bins": ["ocfl"], "label": "Install OCFL CLI (uv pip install)"}]}}
---

# OCFL CLI v3.0 — Orange County FL Government Services

Comprehensive CLI for interacting with Orange County, Florida government data and services.
Commands are organized into logical groups.

## Installation

```bash
cd {baseDir}
uv pip install -e . --python .venv/bin/python
ln -sf {baseDir}/.venv/bin/ocfl ~/bin/ocfl
```

## Command Groups

### `ocfl property` — property

```bash
ocfl property lookup <addr>                             # Property info by address/parcel (live API)
ocfl property tax <addr>                                # Property tax info (live API)
ocfl property homestead                                 # Homestead Exemption Application
ocfl property appraisal                                 # TRIM / VAB Appraisal Appeal
ocfl property flood                                     # Floodplain Determination
ocfl property domicile                                  # Declaration of Domicile
```

### `ocfl vehicles` — vehicles

```bash
ocfl vehicles registration                              # Vehicle Registration / Tag Renewal
ocfl vehicles title                                     # Vehicle Title / Lien Release
ocfl vehicles boat                                      # Boat Registration / Titling
ocfl vehicles mobilehome                                # Mobile Home Titling
ocfl vehicles dmv                                       # Driver License Renewal
```

### `ocfl courts` — courts

```bash
ocfl courts marriage                                    # Marriage License
ocfl courts deeds                                       # Deed / Lien / Mortgage Recording
ocfl courts vitals                                      # Birth / Death / Marriage Certificate
ocfl courts passport                                    # Passport Application
ocfl courts notary                                      # Notary Public Services
ocfl courts probate                                     # Probate / Estate / Name Change
ocfl courts jury                                        # Jury Duty Response
ocfl courts records                                     # Public Records / Sunshine Request
ocfl courts pd                                          # Public Defender Application
```

### `ocfl elections` — elections

```bash
ocfl elections voter                                    # Voter Registration / Update
ocfl elections ballot                                   # Vote-by-Mail Ballot Request
ocfl elections info                                     # Election Info & Polling Lookup
```

### `ocfl permits` — permits

```bash
ocfl permits lookup [type]                              # Permit requirements & fees (offline DB)
ocfl permits biztax                                     # Business Tax Receipt
ocfl permits str                                        # Short-Term Rental Permit
ocfl permits inspection                                 # On-Site Building Inspection
ocfl permits dba                                        # Fictitious Name / DBA Registration
```

### `ocfl safety` — safety

```bash
ocfl safety hurricane                                   # Hurricane / Disaster Assistance
ocfl safety stray                                       # Animal Control / Stray / Bite Report
ocfl safety ccw                                         # Concealed Weapon License
ocfl safety fingerprint                                 # Live Scan Fingerprinting
ocfl safety dv                                          # Domestic Violence Services
ocfl safety code                                        # Code Enforcement Complaint
```

### `ocfl health` — health

```bash
ocfl health inspections <name>                          # DBPR Restaurant Inspections (live)
ocfl health mosquito                                    # Mosquito Control
ocfl health clinic                                      # Public Health Clinic Services
ocfl health crisis                                      # Mental Health / Crisis Services
ocfl health vector                                      # Vector Control Request
ocfl health cemetery                                    # Cemetery / Burial Permit
```

### `ocfl utilities` — utilities

```bash
ocfl utilities 311                                      # 311 Non-Emergency Requests
ocfl utilities trash                                    # Trash / Recycling / Bulk Pickup
ocfl utilities pothole                                  # Pothole / Road Report
ocfl utilities drainage                                 # Stormwater / Drainage Complaint
ocfl utilities dumping                                  # Illegal Dumping Complaint
```

### `ocfl community` — community

```bash
ocfl community seniors                                  # Senior / Disabled / Veterans
ocfl community family                                   # Child Support / Family Services
ocfl community medicaid                                 # Medicaid / SNAP Screening
ocfl community workforce                                # Workforce Development
ocfl community extension                                # UF/IFAS Extension / 4-H
```

### `ocfl recreation` — recreation

```bash
ocfl recreation reserve                                 # Park Pavilion / Facility Reservation
ocfl recreation libcard                                 # Library Card Issuance
ocfl recreation hunting                                 # Hunting / Fishing License
ocfl recreation arts                                    # Arts / Cultural Grant
```

### `ocfl government` — government

```bash
ocfl government budget                                  # County Budget & Transparency
ocfl government bids                                    # Procurement / Bid Opportunities
```

### `ocfl forms` — PDF form filling

```bash
ocfl forms list                                         # List available fillable PDF forms
ocfl forms fields <form-id>                             # Show all fillable fields for a form
ocfl forms fill <form-id> [--field value ...]           # Fill a PDF form and open it
```

**Available forms:**
- `homestead` — DR-501 Homestead Exemption Application (22 fields)
- `building-permit` — Orange County Building Permit Application (107 fields, 24 mapped)

**Examples:**

```bash
# Fill homestead exemption form
ocfl forms fill homestead \
  --name "Jane Doe" \
  --address "123 Main St, Orlando, FL 32801" \
  --parcel "01-23-45-6789-00-100" \
  --date-acquired "01/15/2025"
# → Saves to ~/Downloads/homestead_filled.pdf and opens it

# Fill building permit application
ocfl forms fill building-permit \
  --owner-name "John Smith" \
  --owner-address "456 Oak Ave" \
  --owner-city "Orlando" \
  --owner-state "FL" \
  --owner-zip "32803" \
  --description "Kitchen remodel" \
  --valuation "25000"
# → Saves to ~/Downloads/building_permit_filled.pdf and opens it

# See all available flags for a form
ocfl forms fields homestead
ocfl forms fields building-permit
```

**Key homestead flags:** `--name`, `--co-applicant`, `--address`, `--parcel`, `--phone`, `--ssn`, `--dob`, `--date-acquired`, `--previous-homestead`, `--tax-year`

**Key building permit flags:** `--owner-name`, `--owner-address`, `--owner-city`, `--owner-state`, `--owner-zip`, `--owner-phone`, `--subdivision`, `--tenant`, `--business`, `--architect`, `--description`, `--valuation`

**Delivery:** After filling a form, send the completed PDF back to the user via the channel they connected on. For example, if the user is on Telegram, send it as a Telegram file attachment using the `message` tool with `filePath` pointing to the filled PDF. Same for any other channel (Signal, WhatsApp, Discord, etc.).

## Top-Level Commands

```bash
ocfl gis layers                                    # List available ArcGIS layers
ocfl gis flood <address>                           # Flood zone lookup
ocfl gis zoning <address>                          # Zoning lookup
ocfl gis --layer <name> --near lat,lon             # Query any layer by proximity
ocfl geocode <address>                             # Geocode an Orange County address
ocfl pets --ready --limit 10                       # Search adoptable pets
ocfl pets --type dog --gender F                    # Filter pets by type/gender
ocfl inmate <name>                                 # Search inmates by name
ocfl inmate --bookings                             # Download recent booking reports
ocfl phone <query>                                 # Department phone lookup
ocfl directory                                     # Browse department categories
ocfl directory list                                # Full directory dump
ocfl directory <query>                             # Fuzzy search directory
ocfl directory regex <pattern>                     # Regex search directory
ocfl library <query>                               # Search OCLS catalog
ocfl services                                      # List all commands by category
```

## Global Options

- `--json` — Machine-readable JSON output on all commands
- `--version` — Show version
- `--help` — Help on any command or group

## Data Sources

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

## Key API Endpoints (Reference)

- OCPA REST: `https://ocpa-mainsite-afd-standard.azurefd.net/api/`
- Tax Collector Algolia: app=`0LWZO52LS2`, indexes: `fl-orange.property_tax`, `fl-orange.business_tax`
- ArcGIS: `https://ocgis4.ocfl.net/arcgis/rest/services/` (60+ layers)
- OCPA ArcGIS: `https://vgispublic.ocpafl.org/server/rest/services/`
- Parcel ID format: display `35-20-27-6645-00-550` → API `272035664500550`
