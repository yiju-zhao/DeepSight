from models import Reference


class ReferenceRepository:
    def __init__(self, session):
        self.session = session

    def upsert(self, title: str, **kwargs) -> Reference:
        reference = self.session.query(Reference).filter_by(title=title).first()
        if reference:
            for key, value in kwargs.items():
                setattr(reference, key, value)
        else:
            reference = Reference(title=title, **kwargs)
            self.session.add(reference)

        self.session.commit()
        return reference
