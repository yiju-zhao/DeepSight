from typing import List, Optional
from venv import logger
from models import Paper, Author, Reference, Keyword
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.inspection import inspect


class PaperRepository:
    def __init__(self, session):
        self.session = session

    def _get_author(self, external_id: str) -> Author:
        author = self.session.query(Author).filter_by(external_id=external_id).first()
        if not author:
            raise ValueError(f"Author {external_id} not found.")
        return author

    def _get_reference(self, title: str) -> Reference:
        reference = self.session.query(Reference).filter_by(title=title).first()
        if not reference:
            raise ValueError(f"Reference {title} not found.")
        return reference

    def _get_keyword(self, keyword: str) -> Keyword:
        keyword = self.session.query(Keyword).filter_by(keyword=keyword).first()
        if not keyword:
            raise ValueError(f"Keyword {keyword} not found.")
        return keyword

    def get_papers(
        self, limit: Optional[int] = None, offset: Optional[int] = None, **filters
    ) -> List[Paper]:
        """
        根据传入的过滤条件查询 Paper 表，并支持 limit 和 offset 参数。

        参数:
            limit (int, 可选): 返回结果的最大数量。
            offset (int, 可选): 跳过的记录数（用于分页）。
            **filters: 动态关键字参数，如 title="Example", year=2024。

        返回:
            List[Paper]: 查询结果列表（可能为空列表）。
        """
        if not filters and limit is None and offset is None:
            raise ValueError("请提供至少一个查询条件或分页参数！")

        try:
            # Apply filters if they exist and are valid columns
            valid_filters = {}
            for key, value in filters.items():
                logger.info(f"key:{key}, value:{value}")
                if hasattr(Paper, key):
                    valid_filters[key] = value
                else:
                    logger.warning(f"Ignoring invalid filter field: {key}")

            # Start with base query
            query = self.session.query(Paper)
            if valid_filters:
                query = query.filter_by(**valid_filters)

            if offset is not None:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)

            return query.all()

        except SQLAlchemyError as e:
            raise RuntimeError(f"数据库查询失败: {e}")

    # def _update_relationship(self, existing_rel, new_rel, get_item_func):
    #     """
    #     通用关系更新函数：
    #     - 添加新关联
    #     - 移除已不存在的关联
    #     """
    #     existing_ids = {get_item_func(item).id for item in existing_rel}
    #     new_ids = {get_item_func(item).id for item in new_rel}

    #     # Add new items that are not in the existing list
    #     for item in new_rel:
    #         if get_item_func(item).id not in existing_ids:
    #             existing_rel.append(item)

    #     # Remove items that are no longer in the new list
    #     for item in existing_rel[:]:  # Use a copy of the list for safe removal during iteration
    #         if get_item_func(item).id not in new_ids:
    #             existing_rel.remove(item)

    def upsert(
        self,
        title: str,
        year: int,
        instance_id: str,
        external_author_id: list = None,
        references: list = None,
        keywords: list = None,
        **kwargs,
    ) -> Paper:
        paper = (
            self.session.query(Paper).filter_by(instance_id=instance_id, title=title).first()
        )
        if paper:
            for key, value in kwargs.items():
                setattr(paper, key, value)
        else:
            paper = Paper(instance_id=instance_id, title=title, year=year, **kwargs)
            self.session.add(paper)

        if external_author_id:
            paper.author_to_paper = []
            for authorid in external_author_id:
                author_obj = self._get_author(external_id=authorid)
                paper.author_to_paper.append(author_obj)
        if references:
            paper.reference_to_paper = []
            for reference in references:
                reference_obj = self._get_reference(title=reference["title"])
                paper.reference_to_paper.append(reference_obj)
        if keywords:
            paper.keyword_to_paper = []
            for kw in keywords:
                keyword_obj = self._get_keyword(keyword=kw)
                paper.keyword_to_paper.append(keyword_obj)

        self.session.commit()
        return paper

