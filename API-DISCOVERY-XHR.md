# Orange County FL — API Discovery (XHR/Fetch Interception)

> Discovered 2026-02-22 via browser network interception on live SPAs.

---

## 1. OCPA (Property Appraiser) — ✅ OPEN API, NO AUTH

**Base URL:** `https://ocpa-mainsite-afd-standard.azurefd.net/api/`

The OCPA Angular SPA calls an Azure Front Door-hosted REST API. All endpoints return JSON, require no authentication, and accept simple GET requests.

### 1a. Address Search

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /api/QuickSearch/GetSearchInfoByAddress` |
| **Full URL** | `https://ocpa-mainsite-afd-standard.azurefd.net/api/QuickSearch/GetSearchInfoByAddress` |
| **Method** | GET |
| **Query Params** | `address` (string), `page` (int), `size` (int), `sortBy` (ParcelID\|OwnerName\|Address), `sortDir` (ASC\|DESC) |
| **Response** | JSON array |
| **Auth** | ❌ None |

**Example Request:**
```
GET https://ocpa-mainsite-afd-standard.azurefd.net/api/QuickSearch/GetSearchInfoByAddress?address=1321%20Apopka%20Airport%20Rd&page=1&size=5&sortBy=ParcelID&sortDir=ASC
```

**Example Response:**
```json
[
  {
    "ownerName": " JOHARY AVIATION INC",
    "propertyAddress": "1321 APOPKA AIRPORT RD HNGR A",
    "isHomestead": "False",
    "parcelId": "272035664500001",
    "totalCount": 179
  }
]
```

### 1b. Parcel General Info (Property Card)

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /api/PRC/GetPRCGeneralInfo` |
| **Full URL** | `https://ocpa-mainsite-afd-standard.azurefd.net/api/PRC/GetPRCGeneralInfo` |
| **Method** | GET |
| **Query Params** | `pid` (parcel ID, 15-digit no dashes: e.g. `272035664500001`) |
| **Response** | JSON object |
| **Auth** | ❌ None |

**Example Response:**
```json
{
  "taxYear": 2026,
  "prcTaxYear": 2025,
  "trimYear": 2025,
  "parcelId": "272035664500001",
  "ownerName": " JOHARY AVIATION INC",
  "propertyName": "ORLANDO-APOPKA AIRPORT",
  "propertyAddress": "1321 APOPKA AIRPORT RD HNGR A",
  "mailAddress": "1321 Apopka Airport Rd Unit A",
  "mailCity": "Apopka",
  "mailState": "FL",
  "mailZip": "32712-5977",
  "propertyCity": "Apopka",
  "propertyState": "FL",
  "propertyZip": "32712",
  "dorCode": "1004",
  "dorDescription": "COMM VACANT CONDO",
  "cityDescription": "APOPKA",
  "streetNumber": 1321,
  "streetName": "APOPKA AIRPORT",
  "instNum": "20040284213"
}
```

### 1c. Parcel Statistics

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /api/PRC/GetPRCStats` |
| **Query Params** | `PID` (15-digit parcel ID) |
| **Auth** | ❌ None |

### 1d. Property Values

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /api/PRC/GetPRCPropertyValues` |
| **Query Params** | `PID`, `TaxYear` (0 = current), `ShowAllFlag` (1) |
| **Auth** | ❌ None |

### 1e. Certified Taxes

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /api/PRC/GetPRCCertifiedTaxes` |
| **Query Params** | `PID`, `TaxYear` (0 = current) |
| **Auth** | ❌ None |

### 1f. Non-Ad Valorem Assessments

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /api/PRC/GetPRCNonAdValorem` |
| **Query Params** | `PID`, `TaxYear` (0 = current) |
| **Auth** | ❌ None |

### 1g. Total Taxes

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /api/PRC/GetPRCTotalTaxes` |
| **Query Params** | `PID`, `TaxYear` (0 = current) |
| **Auth** | ❌ None |

### 1h. System Refresh Date

| Field | Value |
|-------|-------|
| **Endpoint** | `GET /api/Parcel/GetSystemRefreshDate` |
| **Query Params** | None |
| **Auth** | ❌ None |

### 1i. Content/Images API

| Field | Value |
|-------|-------|
| **Base** | `https://ocpaimages.ocpafl.org/api/` |
| **Endpoint** | `GET /api/Content/GetContentDynamicFile?contentFileID={id}` |
| **Notes** | Used for documents/PDFs. The `GetContentAlert` endpoint returned 404. |

### Parcel ID Format Note
- Display format: `35-20-27-6645-00-001`
- API format: `272035664500001` (remove dashes, reorder: section-township-range → reversed)
- Pattern: Display `SS-TT-RR-SSSS-SS-SSS` → API `RRTTSSSSSSSSSSS` (needs investigation for exact mapping)

---

## 2. Clerk of Courts (myeclerk.myorangeclerk.com) — ⚠️ NO PUBLIC API

| Field | Value |
|-------|-------|
| **Platform** | ASP.NET MVC (server-rendered) |
| **Search URL** | `https://myeclerk.myorangeclerk.com/Cases/Search` |
| **Method** | POST (form submission) |
| **Auth** | reCAPTCHA required for all anonymous searches |
| **API** | No XHR/JSON API discovered |

**Key Finding:** This is a traditional server-rendered application, NOT an SPA. All searches require Google reCAPTCHA validation. The search form POSTs to `/Cases/Search` and returns HTML.

