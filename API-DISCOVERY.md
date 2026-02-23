# Orange County FL — API & Endpoint Discovery

> Generated: 2026-02-22 | Status: Initial probe complete

## Legend
- 🟢 **Public** — No auth, open JSON/REST
- 🟡 **Semi-public** — Free account or CAPTCHA required
- 🔴 **Private** — Paid, internal, or auth-walled
- ⚪ **None found** — No discoverable API

---

## 1. Tax Collector — octaxcol.com

**Platform:** WordPress (Yoast SEO)  
**Status:** ⚪ No discoverable REST API

| Check | Result |
|-------|--------|
| robots.txt | Disallows `/new-site2020/`, `/_old-site/`, `/TEMP/`, `/TEMP2/` |
| sitemap.xml | WordPress Yoast sitemap index at `/sitemap_index.xml` |
| /api | Not probed (WordPress, no WP REST API exposed publicly) |
| JS endpoints | Site is static WordPress; property tax search links out |

**Notes:**
- Property tax records search and business tax search pages exist but appear to use embedded iframes or external redirects
- Tax roll data is downloadable (mentioned on site nav: "Tax Roll Download")
- No REST/JSON endpoints discovered; lookups are form-based

**Useful URLs:**
- Tax Roll Download: `https://www.octaxcol.com/taxes/tax-roll-download/`
- Business Tax Search: `https://www.octaxcol.com/taxes/business-tax-search-payment/`

---

## 2. Property Appraiser — ocpafl.org / ocpaweb.ocpafl.org

**Platform:** SPA (Angular/React, JS-heavy, "Loading..." without JS)  
**Status:** 🟢 ArcGIS REST services publicly queryable

### 2a. Web Application (ocpaweb.ocpafl.org)
- SPA at `https://ocpaweb.ocpafl.org/` — all routes return the SPA shell
- Parcel search URL pattern: `https://ocpaweb.ocpafl.org/parcelsearch/Parcel%20ID/{PARCEL_ID}`
- **Underlying API not yet captured** — requires browser network inspection to find XHR/fetch endpoints (SPA loads data via JS)
- No robots.txt (returns SPA shell for all paths)

### 2b. ArcGIS Server — vgispublic.ocpafl.org 🟢
**Base:** `https://vgispublic.ocpafl.org/server/rest/services`  
**Version:** 10.81  
**Auth:** None required  
**Format:** JSON (`?f=json`)

**Folders & Key Services:**

| Folder | Services |
|--------|----------|
| OCPA | Base, BaseTrans, Demography, Drone_Catalog, FutureDevelopment, Jurisdiction, LandLines, PLSS, Subdivisions, Zoning |
| OCPA | Aerials2001–2025 (yearly aerial imagery MapServers) |
| Oakland | PARCEL (MapServer) — MaxRecordCount: 3000 |
| DYNAMIC | (various) |
| Webmap | (various) |
| Root | Ian_Damage_Map_Gallery, Nearby_Amenities_MIL1 (FeatureServer + MapServer) |

**Example Queries:**
```
# List all OCPA services
https://vgispublic.ocpafl.org/server/rest/services/OCPA?f=json

# Query parcels (Oakland)
https://vgispublic.ocpafl.org/server/rest/services/Oakland/PARCEL/MapServer/0/query?where=1%3D1&outFields=*&f=json&resultRecordCount=5

# Base map export
https://vgispublic.ocpafl.org/server/rest/services/OCPA/Base/MapServer/export?bbox=-81.5,28.3,-81.3,28.6&format=png&f=image
```

---

## 3. Clerk of Courts — myorangeclerk.com

**Platform:** Custom .NET/Java (heavy JS SPA)  
**Status:** 🟡 Court records searchable with free account

| Check | Result |
|-------|--------|
| robots.txt | No robots.txt (redirects to home page) |
| /api | Redirects to home page |
| Site | SPA-style; minimal content without JS |

**Notes:**
- Court records, official records, and case search require login or are JS-rendered
- Official Records search: `https://or.myorangeclerk.com/` (separate subdomain)
- Court case search likely at: `https://myeclerk.myorangeclerk.com/`
- Maintenance window noted (payments/documents access restricted on weekends)
- **Needs browser-based network inspection** to discover underlying API calls

