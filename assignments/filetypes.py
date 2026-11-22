"""LSM-100: file types an instructor can allow per assignment."""
import os

# key -> (label, extensions). Only safe, non-executable formats are offered.
FILE_TYPES = {
    "pdf":    ("PDF", (".pdf",)),
    "word":   ("Word", (".doc", ".docx")),
    "text":   ("Plain text / Markdown", (".txt", ".md")),
    "zip":    ("ZIP archive", (".zip",)),
    "images": ("Images", (".png", ".jpg", ".jpeg", ".gif", ".webp")),
    "slides": ("PowerPoint", (".ppt", ".pptx")),
    "sheets": ("Excel / CSV", (".xls", ".xlsx", ".csv")),
    "code":   ("Source code", (".py", ".java", ".c", ".cpp", ".h", ".cs",
                               ".html", ".css", ".sql", ".ipynb")),
}

DEFAULT_FILE_TYPES = ["pdf", "word", "text", "zip", "images"]

# never accepted, even if a stored setting somehow includes them
BLOCKED_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".com", ".msi", ".msp", ".scr", ".pif", ".cpl",
    ".ps1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh", ".hta", ".jar",
    ".lnk", ".reg", ".dll", ".sh", ".app", ".dmg", ".apk",
}

CHOICES = [(key, f"{label} ({', '.join(exts)})") for key, (label, exts) in FILE_TYPES.items()]


def default_file_types():
    return list(DEFAULT_FILE_TYPES)  # callable default, so rows don't share a list


def extensions_for(keys):
    exts = []
    for key in keys or []:
        exts.extend(FILE_TYPES.get(key, ("", ()))[1])
    return [e for e in exts if e not in BLOCKED_EXTENSIONS]


def extension_of(filename):
    return os.path.splitext(filename or "")[1].lower()  # "a.pdf.exe" -> ".exe"
