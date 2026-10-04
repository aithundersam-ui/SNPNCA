"""CSV bulk import of members.

Rules (from the agreed defaults):
- Columns: full_name,email, optional language, optional role.
- role is honoured only when the importer is the Master Admin; otherwise it is ignored with a warning.
- A row whose email already has an account is skipped (never overwritten).
- Members not present in the file are left untouched.
"""

import csv
import io
from dataclasses import dataclass, field

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils.translation import gettext as _

from .models import Language, Role, User

TEMPLATE_CSV = "full_name,email,language,role\nAmina Benali,amina.benali@example.com,fr,user\nKarim Haddad,karim.haddad@example.com,en,\n"


@dataclass
class Row:
    line: int
    full_name: str
    email: str
    language: str
    role: str
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    skip: bool = False

    @property
    def ok(self):
        return not self.errors and not self.skip

    def as_dict(self):
        return {"line": self.line, "full_name": self.full_name, "email": self.email, "language": self.language, "role": self.role}


class CsvFormatError(Exception):
    pass


def decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvFormatError(_("The file is not UTF-8 encoded. In Excel, use “Save as → CSV UTF-8”.")) from exc


def parse(text: str, importer) -> list[Row]:
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = [h.strip().lower() for h in (reader.fieldnames or [])]
    if "full_name" not in headers or "email" not in headers:
        raise CsvFormatError(_("The first line must contain the columns full_name and email."))
    reader.fieldnames = headers

    existing = set(User.objects.values_list("email", flat=True))
    seen = set()
    rows = []
    for i, raw in enumerate(reader, start=2):
        if len(rows) >= settings.MAX_CSV_ROWS:
            raise CsvFormatError(_("The file has more than %(max)s rows.") % {"max": settings.MAX_CSV_ROWS})
        values = {k: (v or "").strip() for k, v in raw.items() if k}
        if not any(values.values()):
            continue
        row = Row(
            line=i,
            full_name=values.get("full_name", ""),
            email=values.get("email", "").lower(),
            language=values.get("language", "").lower() or Language.FR,
            role=values.get("role", "").lower() or Role.USER,
        )
        if not row.full_name:
            row.errors.append(_("Full name is missing."))
        elif len(row.full_name) > 150:
            row.errors.append(_("Full name is too long."))
        try:
            validate_email(row.email)
        except ValidationError:
            row.errors.append(_("Invalid email address."))
        if row.language not in Language.values:
            row.errors.append(_("Language must be fr or en."))
        if row.role not in Role.values:
            row.errors.append(_("Role must be user, admin or master."))
        elif row.role != Role.USER and not importer.is_master:
            row.warnings.append(_("Role ignored: only the Master Admin can import admins."))
            row.role = Role.USER
        if row.email in seen:
            row.errors.append(_("This email appears more than once in the file."))
        elif row.email in existing:
            row.skip = True
            row.warnings.append(_("An account with this email already exists; the row will be skipped."))
        seen.add(row.email)
        rows.append(row)
    return rows


@transaction.atomic
def apply(rows: list[dict], importer) -> list[User]:
    """Create users from previously validated rows. Re-checks everything server-side."""
    created = []
    for data in rows:
        email = data["email"].lower()
        if User.objects.filter(email=email).exists():
            continue
        role = data["role"] if importer.is_master and data["role"] in Role.values else Role.USER
        language = data["language"] if data["language"] in Language.values else Language.FR
        created.append(User.objects.create_user(email=email, full_name=data["full_name"][:150], role=role, preferred_language=language))
    return created
