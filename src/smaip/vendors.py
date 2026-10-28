"""On-disk vendor pages shipped with the scaffold.

These are original synthetic briefs. They are not samples from AgentDojo,
InjecAgent, or BIPIA.
"""

import json
from pathlib import Path

from smaip.errors import SandboxError


def default_fixture_root() -> Path:
    return Path(__file__).resolve().parent / "fixture_data" / "vendors"


class VendorLibrary:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or default_fixture_root()).resolve()
        manifest = json.loads((self.root / "vendors.json").read_text(encoding="utf-8"))
        self.vendors = {item["id"]: item for item in manifest["vendors"]}

    def ids(self) -> list[str]:
        return sorted(self.vendors)

    def is_poisoned(self, vendor: str) -> bool:
        self._require(vendor)
        return bool(self.vendors[vendor]["poisoned"])

    def list_pages(self, vendor: str) -> list[str]:
        self._require(vendor)
        folder = self.root / vendor
        return sorted(path.name for path in folder.glob("*.md"))

    def read(self, vendor: str, page: str) -> str:
        self._require(vendor)
        if not isinstance(page, str) or Path(page).name != page or not page.endswith(".md"):
            raise SandboxError("page rejected")
        folder = (self.root / vendor).resolve()
        path = (folder / page).resolve()
        if not path.is_relative_to(folder):
            raise SandboxError("page rejected")
        if not path.is_file():
            raise SandboxError("page not found")
        return path.read_text(encoding="utf-8")

    def _require(self, vendor: str) -> None:
        if vendor not in self.vendors:
            raise SandboxError("vendor rejected")