**Useful URLs:**
- Official Records: `https://or.myorangeclerk.com/`
- Court Records: `https://myeclerk.myorangeclerk.com/`

---

## 4. Sheriff's Office — ocso.com

**Platform:** DNN (DotNetNuke)  
**Status:** ⚪ No public API discovered

| Check | Result |
|-------|--------|
| robots.txt | Standard DNN robots.txt; disallows `/admin/`, `/DesktopModules/`, etc. |
| /api | 404 |
| Calls for Service | Page exists but just promotes mobile app |

**Notes:**
- Active calls: OCSO promotes their **mobile app** (Apple/Android) for calls for service — no public web API
- Sex offender info links to FDLE
- File police report is form-based
- DNN platform unlikely to expose REST APIs without custom modules
- **No ArcGIS or public data services found**

---

## 5. Supervisor of Elections — ocfelections.gov

**Platform:** Drupal  
**Status:** ⚪ No public API discovered  
**Note:** Domain redirected from `ocfelections.com` → `ocfelections.gov`

| Check | Result |
|-------|--------|
| robots.txt | Standard Drupal robots.txt |
| Voter lookup | Likely links to state FVRS system |
| Election results | Published as static pages/PDFs |

**Useful URLs:**
- Voter info check: `https://ocfelections.gov/voters/check-my-info` (likely redirects to state)
- Election results: `https://ocfelections.gov/elections/election-results-and-turnout`
- Campaign finance: `https://ocfelections.gov/candidates/candidatecommittee-finance-login`

---

## 6. OCLS Library — ocls.org / catalog.ocls.org

**Platform:** WordPress (ocls.org) + VuFind/Aspen Discovery (catalog)  
**Status:** 🟢 Catalog search via URL parameters

### 6a. Main Site (ocls.org)
- WordPress with Yoast; sitemap at `https://ocls.org/sitemap_index.xml`
- Events/classes searchable via URL params: `https://ocls.org/classes-events/?_event_search=QUERY`

### 6b. Catalog (catalog.ocls.org) 🟢
**Platform:** Aspen Discovery (open-source ILS frontend)  
**Auth:** None for searching; account for holds/checkouts

**Search URL Pattern:**
```
https://catalog.ocls.org/Search/Results?lookfor={QUERY}&type=AllFields
```

**Known URL Patterns:**
```
# Search
https://catalog.ocls.org/Search/Results?lookfor=python+programming&type=AllFields

# Record detail (by grouped work ID)
https://catalog.ocls.org/GroupedWork/{ID}/Home

# Record detail (Hoopla)
https://catalog.ocls.org/Hoopla/{ID}

# Record detail (Kanopy)
https://catalog.ocls.org/Kanopy/{ID}
```

**API Endpoints (Aspen Discovery standard):**
```
# Search API (may need auth or may be open)
https://catalog.ocls.org/API/SearchAPI?method=getSearchResults&lookfor=test&searchIndex=Keyword

# Item API
https://catalog.ocls.org/API/ItemAPI?method=getItem&id={BIB_ID}

# User API (requires auth)
https://catalog.ocls.org/API/UserAPI?method=login&username=X&password=X
```
*Note: SearchAPI returned 403 (IP-blocked) during testing — may work from different IPs or with API key*

---

## 7. Health Department — FL DOH Orange County

**Status:** ⚪ Not directly probed (state-run)

**Known Resources:**
- Restaurant inspections: `https://data.fdacs.gov` or `https://www.myfloridalicense.com/`
- FL DOH Orange: `http://orange.floridahealth.gov/`
- Restaurant inspection data is available via **FL DBPR** (Dept of Business & Professional Regulation)

**State-Level APIs:**
```
# FL DBPR License/Inspection Search
https://www.myfloridalicense.com/wl11.asp

# Open data portal
https://data.fdacs.gov/
```

---

## 8. Animal Services — orangecountyanimalservicesfl.net / ocnetpets.com

**Platform:** Custom ASP.NET  
**Status:** 🟡 Paginated web search (no REST API discovered)

| Check | Result |
|-------|--------|
| Shelter animals | Server-rendered ASP.NET pages with pagination |
| URL params | `?page=N&pagesize=N` for browsing |
| Filters | Type (Cat/Dog), Age, Gender, Adoption Status — rendered server-side |

