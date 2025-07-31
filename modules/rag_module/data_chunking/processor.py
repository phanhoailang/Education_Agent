import json
import logging
import time
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Chunking imports
from .chunkers import (
    VietnameseTextChunker,
    HybridVietnameseChunker,
    SemanticVietnameseChunker,
    RecursiveVietnameseChunker
)
from .chunking_strategies import (
    FixedSizeStrategy,
    SentenceAwareStrategy,
    SemanticStrategy,
    RecursiveStrategy
)
from .chunk_evaluator import ChunkQualityEvaluator
from .preprocessor import VietnameseTextPreprocessor
from .chunk_metadata import ChunkMetadata

# Setup logging
logger = logging.getLogger(__name__)

class DocumentType(Enum):
    """Phân loại loại tài liệu."""
    ACADEMIC = "academic"       # Học thuật, nghiên cứu
    EDUCATIONAL = "educational" # Giáo dục, bài giảng  
    TECHNICAL = "technical"     # Kỹ thuật, hướng dẫn
    NARRATIVE = "narrative"     # Tường thuật, câu chuyện
    STRUCTURED = "structured"   # Có cấu trúc rõ ràng
    MIXED = "mixed"            # Hỗn hợp nhiều kiểu
    UNKNOWN = "unknown"        # Không xác định

@dataclass
class StrategyPriority:
    """Cấu hình ưu tiên strategy."""
    name: str
    priority: int              # 1 = cao nhất
    min_doc_size: int         # Kích thước tài liệu tối thiểu
    max_doc_size: int         # Kích thước tài liệu tối đa
    suitable_types: List[DocumentType]
    min_quality: float        # Điểm chất lượng tối thiểu
    default_params: Dict[str, Any]

