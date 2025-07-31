import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

try:
    from underthesea import word_tokenize, pos_tag, chunk, ner, sent_tokenize
    UNDERTHESEA_AVAILABLE = True
except ImportError:
    UNDERTHESEA_AVAILABLE = False
    logging.warning("Underthesea not available. Some Vietnamese NLP features will be limited.")

try:
    import pyvi
    from pyvi import ViTokenizer
    PYVI_AVAILABLE = True
except ImportError:
    PYVI_AVAILABLE = False
    logging.warning("PyVi not available. Vietnamese word segmentation will be limited.")

@dataclass
class VietnameseTextStats:
    """Thống kê văn bản tiếng Việt."""
    word_count: int
    sentence_count: int
    paragraph_count: int
    avg_words_per_sentence: float
    avg_chars_per_word: float
    special_chars_count: int
    vietnamese_chars_count: int

class VietnameseTextPreprocessor:
    """
    Tiền xử lý văn bản tiếng Việt cho chunking.
    Sử dụng Underthesea và PyVi để xử lý ngôn ngữ Việt hiệu quả.
    """
    
    def __init__(self, 
                 normalize_text: bool = True,
                 remove_extra_whitespace: bool = True,
                 preserve_structure: bool = True):
        """
        Args:
            normalize_text: Chuẩn hóa văn bản (loại bỏ ký tự đặc biệt, v.v.)
            remove_extra_whitespace: Loại bỏ khoảng trắng thừa
            preserve_structure: Giữ nguyên cấu trúc markdown
        """
        self.normalize_text = normalize_text
        self.remove_extra_whitespace = remove_extra_whitespace
        self.preserve_structure = preserve_structure
        
        # Regex patterns cho tiếng Việt
        self.vietnamese_char_pattern = re.compile(
            r'[aàáạảãâầấậẩẫăằắặẳẵeèéẹẻẽêềếệểễiìíịỉĩoòóọỏõôồốộổỗơờớợởỡuùúụủũưừứựửữyỳýỵỷỹdđAÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴEÈÉẸẺẼÊỀẾỆỂỄIÌÍỊỈĨOÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠUÙÚỤỦŨƯỪỨỰỬỮYỲÝỴỶỸDĐ]'
        )
        
        # Patterns để tách câu tiếng Việt
        self.sentence_endings = re.compile(r'[.!?]+\s*')
        self.abbreviations = {
            'TP.', 'ThS.', 'PGS.', 'GS.', 'TS.', 'BS.', 'KS.', 'CN.',
            'Th.', 'Q.', 'P.', 'TT.', 'HCM.', 'SG.', 'HN.'
        }
        
        # Patterns để nhận dạng cấu trúc markdown
        self.markdown_patterns = {
            'header': re.compile(r'^#+\s+(.+)$', re.MULTILINE),
            'list_item': re.compile(r'^\s*[-*+]\s+(.+)$', re.MULTILINE),
            'numbered_list': re.compile(r'^\s*\d+\.\s+(.+)$', re.MULTILINE),
            'code_block': re.compile(r'```.*?```', re.DOTALL),
            'inline_code': re.compile(r'`[^`]+`'),
            'bold': re.compile(r'\*\*(.+?)\*\*'),
            'italic': re.compile(r'\*(.+?)\*'),
            'link': re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
        }
    
    def preprocess(self, text: str) -> str:
        """
        Tiền xử lý văn bản tiếng Việt.
        
        Args:
            text: Văn bản markdown cần xử lý
            
        Returns:
            Văn bản đã được tiền xử lý
        """
        if not text or not text.strip():
            return ""
        
        processed_text = text
        
        # 1. Chuẩn hóa văn bản
        if self.normalize_text:
            processed_text = self._normalize_vietnamese_text(processed_text)
        
        # 2. Xử lý cấu trúc markdown nếu cần
        if self.preserve_structure:
            processed_text = self._preserve_markdown_structure(processed_text)
        
        # 3. Làm sạch khoảng trắng
        if self.remove_extra_whitespace:
            processed_text = self._clean_whitespace(processed_text)
        
        return processed_text
    
    def _normalize_vietnamese_text(self, text: str) -> str:
        """Chuẩn hóa văn bản tiếng Việt."""
        # Thay thế các ký tự Unicode tương đương
        replacements = {
            '"': '"',  # Smart quotes
            '"': '"',
            ''': "'",
            ''': "'",
            '–': '-',  # En dash
            '—': '-',  # Em dash
            '…': '...',  # Ellipsis
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Chuẩn hóa dấu câu tiếng Việt
        text = re.sub(r'\s+([.!?,:;])', r'\1', text)  # Loại bỏ space trước dấu câu
        text = re.sub(r'([.!?])\s*([.!?])+', r'\1', text)  # Loại bỏ dấu câu trùng lặp
        
        return text
    
    def _preserve_markdown_structure(self, text: str) -> str:
        """Bảo toàn cấu trúc markdown quan trọng."""
        # Thêm marker để bảo toàn headers
        text = re.sub(self.markdown_patterns['header'], 
                     r'HEADER_MARKER \1 HEADER_END', text)
        
        # Bảo toàn list items
        text = re.sub(self.markdown_patterns['list_item'], 
                     r'LIST_MARKER \1 LIST_END', text)
        
        # Bảo toàn numbered lists
        text = re.sub(self.markdown_patterns['numbered_list'], 
                     r'NUMLIST_MARKER \1 NUMLIST_END', text)
        
        return text
    
    def _clean_whitespace(self, text: str) -> str:
        """Làm sạch khoảng trắng thừa."""
        # Loại bỏ spaces/tabs thừa
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Loại bỏ newlines thừa nhưng giữ cấu trúc đoạn văn
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Loại bỏ spaces đầu/cuối dòng
        lines = text.split('\n')
        lines = [line.strip() for line in lines]
        text = '\n'.join(lines)
        
        return text.strip()
    
    def tokenize_sentences(self, text: str) -> List[str]:
        """
        Tách câu tiếng Việt chính xác.
        
        Args:
            text: Văn bản cần tách câu
            
        Returns:
            Danh sách các câu
        """
        if UNDERTHESEA_AVAILABLE:
            try:
                sentences = sent_tokenize(text)
                return [s.strip() for s in sentences if s.strip()]
            except Exception as e:
                logging.warning(f"Underthesea sent_tokenize failed: {e}")
        
        # Fallback: Tách câu bằng regex
        sentences = []
        current_sentence = ""
        
        for match in re.finditer(r'[^.!?]*[.!?]+', text):
            sentence = match.group().strip()
            if sentence:
                # Kiểm tra xem có phải abbreviation không
                words = sentence.split()
                if words and words[-1].rstrip('.!?') + '.' in self.abbreviations:
                    current_sentence += sentence + " "
                else:
                    current_sentence += sentence
                    if current_sentence.strip():
                        sentences.append(current_sentence.strip())
                    current_sentence = ""
        
        if current_sentence.strip():
            sentences.append(current_sentence.strip())
        
        return sentences
    
    def tokenize_words(self, text: str) -> List[str]:
        """
        Tách từ tiếng Việt.
        
        Args:
            text: Văn bản cần tách từ
            
        Returns:
            Danh sách các từ
        """
        if UNDERTHESEA_AVAILABLE:
            try:
                return word_tokenize(text)
            except Exception as e:
                logging.warning(f"Underthesea word_tokenize failed: {e}")
        
        if PYVI_AVAILABLE:
            try:
                tokenized = ViTokenizer.tokenize(text)
                return tokenized.split()
            except Exception as e:
                logging.warning(f"PyVi tokenize failed: {e}")
        
        # Fallback: Tách từ đơn giản
        return text.split()
    
    def get_pos_tags(self, text: str) -> List[tuple]:
        """
        Gán nhãn từ loại cho văn bản tiếng Việt.
        
        Args:
            text: Văn bản cần gán nhãn
            
        Returns:
            Danh sách tuple (từ, nhãn_từ_loại)
        """
        if UNDERTHESEA_AVAILABLE:
            try:
                return pos_tag(text)
            except Exception as e:
                logging.warning(f"Underthesea pos_tag failed: {e}")
        
        # Fallback: Không có POS tagging
        words = self.tokenize_words(text)
        return [(word, 'UNKNOWN') for word in words]
    
    def get_chunks(self, text: str) -> List[tuple]:
        """
        Chunking cú pháp (NP, VP chunks) cho tiếng Việt.
        
        Args:
            text: Văn bản cần chunk
            
        Returns:
            Danh sách tuple (chunk, tag, label)
        """
        if UNDERTHESEA_AVAILABLE:
            try:
                return chunk(text)
            except Exception as e:
                logging.warning(f"Underthesea chunk failed: {e}")
        
        # Fallback: Không có chunking
        words = self.tokenize_words(text)
        return [(word, 'UNKNOWN', 'O') for word in words]
    
    def get_text_statistics(self, text: str) -> VietnameseTextStats:
        """
        Tính toán thống kê văn bản tiếng Việt.
        
        Args:
            text: Văn bản cần phân tích
            
        Returns:
            Thống kê văn bản
        """
        words = self.tokenize_words(text)
        sentences = self.tokenize_sentences(text)
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        word_count = len(words)
        sentence_count = len(sentences)
        paragraph_count = len(paragraphs)
        
        avg_words_per_sentence = word_count / sentence_count if sentence_count > 0 else 0
        avg_chars_per_word = sum(len(word) for word in words) / word_count if word_count > 0 else 0
        
        vietnamese_chars = len(self.vietnamese_char_pattern.findall(text))
        special_chars = len(re.findall(r'[^\w\s]', text))
        
        return VietnameseTextStats(
            word_count=word_count,
            sentence_count=sentence_count,
            paragraph_count=paragraph_count,
            avg_words_per_sentence=avg_words_per_sentence,
            avg_chars_per_word=avg_chars_per_word,
            special_chars_count=special_chars,
            vietnamese_chars_count=vietnamese_chars
        )
    
    def detect_language_confidence(self, text: str) -> float:
        """
        Phát hiện độ tin cậy văn bản là tiếng Việt.
        
        Args:
            text: Văn bản cần kiểm tra
            
        Returns:
            Điểm tin cậy từ 0.0 đến 1.0
        """
        if not text:
            return 0.0
        
        total_chars = len(text)
        vietnamese_chars = len(self.vietnamese_char_pattern.findall(text))
        
        # Tính tỷ lệ ký tự tiếng Việt
        vietnamese_ratio = vietnamese_chars / total_chars if total_chars > 0 else 0
        
        # Kiểm tra các từ đặc trưng tiếng Việt
        vietnamese_words = {
            'và', 'của', 'có', 'là', 'trong', 'với', 'được', 'cho', 'từ', 'một',
            'các', 'này', 'đó', 'để', 'người', 'những', 'việc', 'như', 'về', 'sau'
        }
        
        words = text.lower().split()
        vietnamese_word_count = sum(1 for word in words if word in vietnamese_words)
        word_ratio = vietnamese_word_count / len(words) if words else 0
        
        # Kết hợp cả hai tỷ lệ
        confidence = (vietnamese_ratio * 0.7 + word_ratio * 0.3)
        return min(confidence, 1.0)