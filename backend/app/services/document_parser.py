import csv
import html
import io
import json
import re
from pathlib import Path
from xml.etree import ElementTree


class UnsupportedDocumentFormat(ValueError):
    pass


class DocumentParser:
    supported_extensions = {".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".html", ".htm"}

    def parse(self, file_name: str, content: bytes) -> str:
        extension = Path(file_name).suffix.lower()
        if extension not in self.supported_extensions:
            raise UnsupportedDocumentFormat(
                f"Unsupported format {extension or 'unknown'}. "
                f"Supported formats: {', '.join(sorted(self.supported_extensions))}"
            )

        text = self._decode(content)
        if extension in {".txt", ".md"}:
            return text
        if extension in {".csv", ".tsv"}:
            return self._parse_delimited(text, "\t" if extension == ".tsv" else ",")
        if extension == ".json":
            return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
        if extension == ".xml":
            root = ElementTree.fromstring(text)
            return "\n".join(value.strip() for value in root.itertext() if value.strip())
        return self._parse_html(text)

    def _decode(self, content: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-8", "cp949"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("The file text encoding is not supported")

    def _parse_delimited(self, text: str, delimiter: str) -> str:
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        return "\n".join(" | ".join(cell.strip() for cell in row) for row in reader if row)

    def _parse_html(self, text: str) -> str:
        without_scripts = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.I | re.S)
        without_tags = re.sub(r"<[^>]+>", "\n", without_scripts)
        return "\n".join(
            line.strip() for line in html.unescape(without_tags).splitlines() if line.strip()
        )


document_parser = DocumentParser()
