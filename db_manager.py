from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from models import Base
from config import DATABASE_URL
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection
from pymilvus import utility


class DBManager:
    def __init__(self, database_url=DATABASE_URL):
        """
        Initialize the DataManager by creating a SQLAlchemy engine,
        session factory, and a scoped session.
        """
        self.engine = create_engine(database_url, echo=True)
        self.session_factory = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        self.Session = scoped_session(self.session_factory)

        connections.connect(alias="default", host="localhost", port="19530")

        collection_name = "paper_collection"
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="paper_id", dtype=DataType.INT64),  # 论文 ID
            FieldSchema(name="chunk_id", dtype=DataType.INT64),  # 论文中的 chunk 序号
            FieldSchema(name="chunk_text", dtype=DataType.VARCHAR, max_length=5000),  # chunk 原始文本
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=768),  # chunk 向量
            FieldSchema(name="chunk_type", dtype=DataType.VARCHAR, max_length=50),  # chunk 类型 (如 abstract, conclusion)
        ]
        schema = CollectionSchema(fields, description="Collection for paper embeddings")

        self.vdb_collection = None
        if not utility.has_collection(collection_name):
            self.vdb_collection = Collection(name=collection_name, schema=schema)
            print(f"Collection {collection_name} created.")
        else:
            self.vdb_collection = Collection(name=collection_name)
            print(f"Collection {collection_name} already exists.")

    def get_session(self):
        """
        Return a new SQLAlchemy session.
        This session should be used within a context (or try/finally) and closed when done.
        """
        return self.Session()

    def get_vdb_collection(self):
        return self.vdb_collection

    def close(self):
        """
        Remove (close) all sessions.
        This method is typically called when your application shuts down.
        """
        self.Session.remove()

    def create_tables(self):
        """
        Create all tables defined in the SQLAlchemy declarative Base.
        This is useful when setting up a new database.
        """
        try:
            Base.metadata.create_all(bind=self.engine)
        except Exception as e:
            self.Session.rollback()
            print(f"Error: {e}")

    def drop_all_tables(self):
        """
        Drop all tables.
        Caution: This permanently deletes all data.
        """
        try:
            Base.metadata.drop_all(bind=self.engine)
        except Exception as e:
            self.Session.rollback()
            print(f"Error: {e}")

    def reset_database(self):
        """
        Reset the database by dropping all tables and then recreating them.
        This is useful for testing or development purposes.
        """
        self.drop_all_tables()
        self.create_tables()
