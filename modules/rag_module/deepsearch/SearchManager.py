import logging
from typing import Dict, List
from functools import lru_cache
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

class SearchManager:
    def __init__(self, api_key: str, cse_id: str, max_results: int = 10):
        self.api_key = api_key
        self.cse_id = cse_id
        self.max_results = max_results

        try:
            self.service = build("customsearch", "v1", developerKey=api_key)
        except Exception as e:
            logger.error(f"Failed to initialize Google Search API: {e}")
            raise e

    @lru_cache(maxsize=100)
    def search_with_cache(self, query: str) -> List[Dict]:
        """
        Gọi Google Custom Search API với caching.
        Trả về danh sách dict với keys: title, snippet, url, displayLink.
        """
        try:
            result = self.service.cse().list(
                q=query,
                cx=self.cse_id,
                num=self.max_results,
                lr='lang_vi'
            ).execute()

            items = result.get("items", [])
            if not isinstance(items, list):
                logger.warning(f"⚠️ Unexpected format from API for query: '{query}'")
                return []

            return [{
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "url": item.get("link", ""),
                "displayLink": item.get("displayLink", "")
            } for item in items]

        except Exception as e:
            logger.error(f"🔍 Search error with query='{query}': {e}")
            return []

    def multi_query_search(self, queries: List[str], max_queries: int = None) -> List[Dict]:
        """
        Thực hiện search với nhiều truy vấn. Gộp và loại trùng URL.
        Trả về list[dict] dùng cho DeepSearchPipeline.
        """
        all_results = []
        seen_urls = set()

        if max_queries:
            queries = queries[:max_queries]

        for query in queries:
            results = self.search_with_cache(query)
            for result in results:
                url = result.get("url")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(result)

        return all_results
