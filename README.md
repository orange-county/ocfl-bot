# OCFL — Orange County FL Government Services CLI

A command-line interface for interacting with Orange County, Florida government services.

## Features

- **Property Lookup** — Search parcel data, zoning, owner info
- **Permit Info** — Requirements, fees, checklists for common permits
- **Inmate Search** — Current inmates, booking lists
- **Pet Adoption** — Search adoptable animals with filters
- **Form Wizard** — Generate filled PDFs for permit applications

## Installation

```bash
cd skills/ocfl
uv sync
```

## Usage

```bash
# Property lookup
uv run ocfl property "123 Main St, Orlando"
uv run ocfl property 292234916802030

# Permit info
uv run ocfl permit fence
uv run ocfl permit pool

# Inmate search
uv run ocfl inmate "John Smith"
uv run ocfl inmate --bookings

# Pet search
uv run ocfl pets --type dog --ready
```

## Data Sources

- **Property Appraiser**: ocpafl.org
- **Permits**: fasttrack.ocfl.net
- **Jail**: netapps.ocfl.net/BestJail
- **Animal Services**: orangecountyanimalservicesfl.net
- **GIS**: ocgis-datahub-ocfl.hub.arcgis.com

## Note

Services apply to **unincorporated Orange County** only. Cities like Orlando, Winter Park, etc. have their own systems.
