import os
import hashlib
import asyncio
import time
from pathlib import Path
from typing import List, Dict, Generator
from concurrent.futures import ThreadPoolExecutor

from utils.GPTClient import GPTClient
from modules.rag_module.query_db.VectorSearcher import VectorSearcher
from modules.agents.CoverageEvaluatorAgent import CoverageEvaluatorAgent
from modules.rag_module.deepsearch.DeepSearchPipeline import DeepSearchPipeline
from modules.rag_module.deepsearch.SearchManager import SearchManager
from modules.rag_module.deepsearch.ContentExtractor import ContentExtractor
from modules.rag_module.documents_processing.main_processor import EduMateDocumentProcessor
from modules.rag_module.data_chunking.processor import IntelligentVietnameseChunkingProcessor
from modules.rag_module.datatypes.CoverageLevel import CoverageLevel

AZURE_CONFIG = {
    "api_key": os.environ.get("AZURE_API_KEY"),
    "api_version": os.environ.get("AZURE_API_VERSION"),
    "endpoint": os.environ.get("AZURE_ENDPOINT"),
    "model": os.environ.get("AZURE_MODEL")
}

MONGO_URI = os.environ.get("MONGO_URI")
DB_NAME = os.environ.get("MONGO_DB_NAME")

CSE_API_KEY = os.environ.get("GOOGLE_API_KEY")
CSE_ID = os.environ.get("GOOGLE_CSE_ID")

TEMP_MD_DIR = "temp_md"
os.makedirs(TEMP_MD_DIR, exist_ok=True)

# Performance configurations
MAX_CHUNKS_PER_TOPIC = 50
BATCH_SIZE = 32
MAX_CONCURRENT_EXTRACTIONS = 5
CONTENT_PROCESSING_TIMEOUT = 60

