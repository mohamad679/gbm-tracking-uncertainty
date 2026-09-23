import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
AUDIT = DOCS / "documentation-audit.json"


class DocumentationLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        cls.entries = []
        cls.entries.extend(
            {"source": source, "action": "KEEP", "destination": source}
            for source in cls.audit["keep"]
        )
        cls.entries.extend(
            {"source": source, "action": "MOVE_TO_EVIDENCE", "destination": destination}
            for source, destination in cls.audit["move_to_evidence"].items()
        )
        cls.entries.extend(
            {"source": source, "action": "ARCHIVE", "destination": destination}
            for source, destination in cls.audit["archive"].items()
        )
        cls.entries.extend(
            {"source": source, "action": "DELETE", "destination": None}
            for source in cls.audit["delete"]
        )

    def test_audit_is_complete_and_counts_match(self):
        self.assertEqual(self.audit["original_file_count"], 100)
        self.assertEqual(len(self.entries), 100)
        counts = {key: 0 for key in self.audit["summary"]}
        for entry in self.entries:
            counts[entry["action"]] += 1
        self.assertEqual(counts, self.audit["summary"])

    def test_every_retained_destination_exists(self):
        missing = []
        for entry in self.entries:
            if entry["action"] == "DELETE":
                continue
            destination = DOCS / entry["destination"]
            if not destination.exists():
                missing.append(str(destination.relative_to(ROOT)))
        self.assertEqual(missing, [], "Missing audited destinations: " + ", ".join(missing))

    def test_no_moved_or_archived_source_path_remains_at_docs_root(self):
        leftovers = []
        for entry in self.entries:
            if entry["action"] == "KEEP":
                continue
            old = DOCS / entry["source"]
            if old.exists():
                leftovers.append(str(old.relative_to(ROOT)))
        self.assertEqual(leftovers, [], "Old docs paths still exist: " + ", ".join(leftovers))

    def test_active_repository_has_no_stale_docs_references(self):
        relocated = [e for e in self.entries if e["action"] in {"MOVE_TO_EVIDENCE", "ARCHIVE"}]
        stale = []

        active_files = [ROOT / "README.md", ROOT / "CHANGELOG.md", ROOT / "CONTRIBUTING.md"]
        active_files += sorted((ROOT / ".github" / "workflows").glob("*.yml"))
        active_files += sorted((ROOT / "src").rglob("*.py"))
        active_files += [
            p
            for p in sorted(DOCS.glob("*.md"))
            if p.name != "README.md"
        ]

        for path in active_files:
            text = path.read_text(encoding="utf-8")
            for entry in relocated:
                source = entry["source"]
                if path.parent == DOCS:
                    hit = source in text
                else:
                    hit = f"docs/{source}" in text
                if hit:
                    stale.append(f"{path.relative_to(ROOT)} -> {source}")

        self.assertEqual(
            stale,
            [],
            "Stale documentation references must use audited destinations:\n" + "\n".join(stale),
        )

    def test_tests_do_not_open_removed_top_level_docs_paths(self):
        relocated_sources = [
            e["source"] for e in self.entries if e["action"] in {"MOVE_TO_EVIDENCE", "ARCHIVE"}
        ]
        stale = []
        for path in sorted((ROOT / "tests").rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for source in relocated_sources:
                quoted_path = f"docs/{source}"
                direct_open_patterns = (
                    f'Path("{quoted_path}")',
                    f"Path('{quoted_path}')",
                )
                if any(pattern in text for pattern in direct_open_patterns):
                    stale.append(f"{path.relative_to(ROOT)} -> {source}")
        self.assertEqual(
            stale,
            [],
            "Tests still open removed top-level docs paths:\n" + "\n".join(stale),
        )


if __name__ == "__main__":
    unittest.main()