**Useful URLs:**
```
# Browse all shelter animals (paginated)
https://www.ocnetpets.com/Adopt/AnimalsinShelter.aspx?page=1&pagesize=100

# Foster animals
https://www.ocnetpets.com/GetInvolved/FosterCare.aspx
```

**Notes:**
- Same content on both `orangecountyanimalservicesfl.net` and `ocnetpets.com`
- No JSON API discovered; data is server-rendered HTML
- Could potentially be scraped via URL parameters
- Animal IDs follow pattern `A######`

---

## 9. ArcGIS Hub — ocgis-datahub-ocfl.hub.arcgis.com 🟢🟢🟢

**Platform:** Esri ArcGIS Hub  
**Status:** 🟢 Fully public, rich API

### Hub Search API
```
# Search all datasets
https://ocgis-datahub-ocfl.hub.arcgis.com/api/v3/search?q=*

# Search specific topics
https://ocgis-datahub-ocfl.hub.arcgis.com/api/v3/search?q=parcels
https://ocgis-datahub-ocfl.hub.arcgis.com/api/v3/search?q=zoning
```

### ArcGIS Server — ocgis4.ocfl.net 🟢
**Base:** `https://ocgis4.ocfl.net/arcgis/rest/services`  
**Version:** 10.91  
**Auth:** None  
**Format:** JSON

**Available Services:**

| Service | Type | Description |
|---------|------|-------------|
| AGOL_Open_Data | MapServer | **60+ layers** — parcels, zoning, flood zones, parks, schools, etc. |
| AGOL_Open_Data2 | MapServer | Additional open data layers |
| Public_Dynamic | MapServer | Dynamic rendering, 220+ layers |
| Public_Base | MapServer | Base map tiles |
| Public_Aerial_Base | MapServer | Aerial imagery |
| Public_Notification | MapServer | Notification areas |
| InfoMap_Public_Layers | MapServer | InfoMap layers |
| FR_ISO_Parcels | MapServer | Fire Rescue ISO parcels |
| Gridics | MapServer | Gridics zoning data |
| Tree_Cover | MapServer | Tree canopy data |
| PUBLIC_SITUS_ADDRESS_LOC | GeocodeServer | **Address geocoder (situs)** |
| PUBLIC_STREET_ADDRESS_LOC | GeocodeServer | **Address geocoder (street)** |
| PublicCompositeLoc_AGO | GeocodeServer | Composite address locator |

**Key AGOL_Open_Data Layers (partial — 60+ total):**

| ID | Layer Name |
|----|-----------|
| 0 | Address Points |
| 1 | Address Range |
| 3 | Airport Noise Contours |
| 6 | Boat Ramps |
| 9 | Code Enforcement Officer Zones |
| 10 | Colleges and Universities |
| 11 | Commission Districts |
| 12 | Community Development Districts |
| 15 | Conservation |
| 16 | County Boundary |
| 19 | FEMA Flood Zones |
| 20 | Fire Stations Countywide |
| 21 | Future Land Use |
| 25 | Hospitals |
| 28 | Hydrology |
| 31 | Jurisdictions |
| 32 | Law Enforcement Agencies |
| 33 | Major Drainage Basins |
| 34 | Neighborhood Organizations |
| 60 | Water Service Provider |
| ... | (many more) |

**Example Queries:**
```
# Query address points near a location
https://ocgis4.ocfl.net/arcgis/rest/services/AGOL_Open_Data/MapServer/0/query?where=1%3D1&geometry=-81.38,28.54,-81.37,28.55&geometryType=esriGeometryEnvelope&spatialRel=esriSpatialRelIntersects&outFields=*&f=json&resultRecordCount=10

# Query FEMA flood zones for a point
https://ocgis4.ocfl.net/arcgis/rest/services/AGOL_Open_Data/MapServer/19/query?geometry=-81.38,28.54&geometryType=esriGeometryPoint&spatialRel=esriSpatialRelIntersects&outFields=*&f=json&inSR=4326

# Geocode an address
https://ocgis4.ocfl.net/arcgis/rest/services/PUBLIC_SITUS_ADDRESS_LOC/GeocodeServer/findAddressCandidates?SingleLine=201+S+Rosalind+Ave+Orlando&outFields=*&f=json

# Query jurisdictions
https://ocgis4.ocfl.net/arcgis/rest/services/AGOL_Open_Data/MapServer/31/query?where=1%3D1&outFields=*&f=json&resultRecordCount=5

# Fire stations
https://ocgis4.ocfl.net/arcgis/rest/services/AGOL_Open_Data/MapServer/20/query?where=1%3D1&outFields=*&f=json
```

