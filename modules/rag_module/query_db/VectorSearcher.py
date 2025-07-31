# modules/agents/vector_searcher.py
import torch
import logging
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer
from modules.rag_module.datatypes.QueryResult import QueryResult

class VectorSearcher:
    def __init__(self, mongo_uri: str, db_name: str, collection_name: str,
                 embedding_model: str = "keepitreal/vietnamese-sbert",
                 search_index: str = "default",
                 top_k: int = 10,
                 relevance_threshold: float = 0.2):

        self.client = MongoClient(mongo_uri)
        self.collection = self.client[db_name][collection_name]

        self.top_k = top_k
        self.search_index = search_index
        self.relevance_threshold = relevance_threshold

        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer(embedding_model, device=device)

        self.logger = logging.getLogger(__name__)
        self.logger.info(f"VectorSearcher initialized on {device}")

    def embed_text(self, text: str) -> list[float]:
        try:
            return self.model.encode(text, convert_to_tensor=False).tolist()
        except Exception as e:
            self.logger.error(f"Embedding error: {e}")
            raise

    def search(self, subtopic: str) -> list[QueryResult]:
        try:
            vector = self.embed_text(subtopic)
            pipeline = [
                {
                    "$search": {
                        "index": self.search_index,
                        "knnBeta": {
                            "vector": vector,
                            "path": "embedding",
                            "k": self.top_k
                        }
                    }
                },
                {
                    "$project": {
                        "chunk_id": 1,
                        "content": 1,
                        "score": {"$meta": "searchScore"},
                        "source_file": 1,
                        "page_number": 1
                    }
                }
            ]
            results = list(self.collection.aggregate(pipeline))

            output = []
            for r in results:
                if r.get("score", 0) >= self.relevance_threshold:
                    output.append(QueryResult(
                        chunk_id=r.get("chunk_id", ""),
                        content=r.get("content", ""),
                        score=r.get("score", 0.0),
                        source_file=r.get("source_file", ""),
                        page_number=r.get("page_number"),
                        subtopic=subtopic
                    ))
            return output
        except Exception as e:
            self.logger.error(f"Search error for subtopic '{subtopic}': {e}")
            return []

    def deduplicate(self, chunks: list[QueryResult]) -> list[QueryResult]:
        if not chunks:
            return []

        chunks.sort(key=lambda x: x.score, reverse=True)
        seen = set()
        unique = []

        for c in chunks:
            h = hash(c.content.strip())
            if h not in seen:
                seen.add(h)
                unique.append(c)

        return unique
