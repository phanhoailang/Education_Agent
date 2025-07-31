import numpy as np
from typing import List, Dict, Union
from functools import lru_cache
from sentence_transformers import SentenceTransformer, util
import logging

class SemanticChunkFilter:
    def __init__(self, model_name: str = "keepitreal/vietnamese-sbert", cache_size: int = 1000):
        self.model = SentenceTransformer(model_name)
        self.cache_size = cache_size
        self.chunk_embeddings_cache = {} 
        self.logger = logging.getLogger(__name__)
        
        # Stats for monitoring
        self.cache_hits = 0
        self.cache_misses = 0

    @lru_cache(maxsize=500)
    def _get_query_embedding(self, query: str) -> tuple:
        """Cache query embeddings. Return tuple để hashable."""
        embedding = self.model.encode([query], convert_to_tensor=False)[0]
        return tuple(embedding.tolist())

    def precompute_chunk_embeddings(self, chunks: List[dict], batch_size: int = 32):
        """🚀 Pre-compute embeddings cho chunks để avoid runtime computation"""
        self.logger.info(f"Pre-computing embeddings for {len(chunks)} chunks...")
        
        # Extract valid chunks
        valid_chunks = []
        chunk_texts = []
        
        for chunk in chunks:
            if self._is_valid_chunk(chunk):
                chunk_id = chunk.get('chunk_id', f"chunk_{len(valid_chunks)}")
                valid_chunks.append((chunk_id, chunk))
                chunk_texts.append(chunk['content'])
        
        if not chunk_texts:
            self.logger.warning("No valid chunks to pre-compute embeddings")
            return
        
        # Batch compute embeddings
        try:
            embeddings = self.model.encode(chunk_texts, batch_size=batch_size, 
                                         convert_to_tensor=False, show_progress_bar=True)
            
            # Cache embeddings
            for (chunk_id, chunk), embedding in zip(valid_chunks, embeddings):
                self.chunk_embeddings_cache[chunk_id] = {
                    'embedding': embedding,
                    'content': chunk['content'][:100],  # Store snippet for debugging
                    'source': chunk.get('source_file', 'unknown')
                }
                
        except Exception as e:
            self.logger.error(f"Error pre-computing embeddings: {e}")
            
        self.logger.info(f"✅ Pre-computed {len(self.chunk_embeddings_cache)} chunk embeddings")

    def filter(self, chunks: List[dict], query: Union[str, List[str]], 
               threshold: float = 0.5, batch_size: int = 32, 
               use_precomputed: bool = True) -> List[dict]:
        """🚀 OPTIMIZED filtering với multiple strategies"""
        
        if isinstance(query, str):
            queries = [query]
        elif isinstance(query, list):
            queries = query
        else:
            raise ValueError("query phải là string hoặc list of strings")

        self.logger.debug(f"🔍 Semantic filter với {len(queries)} queries, {len(chunks)} chunks")

        # Validate chunks
        valid_chunks = [chunk for chunk in chunks if self._is_valid_chunk(chunk)]
        if not valid_chunks:
            self.logger.warning("⚠️ Không có chunk nào hợp lệ để lọc")
            return []

        # Strategy 1: Use pre-computed embeddings if available
        if use_precomputed and self._has_precomputed_embeddings(valid_chunks):
            return self._filter_with_precomputed(valid_chunks, queries, threshold)
        
        # Strategy 2: Batch processing for runtime computation
        return self._filter_with_batch_compute(valid_chunks, queries, threshold, batch_size)

    def _has_precomputed_embeddings(self, chunks: List[dict]) -> bool:
        """Check if we have pre-computed embeddings for most chunks"""
        available_count = 0
        for chunk in chunks[:10]:  # Sample first 10
            chunk_id = chunk.get('chunk_id', '')
            if chunk_id in self.chunk_embeddings_cache:
                available_count += 1
        
        return available_count / min(len(chunks), 10) > 0.7  # 70% availability

    def _filter_with_precomputed(self, chunks: List[dict], queries: List[str], 
                                threshold: float) -> List[dict]:
        """🚀 Ultra-fast filtering using pre-computed embeddings"""
        
        # Get query embeddings (cached)
        query_embeddings = []
        for query in queries:
            query_emb = list(self._get_query_embedding(query))
            query_embeddings.append(query_emb)
            self.cache_hits += 1
        
        filtered_chunks = []
        
        for chunk in chunks:
            chunk_id = chunk.get('chunk_id', '')
            
            if chunk_id in self.chunk_embeddings_cache:
                chunk_embedding = self.chunk_embeddings_cache[chunk_id]['embedding']
                
                # Calculate max similarity across all queries
                max_score = 0.0
                for query_emb in query_embeddings:
                    score = self._cosine_similarity(query_emb, chunk_embedding)
                    max_score = max(max_score, score)
                
                if max_score >= threshold:
                    chunk['semantic_score'] = float(max_score)
                    filtered_chunks.append(chunk)
                    
                self.cache_hits += 1
            else:
                # Fallback: compute on the fly
                chunk_text = chunk['content']
                chunk_emb = list(self._get_query_embedding(chunk_text))
                
                max_score = 0.0
                for query_emb in query_embeddings:
                    score = self._cosine_similarity(query_emb, chunk_emb)
                    max_score = max(max_score, score)
                
                if max_score >= threshold:
                    chunk['semantic_score'] = float(max_score)
                    filtered_chunks.append(chunk)
                    
                self.cache_misses += 1

        # Sort by semantic score
        filtered_chunks.sort(key=lambda x: x.get('semantic_score', 0), reverse=True)
        
        self.logger.debug(f"✅ Pre-computed filter: {len(filtered_chunks)}/{len(chunks)} chunks passed")
        return filtered_chunks

    def _filter_with_batch_compute(self, chunks: List[dict], queries: List[str], 
                                  threshold: float, batch_size: int) -> List[dict]:
        """Batch processing for chunks without pre-computed embeddings"""
        
        # Get query embeddings
        query_embeddings = self.model.encode(queries, convert_to_tensor=True)
        
        filtered_chunks = []
        
        # Process chunks in batches
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_texts = [chunk['content'] for chunk in batch_chunks]
            
            try:
                # Batch encode chunk texts
                chunk_embeddings = self.model.encode(batch_texts, convert_to_tensor=True)
                
                # Calculate similarities
                cosine_scores = util.cos_sim(query_embeddings, chunk_embeddings)
                max_scores = cosine_scores.max(dim=0).values  # Max across queries
                
                # Filter by threshold
                for j, (chunk, score) in enumerate(zip(batch_chunks, max_scores)):
                    if score >= threshold:
                        chunk['semantic_score'] = float(score)
                        filtered_chunks.append(chunk)
                        
            except Exception as e:
                self.logger.error(f"Error in batch processing: {e}")
                # Fallback to individual processing
                for chunk in batch_chunks:
                    if self._single_chunk_filter(chunk, queries, threshold):
                        filtered_chunks.append(chunk)

        # Sort by semantic score
        filtered_chunks.sort(key=lambda x: x.get('semantic_score', 0), reverse=True)
        
        self.logger.debug(f"✅ Batch filter: {len(filtered_chunks)}/{len(chunks)} chunks passed")
        return filtered_chunks

    def _single_chunk_filter(self, chunk: dict, queries: List[str], threshold: float) -> bool:
        """Fallback single chunk filtering"""
        try:
            chunk_text = chunk['content']
            chunk_emb = list(self._get_query_embedding(chunk_text))
            
            max_score = 0.0
            for query in queries:
                query_emb = list(self._get_query_embedding(query))
                score = self._cosine_similarity(query_emb, chunk_emb)
                max_score = max(max_score, score)
            
            if max_score >= threshold:
                chunk['semantic_score'] = float(max_score)
                return True
                
        except Exception as e:
            self.logger.error(f"Error in single chunk filter: {e}")
            
        return False

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Fast cosine similarity calculation"""
        try:
            vec1_np = np.array(vec1)
            vec2_np = np.array(vec2)
            
            dot_product = np.dot(vec1_np, vec2_np)
            norm1 = np.linalg.norm(vec1_np)
            norm2 = np.linalg.norm(vec2_np)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
                
            return float(dot_product / (norm1 * norm2))
        except:
            return 0.0

    def _is_valid_chunk(self, chunk: dict) -> bool:
        """Validate chunk structure and content"""
        return (
            isinstance(chunk, dict) and 
            "content" in chunk and 
            isinstance(chunk["content"], str) and 
            len(chunk["content"].strip()) > 20
        )

    def get_cache_stats(self) -> Dict[str, int]:
        """Get caching statistics"""
        total = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total if total > 0 else 0
        
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": hit_rate,
            "precomputed_chunks": len(self.chunk_embeddings_cache)
        }

    def clear_cache(self):
        """Clear all caches"""
        self._get_query_embedding.cache_clear()
        self.chunk_embeddings_cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        self.logger.info("All caches cleared")

    def save_precomputed_embeddings(self, filepath: str):
        """Save pre-computed embeddings to disk"""
        try:
            import pickle
            with open(filepath, 'wb') as f:
                pickle.dump(self.chunk_embeddings_cache, f)
            self.logger.info(f"Saved {len(self.chunk_embeddings_cache)} embeddings to {filepath}")
        except Exception as e:
            self.logger.error(f"Error saving embeddings: {e}")

    def load_precomputed_embeddings(self, filepath: str):
        """Load pre-computed embeddings from disk"""
        try:
            import pickle
            with open(filepath, 'rb') as f:
                self.chunk_embeddings_cache = pickle.load(f)
            self.logger.info(f"Loaded {len(self.chunk_embeddings_cache)} embeddings from {filepath}")
        except Exception as e:
            self.logger.error(f"Error loading embeddings: {e}")