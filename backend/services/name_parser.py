"""Parse name lists from plain text, CSV, or XLSX."""
import csv
import io
import re

_PREPOSITIONS = frozenset({
    "de", "da", "do", "das", "dos",
    "e", "em", "na", "no", "nas", "nos",
    "por", "para", "com", "sem", "sob",
    "sobre", "entre", "até", "após",
    "ante", "perante", "segundo", "conforme",
    "a", "o", "as", "os",
})


def format_name(name: str) -> str:
    """Title-case each word, keeping prepositions lowercase (except first word)."""
    words = re.split(r"(\s+)", name.strip())
    result = []
    first_word = True
    for token in words:
        if re.match(r"\s+", token):
            result.append(token)
        else:
            lower = token.lower()
            if first_word or lower not in _PREPOSITIONS:
                result.append(token.capitalize())
            else:
                result.append(lower)
            first_word = False
    return "".join(result)


def parse_names_from_text(text: str) -> list[str]:
    """One name per line; strips blanks and formats casing."""
    names = []
    for line in text.splitlines():
        name = line.strip()
        if name:
            names.append(format_name(name))
    return names


def parse_names_from_file(
    file_bytes: bytes,
    ext: str,
    column_index: int = 0,
    has_header: bool = True,
) -> list[str]:
    if ext == ".csv":
        return _parse_csv(file_bytes, column_index, has_header)
    elif ext == ".xlsx":
        return _parse_xlsx(file_bytes, column_index, has_header)
    raise ValueError(f"Formato não suportado: {ext}")


def _parse_csv(file_bytes: bytes, column_index: int, has_header: bool) -> list[str]:
    text = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)

    if has_header and rows:
        rows = rows[1:]

    names = []
    for row in rows:
        if len(row) > column_index:
            name = row[column_index].strip()
            if name:
                names.append(format_name(name))
    return names


def _parse_xlsx(file_bytes: bytes, column_index: int, has_header: bool) -> list[str]:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if has_header and rows:
        rows = rows[1:]

    names = []
    for row in rows:
        if len(row) > column_index and row[column_index] is not None:
            name = str(row[column_index]).strip()
            if name:
                names.append(format_name(name))
    return names