---

## 10. Fast Track Permits — fasttrack.ocfl.net

**Platform:** Custom ASP.NET  
**Status:** 🔴 Login required for all functionality

| Check | Result |
|-------|--------|
| robots.txt | `Allow: /OnlineServices/Default.aspx` / `Disallow: /` — everything blocked except landing |
| /api | 404 |
| Site | Redirects to `/OnlineServices/` — permit dashboard requires login |

**Notes:**
- All permit operations (apply, inspect, pay) require contractor/homeowner account
- No public API; form-based with ASP.NET postbacks
- Escrow accounts, inspections, shopping cart — all behind auth

---

## 11. 311 / Service Requests — orangecountyfl.net

**Platform:** DNN (orangecountyfl.net) + QAlert/custom (311 portal)  
**Status:** 🟡 Online request portal available

### 311 Online Request Portal
**URL:** `https://311onlinerequests.ocfl.net/portal/default.aspx`
- Redirect loop during testing — may require browser access
- Accepts service requests for: animals, potholes, traffic signs, graffiti, sidewalks, etc.

### OCFL 311 Mobile App
- iOS: App Store "OCFL 311"
- Android: Google Play "OCFL 311"
- Likely uses a backend API (SeeClickFix or QAlert style) — not publicly documented

### Fire Rescue Active Calls
**Note:** Uses **PulsePoint** (third-party) — not a county API
- Web: `https://web.pulsepoint.org/` → select "Orange County Fire Rescue Department (FL)"
- PulsePoint has its own API

**Other orangecountyfl.net endpoints of interest:**
```
# DNN-based, various modules
https://www.orangecountyfl.net/EmergencySafety/FireRescue/ActiveCalls.aspx
https://www.orangecountyfl.net/OpenGovernment/OrangeSTATS.aspx
https://netapps.ocfl.net/ocserves/Organization.aspx?oid=20
```

---

## Summary: Best Public APIs

| Rank | Service | Type | Richness |
|------|---------|------|----------|
| 🥇 | **OCFL ArcGIS (ocgis4)** | REST/JSON | 60+ layers, geocoding, open query |
| 🥈 | **OCPA ArcGIS (vgispublic)** | REST/JSON | Parcels, aerials, zoning, base maps |
| 🥉 | **ArcGIS Hub** | REST/JSON | Dataset search/discovery API |
| 4 | **OCLS Catalog** | URL/HTML | Searchable, Aspen Discovery patterns |
| 5 | **Animal Services** | HTML scrape | Paginated, filterable shelter listings |
| 6 | **PulsePoint** | Third-party | Fire/rescue active calls |

## Needs Browser Inspection (SPA/JS-heavy)
- **OCPA Web** (ocpaweb.ocpafl.org) — SPA likely has XHR/fetch API for parcel data
- **Clerk of Courts** (myorangeclerk.com) — Court records behind JS/login
- **311 Portal** (311onlinerequests.ocfl.net) — Request system backend
- **Tax Collector** property tax search — may have embedded lookup API

---

## ArcGIS Quick Reference

Both ArcGIS servers support standard Esri REST API patterns:

```
# List services
{base}/rest/services?f=json

# Service info
{base}/rest/services/{name}/MapServer?f=json

# Layer query
{base}/rest/services/{name}/MapServer/{layerId}/query?where=FIELD='VALUE'&outFields=*&f=json

# Spatial query
...&geometry={lon},{lat}&geometryType=esriGeometryPoint&spatialRel=esriSpatialRelIntersects&inSR=4326

# Geocode
{base}/rest/services/{name}/GeocodeServer/findAddressCandidates?SingleLine={address}&f=json

# Export map image
{base}/rest/services/{name}/MapServer/export?bbox={xmin},{ymin},{xmax},{ymax}&format=png&f=image
```
