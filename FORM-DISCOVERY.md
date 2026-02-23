# OCFL & Florida Government Form Discovery

*Last updated: 2026-02-22*

---

## 1. OCFL 311 Online Request Portal

### URL
`https://311onlinerequests.ocfl.net/portal/default.aspx`

### Technology
- ASP.NET WebForms (postback-based)
- reCAPTCHA v3 (invisible) - site key: `6LcrgOQUAAAAADU5t5ZqvEnVtfLPtuexQhpkDlmq`
- jQuery 1.9.1 + jQuery UI 1.10.3

### Login Page (default.aspx)
| Field | Name | Type | Required |
|-------|------|------|----------|
| Email Address | `ctl00$cphMain$txtClientID` | text | No (for guest) |
| Password | `ctl00$cphMain$txtPassword` | password | No (for guest) |
| reCAPTCHA | `g-recaptcha-response` | hidden | Yes (auto-filled by reCAPTCHA v3) |
| ViewState | `__VIEWSTATE` | hidden | Yes (ASP.NET) |
| EventValidation | `__EVENTVALIDATION` | hidden | Yes (ASP.NET) |

### Buttons
| Button | Name | Action |
|--------|------|--------|
| Guest Log In | `ctl00$cphMain$btnGuestLogin` | submit - no credentials needed |
| Registered Member Log In | `ctl00$cphMain$Button1` | submit - requires email + password |
| Register | postback `ctl00$cphMain$hlRegister` | Creates new account |
| Forgot Password | postback `ctl00$cphMain$lbForgotPassword` | Password reset |

### Form Action
POST to `default.aspx` (same page, ASP.NET postback)

### Guest Access
- ✅ Guest login available (no account required)
- ⚠️ reCAPTCHA v3 blocks headless/automated browsers
- After guest login, redirects to `servicetypelist.aspx` (category selection)
- Internal pages redirect back to login if no session

### Known Service Request Categories
From Apple App Store description and mobile site:
- Animals (stray animals, animal complaints)
- Traffic Signs (damaged, missing signs)
- Potholes (road surface issues)
- Graffiti (graffiti removal)
- Sidewalk Repair
- "Many other common issues"

### Expected Workflow (based on ASP.NET portal pattern)
1. Login (guest or registered) → `default.aspx`
2. Select service category → `servicetypelist.aspx`
3. Fill request form (location, description, contact info) → likely `servicerequest.aspx`
4. Submit → confirmation with tracking number
5. Status lookup (for registered users)

### Request Status Lookup
- Registered users can view status of their reports
- Mobile app also supports status tracking
- No public status lookup by confirmation number found (registration required)

### API Endpoints
- No REST API discovered; portal uses ASP.NET WebForms postbacks
- Form action: POST to same page with `__EVENTTARGET`, `__EVENTARGUMENT`, `__VIEWSTATE`
- Search endpoint: `http://search.ocfl.net/search?access=p&client=OCFL_frontend&output=xml_no_dtd&proxystylesheet=OCFL_frontend&sort=date%3AD%3AL%3Ad1&oe=UTF-8&ie=UTF-8&ud=1&exclude_apps=1&site=default_collection&q=<query>`

---

## 2. OCFL 311 Help & Info Page

### URL
`https://orangecountyfl.net/Home/311HelpInfo.aspx`

### Entry Points
| Channel | Details |
|---------|---------|
| Phone | Dial 311 or 407-836-3111 |
| Online Portal | https://311onlinerequests.ocfl.net/portal/default.aspx |
| iPhone App | http://itunes.apple.com/us/app/ocfl-311/id533186440?ls=1&mt=8 |
| Android App | https://play.google.com/store/apps/details?id=net.ocfl.android.ocfl311 |
| Speaker Scheduling | Contact 311 |

### Mobile App Details
- **App Name**: OCFL 311
- **iOS Bundle**: `id533186440`
- **Android Package**: `net.ocfl.android.ocfl311`
- **Size**: 5.5 MB (iOS)
- **Min iOS**: 12.4
- **Languages**: English, Spanish
- **Rating**: 2.7/5 (16 ratings)
- **Data Collection**: None
- **Copyright**: © 2016-2024 Orange County, FL
- No public API endpoints found (app likely uses same portal backend or proprietary API)

---

## 3. OCFL Live Chat (WhosOn)

### URL
`https://ocachat.whoson.com/`

### Details
- Platform: WhosOn (by Parker Software)
- Minimal page - JavaScript-heavy chat widget
- No public API endpoints accessible
- No forms to document (chat interface only)

---

## 4. FL Voter Registration Lookup

