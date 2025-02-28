import re
from fuzzywuzzy import fuzz
from models import Affiliation
from sqlalchemy import or_


class AffiliationRepository:
    def __init__(self, session):
        self.session = session

    def _clean_name(self, name: str) -> str:
        """Clean name by removing special characters and standardizing format"""
        if not name:
            return name

        # Convert to uppercase for standardization
        name = name.upper()

        # Remove special characters and extra whitespace
        name = re.sub(r"[^\w\s]", "", name)
        name = re.sub(r"\s+", " ", name).strip()

        # Common abbreviation standardization
        replacements = {
            "MASSACHUSETTS INSTITUTE OF TECHNOLOGY": "MIT",
            "MASS INST OF TECH": "MIT",
            "MASS INSTITUTE OF TECHNOLOGY": "MIT",
            # Add more common variations as needed
        }
        return replacements.get(name, name)

    def _find_best_matching_affiliation(
        self, name: str, affiliations: list, threshold: int
    ) -> str:
        """Find the best matching affiliation using fuzzy string matching"""
        best_score = 0
        best_match = None

        for affiliation in affiliations:
            # Check primary name
            score = fuzz.ratio(name, affiliation.name)
            if score > best_score:
                best_score = score
                best_match = affiliation

            # Check aliases
            if affiliation.aliases:
                for alias in affiliation.aliases:
                    score = fuzz.ratio(name, self._clean_institution_name(alias))
                    if score > best_score:
                        best_score = score
                        best_match = affiliation

        return best_match if best_score >= threshold else None

    def upsert(self, name: str, **kwargs) -> Affiliation:
        affiliation = self.session.query(Affiliation).filter_by(name=name).first()
        if not affiliation:
            cleaned_name = self._clean_name(name)
            affiliation = (
                self.session.query(Affiliation)
                .filter(
                    or_(
                        Affiliation.aliases.contains(
                            [cleaned_name]
                        ),  # Check if cleaned_name is in aliases
                        Affiliation.name == cleaned_name,
                    )
                )
                .first()
            )

        if affiliation:
            for key, value in kwargs.items():
                setattr(affiliation, key, value)
        else:
            affiliation = Affiliation(name=name, **kwargs)
            self.session.add(affiliation)

        self.session.commit()
        return affiliation
