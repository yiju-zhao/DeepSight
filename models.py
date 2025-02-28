from sqlalchemy import (
    TIMESTAMP,
    Table,
    Column,
    Date,
    Float,
    Integer,
    String,
    Text,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import ARRAY

Base = declarative_base()


# 会议信息表
class Conference(Base):
    __tablename__ = "conference"

    conference_id = Column(Integer, primary_key=True, autoincrement=True)  # 主键，自增
    name = Column(String(255), nullable=False, unique=True)  # 会议名称，唯一，不能为空
    type = Column(String(255))  # 会议类型
    description = Column(Text)  # 会议描述，允许为空

    instance_to_conference = relationship(
        "ConferenceInstance",
        back_populates="conference_to_instance",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        # 这是数据库级别的唯一约束
        UniqueConstraint("name", name="unique_conference_name"),
    )

    def __repr__(self):
        return f"<Conference(id={self.conference_id}, name={self.name})>"


# 会议实例表
class ConferenceInstance(Base):
    __tablename__ = "conference_instance"

    instance_id = Column(Integer, primary_key=True, autoincrement=True)  # 主键，自增
    conference_id = Column(
        Integer, ForeignKey("conference.conference_id"), nullable=False
    )  # 外键，关联 `Conference` 表
    conference_name = Column(String(255), nullable=False)  # 会议实例名称，唯一，不能为空
    year = Column(Integer, nullable=False)  # 会议举办年份，不能为空
    start_date = Column(Date)  # 会议开始日期
    end_date = Column(Date)  # 会议结束日期
    location = Column(String(255))  # 会议举办地点
    website = Column(String(255))  # 会议官网链接

    # 定义与 `Conference` 表的关系
    conference_to_instance = relationship(
        "Conference", back_populates="instance_to_conference"
    )
    # 定义与 `Paper` 表的关系
    paper_to_instance = relationship("Paper", back_populates="instance_to_paper")

    def __repr__(self):
        return (
            f"<ConferenceInstance(id={self.instance_id}, name={self.name}， year={self.year})>"
        )


# 参考文献信息表
class Reference(Base):
    __tablename__ = "reference"

    reference_id = Column(Integer, primary_key=True)  # 自增主键
    title = Column(String(255), nullable=False)  # 参考文献标题，不能为空
    author = Column(Text)  # 作者，多个作者用逗号分隔，可以为空
    year = Column(Integer)  # 参考文献出版年份
    journal = Column(String(255))  # 参考文献所属期刊名称
    web_url = Column(String(255))  # 参考文献的网页 URL 或指向原始论文的 URL
    # 定义与 Paper 表的多对多关系，通过 paper_reference 中间表
    paper_to_reference = relationship(
        "Paper", secondary="paper_reference", back_populates="reference_to_paper"
    )

    def __repr__(self):
        return f"<Reference(id={self.reference_id}, title={self.title}, author={self.author}, year={self.year})>"


# 文章-参考文献关系表
class PaperReference(Base):
    __tablename__ = "paper_reference"
    paper_id = Column(
        Integer, ForeignKey("paper.paper_id", ondelete="CASCADE"), primary_key=True
    )  # 关联论文
    reference_id = Column(
        Integer,
        ForeignKey("reference.reference_id", ondelete="CASCADE"),
        primary_key=True,
    )  # 关联参考文献


# 文章信息表
class Paper(Base):
    __tablename__ = "paper"

    paper_id = Column(Integer, primary_key=True, autoincrement=True)  # 主键，自增
    instance_id = Column(
        Integer, ForeignKey("conference_instance.instance_id"), nullable=False
    )  # 外键，关联 `ConferenceInstance` 表
    title = Column(String(255), nullable=False)  # 论文标题，不能为空
    venue = Column(String(50))  # 论文类型，例如 oral, poster
    year = Column(Integer, nullable=False)  # 论文出版年份，不能为空
    publish_date = Column(Date)  # 论文发布日期
    research_area = Column(String(255))  # 论文研究领域
    tldr = Column(Text)  # 论文简短总结
    abstract = Column(Text)  # 论文摘要
    content_raw_text = Column(Text)  # 论文完整内容，纯文本
    conclusion = Column(Text)  # 论文结论
    reference_raw_text = Column(Text)  # 参考文献的原始数据，用于后续批处理
    pdf_path = Column(String(255))  # 论文 PDF 路径或 URL
    citation_count = Column(Integer, default=0)  # 论文引用次数，默认为 0
    award = Column(String(255))  # 获奖情况（例如 best paper, best paper runner）
    doi = Column(String(255))  # Digital Object Identifier
    url = Column(String(255))  # 论文链接
    pdf_url = Column(String(255))  # 论文 PDF 链接
    attachment_url = Column(String(255))  # 论文代码库链接

    # 定义与 ConferenceInstance 的关系
    instance_to_paper = relationship("ConferenceInstance", back_populates="paper_to_instance")

    # 定义与 authoer 的关系
    author_to_paper = relationship(
        "Author", secondary="paper_author", back_populates="paper_to_author"
    )
    # 定义与 keyword 的关系
    keyword_to_paper = relationship(
        "Keyword", secondary="paper_keyword", back_populates="paper_to_keyword"
    )
    # 定义与 reference 的关系
    reference_to_paper = relationship(
        "Reference", secondary="paper_reference", back_populates="paper_to_reference"
    )

    # 创建索引，方便通过标题进行快速查找
    __table_args__ = (
        Index("idx_paper_title", "title"),
        Index("idx_paper_year", "year"),
        Index("idx_paper_publish_date", "publish_date"),
    )

    def __repr__(self):
        return f"<Paper(id={self.paper_id},title={self.title}, year={self.year}, tldr={self.tldr})>"


# 作者信息表
class Author(Base):
    __tablename__ = "author"

    author_id = Column(Integer, primary_key=True, autoincrement=True)  # 主键，自增
    external_id = Column(String(255), unique=True)  # 外部来源的作者ID (e.g., "~name")
    name = Column(String(100), nullable=False)  # 作者名字，不能为空
    email = Column(String(320))  # 邮箱，可为空
    google_scholar_url = Column(String(255))  # Google Scholar 主页
    home_website = Column(String(255))  # 个人主页
    nationality = Column(String(100))  # 国籍
    # 多对多关系配置
    paper_to_author = relationship(
        "Paper", secondary="paper_author", back_populates="author_to_paper"
    )
    affiliation_to_author = relationship(
        "Affiliation",
        secondary="author_affiliation",
        back_populates="author_to_affiliation",
    )

    __table_args__ = (
        # 创建索引方便通过name查询
        Index("idx_author_name", "name"),
    )

    def __repr__(self):
        return f"<Author(id={self.author_id}, name={self.name}, email={self.email})>"


# 文章-作者关系表
# class PaperAuthors(Base):
#     __tablename__ = "paper_author"
#     paper_id = Column(Integer, ForeignKey('paper.paper_id', ondelete='CASCADE'), primary_key=True)  # 外键，关联 `Paper` 表
#     author_id = Column(Integer), ForeignKey('author.author_id', ondelete='CASCADE'), primary_key=True)  # 外键，关联 `Author` 表

### Define the association table for Paper-Author relationship
paper_author = Table(
    "paper_author",
    Base.metadata,
    Column(
        "paper_id",
        Integer,
        ForeignKey("paper.paper_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "author_id",
        Integer,
        ForeignKey("author.author_id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# 机构信息表
class Affiliation(Base):
    __tablename__ = "affiliation"

    affiliation_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)  # 组织名称
    aliases = Column(ARRAY(String), nullable=True)  # 组织别名
    type = Column(String(100), nullable=True)  # 类型（如 university, industry 等）
    location = Column(String(255), nullable=True)  # 地点
    website = Column(String(255), nullable=True)  # 网站
    description = Column(Text, nullable=True)  # 描述
    author_to_affiliation = relationship(
        "Author",  # 目标表是 Author
        secondary="author_affiliation",  # 通过 author_affiliation 连接表
        back_populates="affiliation_to_author",  # 在 Author 中定义反向关系
    )

    def __repr__(self):
        return f"<Affiliation(id={self.affiliation_id}, name={self.name}, type={self.type})>"


# 作者-机构关系表
class AuthorAffiliation(Base):
    __tablename__ = "author_affiliation"
    author_id = Column(
        Integer, ForeignKey("author.author_id", ondelete="CASCADE"), primary_key=True
    )  # 关联作者
    affiliation_id = Column(
        Integer,
        ForeignKey("affiliation.affiliation_id", ondelete="CASCADE"),
        primary_key=True,
    )  # 关联组织


# 关键字信息表
class Keyword(Base):
    __tablename__ = "keyword"

    keyword_id = Column(Integer, primary_key=True)  # 自增主键
    keyword = Column(String(255), unique=True, nullable=False)  # 关键字，不能为空，唯一
    description = Column(Text)  # 关键字的描述
    # 定义与 Paper 表的多对多关系，通过 paper_keyword 中间表
    paper_to_keyword = relationship(
        "Paper", secondary="paper_keyword", back_populates="keyword_to_paper"
    )

    def __repr__(self):
        return f"<Keyword(id={self.keyword_id}, keyword={self.keyword}, description={self.description})>"


# 文章-关键字关系表
class PaperKeyword(Base):
    __tablename__ = (
        "paper_keyword"  # Ensure this matches the secondary table name used in the Paper class
    )
    paper_id = Column(
        Integer, ForeignKey("paper.paper_id", ondelete="CASCADE"), primary_key=True
    )  # 关联论文
    keyword_id = Column(
        Integer, ForeignKey("keyword.keyword_id", ondelete="CASCADE"), primary_key=True
    )  # 关联关键字
