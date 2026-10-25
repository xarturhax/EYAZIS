import csv
import json
import os
from typing import Optional


class Dictionary:
    """
    Stores English lexemes and their wordforms with frequency and morphology notes.

    Internal structure:
    {
        "run": {
            "wordforms": {
                "run":     {"frequency": 5, "morphology": ""},
                "runs":    {"frequency": 2, "morphology": "3sg present"},
                "ran":     {"frequency": 1, "morphology": "past tense"},
                "running": {"frequency": 3, "morphology": "present participle"}
            }
        }
    }
    """

    def __init__(self):
        self._data: dict = {}

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build_from_analysis(self, analysis: dict) -> None:
        """
        Populate/extend dictionary from lexical_analyzer.analyze() result.
        analysis: {lemma: {wordform: frequency}}
        """
        for lemma, wordforms in analysis.items():
            if lemma not in self._data:
                self._data[lemma] = {"wordforms": {}}
            for wf, freq in wordforms.items():
                if wf in self._data[lemma]["wordforms"]:
                    self._data[lemma]["wordforms"][wf]["frequency"] += freq
                else:
                    self._data[lemma]["wordforms"][wf] = {
                        "frequency": freq,
                        "morphology": "",
                    }

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add_entry(
        self,
        lemma: str,
        wordform: str,
        frequency: int = 1,
        morphology: str = "",
    ) -> None:
        lemma = lemma.strip().lower()
        wordform = wordform.strip().lower()
        if lemma not in self._data:
            self._data[lemma] = {"wordforms": {}}
        self._data[lemma]["wordforms"][wordform] = {
            "frequency": frequency,
            "morphology": morphology,
        }

    def update_morphology(self, lemma: str, wordform: str, morphology: str) -> bool:
        lemma = lemma.strip().lower()
        wordform = wordform.strip().lower()
        try:
            self._data[lemma]["wordforms"][wordform]["morphology"] = morphology
            return True
        except KeyError:
            return False

    def update_frequency(self, lemma: str, wordform: str, frequency: int) -> bool:
        lemma = lemma.strip().lower()
        wordform = wordform.strip().lower()
        try:
            self._data[lemma]["wordforms"][wordform]["frequency"] = frequency
            return True
        except KeyError:
            return False

    def delete_wordform(self, lemma: str, wordform: str) -> bool:
        lemma = lemma.strip().lower()
        wordform = wordform.strip().lower()
        try:
            del self._data[lemma]["wordforms"][wordform]
            if not self._data[lemma]["wordforms"]:
                del self._data[lemma]
            return True
        except KeyError:
            return False

    def delete_lemma(self, lemma: str) -> bool:
        lemma = lemma.strip().lower()
        if lemma in self._data:
            del self._data[lemma]
            return True
        return False

    def rename_lemma(self, old_lemma: str, new_lemma: str) -> bool:
        old_lemma = old_lemma.strip().lower()
        new_lemma = new_lemma.strip().lower()
        if old_lemma not in self._data:
            return False
        self._data[new_lemma] = self._data.pop(old_lemma)
        return True

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_sorted(self) -> list[tuple[str, str, int, str]]:
        """Return all rows sorted alphabetically by lemma then wordform.
        Each row: (lemma, wordform, frequency, morphology)
        """
        rows = []
        for lemma in sorted(self._data):
            for wf in sorted(self._data[lemma]["wordforms"]):
                entry = self._data[lemma]["wordforms"][wf]
                rows.append((lemma, wf, entry["frequency"], entry["morphology"]))
        return rows

    def search(self, query: str) -> list[tuple[str, str, int, str]]:
        """Search by lemma, wordform or morphology text (case-insensitive)."""
        q = query.strip().lower()
        results = []
        for lemma in sorted(self._data):
            for wf in sorted(self._data[lemma]["wordforms"]):
                entry = self._data[lemma]["wordforms"][wf]
                if (
                    q in lemma
                    or q in wf
                    or q in entry["morphology"].lower()
                ):
                    results.append((lemma, wf, entry["frequency"], entry["morphology"]))
        return results

    def filter_by_frequency(
        self,
        min_freq: Optional[int] = None,
        max_freq: Optional[int] = None,
    ) -> list[tuple[str, str, int, str]]:
        rows = []
        for lemma in sorted(self._data):
            for wf in sorted(self._data[lemma]["wordforms"]):
                entry = self._data[lemma]["wordforms"][wf]
                freq = entry["frequency"]
                if min_freq is not None and freq < min_freq:
                    continue
                if max_freq is not None and freq > max_freq:
                    continue
                rows.append((lemma, wf, freq, entry["morphology"]))
        return rows

    def get_entry(self, lemma: str, wordform: str) -> Optional[dict]:
        lemma = lemma.strip().lower()
        wordform = wordform.strip().lower()
        try:
            return dict(self._data[lemma]["wordforms"][wordform])
        except KeyError:
            return None

    def count(self) -> int:
        return sum(len(v["wordforms"]) for v in self._data.values())

    def lemma_count(self) -> int:
        return len(self._data)

    def clear(self) -> None:
        self._data.clear()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"lexemes": self._data}, f, ensure_ascii=False, indent=2)

    def load(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self._data = raw.get("lexemes", {})

    def export_csv(self, path: str) -> None:
        rows = self.get_sorted()
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["Lemma", "Wordform", "Frequency", "Morphology"])
            writer.writerows(rows)
