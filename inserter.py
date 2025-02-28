from sqlalchemy.orm import Session
from db import SessionLocal
from models import Paper, Author, Keyword, Reference


def insert_papers(paper_data):
    with SessionLocal() as db:
        for paper in paper_data:
            existing_paper = db.query(Paper).filter(Paper.title == paper["title"]).first()
            if existing_paper:
                continue  # 避免重复插入

            new_paper = Paper(
                title=paper["title"], url=paper["url"], abstract=paper.get("abstract")
            )
            db.add(new_paper)
            db.commit()
            db.refresh(new_paper)

            # 处理作者
            for author_name in paper["authors"]:
                author = db.query(Author).filter(Author.name == author_name).first()
                if not author:
                    author = Author(name=author_name)
                    db.add(author)
                    db.commit()
                new_paper.authors.append(author)

            # 处理关键词
            for keyword in paper.get("keywords", []):
                kw = db.query(Keyword).filter(Keyword.word == keyword).first()
                if not kw:
                    kw = Keyword(word=keyword)
                    db.add(kw)
                    db.commit()
                new_paper.keywords.append(kw)

            # 处理参考文献
            for ref_title in paper.get("references", []):
                ref = Reference(cited_paper_title=ref_title, paper=new_paper)
                db.add(ref)

            db.commit()
