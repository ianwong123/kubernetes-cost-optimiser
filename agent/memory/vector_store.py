import numpy as np
from typing import List
from redis import Redis
from redis.commands.search.field import VectorField, TextField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from sentence_transformers import SentenceTransformer

INDEX_NAME = "history_idx"
VECTOR_DIM = 384

# The job is to remember past optimisation and 
# find similar ones when a new problem appears
class RedisVectorStore:
    def __init__(self, redis_client: Redis):
        self.client = redis_client
        self.model = SentenceTransformer('all-MiniLM-L6-v2') 
        self._check_index_exists()

    # create vector search index
    def _check_index_exists(self):
        """Create vector search index if it doesnt exist"""
        try:
            self.client.ft(INDEX_NAME).info()
            print("Index already exist")
        except:
            print("No index found, creating new index...")
            schema = (
                TextField("content"),
                VectorField("vector", "FLAT", {
                    "TYPE": "FLOAT32",
                    "DIM": VECTOR_DIM,
                    "DISTANCE_METRIC": "COSINE"
                }),
            )
            self.client.ft(INDEX_NAME).create_index(
                schema,
                definition=IndexDefinition(prefix=["doc:"], index_type=IndexType.HASH)
            )

    # embedding optimisation results to vectors
    def embed_text(self, text:str) -> np.ndarray:
        return self.model.encode(text).astype(np.float32).tobytes()

    # the idea is to store some scenario and its outcome after optimisation
    # we embed the scenario text only, the outcome is stored as metadata to be reused later
    # this will be called later when an proposed optimisaton is accepted via PR merge
    # args: take in some text problem and its outcome after optimisation
    def add_memory(self, text: str, outcome: str):
        doc_id = f"doc:{hash(text)}"
        vector = self.embed_text(text)

        self.client.hset(doc_id, mapping={
            "content": f"Scenario: {text} | Outcome: {outcome}",
            "vector": vector
        })

    # query top 3 similar past optimisations with knn
    def search_similar(self, query_text: str, k: int = 3) -> List[str]:
        query_vector = self.embed_text(query_text)
        params = {"vec": query_vector}

        # use RediSearch 2.0 query syntax
        query = (
            Query(f"*=>[KNN {k} @vector $vec AS vector_score]")
            .sort_by("vector_score")
            .return_fields("content")
            .dialect(2)
        )

        results = self.client.ft(INDEX_NAME).search(query, query_params=params)
        return [doc.content for doc in results.docs]

