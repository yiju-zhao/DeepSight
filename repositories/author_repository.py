import re
from models import Author, Affiliation
from sqlalchemy import or_


class AuthorRepository:
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

    def _get_affiliation(self, name: str) -> Affiliation:
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
        return affiliation
    
    def get_author(self, external_id: str) -> Author:
        return self.session.query(Author).filter_by(external_id=external_id).first()

    def upsert(self, external_id: str, affiliations: list = None, **kwargs) -> Author:
        author = self.get_author(external_id)
        if author:
            for key, value in kwargs.items():
                setattr(author, key, value)
        else:
            author = Author(external_id=external_id, **kwargs)
            self.session.add(author)

        # Update affiliations
        if affiliations is not None:
            author.affiliation_to_author = []
            for affil_name in affiliations:
                cleaned_name = self._clean_name(affil_name)
                affiliation = self._get_affiliation(cleaned_name)
                if not affiliation:
                    affiliation = Affiliation(name=cleaned_name)
                    self.session.add(affiliation)
                if affiliation not in author.affiliation_to_author:
                    author.affiliation_to_author.append(affiliation)

        self.session.commit()
        return author
