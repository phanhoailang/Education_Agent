from typing import List, Dict
from urllib.parse import urlparse
from modules.rag_module.datatypes.SearchResult import SearchResult
from modules.agents.SearchQueryGeneratorAgent import SearchQueryGeneratorAgent
from modules.agents.FinalLinkSelectorAgent import FinalLinkSelectorAgent
from modules.rag_module.deepsearch.ContentExtractor import ContentExtractor
from sentence_transformers import SentenceTransformer
import numpy as np

class DeepSearchPipeline:
    def __init__(self, llm_client, api_key: str, cse_id: str, embedding_model="all-MiniLM-L6-v2"):
        self.query_agent = SearchQueryGeneratorAgent(llm_client)
        self.selector_agent = FinalLinkSelectorAgent(llm_client)
        self.extractor = ContentExtractor() 
        self.embedder = SentenceTransformer(embedding_model)
        self.api_key = api_key
        self.cse_id = cse_id
        

    def run(self, user_input: str, raw_links: List[Dict], top_k: int = 3) -> List[SearchResult]:
        query, criteria, alt_queries, _, quality, avoid = self.query_agent.run(user_input)

        # Step 1: Convert raw links to SearchResult + score
        all_links = []
        for link in raw_links:
            result = SearchResult(
                title=link.get('title', ''),
                snippet=link.get('snippet', ''),
                url=link.get('url', ''),
                metadata=link
            )
            result.score = self.basic_filtering_score(result, query, quality, avoid)
            all_links.append(result)

        all_links.sort(key=lambda x: x.score, reverse=True)
        top_results = all_links[:5]

        print("\n🎯 TOP 5 sau lọc cơ bản:")
        for i, r in enumerate(top_results):
            print(f"{i+1}. [{r.score:.2f}] {r.title}")
            print(f"   🌐 {urlparse(r.url).netloc}")
            print(f"   📝 {r.snippet[:100]}...\n")

        # Step 2: LLM chọn chung kết
        final_selection = self.selector_agent.run(top_results, user_input, criteria, top_k=top_k)
        return final_selection

    def basic_filtering_score(self, link: SearchResult, topic: str,
                              quality_indicators: List[str], avoid_patterns: List[str]) -> float:
        score = 0.0
        text_combined = f"{link.title} {link.snippet}".lower()

        domain = urlparse(link.url).netloc.lower()
        domain_scores = {
            'vietjack.com': 3.0,
            'loigiaihay.com': 3.0,
            '.edu.vn': 2.8,
            '.gov.vn': 2.8,
            'giaibaitap123.com': 2.5,
            'toanmath.com': 2.5,
            'hoc247.net': 2.0,
            'violet.vn': 2.0,
        }

        base_score = 1.0
        for k, v in domain_scores.items():
            if k in domain:
                base_score = v
                break

        topic_similarity = self.calculate_semantic_score(topic.lower(), text_combined)
        score += topic_similarity * 3.0

        for kw in quality_indicators:
            if kw.lower() in text_combined:
                score += 1.0

        for p in avoid_patterns:
            if p.lower() in text_combined:
                score -= 3.0

        snippet_length = len(link.snippet)
        if snippet_length > 200:
            score += 2.0
        elif snippet_length > 100:
            score += 1.0
        elif snippet_length < 50:
            score -= 1.0

        if 20 < len(link.title) < 120:
            score += 1.0

        score *= base_score
        return max(0.0, score)

    def calculate_semantic_score(self, text1: str, text2: str) -> float:
        try:
            embeddings = self.embedder.encode([text1, text2])
            return float(np.dot(embeddings[0], embeddings[1]) /
                        (np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])))
        except:
            return 0.0