**Internal AJAX endpoints found in site.js:**
- `POST /DocView/_showDoc` — View document (requires `docVersionId`, likely session-gated)
- `POST /CaseDetails/VORSubmit` — VOR document submission

**Case Number URL Pattern:**
- `https://myeclerk.myorangeclerk.com/Cases/Search?caseType=CV&caseTypeDesc=Civil%20Case%20Records`
- Case types: TR (Traffic), CV (Civil), CR (Criminal), FAM (Family), PR (Probate)

**Verdict:** Not automatable without reCAPTCHA bypass. Consider registered user login for API access.

---

## 3. 311 Portal (311onlinerequests.ocfl.net) — ⚠️ LEGACY, NO API

| Field | Value |
|-------|-------|
| **Platform** | ASP.NET WebForms (legacy custom system) |
| **URL** | `https://311onlinerequests.ocfl.net/portal/default.aspx` |
| **Auth** | Login required (guest or registered) |
| **Third-party** | None (NOT SeeClickFix, NOT Accela) |
| **API** | No public API discovered |

**Key Finding:** Orange County uses a completely custom, in-house 311 system. It's a WebForms application from ~2019 with guest login capability. No SPA, no XHR APIs detected.

**Alternative access points:**
- Chat: `https://ocachat.whoson.com/newchat/chat.aspx?domain=www.orangecountyfl.net` (WhoSON live chat)
- Mobile App: OCFL 311 (iOS/Android) — may use a different API backend worth investigating via app decompilation
- Phone: (407) 836-3111

---

## 4. Tax Collector (county-taxes.net) — ✅ ALGOLIA SEARCH API

**Platform:** Grant Street Group (county-taxes.net / "Orange PayHub")

### 4a. Property Tax Search (Algolia)

| Field | Value |
|-------|-------|
| **Endpoint** | `POST https://0LWZO52LS2-dsn.algolia.net/1/indexes/*/queries` |
| **Method** | POST |
| **Auth** | Public API key in URL params (no auth needed) |
| **Index Name** | `fl-orange.property_tax` |
| **Response** | JSON (Algolia format with hits array) |

**Required URL Params:**
- `x-algolia-api-key=c0745578b56854a1b90ed57b63fbf0ba`
- `x-algolia-application-id=0LWZO52LS2`

**Example Request:**
```bash
curl -X POST 'https://0LWZO52LS2-dsn.algolia.net/1/indexes/*/queries?x-algolia-api-key=c0745578b56854a1b90ed57b63fbf0ba&x-algolia-application-id=0LWZO52LS2' \
  -H 'Content-Type: application/json' \
  -d '{"requests":[{"indexName":"fl-orange.property_tax","params":"query=1321+Apopka+Airport&hitsPerPage=5"}]}'
```

**Example Response (truncated):**
```json
{
  "results": [{
    "hits": [{
      "display_name": "HELISERVICE LLC",
      "display_type": "property_tax",
      "child_groups": [{
        "children": [{
          "external_id": "35-20-27-0000-00049",
          "custom_parameters": {
            "roll_year": "2025",
            "external_type": "Account",
            "custom_payable_type": "accounts"
          }
        }]
      }],
      "custom_parameters": {
        "public_url": "/public/real_estate/parcels/35-20-27-0000-00049/bills?parcel=7ebb752e-d853-11ef-8626-cf6e57f2283b",
        "entities": [{
          "name": "HELISERVICE LLC",
          "address": "1321 APOPKA AIRPORT RD UNIT 161",
          "city": "APOPKA",
          "state": "FL",
          "zip": "32712-5976"
        }]
      }
    }]
  }]
}
```

### 4b. Tax Bill Detail (Grant Street MQ Gateway)

| Field | Value |
|-------|-------|
| **Endpoint** | `POST https://mq-gateway.grantstreet.com/v1/request/tax-cbs-public-site.request` |
| **Method** | POST |
| **Auth** | Session-based (requires browser session cookie) |
| **Notes** | Complex message-queue based API; not easily callable directly |

### 4c. Tax Bill Public URLs

Property tax bills are viewable at:
```
https://county-taxes.net/public/real_estate/parcels/{account-number}/bills?parcel={uuid}
```

### 4d. Business Tax Receipt Search

| Field | Value |
|-------|-------|
| **URL** | `https://county-taxes.net/fl-orange/business-tax` |
| **Notes** | Same Algolia infrastructure, likely index `fl-orange.business_tax` |

---

## Summary

| Site | API Available | Auth Required | Format | Ease of Use |
|------|:---:|:---:|:---:|:---:|
| OCPA (Property Appraiser) | ✅ Yes | ❌ No | JSON | ⭐⭐⭐⭐⭐ |
| Clerk of Courts | ❌ No (HTML + reCAPTCHA) | ✅ Yes | HTML | ⭐ |
| 311 Portal | ❌ No (legacy WebForms) | ✅ Yes (login) | HTML | ⭐ |
| Tax Collector (Algolia) | ✅ Yes | ❌ No (public key) | JSON | ⭐⭐⭐⭐ |
| Tax Collector (Detail) | ⚠️ Partial | ✅ Session | JSON | ⭐⭐ |

### Best Opportunities
1. **OCPA API** — Fully open, rich data, easy to integrate. Best target for property data.
2. **Tax Collector Algolia** — Public search key, standard Algolia API. Great for tax lookups.
3. **Clerk of Courts** — Would need registered user account + session management to automate.
4. **311 Portal** — Legacy system; mobile app reverse-engineering might yield better results.