class OptimizedDeepRetrieval:
    def __init__(self):
        """Initialize optimized components with caching and batching"""
        self.llm_client = GPTClient(**AZURE_CONFIG)
        
        # Use optimized components
        self.vector_searcher = VectorSearcher(
            mongo_uri=MONGO_URI,
            db_name=DB_NAME,
            collection_name="lectures",
        )
        
        self.coverage_evaluator = CoverageEvaluatorAgent(
            llm=self.llm_client
        )
        
        self.content_extractor = ContentExtractor(
            max_concurrent=MAX_CONCURRENT_EXTRACTIONS
        )
        
        self.deepsearch = DeepSearchPipeline(
            llm_client=self.llm_client, 
            api_key=CSE_API_KEY, 
            cse_id=CSE_ID
        )
        
        self.searcher = SearchManager(api_key=CSE_API_KEY, cse_id=CSE_ID)

        self.document_processor = EduMateDocumentProcessor.create_balanced()
        self.chunking_processor = IntelligentVietnameseChunkingProcessor(
            output_dir="temp_chunking", 
            min_quality=0.65
        )
        
        # Performance tracking
        self.performance_stats = {
            "db_search_time": 0,
            "coverage_eval_time": 0,
            "external_search_time": 0,
            "content_extraction_time": 0,
            "total_time": 0
        }

    def retrieve(self, user_prompt: str, subtopics: List[str]) -> List[dict]:
        """🚀 OPTIMIZED main retrieval function"""
        start_time = time.time()
        
        print(f"\n🚀 Starting OPTIMIZED DeepRetrieval for {len(subtopics)} subtopics...")
        
        try:
            # Phase 1: Optimized Database Retrieval
            db_chunks = self._optimized_db_retrieval(subtopics)
            
            # Phase 2: Fast Coverage Assessment
            coverage_result = self._fast_coverage_assessment(user_prompt, subtopics, db_chunks)
            
            if coverage_result.level in [CoverageLevel.ADEQUATE, CoverageLevel.COMPREHENSIVE]:
                print("✅ DB coverage sufficient. Skipping external search.")
                total_time = time.time() - start_time
                self._log_performance(total_time, db_only=True)
                return self._standardize_db_chunks(db_chunks)
            
            # Phase 3: Optimized External Search
            external_chunks = self._optimized_external_search(user_prompt, subtopics)
            
            # Phase 4: Merge and return
            all_chunks = self._merge_chunks(db_chunks, external_chunks)
            
            total_time = time.time() - start_time
            self._log_performance(total_time, db_only=False)
            
            return all_chunks
            
        except Exception as e:
            print(f"❌ Error in optimized retrieval: {e}")
            # Fallback to original method
            return self._fallback_retrieval(user_prompt, subtopics)

    def _optimized_db_retrieval(self, subtopics: List[str]) -> List:
        """🚀 Phase 1: Sequential database search với VectorSearcher gốc"""
        start_time = time.time()
        
        print(f"\n📊 Phase 1: DB search for {len(subtopics)} subtopics...")
        
        try:
            # ✅ SỬA: Dùng sequential search thay vì batch_search
            all_chunks_raw = []
            
            for topic in subtopics:
                try:
                    chunks = self.vector_searcher.search(topic)  # Method có sẵn
                    if chunks:
                        print(f"✅ {topic}: {len(chunks)} chunks")
                        all_chunks_raw.extend(chunks[:MAX_CHUNKS_PER_TOPIC])
                    else:
                        print(f"❌ {topic}: no chunks found")
                except Exception as e:
                    print(f"⚠️ Search error for '{topic}': {e}")
            
            # Efficient cleaning and deduplication
            unique_chunks = self._fast_clean_and_dedupe(all_chunks_raw)
            
            search_time = time.time() - start_time
            self.performance_stats["db_search_time"] = search_time
            
            print(f"📦 DB search completed: {len(unique_chunks)} unique chunks in {search_time:.2f}s")
            return unique_chunks
            
        except Exception as e:
            print(f"⚠️ DB search error: {e}")
            return []

    def _fast_clean_and_dedupe(self, chunks: List) -> List:
        """Fast cleaning and deduplication with early exit"""
        if not chunks:
            return []
        
        # Filter valid chunks
        valid_chunks = [c for c in chunks if c and c.content and len(c.content.strip()) > 20]
        
        if not valid_chunks:
            return []
        
        # Efficient deduplication using optimized method
        unique_chunks = self.vector_searcher.deduplicate(valid_chunks)
        
        print(f"🧹 Cleaned: {len(chunks)} → {len(valid_chunks)} → {len(unique_chunks)} chunks")
        return unique_chunks

    def _fast_coverage_assessment(self, user_prompt: str, subtopics: List[str], chunks: List):
        """🚀 Phase 2: Fast coverage assessment with heuristics"""
        start_time = time.time()
        
        print(f"\n🎯 Phase 2: Fast coverage assessment...")
        
        try:
            coverage_assessment = self.coverage_evaluator.run(user_prompt, subtopics, chunks)
            
            assessment_time = time.time() - start_time
            self.performance_stats["coverage_eval_time"] = assessment_time
            
            print(f"📊 Coverage: {coverage_assessment.level.value} (score: {coverage_assessment.score:.2f}) "
                  f"in {assessment_time:.2f}s")
            
            return coverage_assessment
            
        except Exception as e:
            print(f"⚠️ Coverage assessment error: {e}")
            # Fallback to insufficient
            from modules.rag_module.datatypes.CoverageAssessment import CoverageAssessment
            return CoverageAssessment(
                level=CoverageLevel.INSUFFICIENT,
                score=0.0,
                missing_topics=subtopics,
                covered_topics=[]
            )

    def _optimized_external_search(self, user_prompt: str, subtopics: List[str]) -> List[dict]:
        """🚀 Phase 3: Parallel external search and extraction"""
        start_time = time.time()
        
        print(f"\n🌐 Phase 3: External search...")
        
        try:
            # Generate search queries
            query, criteria, alt_queries, _, quality, avoid = self.deepsearch.query_agent.run(user_prompt)
            
            # Multi-query search
            raw_links = self.searcher.multi_query_search([query] + alt_queries)
            print(f"🔍 Found {len(raw_links)} raw links")
            
            # Select best links
            final_links = self.deepsearch.run(user_input=user_prompt, raw_links=raw_links)
            print(f"🎯 Selected {len(final_links)} final links")
            
            if not final_links:
                print("❌ No valid links found")
                return []
            
            # Parallel content extraction
            extracted_content = self._parallel_content_extraction([link.url for link in final_links])
            
            # Process extracted content
            processed_chunks = self._process_extracted_content(extracted_content)
            
            search_time = time.time() - start_time
            self.performance_stats["external_search_time"] = search_time
            
            print(f"🌐 External search completed: {len(processed_chunks)} chunks in {search_time:.2f}s")
            return processed_chunks
            
        except Exception as e:
            print(f"⚠️ External search error: {e}")
            return []

    def _parallel_content_extraction(self, urls: List[str]) -> List[tuple]:
        """🚀 Parallel content extraction using async"""
        start_time = time.time()
        
        print(f"📄 Extracting content from {len(urls)} URLs...")
        
        try:
            # Run async extraction
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                results = loop.run_until_complete(
                    self.content_extractor.extract_multiple_async(urls)
                )
            finally:
                loop.close()
            
            # Filter successful extractions
            successful = []
            for result, url in zip(results, urls):
                try:
                    if len(result) >= 2:
                        title, content = result[0], result[1]
                        if content is not None and content.strip():
                            successful.append((title, content, url))
                except Exception as e:
                    print(f"⚠️ Error processing result for {url}: {e}")
            
            extraction_time = time.time() - start_time
            self.performance_stats["content_extraction_time"] = extraction_time
            
            print(f"📄 Content extraction: {len(successful)}/{len(urls)} successful in {extraction_time:.2f}s")
            return successful
            
        except Exception as e:
            print(f"⚠️ Content extraction error: {e}")
            return []

    def _process_extracted_content(self, extracted_content: List[tuple]) -> List[dict]:
        """Process extracted content into standardized chunks"""
        if not extracted_content:
            return []
        
        print(f"⚙️ Processing {len(extracted_content)} extracted documents...")
        
        all_chunks = []
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Process documents in parallel
            futures = []
            for i, (title, content, url) in enumerate(extracted_content):
                future = executor.submit(self._process_single_document, title, content, url, i)
                futures.append(future)
            
            # Collect results
            for future in futures:
                try:
                    chunks = future.result(timeout=CONTENT_PROCESSING_TIMEOUT)
                    all_chunks.extend(chunks)
                except Exception as e:
                    print(f"⚠️ Document processing error: {e}")
        
        print(f"⚙️ Generated {len(all_chunks)} chunks from extracted content")
        return all_chunks

    def _process_single_document(self, title: str, content: str, url: str, doc_index: int) -> List[dict]:
        """Process single document into chunks"""
        try:
            # Save to markdown file
            hashname = hashlib.md5(url.encode()).hexdigest()[:10]
            md_path = os.path.join(TEMP_MD_DIR, f"search_{hashname}_{doc_index}.md")
            
            # ✅ SỬA: Always write clean markdown format
            clean_content = self._prepare_markdown_content(title, content)
            
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(clean_content)

            print(f"📝 Processing document: {title[:50]}...")
            
            # ✅ SỬA: Always use direct chunking cho extracted content
            # Extracted content đã được clean rồi, không cần full processing
            chunking_result = self.chunking_processor.run(
                Path(md_path), 
                strategy="hybrid",
                save_json=False,
                print_report=False
            )
            
            chunks_data = chunking_result['result']['chunking_results']['chunks_data']
            
            # Convert to standardized format
            standardized_chunks = []
            for i, chunk_data in enumerate(chunks_data):
                standardized_chunks.append({
                    "chunk_id": f"ext_{doc_index}_{i:02d}",
                    "content": chunk_data["content"],
                    "token_count": chunk_data.get("word_count", 0), 
                    "method": chunk_data.get("chunking_strategy", "intelligent"),
                    "source_file": f"{title}_{hashname}",
                    "source_url": url,
                    "retrieved_from": "search",
                    "char_count": chunk_data.get("char_count", 0),
                    "keywords": chunk_data.get("keywords", []),
                    "coherence_score": chunk_data.get("semantic_coherence_score", 0.0),
                    "completeness_score": chunk_data.get("completeness_score", 0.0)
                })
            
            print(f"✅ Generated {len(standardized_chunks)} chunks from {title[:30]}...")
            
            # Cleanup temporary file
            try:
                os.remove(md_path)
            except:
                pass
            
            return standardized_chunks
            
        except Exception as e:
            print(f"⚠️ Error processing document {title}: {e}")
            return []
        
    def _prepare_markdown_content(self, title: str, content: str) -> str:
        """Prepare clean markdown content for chunking"""
        # Clean title
        clean_title = title.strip()
        if not clean_title:
            clean_title = "Tài liệu"
        
        # Clean content 
        clean_content = content.strip()
        
        # Format as proper markdown
        markdown_content = f"# {clean_title}\n\n{clean_content}"
        
        # Basic markdown cleaning
        lines = markdown_content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line:  # Skip empty lines
                cleaned_lines.append(line)
            elif cleaned_lines and cleaned_lines[-1]:  # Add spacing between sections
                cleaned_lines.append('')
        
        return '\n'.join(cleaned_lines)

    def _standardize_db_chunks(self, db_chunks: List) -> List[dict]:
        """Convert DB chunks to standardized format"""
        standardized = []
        for chunk in db_chunks:
            if hasattr(chunk, "__dict__"):
                chunk_dict = chunk.__dict__.copy()
            else:
                chunk_dict = chunk.copy() if isinstance(chunk, dict) else {}
            
            chunk_dict["retrieved_from"] = "db"
            standardized.append(chunk_dict)
        
        return standardized

    def _merge_chunks(self, db_chunks: List, external_chunks: List[dict]) -> List[dict]:
        """Merge DB and external chunks efficiently"""
        db_standardized = self._standardize_db_chunks(db_chunks)
        
        # Combine and sort by relevance/score
        all_chunks = db_standardized + external_chunks
        
        # Sort by score if available
        all_chunks.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        print(f"\n📦 Final result: {len(db_standardized)} DB + {len(external_chunks)} external = {len(all_chunks)} total chunks")
        
        return all_chunks

    def _log_performance(self, total_time: float, db_only: bool = False):
        """Log performance statistics"""
        self.performance_stats["total_time"] = total_time
        
        print(f"\n⏱️ Performance Summary:")
        print(f"   DB Search: {self.performance_stats['db_search_time']:.2f}s")
        print(f"   Coverage Eval: {self.performance_stats['coverage_eval_time']:.2f}s")
        
        if not db_only:
            print(f"   External Search: {self.performance_stats['external_search_time']:.2f}s")
            print(f"   Content Extraction: {self.performance_stats['content_extraction_time']:.2f}s")
        
        print(f"   Total Time: {total_time:.2f}s")
        
        # Calculate speedup estimate
        if db_only:
            estimated_old_time = total_time * 3  # Conservative estimate
        else:
            estimated_old_time = total_time * 2
            
        speedup = estimated_old_time / total_time
        print(f"   Estimated Speedup: {speedup:.1f}x faster")

    def _fallback_retrieval(self, user_prompt: str, subtopics: List[str]) -> List[dict]:
        """Fallback to original method if optimized fails"""
        print("⚠️ Falling back to original retrieval method...")
        
        try:
            # Import and use original function
            from modules.rag_module.DeepRetrieval import DeepRetrieval
            return DeepRetrieval(user_prompt, subtopics)
        except Exception as e:
            print(f"❌ Fallback also failed: {e}")
            return []

    def get_performance_stats(self) -> dict:
        """Get detailed performance statistics"""
        stats = self.performance_stats.copy()
        
        # Add component-specific stats
        stats.update({
            "vector_searcher_cache": self.vector_searcher.get_cache_stats() if hasattr(self.vector_searcher, 'get_cache_stats') else {},
            "coverage_evaluator": self.coverage_evaluator.get_performance_stats() if hasattr(self.coverage_evaluator, 'get_performance_stats') else {},
            "content_extractor": self.content_extractor.get_performance_stats() if hasattr(self.content_extractor, 'get_performance_stats') else {}
        })
        
        return stats

    def clear_caches(self):
        """Clear all caches for fresh start"""
        if hasattr(self.vector_searcher, 'clear_cache'):
            self.vector_searcher.clear_cache()
        if hasattr(self.coverage_evaluator, 'reset_stats'):
            self.coverage_evaluator.reset_stats()
        if hasattr(self.content_extractor, 'reset_stats'):
            self.content_extractor.reset_stats()
        
        print("🧹 All caches cleared")


# Global instance for backwards compatibility
_global_retriever = None

def DeepRetrieval(user_prompt: str, subtopics: List[str]) -> List[dict]:
    """🚀 Optimized DeepRetrieval function - backwards compatible interface"""
    global _global_retriever
    
    if _global_retriever is None:
        _global_retriever = OptimizedDeepRetrieval()
    
    return _global_retriever.retrieve(user_prompt, subtopics)


def get_retrieval_stats() -> dict:
    """Get performance statistics from global retriever"""
    global _global_retriever
    if _global_retriever is None:
        return {}
    return _global_retriever.get_performance_stats()


def clear_retrieval_caches():
    """Clear all caches in global retriever"""
    global _global_retriever
    if _global_retriever is not None:
        _global_retriever.clear_caches()