### URL
`https://registration.elections.myflorida.com/CheckVoterStatus`
(Redirects to: `https://registration.dos.fl.gov/CheckVoterStatus`)

### Protection
- ⚠️ Cloudflare managed challenge (blocks curl and headless browsers)
- JavaScript + cookies required

### Form Fields (from rendered page)
| Field | Type | Required |
|-------|------|----------|
| First Name | text | Yes (*) |
| Last Name | text | Yes (*) |
| Birth Date (MM/DD/YYYY) | text/date | Yes (*) |
| Agreement checkbox | checkbox | Yes (*) |

### Notes
- No CAPTCHA visible (Cloudflare challenge serves as bot protection)
- No login/account required
- Read-only lookup, no submission
- Legal notice: unlawful to alter another person's voter registration
- API endpoints not accessible due to Cloudflare protection

---

## 5. DBPR Licensee/Restaurant Inspection Search

### URL
`https://www.myfloridalicense.com/wl11.asp`

### Technology
- Classic ASP (`.asp`)
- No CAPTCHA
- No login required
- Multi-step form wizard (mode parameter controls flow)

### URL Parameters
| Param | Description |
|-------|-------------|
| `mode` | 0=search type selection, 1=search form, 2=results |
| `SID` | Session ID (empty for new sessions) |
| `brd` | Board filter (e.g., `H` = Hotels & Restaurants only) |
| `typ` | Type (`N` = new search) |
| `search` | Search type for mode=1 (`Name`, `LicNbr`, `City`, `LicTyp`) |

### Search Type Selection (mode=0)
Radio buttons with `name="SearchType"`:
| Value | Label | Notes |
|-------|-------|-------|
| `Name` | Search by Name | Default selected |
| `LicNbr` | Search by License Number | |
| `City` | Search by City or County | Not available when `brd=H` |
| `LicTyp` | Search by License Type | Not available when `brd=H` |

### Search by Name Form (mode=1, search=Name)
**Action**: POST to `wl11.asp?mode=2&search=&SID=&brd=&typ=N`

| Field | Name | Type | Required | Max Length |
|-------|------|------|----------|------------|
| Last Name | `LastName` | text | Conditional* | 50 |
| First Name | `FirstName` | text | Conditional* | 50 |
| Middle Name | `MiddleName` | text | No | 50 |
| Organization Name | `OrgName` | text | Conditional* | 50 |
| Exact prefix match | `SearchPartName` | checkbox | No | value="Part" |
| Fuzzy/alternate spellings | `SearchFuzzy` | checkbox | No | value="Y" |
| Board/Profession | `Board` | select | No | see board list |
| License Type | `LicenseType` | select | No | depends on Board |
| Specialty/Qualification | `SpecQual` | select | No | depends on Board |
| City | `City` | text | No | 50 |
| County | `County` | select | No | see county list |
| State | `State` | select | No | US states |
| Include Historic | `SearchHistoric` | checkbox | No | value="Yes" |
| Results Per Page | `RecsPerPage` | select | No | 10/20/30/40/50 |

*Validation: Either LastName OR OrgName required. If LastName provided, FirstName alone is insufficient.

### Search by City or County Form (mode=1, search=City)
**Action**: POST to `wl11.asp?mode=2&search=&SID=&brd=&typ=N`

| Field | Name | Type | Required |
|-------|------|------|----------|
| Board/Profession | `Board` | select | Yes |
| License Type | `LicenseType` | select | No |
| City | `City` | text | Conditional** |
| County | `County` | select | Conditional** |
| State | `State` | select | No |
| Include Historic | `SearchHistoric` | checkbox | No |
| Results Per Page | `RecsPerPage` | select | No |

**Validation: Either City or County required (unless State = "NA")

### Board/Profession Options (select name="Board")
| Value | Label |
|-------|-------|
| 400 | Alcoholic Beverages & Tobacco |
| 02 | Architecture & Interior Design |
| 59 | Asbestos Contractors and Consultants |
| 60 | Athlete Agents |
| 48 | Auctioneers |
| 03 | Barbers |
| 600 | Boxing, Kick Boxing & Mixed Martial Arts |
| 50 | Building Code Administrators and Inspectors |
| 830 | CTMH Other Entities |
| 01 | Certified Public Accounting |
| 38 | Community Association Managers and Firms |
| 800 | Condominiums, Cooperatives, Timeshares, & Multi-Site Timeshares |
| 06 | Construction Industry |
| 05 | Cosmetology |
| 33 | Drugs, Devices and Cosmetics |
| 08 | Electrical Contractors |
| 210 | Elevator Safety |
| 63 | Employee Leasing Companies |
| 09 | Engineers |
| 75 | Farm Labor |
| 53 | Geologists |
| 23 | Harbor Pilots |
| 04 | Home Inspectors |
| 840 | Homeowners' Associations |
| **200** | **Hotels and Restaurants** ← restaurant inspections |
| 74 | Labor Organizations |
| 820 | Land Sales |
| 13 | Landscape Architecture |
| 810 | Mobile Homes |
| 07 | Mold-Related Services |
| 100 | Pari-Mutuel Wagering |
| 101 | Pari-Mutuel Wagering - Slots |
| 25 | Real Estate |
| 64 | Real Estate Appraisers |
| 49 | Talent Agencies |
| 26 | Veterinary Medicine |
| 85 | Yacht and Ships |

