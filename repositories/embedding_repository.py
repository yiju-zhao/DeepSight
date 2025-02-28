from typing import List, Tuple
import numpy as np
from pymilvus import Collection, connections
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class EmbeddingRepository:
    def __init__(self, collection: Collection):
        """Initialize EmbeddingRepository

        Args:
            collection (Collection): Milvus collection instance
        """
        self.collection = collection  # Changed from session to collection for clarity

    @contextmanager
    def connect(self, host: str = "localhost", port: int = 19530):
        """Context manager for Milvus connection

        Args:
            host: Milvus server host
            port: Milvus server port
        """
        try:
            connections.connect(alias="default", host=host, port=port)
            yield
        finally:
            connections.disconnect("default")

    def insert_chunks_batch(
        self, paper_id: int, embeddings_list: List[Tuple[int, str, str, np.ndarray]]
    ) -> bool:
        """Batch insert paper chunks and their embeddings

        Args:
            paper_id: Paper identifier
            embeddings_list: List of tuples containing (chunk_id, chunk_type, chunk_text, embedding)

        Returns:
            bool: True if insertion successful, False otherwise

        Raises:
            ValueError: If embeddings_list is malformed
        """
        try:
            if not embeddings_list:
                logger.warning(f"No chunks to insert for paper {paper_id}.")
                return False

            # Validate input data
            if not all(len(chunk) == 4 for chunk in embeddings_list):
                raise ValueError("Each chunk must contain exactly 4 elements")

            # Split fields
            chunk_ids = [int(chunk[0]) for chunk in embeddings_list]
            chunk_types = [chunk[1] for chunk in embeddings_list]
            chunk_texts = [chunk[2] for chunk in embeddings_list]
            embeddings = [chunk[3] for chunk in embeddings_list]

            # Validate embeddings dimensions
            embedding_dim = len(embeddings[0])
            if not all(len(embeddings) == embedding_dim for embeddings in embeddings):
                raise ValueError("All embeddings must have the same dimension")

            data = [
                [paper_id] * len(embeddings_list),
                chunk_ids,
                chunk_texts,
                embeddings,
                chunk_types,
            ]

            insert_result = self.collection.insert(data)
            self.collection.flush()

            logger.info(
                f"Successfully inserted {len(embeddings_list)} chunks for paper {paper_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Error inserting chunks for paper {paper_id}: {e}")

    def search_similar_chunks(
        self, query_embedding: np.ndarray, top_k: int = 5, filter_expr: str = None
    ) -> List[dict]:
        """Search for similar chunks using vector similarity

        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            filter_expr: Optional filter expression

        Returns:
            List of similar chunks with distances
        """
        try:
            search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=filter_expr,
                output_fields=["paper_id", "chunk_id", "chunk_text"],
            )

            return results

        except Exception as e:
            logger.error(f"Error during similarity search: {str(e)}")
            return []
