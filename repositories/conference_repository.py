from models import Conference


class ConferenceRepository:
    def __init__(self, session):
        self.session = session

    def upsert(self, name: str, **kwargs) -> Conference:
        conference = self.session.query(Conference).filter_by(name=name).first()
        if conference:
            for key, value in kwargs.items():
                setattr(conference, key, value)
        else:
            conference = Conference(name=name, **kwargs)
            self.session.add(conference)

        self.session.commit()
        return conference

    def get_conference_by_name(self, name: str) -> Conference:
        conference = self.session.query(Conference).filter_by(name=name).first()
        if not conference:
            raise ValueError(f"Conference {name} not found.")
        return conference
