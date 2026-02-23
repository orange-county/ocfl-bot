"""
OCFL Forms — Download, inspect, and fill PDF forms for Orange County FL services.

Supported forms:
  homestead       — DR-501 Homestead Exemption Application
  building-permit — Orange County Building Permit Application
"""

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

FORMS_DIR = Path(__file__).parent
PDFS_DIR = FORMS_DIR / "pdfs"

# ── Form Registry ─────────────────────────────────────────────

FORM_REGISTRY = {
    "homestead": {
        "name": "DR-501 Homestead Exemption Application",
        "pdf": "dr501.pdf",
        "fields_json": "dr501_fields.json",
        "source_url": "https://floridarevenue.com/property/documents/dr501.pdf",
        "description": "Florida homestead exemption application — saves $750-$1,000+/yr on property taxes.",
    },
    "building-permit": {
        "name": "Orange County Building Permit Application",
        "pdf": "building_permit.pdf",
        "fields_json": "building_permit_fields.json",
        "source_url": "https://www.orangecountyfl.net/Portals/0/resource%20library/permits%20-%20licenses/Building%20Permit-CERT.pdf",
        "description": "Building permit application for Orange County Division of Building Safety.",
    },
}


def _load_field_map(form_id):
    """Load field mapping JSON for a form."""
    reg = FORM_REGISTRY.get(form_id)
    if not reg:
        return None
    json_path = FORMS_DIR / reg["fields_json"]
    if not json_path.exists():
        return None
    return json.loads(json_path.read_text())


def _get_pdf_path(form_id):
    reg = FORM_REGISTRY.get(form_id)
    if not reg:
        return None
    return PDFS_DIR / reg["pdf"]


def _open_file(path):
    """Open a file with the default system application."""
    if platform.system() == "Darwin":
        subprocess.run(["open", str(path)])
    elif platform.system() == "Linux":
        subprocess.run(["xdg-open", str(path)])
    elif platform.system() == "Windows":
        os.startfile(str(path))


# ── CLI Commands ───────────────────────────────────────────────

@click.group()
def forms():
    """📝 Download and fill PDF forms for Orange County FL services."""
    pass


@forms.command("list")
@click.option("--json", "as_json", is_flag=True, hidden=True, help="Output as JSON")
@click.pass_context
def forms_list(ctx, as_json):
    """List available fillable PDF forms."""
    json_out = as_json or "--json" in sys.argv
    if json_out:
        click.echo(json.dumps({k: {"name": v["name"], "description": v["description"], "source": v["source_url"]} for k, v in FORM_REGISTRY.items()}, indent=2))
        return

    table = Table(title="📝 Available PDF Forms", box=box.ROUNDED)
    table.add_column("Form ID", style="cyan bold")
    table.add_column("Name")
    table.add_column("Description", max_width=50)
    table.add_column("PDF", style="dim")
    for fid, info in FORM_REGISTRY.items():
        pdf_path = PDFS_DIR / info["pdf"]
        status = "✅" if pdf_path.exists() else "❌ missing"
        table.add_row(fid, info["name"], info["description"], status)
    console.print(table)
    console.print("\n[dim]Usage: ocfl forms fields <form-id> | ocfl forms fill <form-id> [options][/dim]")


@forms.command("fields")
@click.argument("form_id")
@click.option("--json", "as_json", is_flag=True, hidden=True, help="Output as JSON")
@click.pass_context
def forms_fields(ctx, form_id, as_json):
    """Show fillable fields for a form.

    \b
    Examples:
      ocfl forms fields homestead
      ocfl forms fields building-permit
    """
    if form_id not in FORM_REGISTRY:
        console.print(f"[red]Unknown form '{form_id}'. Available: {', '.join(FORM_REGISTRY.keys())}[/red]")
        sys.exit(1)

    data = _load_field_map(form_id)
    if not data:
        console.print(f"[red]No field mapping found for '{form_id}'.[/red]")
        sys.exit(1)

    json_out = as_json or "--json" in sys.argv
    if json_out:
        click.echo(json.dumps(data, indent=2))
        return

    table = Table(title=f"📝 {data.get('name', form_id)} — Fillable Fields", box=box.ROUNDED)
    table.add_column("CLI Flag", style="cyan bold")
    table.add_column("PDF Field Name", style="dim")
    for flag, pdf_field in data.get("field_map", {}).items():
        if isinstance(pdf_field, list):
            table.add_row(flag, " + ".join(pdf_field))
        else:
            table.add_row(flag, pdf_field)
    console.print(table)
    console.print(f"\n[dim]Fill: ocfl forms fill {form_id} {list(data['field_map'].keys())[0]} \"value\" ...[/dim]")