class IntelligentVietnameseChunkingProcessor:
    """
    Processor thông minh với cơ chế ưu tiên và fallback.
    
    Workflow:
    1. Phân tích văn bản → xác định loại tài liệu
    2. Thử strategies theo thứ tự ưu tiên
    3. Đánh giá chất lượng → fallback nếu không đạt
    4. Trả về kết quả tốt nhất
    """
    
    def __init__(self, output_dir: str = "chunking_output", min_quality: float = 0.65):
        """
        Args:
            output_dir: Thư mục lưu kết quả
            min_quality: Điểm chất lượng tối thiểu chấp nhận
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.min_quality = min_quality
        
        # Tạo evaluator
        self.evaluator = ChunkQualityEvaluator(
            min_acceptable_coherence=0.6,
            min_acceptable_completeness=0.7,
            target_chunk_size=1000
        )
        
        # Preprocessor
        self.preprocessor = VietnameseTextPreprocessor(
            normalize_text=True,
            remove_extra_whitespace=True,
            preserve_structure=True
        )
        
        # Cấu hình strategies theo thứ tự ưu tiên
        self.strategy_priorities = [
            StrategyPriority(
                name="hybrid",
                priority=1,
                min_doc_size=1000,
                max_doc_size=100000,
                suitable_types=[DocumentType.MIXED, DocumentType.EDUCATIONAL, DocumentType.ACADEMIC],
                min_quality=0.65,
                default_params={
                    'selection_criteria': 'balanced',
                    'chunk_size': 1000,
                    'overlap_ratio': 0.2
                }
            ),
            StrategyPriority(
                name="semantic",
                priority=2,
                min_doc_size=2000,
                max_doc_size=50000,
                suitable_types=[DocumentType.ACADEMIC, DocumentType.EDUCATIONAL, DocumentType.TECHNICAL],
                min_quality=0.75,
                default_params={
                    'embedding_model': 'all-MiniLM-L6-v2',
                    'similarity_threshold': 0.75,
                    'adaptive_threshold': True
                }
            ),
            StrategyPriority(
                name="recursive",
                priority=3,
                min_doc_size=500,
                max_doc_size=200000,
                suitable_types=[DocumentType.STRUCTURED, DocumentType.TECHNICAL, DocumentType.NARRATIVE],
                min_quality=0.6,
                default_params={
                    'base_chunk_size': 1000,
                    'overlap_ratio': 0.2,
                    'adaptive_sizing': True,
                    'preserve_sentences': True
                }
            ),
            StrategyPriority(
                name="sentence",
                priority=4,
                min_doc_size=300,
                max_doc_size=50000,
                suitable_types=[DocumentType.EDUCATIONAL, DocumentType.NARRATIVE],
                min_quality=0.55,
                default_params={
                    'target_size': 800,
                    'max_sentences': 8
                }
            ),
            StrategyPriority(
                name="fixed",
                priority=5,              # Fallback cuối cùng
                min_doc_size=100,
                max_doc_size=1000000,    # Luôn hoạt động
                suitable_types=list(DocumentType),
                min_quality=0.4,
                default_params={
                    'chunk_size': 1000,
                    'overlap': 200
                }
            )
        ]
        
        logger.info(f"✅ IntelligentProcessor initialized with min_quality: {self.min_quality}")
        logger.info(f"   • Strategies configured: {len(self.strategy_priorities)}")
    
    def read_file(self, file_path: Path) -> str:
        """Đọc nội dung file markdown."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                raise ValueError("File rỗng hoặc chỉ chứa whitespace")
            
            logger.info(f"📖 Đọc file thành công: {file_path.name} ({len(content):,} ký tự)")
            return content
            
        except FileNotFoundError:
            logger.error(f"❌ Không tìm thấy file: {file_path}")
            raise
        except UnicodeDecodeError:
            logger.error(f"❌ Lỗi encoding file: {file_path}")
            raise
        except Exception as e:
            logger.error(f"❌ Lỗi đọc file {file_path}: {e}")
            raise
    
    def analyze_document(self, content: str) -> Tuple[DocumentType, Dict[str, Any]]:
        """
        Phân tích tài liệu để xác định loại và đặc điểm.
        
        Args:
            content: Nội dung tài liệu
            
        Returns:
            Tuple (DocumentType, analysis_info)
        """
        logger.info("🔍 Phân tích đặc điểm tài liệu...")
        
        # Thống kê cơ bản
        stats = self.preprocessor.get_text_statistics(content)
        vietnamese_ratio = self.preprocessor.detect_language_confidence(content)
        
        # Phân tích cấu trúc
        has_headers = bool(re.search(r'^#+\s', content, re.MULTILINE))
        has_lists = bool(re.search(r'^[\s]*[-*+]\s|^\s*\d+\.\s', content, re.MULTILINE))
        has_code = bool(re.search(r'```|`[^`]+`', content))
        
        # Phát hiện thuật ngữ kỹ thuật
        technical_indicators = len(re.findall(r'[A-Z]{2,}|[a-z]+\([^)]*\)|[α-ω]|\d+\.\d+|%|\$', content))
        has_technical = technical_indicators > len(content) * 0.01
        
        # Tính điểm phức tạp
        complexity_score = min(1.0, (
            min(stats.avg_words_per_sentence / 20, 1.0) * 0.3 +
            min(technical_indicators / 100, 1.0) * 0.3 +
            min(stats.paragraph_count / 50, 1.0) * 0.2 +
            (1.0 - vietnamese_ratio) * 0.2
        ))
        
        # Tính điểm cấu trúc  
        structure_score = (
            (1.0 if has_headers else 0.0) * 0.4 +
            (1.0 if has_lists else 0.0) * 0.3 +
            (1.0 if has_code else 0.0) * 0.1 +
            min(stats.paragraph_count / 20, 1.0) * 0.2
        )
        
        # Xác định loại tài liệu
        doc_type = self._classify_document_type(
            stats, complexity_score, structure_score, 
            has_headers, has_lists, has_technical, vietnamese_ratio
        )
        
        analysis_info = {
            'doc_type': doc_type,
            'complexity_score': complexity_score,
            'structure_score': structure_score,
            'vietnamese_ratio': vietnamese_ratio,
            'avg_sentence_length': stats.avg_words_per_sentence,
            'paragraph_count': stats.paragraph_count,
            'has_headers': has_headers,
            'has_lists': has_lists,
            'has_technical': has_technical,
            'file_size': len(content)
        }
        
        logger.info(f"📊 Phân tích hoàn tất:")
        logger.info(f"   • Loại tài liệu: {doc_type.value}")
        logger.info(f"   • Độ phức tạp: {complexity_score:.2f}")
        logger.info(f"   • Cấu trúc: {structure_score:.2f}")
        logger.info(f"   • Tiếng Việt: {vietnamese_ratio:.1%}")
        
        return doc_type, analysis_info
    
    def _classify_document_type(self, stats, complexity_score, structure_score,
                               has_headers, has_lists, has_technical, vietnamese_ratio) -> DocumentType:
        """Phân loại loại tài liệu."""
        
        # Academic: phức tạp, có cấu trúc, thuật ngữ kỹ thuật
        if (complexity_score > 0.6 and structure_score > 0.5 and 
            has_technical and has_headers):
            return DocumentType.ACADEMIC
        
        # Educational: cấu trúc tốt, độ phức tạp vừa
        if (structure_score > 0.6 and 0.3 < complexity_score < 0.7 and
            (has_headers or has_lists)):
            return DocumentType.EDUCATIONAL
        
        # Technical: có thuật ngữ kỹ thuật, có cấu trúc
        if has_technical and structure_score > 0.4:
            return DocumentType.TECHNICAL
        
        # Structured: có headers, lists, cấu trúc rõ ràng
        if structure_score > 0.7 and (has_headers and has_lists):
            return DocumentType.STRUCTURED
        
        # Narrative: câu dài, ít cấu trúc, nhiều tiếng Việt
        if (stats.avg_words_per_sentence > 15 and structure_score < 0.4 and
            vietnamese_ratio > 0.8):
            return DocumentType.NARRATIVE
        
        # Mixed: trung bình về các chỉ số
        if 0.3 < complexity_score < 0.7 and 0.3 < structure_score < 0.7:
            return DocumentType.MIXED
        
        return DocumentType.UNKNOWN
    
    def get_prioritized_strategies(self, doc_type: DocumentType, doc_size: int) -> List[StrategyPriority]:
        """Lấy danh sách strategies theo thứ tự ưu tiên."""
        
        suitable_strategies = []
        
        for strategy_config in self.strategy_priorities:
            # Kiểm tra phù hợp với loại tài liệu và kích thước
            if strategy_config.min_doc_size <= doc_size <= strategy_config.max_doc_size:
                suitable_strategies.append(strategy_config)
        
        # Sắp xếp theo priority (1 = cao nhất)
        suitable_strategies.sort(key=lambda x: x.priority)
        
        # Luôn có ít nhất fixed strategy
        if not suitable_strategies:
            fixed_strategy = next(s for s in self.strategy_priorities if s.name == "fixed")
            suitable_strategies = [fixed_strategy]
        
        return suitable_strategies
    
    def create_chunker_from_config(self, strategy_config: StrategyPriority, custom_params: Dict = None):
        """Tạo chunker từ config."""
        
        params = strategy_config.default_params.copy()
        if custom_params:
            params.update(custom_params)
        
        strategy_name = strategy_config.name
        
        if strategy_name == 'semantic':
            return SemanticVietnameseChunker(
                preprocessor=self.preprocessor,
                **params
            )
        
        elif strategy_name == 'hybrid':
            chunk_size = params.get('chunk_size', 1000)
            overlap_ratio = params.get('overlap_ratio', 0.2)
            
            strategies = [
                FixedSizeStrategy(chunk_size=chunk_size, overlap=int(chunk_size * overlap_ratio)),
                SentenceAwareStrategy(target_size=chunk_size),
                RecursiveStrategy(chunk_size=chunk_size, chunk_overlap=int(chunk_size * overlap_ratio))
            ]
            
            return HybridVietnameseChunker(
                strategies=strategies,
                selection_criteria=params.get('selection_criteria', 'balanced'),
                preprocessor=self.preprocessor
            )
        
        elif strategy_name == 'recursive':
            return RecursiveVietnameseChunker(
                preprocessor=self.preprocessor,
                **params
            )
        
        elif strategy_name == 'sentence':
            return VietnameseTextChunker(
                SentenceAwareStrategy(
                    target_size=params.get('target_size', 800),
                    max_sentences=params.get('max_sentences', 8)
                ),
                preprocessor=self.preprocessor
            )
        
        elif strategy_name == 'fixed':
            return VietnameseTextChunker(
                FixedSizeStrategy(
                    chunk_size=params.get('chunk_size', 1000),
                    overlap=params.get('overlap', 200)
                ),
                preprocessor=self.preprocessor
            )
        
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")
    
    def process_chunking(self, file_path: Path, custom_strategy: str = None, **kwargs) -> Dict[str, Any]:
        """
        Xử lý chunking thông minh với ưu tiên strategies.
        
        Args:
            file_path: Đường dẫn file
            custom_strategy: Strategy cụ thể (bỏ qua intelligent nếu có)
            **kwargs: Parameters tùy chỉnh
            
        Returns:
            Kết quả chunking và thông tin attempts
        """
        start_time = time.time()
        
        logger.info(f"🧠 Bắt đầu intelligent chunking: {file_path.name}")
        
        # Đọc file
        content = self.read_file(file_path)
        
        # Nếu có custom strategy, sử dụng trực tiếp
        if custom_strategy:
            logger.info(f"🎯 Sử dụng custom strategy: {custom_strategy}")
            return self._process_single_strategy(content, file_path, custom_strategy, start_time, **kwargs)
        
        # Phân tích tài liệu
        doc_type, analysis_info = self.analyze_document(content)
        
        # Lấy strategies theo thứ tự ưu tiên
        prioritized_strategies = self.get_prioritized_strategies(doc_type, len(content))
        
        logger.info(f"📋 Strategies sẽ thử theo thứ tự:")
        for i, strategy in enumerate(prioritized_strategies, 1):
            logger.info(f"   {i}. {strategy.name} (min_quality: {strategy.min_quality})")
        
        # Thử từng strategy theo thứ tự ưu tiên
        attempts = []
        best_result = None
        
        for attempt_num, strategy_config in enumerate(prioritized_strategies, 1):
            logger.info(f"🔄 Attempt {attempt_num}: Trying {strategy_config.name}")
            
            try:
                # Tạo chunker
                chunker = self.create_chunker_from_config(strategy_config, kwargs)
                
                # Chunking
                chunk_start_time = time.time()
                chunks = chunker.chunk_text(content)  # Không truyền source_info
                chunk_time = time.time() - chunk_start_time
                
                if not chunks:
                    logger.warning(f"⚠️  {strategy_config.name} produced no chunks")
                    continue
                
                # Đánh giá chất lượng
                evaluation = self.evaluator.evaluate_chunks(chunks, content)
                quality_score = evaluation.overall_quality_score
                
                attempt_info = {
                    'strategy': strategy_config.name,
                    'params': strategy_config.default_params,
                    'chunks_count': len(chunks),
                    'quality_score': quality_score,
                    'processing_time': chunk_time,
                    'success': quality_score >= strategy_config.min_quality,
                    'chunks': chunks,
                    'evaluation': evaluation
                }
                
                attempts.append(attempt_info)
                
                logger.info(f"   • Quality: {quality_score:.2f} (cần: {strategy_config.min_quality:.2f})")
                logger.info(f"   • Chunks: {len(chunks)}")
                logger.info(f"   • Time: {chunk_time:.2f}s")
                
                # Kiểm tra chất lượng
                if quality_score >= strategy_config.min_quality:
                    logger.info(f"✅ {strategy_config.name} PASSED - sử dụng strategy này!")
                    best_result = attempt_info
                    break
                else:
                    logger.info(f"❌ {strategy_config.name} FAILED - thử strategy tiếp theo")
                    
            except Exception as e:
                logger.error(f"❌ {strategy_config.name} error: {e}")
                attempts.append({
                    'strategy': strategy_config.name,
                    'error': str(e),
                    'success': False
                })
                continue
        
        # Nếu không có strategy nào pass, chọn cái tốt nhất
        if not best_result and attempts:
            successful_attempts = [a for a in attempts if 'quality_score' in a]
            if successful_attempts:
                best_result = max(successful_attempts, key=lambda x: x['quality_score'])
                logger.warning(f"⚠️  Không có strategy nào đạt yêu cầu, chọn tốt nhất: {best_result['strategy']}")
            else:
                logger.error("❌ Tất cả strategies đều thất bại hoàn toàn")
        
        if not best_result:
            raise RuntimeError("❌ Tất cả strategies đều thất bại!")
        
        total_time = time.time() - start_time
        
        # Tạo kết quả cuối cùng
        result = self._build_final_result(
            file_path, content, analysis_info, best_result, attempts, total_time
        )
        
        logger.info(f"🎯 Selected: {best_result['strategy']} (Quality: {best_result['quality_score']:.2f})")
        
        return result
    
    def _process_single_strategy(self, content: str, file_path: Path, strategy_name: str, 
                               start_time: float, **kwargs) -> Dict[str, Any]:
        """Xử lý với một strategy cụ thể."""
        
        # Tìm config strategy
        strategy_config = next((s for s in self.strategy_priorities if s.name == strategy_name), None)
        if not strategy_config:
            raise ValueError(f"Strategy '{strategy_name}' không tồn tại")
        
        # Tạo chunker
        chunker = self.create_chunker_from_config(strategy_config, kwargs)
        
        # Chunking
        chunks = chunker.chunk_text(content)
        
        if not chunks:
            raise RuntimeError(f"Strategy {strategy_name} không tạo ra chunks nào")
        
        # Đánh giá
        evaluation = self.evaluator.evaluate_chunks(chunks, content)
        total_time = time.time() - start_time
        
        # Fake analysis info
        analysis_info = {
            'doc_type': DocumentType.UNKNOWN,
            'complexity_score': 0.5,
            'structure_score': 0.5,
            'file_size': len(content)
        }
        
        result_info = {
            'strategy': strategy_name,
            'chunks_count': len(chunks),
            'quality_score': evaluation.overall_quality_score,
            'chunks': chunks,
            'evaluation': evaluation,
            'success': True
        }
        
        return self._build_final_result(
            file_path, content, analysis_info, result_info, [result_info], total_time
        )
    
    def _build_final_result(self, file_path: Path, content: str, analysis_info: Dict,
                           best_result: Dict, attempts: List, total_time: float) -> Dict[str, Any]:
        """Tạo kết quả cuối cùng."""
        
        return {
            'input_info': {
                'file_path': str(file_path),
                'file_name': file_path.name,
                'file_size': len(content),
                'character_count': len(content),
                'line_count': content.count('\n') + 1,
                'strategy': best_result['strategy']
            },
            
            'document_analysis': {
                **analysis_info,
                'doc_type': analysis_info['doc_type'].value if hasattr(analysis_info.get('doc_type'), 'value') else str(analysis_info.get('doc_type', 'unknown'))
            },
            
            'intelligent_process': {
                'selected_strategy': best_result['strategy'],
                'total_attempts': len(attempts),
                'success_on_attempt': next((i+1 for i, a in enumerate(attempts) if a.get('success')), len(attempts)),
                'total_processing_time': total_time
            },
            
            'chunking_results': {
                'total_chunks': best_result['chunks_count'],
                'chunking_time': best_result.get('processing_time', total_time),
                'total_processing_time': total_time,
                'chunks_data': [chunk.to_dict() for chunk in best_result['chunks']]
            },
            
            'quality_evaluation': {
                'overall_score': best_result['evaluation'].overall_quality_score,
                'coherence_score': best_result['evaluation'].avg_coherence_score,
                'completeness_score': best_result['evaluation'].avg_completeness_score,
                'language_confidence': best_result['evaluation'].avg_language_confidence,
                'chunk_size_stats': {
                    'avg_size': best_result['evaluation'].avg_chunk_size,
                    'min_size': best_result['evaluation'].min_chunk_size,
                    'max_size': best_result['evaluation'].max_chunk_size,
                    'std_size': best_result['evaluation'].std_chunk_size
                },
                'structure_metrics': {
                    'complete_sentences_ratio': best_result['evaluation'].complete_sentences_ratio,
                    'paragraph_preservation': best_result['evaluation'].paragraph_preservation_ratio,
                    'overlap_efficiency': best_result['evaluation'].overlap_efficiency
                },
                'vietnamese_metrics': {
                    'vietnamese_chars_ratio': best_result['evaluation'].vietnamese_chars_ratio,
                    'avg_words_per_sentence': best_result['evaluation'].avg_words_per_sentence,
                    'pos_diversity': best_result['evaluation'].pos_diversity
                },
                'recommendations': best_result['evaluation'].recommendations
            },
            
            'all_attempts': [
                {
                    'strategy': att.get('strategy'),
                    'success': att.get('success', False),
                    'quality_score': att.get('quality_score', 0.0),
                    'chunks_count': att.get('chunks_count', 0),
                    'error': att.get('error')
                }
                for att in attempts
            ],
            
            'metadata': {
                'processing_timestamp': datetime.now().isoformat(),
                'processor_version': "2.0.0",
                'intelligence_enabled': True
            }
        }
    
    def print_report(self, result: Dict[str, Any]):
        """In báo cáo intelligent chunking."""
        
        print("\n" + "=" * 80)
        print("🧠 BÁO CÁO INTELLIGENT CHUNKING")
        print("=" * 80)
        
        # Input info
        input_info = result['input_info']
        print(f"\n📁 THÔNG TIN FILE:")
        print(f"   • File: {input_info['file_name']}")
        print(f"   • Kích thước: {input_info['file_size']:,} ký tự")
        print(f"   • Strategy được chọn: {input_info['strategy']}")
        
        # Document analysis
        if 'document_analysis' in result:
            analysis = result['document_analysis']
            print(f"\n🔍 PHÂN TÍCH TÀI LIỆU:")
            print(f"   • Loại: {analysis.get('doc_type', 'unknown')}")
            print(f"   • Độ phức tạp: {analysis.get('complexity_score', 0):.2f}")
            print(f"   • Cấu trúc: {analysis.get('structure_score', 0):.2f}")
        
        # Intelligence process
        if 'intelligent_process' in result:
            intel = result['intelligent_process']
            print(f"\n🧠 QUÁ TRÌNH THÔNG MINH:")
            print(f"   • Số attempts: {intel['total_attempts']}")
            print(f"   • Thành công ở attempt: {intel['success_on_attempt']}")
            print(f"   • Thời gian tổng: {intel['total_processing_time']:.2f}s")
            
            if intel['success_on_attempt'] == 1:
                print("   🎯 PERFECT! Strategy đầu tiên đã thành công!")
            elif intel['success_on_attempt'] <= 2:
                print("   ✅ GOOD! Nhanh chóng tìm được strategy phù hợp")
            else:
                print("   ⚠️ OK - Cần nhiều attempts")
        
        # Results
        chunking = result['chunking_results']
        quality = result['quality_evaluation']
        
        print(f"\n⚡ KẾT QUẢ:")
        print(f"   • Chunks: {chunking['total_chunks']}")
        print(f"   • Quality: {quality['overall_score']:.2f}/1.00")
        print(f"   • Coherence: {quality['coherence_score']:.2f}")
        print(f"   • Completeness: {quality['completeness_score']:.2f}")
        
        # Attempts summary
        if 'all_attempts' in result:
            print(f"\n📊 TẤT CẢ ATTEMPTS:")
            for i, attempt in enumerate(result['all_attempts'], 1):
                status = "✅" if attempt['success'] else "❌"
                quality_str = f"{attempt['quality_score']:.2f}" if attempt['quality_score'] > 0 else "N/A"
                print(f"   {i}. {attempt['strategy']}: {status} (Quality: {quality_str})")
        
        # Sample chunks
        chunks_data = chunking['chunks_data']
        print(f"\n📄 MẪU CHUNKS (2 chunks đầu):")
        for i, chunk_data in enumerate(chunks_data[:2], 1):
            preview = chunk_data['content'][:100] + "..." if len(chunk_data['content']) > 100 else chunk_data['content']
            print(f"\n   Chunk {i} ({chunk_data['char_count']} chars):")
            print(f"     • Keywords: {', '.join(chunk_data['keywords'][:3])}")
            print(f"     • Preview: {preview}")
        
        print(f"\n🎯 ĐÁNH GIÁ:")
        if quality['overall_score'] >= 0.8:
            print("   🌟 XUẤT SẮC - Intelligent chunking hoạt động tối ưu!")
        elif quality['overall_score'] >= 0.7:
            print("   ✅ TỐT - Intelligent chunking hiệu quả")
        elif quality['overall_score'] >= 0.6:
            print("   ⚠️ CHẤP NHẬN ĐƯỢC - Có thể cần fine-tuning")
        else:
            print("   🔧 CẦN CẢI THIỆN - Tài liệu có đặc điểm phức tạp")
        
        print("\n" + "=" * 80)
    
    def save_json_results(self, result: Dict[str, Any], file_path: Path) -> Dict[str, str]:
        """
        Lưu kết quả ra file JSON - chỉ chunks thuần.
        
        Args:
            result: Kết quả chunking
            file_path: Đường dẫn file gốc
            
        Returns:
            Dict với đường dẫn file đã lưu
        """
        # Tạo tên file output
        input_filename = file_path.stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        strategy = result['input_info']['strategy']
        
        # File chunks thuần cho embedding
        chunks_filename = f"{input_filename}_{strategy}_{timestamp}_chunks.json"
        chunks_path = self.output_dir / chunks_filename
        
        try:
            # Tạo chunks array thuần - chỉ chunks, không có metadata thừa
            chunks_data = []
            
            for chunk_data in result['chunking_results']['chunks_data']:
                chunk_clean = {
                    'id': chunk_data['chunk_id'],
                    'content': chunk_data['content'],
                    'metadata': {
                        'chunk_index': chunk_data['chunk_index'],
                        'char_count': chunk_data['char_count'],
                        'word_count': chunk_data['word_count'],
                        'keywords': chunk_data['keywords'],
                        'coherence_score': chunk_data['semantic_coherence_score'],
                        'completeness_score': chunk_data['completeness_score'],
                        'language_confidence': chunk_data['language_confidence'],
                        'chunking_strategy': chunk_data['chunking_strategy']
                    }
                }
                chunks_data.append(chunk_clean)
            
            # Lưu chỉ mảng chunks
            with open(chunks_path, 'w', encoding='utf-8') as f:
                json.dump(chunks_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"💾 Đã lưu chunks: {chunks_path}")
            
            return {
                'chunks_json': str(chunks_path)
            }
            
        except Exception as e:
            logger.error(f"❌ Lỗi lưu file: {e}")
            raise
    
    def run(self, file_path: Path, strategy: str = None, 
            save_json: bool = True, print_report: bool = True, **kwargs) -> Dict[str, Any]:
        """
        Chạy intelligent chunking hoàn chỉnh.
        
        Args:
            file_path: Đường dẫn file markdown
            strategy: Strategy cụ thể (None = intelligent auto-select)
            save_json: Có lưu kết quả JSON không
            print_report: Có in báo cáo không
            **kwargs: Parameters tùy chỉnh cho strategies
            
        Returns:
            Kết quả chunking và đường dẫn files đã lưu
        """
        try:
            # Xử lý chunking (intelligent hoặc single strategy)
            result = self.process_chunking(file_path, custom_strategy=strategy, **kwargs)
            
            # In báo cáo
            if print_report:
                self.print_report(result)
            
            # Lưu JSON
            saved_files = {}
            if save_json:
                saved_files = self.save_json_results(result, file_path)
                print(f"\n💾 FILE ĐÃ LƯU:")
                print(f"   • Chunks: {saved_files['chunks_json']}")
            
            return {
                'result': result,
                'saved_files': saved_files
            }
            
        except Exception as e:
            logger.error(f"❌ Lỗi intelligent processing: {e}")
            raise

# Alias cho backward compatibility
VietnameseChunkingProcessor = IntelligentVietnameseChunkingProcessor