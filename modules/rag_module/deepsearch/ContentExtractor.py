import json
import re
import asyncio
import aiohttp
import aiofiles
from typing import Tuple, Optional, List
from urllib.parse import urlparse, parse_qs
from io import BytesIO
import pdfplumber
from readability import Document
from bs4 import BeautifulSoup
import logging
import time


class ContentExtractor:
    def __init__(self, config_file: str = "data/cleaning_rules.json", 
                 max_concurrent: int = 5, timeout: int = 30):
        # Async session management
        self.max_concurrent = max_concurrent
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # Headers để avoid blocking
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        # Configuration
        self.config_file = config_file
        self.clean_contains = []
        self.clean_regex = []

        # Performance tracking
        self.extraction_times = []
        self.success_count = 0
        self.error_count = 0
        
        self.logger = logging.getLogger(__name__)

        # Load cleaning rules
        self.load_cleaning_rules()

    def load_cleaning_rules(self, config_file: str = None):
        """Load cleaning rules from JSON file"""
        config_file = config_file or self.config_file
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                clean_rules = json.load(f)
            self.clean_contains = clean_rules.get("contains", [])
            self.clean_regex = [re.compile(p, re.IGNORECASE) for p in clean_rules.get("regex", [])]
            self.logger.info(f"✅ Loaded {len(self.clean_contains)} contains rules, {len(self.clean_regex)} regex rules")
        except FileNotFoundError:
            self.clean_contains = []
            self.clean_regex = []
            self.logger.warning("No cleaning rules file found, using empty rules")

    def convert_to_latex_math(self, text: str) -> str:
        """Convert mathematical expressions to LaTeX format"""
        # Decimal numbers
        text = re.sub(r'(\d+),(\d+)', r'\1.\2', text)

        # Absolute values
        text = re.sub(r'\|([^\|]+)\|', r'\\left|\1\\right|', text)

        # Mathematical symbols and functions
        text = re.sub(r'\(k ?∈ ?ℤ\)', r'(k \\in \\mathbb{Z})', text)
        text = text.replace("sin", r"\\sin").replace("cos", r"\\cos").replace("tan", r"\\tan")
        text = text.replace("log", r"\\log").replace("ln", r"\\ln").replace("sqrt", r"\\sqrt")
        text = text.replace("pi", r"\\pi").replace("e", r"\\mathrm{e}")
        text = text.replace("lim", r"\\lim").replace("×", r"\\times").replace("÷", r"\\div")
        text = text.replace("≠", r"\\ne").replace("≈", r"\\approx").replace("∑", r"\\sum")
        text = text.replace("∈", r"\\in").replace("ℤ", r"\\mathbb{Z}").replace("ℝ", r"\\mathbb{R}")
        text = text.replace("≥", r"\\ge").replace("≤", r"\\le").replace("°", r"^\\circ").replace("Δ", r"\\Delta")

        # Fractions
        text = re.sub(r'(?<!\\)(\d+)\s*/\s*(\d+)', r'\\frac{\1}{\2}', text)
        text = re.sub(r'(\d+)\s*\\pi\s*/\s*(\d+)', r'\\frac{\1\\pi}{\2}', text)
        text = re.sub(r'(?<!\\)(\d+)π', r'\1\\pi', text)

        # Exponents
        text = re.sub(r'([a-zA-Z])\s*(\d+)', r'\1^{\2}', text)

        # Escape special characters
        text = text.replace("\\", "\\textbackslash{}").replace("%", "\\%").replace("&", "\\&")

        return text

    def clean_text_and_format(self, text: str) -> str:
        """Clean and format text using chain rules"""
        lines = text.split("\n")
        seen = set()
        result = []

        for line in lines:
            line = line.strip()
            if not line or line in seen:
                continue

            # Apply contains filter
            if any(key.lower() in line.lower() for key in self.clean_contains):
                continue

            # Apply regex filter
            if any(regex.search(line) for regex in self.clean_regex):
                continue

            # Skip short meaningless lines
            if len(line) <= 5 and not re.search(r'\w{3,}', line):
                continue

            seen.add(line)
            result.append(line)

        return "\n\n".join(result)

    def validate_content_quality(self, content: str, title: str = "",
                               min_length: int = 200, min_words: int = 50, max_words: int = 20000,
                               edu_keywords: list = None, spam_patterns: list = None,
                               min_edu_keywords: int = 2, max_spam_patterns: int = 2) -> Tuple[bool, str]:
        """Enhanced content quality validation with configurable parameters"""
        if not content or len(content.strip()) < min_length:
            return False, "Nội dung quá ngắn"

        words = content.split()
        if len(words) < min_words:
            return False, "Số từ quá ít"
        elif len(words) > max_words:
            return False, "Nội dung quá dài"

        # Check for spam patterns
        if spam_patterns is None:
            spam_patterns = ['click here', 'download now', 'free trial', 'limited time']
        spam_found = [pattern for pattern in spam_patterns if pattern in content.lower()]

        if len(spam_found) > max_spam_patterns:
            return False, "Có dấu hiệu spam"

        return True, f"Chất lượng tốt"

    def clean_content(self, content: str, noise_patterns: list = None) -> str:
        """Enhanced content cleaning with configurable noise patterns"""
        # Remove extra whitespace
        content = re.sub(r'\n\s*\n', '\n\n', content)
        content = re.sub(r' +', ' ', content)

        # Remove noise patterns
        if noise_patterns is None:
            noise_patterns = [
                r'Quảng cáo.*?\n',
                r'Đăng ký.*?\n',
                r'Theo dõi.*?\n',
                r'Facebook.*?\n',
                r'Zalo.*?\n',
                r'Liên hệ.*?\n',
                r'Hotline.*?\n',
                r'Email.*?\n'
            ]

        for pattern in noise_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)

        # Remove URLs
        content = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', content)

        # Apply chain rules cleaning
        content = self.clean_text_and_format(content)

        return content.strip()

    # 🚀 MAIN OPTIMIZATION: Async batch extraction
    async def extract_multiple_async(self, urls: List[str]) -> List[Tuple[Optional[str], Optional[str], str]]:
        """🚀 Extract content từ multiple URLs parallel"""
        if not urls:
            return []

        start_time = time.time()
        
        async with aiohttp.ClientSession(
            headers=self.headers,
            timeout=self.timeout,
            connector=aiohttp.TCPConnector(limit=self.max_concurrent, limit_per_host=3)
        ) as session:
            tasks = [self._extract_single_async(session, url) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Exception extracting {urls[i]}: {result}")
                processed_results.append((None, None, str(result)))
                self.error_count += 1
            else:
                processed_results.append(result)
                if result[1]:  # If content extracted successfully
                    self.success_count += 1
                else:
                    self.error_count += 1

        total_time = time.time() - start_time
        self.extraction_times.append(total_time)
        
        self.logger.info(f"🚀 Extracted {len(urls)} URLs in {total_time:.2f}s "
                        f"(avg: {total_time/len(urls):.2f}s per URL)")
        
        return processed_results

    async def _extract_single_async(self, session: aiohttp.ClientSession, url: str) -> Tuple[Optional[str], Optional[str], str]:
        """Extract content từ single URL async"""
        async with self.semaphore:  # Limit concurrent requests
            try:
                # Check if URL is safe first
                if not self._is_safe_url(url):
                    return None, None, f"Unsafe URL: {url}"

                # Try to detect PDF viewer URL
                viewer_url = await self._get_viewer_url_async(session, url)
                
                if viewer_url:
                    self.logger.debug(f"[PDF VIEWER] Detected PDF: {viewer_url}")
                    return await self._extract_pdf_content_async(session, viewer_url)
                else:
                    return await self._extract_html_content_async(session, url)

            except asyncio.TimeoutError:
                return None, None, f"Timeout extracting: {url}"
            except Exception as e:
                self.logger.error(f"[EXTRACT ERROR] {url}: {e}")
                return None, None, f"Extraction error: {str(e)}"

    def _is_safe_url(self, url: str) -> bool:
        """Basic URL safety validation"""
        try:
            parsed = urlparse(url)
            
            # Check scheme
            if parsed.scheme not in ['http', 'https']:
                return False
                
            # Check for malicious patterns
            malicious_patterns = [
                'localhost', '127.0.0.1', '0.0.0.0',
                'file://', 'ftp://', 'javascript:',
                '10.', '172.', '192.168.'
            ]
            
            url_lower = url.lower()
            if any(pattern in url_lower for pattern in malicious_patterns):
                return False
                
            return True
        except:
            return False

    async def _get_viewer_url_async(self, session: aiohttp.ClientSession, page_url: str) -> Optional[str]:
        """Get PDF viewer URL if exists - async version"""
        try:
            async with session.get(page_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    return None
                    
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")

                iframe = soup.find("iframe", src=lambda x: x and "viewer.html" in x)
                if iframe:
                    src = iframe["src"]
                    if src.startswith("/"):
                        parsed = urlparse(page_url)
                        return f"{parsed.scheme}://{parsed.netloc}{src}"
                    return src
                return None
        except:
            return None

    async def _extract_pdf_content_async(self, session: aiohttp.ClientSession, viewer_url: str) -> Tuple[str, str]:
        """Extract content from PDF viewer - async version"""
        try:
            file_url = parse_qs(urlparse(viewer_url).query).get("file", [None])[0]
            if not file_url:
                return None, None

            async with session.get(file_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    return None, None
                    
                pdf_content = await response.read()
                
                # Process PDF in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                content = await loop.run_in_executor(None, self._process_pdf_sync, pdf_content)
                
                if content:
                    return "Tài liệu PDF", content
                    
        except Exception as e:
            self.logger.error(f"[PDF ERROR] {e}")
            
        return None, None

    def _process_pdf_sync(self, pdf_content: bytes) -> str:
        """Synchronous PDF processing (run in executor)"""
        try:
            with pdfplumber.open(BytesIO(pdf_content)) as pdf:
                pages_text = []
                for page in pdf.pages[:20]:  # Limit to 20 pages
                    text = page.extract_text()
                    if text:
                        pages_text.append(text)

                content = "\n\n".join(pages_text)
                return self.clean_text_and_format(content)
        except Exception as e:
            self.logger.error(f"PDF processing error: {e}")
            return ""

    async def _extract_html_content_async(self, session: aiohttp.ClientSession, url: str) -> Tuple[str, str]:
        """Extract content from HTML page - async version"""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status != 200:
                    return None, None
                    
                html = await response.text()
                
                # Process HTML in thread pool
                loop = asyncio.get_event_loop()
                title, content = await loop.run_in_executor(None, self._process_html_sync, html)
                
                if content:
                    content = self.clean_content(content)
                    is_valid, reason = self.validate_content_quality(content, title)

                    if is_valid:
                        return title, content
                    else:
                        self.logger.debug(f"[QUALITY] {reason} for {url}")
                        return None, None

        except Exception as e:
            self.logger.error(f"[HTML ERROR] {url}: {e}")
            
        return None, None

    def _process_html_sync(self, html: str) -> Tuple[str, str]:
        """Synchronous HTML processing (run in executor)"""
        try:
            # Use readability for main content extraction
            doc = Document(html)
            title = doc.short_title() or "Tài liệu Web"
            summary_html = doc.summary()

            # Parse with BeautifulSoup for further cleaning
            soup = BeautifulSoup(summary_html, "html.parser")

            # Remove unwanted elements
            unwanted_tags = ["script", "style", "nav", "footer", "header", "form", "noscript"]
            for tag in soup(unwanted_tags):
                tag.decompose()

            # Find main content area
            main_content = soup.find(['article', 'main']) or soup
            content_parts = []
            seen_texts = set()

            # Extract content from relevant tags
            target_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li']
            
            for tag in main_content.find_all(target_tags):
                text = tag.get_text(strip=True)
                if text and len(text) > 10 and text not in seen_texts:
                    seen_texts.add(text)
                    if tag.name.startswith('h'):
                        level = '#' * int(tag.name[1])
                        content_parts.append(f"{level} {text}")
                    elif tag.name == 'li':
                        content_parts.append(f"- {text}")
                    else:
                        content_parts.append(text)

            content = "\n\n".join(content_parts)
            return title, self.clean_text_and_format(content)
            
        except Exception as e:
            self.logger.error(f"HTML processing error: {e}")
            return None, None

    # Backward compatibility methods
    def extract_with_timeout(self, url: str, timeout: int = 30, subject_hint: str = "") -> Tuple[Optional[str], Optional[str], str]:
        """Backward compatibility - single URL extraction"""
        try:
            # Run async method in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                results = loop.run_until_complete(self.extract_multiple_async([url]))
                return results[0] if results else (None, None, "No results")
            finally:
                loop.close()
                
        except Exception as e:
            return None, None, f"Sync extraction error: {str(e)}"

    def get_performance_stats(self) -> dict:
        """Get extraction performance statistics"""
        total_extractions = self.success_count + self.error_count
        success_rate = self.success_count / total_extractions if total_extractions > 0 else 0
        avg_time = sum(self.extraction_times) / len(self.extraction_times) if self.extraction_times else 0
        
        return {
            "total_extractions": total_extractions,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": success_rate,
            "avg_extraction_time": avg_time,
            "total_batches": len(self.extraction_times)
        }

    def reset_stats(self):
        """Reset performance counters"""
        self.extraction_times = []
        self.success_count = 0
        self.error_count = 0
