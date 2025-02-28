from models import Conference, ConferenceInstance


class ConferenceInstanceRepository:
    def __init__(self, session):
        self.session = session

    def upsert(
        self, conference_id: str, name: str, year: int, **kwargs
    ) -> ConferenceInstance:

        conference = (
            self.session.query(Conference)
            .filter_by(conference_id=conference_id)
            .first()
        )
        if not conference:
            raise ValueError("Conference not found")

        instance = (
            self.session.query(ConferenceInstance)
            .filter_by(conference_id=conference_id, year=year)
            .first()
        )
        if instance:
            for key, value in kwargs.items():
                setattr(instance, key, value)
        else:
            instance = ConferenceInstance(
                conference_id=conference_id, conference_name=name, year=year, **kwargs
            )
            self.session.add(instance)

        self.session.commit()
        return instance
