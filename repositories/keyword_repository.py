from models import Keyword


class KeywordRepository:
    def __init__(self, session):
        self.session = session

    def upsert(self, keyword: str, description: str = "") -> Keyword:
        keyword_obj = self.session.query(Keyword).filter_by(keyword=keyword).first()
        if keyword_obj:
            setattr(keyword_obj, description, description)
        else:
            keyword_obj = Keyword(keyword=keyword, description=description)
            self.session.add(keyword_obj)

        self.session.commit()
        return keyword_obj