@forms.command("fill")
@click.argument("form_id")
@click.option("-o", "--output", help="Output path (default: ~/Downloads/<form>_filled.pdf)")
@click.option("--no-open", is_flag=True, help="Don't open the filled PDF")
# Homestead fields
@click.option("--name", help="Applicant name")
@click.option("--co-applicant", help="Co-applicant/spouse name")
@click.option("--address", help="Homestead / property address")
@click.option("--mailing-address", help="Mailing address")
@click.option("--parcel", help="Parcel ID or legal description")
@click.option("--phone", help="Applicant phone number")
@click.option("--co-phone", help="Co-applicant phone number")
@click.option("--ssn", help="Applicant SSN (last 4 or full)")
@click.option("--co-ssn", help="Co-applicant SSN")
@click.option("--dob", help="Applicant date of birth")
@click.option("--co-dob", help="Co-applicant date of birth")
@click.option("--deed-type", help="Type of deed")
@click.option("--book", help="Deed book number")
@click.option("--page", "page_num", help="Deed page number")
@click.option("--recorded-date", help="Deed recorded date")
@click.option("--instrument", help="Instrument number")
@click.option("--trust-name", help="Trust name on deed")
@click.option("--tax-year", help="Tax year")
@click.option("--date-acquired", help="Date property was acquired")
@click.option("--date-established", help="Date homestead was established")
@click.option("--previous-homestead", help="Previous homestead address")
@click.option("--relationship", help="Co-applicant relationship to applicant")
# Building permit fields
@click.option("--owner-name", help="Property owner / title holder name")
@click.option("--owner-address", help="Owner address")
@click.option("--owner-city", help="Owner city")
@click.option("--owner-state", help="Owner state")
@click.option("--owner-zip", help="Owner zip code")
@click.option("--owner-phone", help="Owner phone (10 digits)")
@click.option("--subdivision", help="Subdivision name")
@click.option("--section", help="Section")
@click.option("--township", help="Township")
@click.option("--range", "range_val", help="Range")
@click.option("--block", help="Block")
@click.option("--lot", help="Lot")
@click.option("--tenant", help="Tenant name")
@click.option("--business", help="Business name")
@click.option("--architect", help="Architect name")
@click.option("--architect-license", help="Architect license number")
@click.option("--engineer", help="Civil engineer name")
@click.option("--engineer-license", help="Engineer license number")
@click.option("--description", help="Nature of improvements (line 1)")
@click.option("--description2", help="Nature of improvements (line 2)")
@click.option("--valuation", help="Total job valuation")
@click.option("--contractor", help="Contractor / license holder name")
@click.option("--contractor-license", help="Contractor license number")
@click.option("--contact-email", help="Contact email")
@click.option("--job-name", help="Job name")
@click.pass_context
def forms_fill(ctx, form_id, output, no_open, **kwargs):
    """Fill a PDF form and save it.

    \b
    Examples:
      ocfl forms fill homestead --name "Jane Doe" --address "123 Main St, Orlando, FL 32801" --parcel "01-23-45-6789-00-100"
      ocfl forms fill building-permit --owner-name "John Smith" --description "Kitchen remodel" -o ~/Desktop/permit.pdf
    """
    if form_id not in FORM_REGISTRY:
        console.print(f"[red]Unknown form '{form_id}'. Available: {', '.join(FORM_REGISTRY.keys())}[/red]")
        sys.exit(1)

    pdf_path = _get_pdf_path(form_id)
    if not pdf_path or not pdf_path.exists():
        console.print(f"[red]PDF not found: {pdf_path}[/red]")
        console.print(f"[dim]Source: {FORM_REGISTRY[form_id]['source_url']}[/dim]")
        sys.exit(1)

    data = _load_field_map(form_id)
    if not data:
        console.print(f"[red]No field mapping for '{form_id}'.[/red]")
        sys.exit(1)

    field_map = data.get("field_map", {})

    # Build the fill dict from provided options
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)

    filled_count = 0
    fill_data = {}

    # Normalize kwargs keys: click converts --foo-bar to foo_bar
    for flag, pdf_field in field_map.items():
        # Convert flag like --date-acquired to date_acquired
        param_name = flag.lstrip("-").replace("-", "_")
        # Special case for --range -> range_val, --page -> page_num
        if param_name == "range":
            param_name = "range_val"
        elif param_name == "page":
            param_name = "page_num"

        value = kwargs.get(param_name)
        if value is None:
            continue

        if isinstance(pdf_field, list):
            # Split phone into parts
            digits = "".join(c for c in value if c.isdigit())
            if len(digits) == 10 and len(pdf_field) == 3:
                fill_data[pdf_field[0]] = digits[:3]
                fill_data[pdf_field[1]] = digits[3:6]
                fill_data[pdf_field[2]] = digits[6:]
                filled_count += 1
            else:
                fill_data[pdf_field[0]] = value
                filled_count += 1
        else:
            fill_data[pdf_field] = value
            filled_count += 1

    if not fill_data:
        console.print("[yellow]No fields provided to fill. Use --help to see available flags.[/yellow]")
        console.print(f"[dim]Try: ocfl forms fields {form_id}[/dim]")
        sys.exit(1)

    # Apply fields to all pages
    for page_num in range(len(writer.pages)):
        writer.update_page_form_field_values(writer.pages[page_num], fill_data)

    # Determine output path
    if not output:
        downloads = Path.home() / "Downloads"
        downloads.mkdir(exist_ok=True)
        output = str(downloads / f"{form_id.replace('-', '_')}_filled.pdf")

    output_path = Path(output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "wb") as f:
        writer.write(f)

    console.print(f"[bold green]✅ Filled {filled_count} field(s) → {output_path}[/bold green]")
    console.print(f"[dim]Form: {FORM_REGISTRY[form_id]['name']}[/dim]")

    # Show what was filled
    for flag, pdf_field in field_map.items():
        param_name = flag.lstrip("-").replace("-", "_")
        if param_name == "range":
            param_name = "range_val"
        elif param_name == "page":
            param_name = "page_num"
        value = kwargs.get(param_name)
        if value:
            console.print(f"  {flag}: {value}")

    if not no_open:
        _open_file(output_path)
        console.print(f"\n[dim]📄 Opened in default PDF viewer[/dim]")
