import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date
from models import (
    Base,
    Conference,
    ConferenceInstance,
    Paper,
    Author,
    PaperAuthors,
    Affiliation,
    AuthorAffiliation,
    Keyword,
    PaperKeyword,
    Reference,
    PaperReference,
    ContentEmbedding,
)  # 导入您的模型

# 配置本地 PostgreSQL 数据库 URL
DATABASE_URL = "postgresql://admin:admin123@localhost/test_db"
engine = create_engine(DATABASE_URL, echo=True)

# 创建会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建所有表
Base.metadata.create_all(bind=engine)


# 测试数据插入和查询
def test_conference_insert_and_query():
    session = SessionLocal()
    conference = Conference(
        name="ICML",
        type="AI",
        description="International Conference on Machine Learning",
    )

    session.add(conference)
    session.commit()

    # 查询
    saved_conference = session.query(Conference).filter_by(name="ICML").first()

    assert saved_conference is not None
    assert saved_conference.name == "ICML"
    assert saved_conference.type == "AI"

    session.close()


def test_paper_insert_and_query():
    session = SessionLocal()
    conference_instance = ConferenceInstance(name="NeurIPS 2025", year=2025)
    session.add(conference_instance)
    session.commit()

    paper = Paper(
        instance_id=conference_instance.instance_id,
        title="Deep Learning for AI",
        year=2025,
        abstract="This is an abstract.",
        content="Full paper content",
        pdf_path="http://example.com/paper.pdf",
    )
    session.add(paper)
    session.commit()

    # 查询
    saved_paper = session.query(Paper).filter_by(title="Deep Learning for AI").first()

    assert saved_paper is not None
    assert saved_paper.title == "Deep Learning for AI"
    assert saved_paper.abstract == "This is an abstract."

    session.close()


def test_embedding_insert_and_query():
    session = SessionLocal()
    paper = Paper(title="Deep Learning for AI", year=2025)
    session.add(paper)
    session.commit()

    # 模拟 768 维向量
    import numpy as np

    embedding_vector = np.random.rand(768).tolist()  # 随机生成一个 768 维向量

    content_embedding = ContentEmbedding(
        paper_id=paper.paper_id, embedding=embedding_vector
    )
    session.add(content_embedding)
    session.commit()

    # 查询
    saved_embedding = (
        session.query(ContentEmbedding).filter_by(paper_id=paper.paper_id).first()
    )

    assert saved_embedding is not None
    assert len(saved_embedding.embedding) == 768  # 确认嵌入向量的长度为 768

    session.close()


def test_author_and_affiliation():
    session = SessionLocal()
    affiliation = Affiliation(name="Redwood Research", type="Research", location="USA")
    session.add(affiliation)
    session.commit()

    author = Author(name="Ryan Greenblatt", email="ryan@rdwrs.com")
    session.add(author)
    session.commit()

    author_affiliation = AuthorAffiliation(
        author_id=author.author_id, affiliation_id=affiliation.affiliation_id
    )
    session.add(author_affiliation)
    session.commit()

    # 查询
    saved_author_affiliation = session.query(AuthorAffiliation).first()
    assert saved_author_affiliation is not None
    assert saved_author_affiliation.author.name == "Ryan Greenblatt"
    assert saved_author_affiliation.affiliation.name == "Redwood Research"

    session.close()


def test_keyword_and_paper_keyword():
    session = SessionLocal()
    keyword = Keyword(keyword="AI", description="Artificial Intelligence")
    session.add(keyword)
    session.commit()

    paper = Paper(title="Deep Learning for AI", year=2025)
    session.add(paper)
    session.commit()

    paper_keyword = PaperKeyword(paper_id=paper.paper_id, keyword_id=keyword.keyword_id)
    session.add(paper_keyword)
    session.commit()

    # 查询
    saved_paper_keyword = session.query(PaperKeyword).first()
    assert saved_paper_keyword is not None
    assert saved_paper_keyword.paper.title == "Deep Learning for AI"
    assert saved_paper_keyword.keyword.keyword == "AI"

    session.close()


def test_multiple_relationships():
    session = SessionLocal()
    author = Author(name="Fabien Roger", email="fabien.d.roger@gmail.com")
    session.add(author)
    session.commit()

    paper = Paper(title="AI for Research", year=2025)
    session.add(paper)
    session.commit()

    paper_author = PaperAuthors(
        paper_id=paper.paper_id,
        author_id=author.author_id,
        author_order=1,
        is_corresponding=True,
    )
    session.add(paper_author)
    session.commit()

    # 查询
    saved_paper_author = session.query(PaperAuthors).first()
    assert saved_paper_author is not None
    assert saved_paper_author.author.name == "Fabien Roger"
    assert saved_paper_author.paper.title == "AI for Research"

    session.close()


# 启动测试
if __name__ == "__main__":
    pytest.main()