### County Options (Orange County = value `58`)
All 67 FL counties plus Foreign (80), Out of State (79), Unknown (78).

### Hidden Fields (all search modes)
All forms carry these hidden fields for state management:
`hSID`, `hSearchType`, `hLastName`, `hFirstName`, `hMiddleName`, `hOrgName`, `hSearchOpt`, `hSearchOpt2`, `hSearchAltName`, `hSearchPartName`, `hSearchFuzzy`, `hDivision`, `hBoard`, `hLicenseType`, `hSpecQual`, `hAddrType`, `hCity`, `hCounty`, `hState`, `hLicNbr`, `hAction`, `hCurrPage`, `hTotalPages`, `hTotalRecords`, `hPageAction`, `hDDChange`, `hBoardType`, `hLicTyp`, `hSearchHistoric`, `hRecsPerPage`

### Restaurant Inspection Search Recipe
To search Orange County restaurants:
```
POST https://www.myfloridalicense.com/wl11.asp?mode=2&search=City&SID=&brd=&typ=N
Form data:
  Board=200
  County=58
  State=FL
  RecsPerPage=50
  (plus hidden fields with empty values)
```

### Results Format
Table with columns: License Type, Name, Name Type, License Number/Rank, Status/Expires
Click name for details including inspection reports (for Hotels & Restaurants board).

### Food & Lodging Inspections Direct Entry
`https://www.myfloridalicense.com/wl11.asp?mode=0&SID=&brd=H`
- Pre-filtered to Hotels & Restaurants board
- Only offers Search by Name and Search by License Number
- Includes "Terms of Use" agreement notice

---

## 6. OCFL Public Records Requests

### URL
`https://www.orangecountyfl.net/OpenGovernment/PublicRecords.aspx`

### Overview
No single online form. Public records are routed to different agencies:

| Agency | URL/Contact | Record Types |
|--------|-------------|--------------|
| City of Orlando | orlando.gov/Our-Government/Records-and-Documents/Request-a-Public-Record | Fire dept, permits, personnel, police |
| GOAA (Airport) | goaa.mycusthelp.com | Business opportunities, FTZ, lobbyist info |
| OC Comptroller | occompt.com | Deeds, mortgages, liens, marriage licenses, BCC minutes |
| OC Sheriff | ocso-fl.nextrequest.com | Incident reports, arrests, body cam, 911 calls |
| Orange County Govt | PublicRecordRequest@ocfl.net | General county records |

### Payment for Records
`https://www.orangecountyfl.net/PaymentCenter/PublicRecordsRequestPayment.aspx`
- Requires public records request number to proceed

### Contact
Orange County Government Office of Professional Standards Public Records Unit
450 East South Street, Suite 360, Orlando, FL 32801
Monday – Friday (excluding county holidays)

---

## 7. OC Sheriff Public Records (NextRequest)

### URL
`https://ocso-fl.nextrequest.com/`

### Platform
NextRequest (SaaS public records request platform)
- Account creation available but not required for browsing
- Online submission likely requires account
- Searchable database of past requests

---

## Summary: Automation Feasibility

| Service | Automatable? | Blockers |
|---------|-------------|----------|
| OCFL 311 Portal | ⚠️ Partial | reCAPTCHA v3 blocks headless browsers; ASP.NET ViewState |
| FL Voter Lookup | ❌ No | Cloudflare managed challenge |
| DBPR Search | ✅ Yes | No CAPTCHA, simple POST forms |
| OCFL Public Records | ❌ No | No unified form; email-based |
| OCSO Records (NextRequest) | ⚠️ Partial | Likely requires account |
| OCFL Live Chat | ❌ No | Proprietary WhosOn widget |
| OCFL 311 Mobile App | ❓ Unknown | Native app, API not discovered |

### Most Promising for Automation
**DBPR Licensee/Inspection Search** - Simple classic ASP forms, no CAPTCHA, no login, well-structured POST parameters. Can be fully automated with curl/fetch.
