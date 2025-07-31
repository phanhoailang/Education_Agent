import statistics
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

from .chunk_metadata import ChunkMetadata

@dataclass
class ChunkingEvaluation:
    """Kết quả đánh giá chất lượng chunking."""
    
    # Metrics cơ bản
    total_chunks: int
    avg_chunk_size: float
    min_chunk_size: int
    max_chunk_size: int
    std_chunk_size: float
    
    # Metrics chất lượng
    avg_coherence_score: float
    avg_completeness_score: float
    avg_language_confidence: float
    
    # Metrics cấu trúc
    complete_sentences_ratio: float
    paragraph_preservation_ratio: float
    overlap_efficiency: float
    
    # Metrics đặc trưng tiếng Việt
    vietnamese_chars_ratio: float
    avg_words_per_sentence: float
    named_entities_count: int
    pos_diversity: float
    
    # Tổng điểm
    overall_quality_score: float
    
    # Thông tin chi tiết
    strategy_name: str
    processing_time: float
    recommendations: List[str]

class ChunkQualityEvaluator:
    """Đánh giá chất lượng chunking cho văn bản tiếng Việt."""
    
    def __init__(self, 
                 min_acceptable_coherence: float = 0.6,
                 min_acceptable_completeness: float = 0.7,
                 target_chunk_size: int = 1000,
                 size_tolerance: float = 0.3):
        """
        Args:
            min_acceptable_coherence: Điểm coherence tối thiểu
            min_acceptable_completeness: Điểm completeness tối thiểu
            target_chunk_size: Kích thước chunk mục tiêu
            size_tolerance: Độ chấp nhận sai lệch kích thước (30% = 0.3)
        """
        self.min_acceptable_coherence = min_acceptable_coherence
        self.min_acceptable_completeness = min_acceptable_completeness
        self.target_chunk_size = target_chunk_size
        self.size_tolerance = size_tolerance
        
        self.logger = logging.getLogger(__name__)
    
    def evaluate_chunks(self, 
                       chunks: List[ChunkMetadata],
                       original_text: Optional[str] = None) -> ChunkingEvaluation:
        """
        Đánh giá toàn diện chất lượng chunking.
        
        Args:
            chunks: Danh sách chunks để đánh giá
            original_text: Văn bản gốc (để tính preservation metrics)
            
        Returns:
            Kết quả đánh giá chi tiết
        """
        if not chunks:
            return self._empty_evaluation()
        
        # Tính metrics cơ bản
        basic_metrics = self._calculate_basic_metrics(chunks)
        
        # Tính metrics chất lượng
        quality_metrics = self._calculate_quality_metrics(chunks)
        
        # Tính metrics cấu trúc
        structure_metrics = self._calculate_structure_metrics(chunks, original_text)
        
        # Tính metrics tiếng Việt
        vietnamese_metrics = self._calculate_vietnamese_metrics(chunks)
        
        # Tính tổng điểm
        overall_score = self._calculate_overall_score(
            basic_metrics, quality_metrics, structure_metrics, vietnamese_metrics
        )
        
        # Tạo recommendations
        recommendations = self._generate_recommendations(
            chunks, basic_metrics, quality_metrics, structure_metrics
        )
        
        # Lấy thông tin strategy và processing time
        strategy_name = chunks[0].chunking_strategy if chunks else "unknown"
        avg_processing_time = statistics.mean([
            chunk.processing_time or 0.0 for chunk in chunks
        ])
        
        return ChunkingEvaluation(
            # Basic metrics
            total_chunks=basic_metrics['total_chunks'],
            avg_chunk_size=basic_metrics['avg_size'],
            min_chunk_size=basic_metrics['min_size'],
            max_chunk_size=basic_metrics['max_size'],
            std_chunk_size=basic_metrics['std_size'],
            
            # Quality metrics
            avg_coherence_score=quality_metrics['avg_coherence'],
            avg_completeness_score=quality_metrics['avg_completeness'],
            avg_language_confidence=quality_metrics['avg_language_confidence'],
            
            # Structure metrics
            complete_sentences_ratio=structure_metrics['complete_sentences_ratio'],
            paragraph_preservation_ratio=structure_metrics['paragraph_preservation'],
            overlap_efficiency=structure_metrics['overlap_efficiency'],
            
            # Vietnamese metrics
            vietnamese_chars_ratio=vietnamese_metrics['vietnamese_chars_ratio'],
            avg_words_per_sentence=vietnamese_metrics['avg_words_per_sentence'],
            named_entities_count=vietnamese_metrics['named_entities_count'],
            pos_diversity=vietnamese_metrics['pos_diversity'],
            
            # Overall
            overall_quality_score=overall_score,
            strategy_name=strategy_name,
            processing_time=avg_processing_time,
            recommendations=recommendations
        )
    
    def _calculate_basic_metrics(self, chunks: List[ChunkMetadata]) -> Dict[str, Any]:
        """Tính các metrics cơ bản."""
        sizes = [chunk.char_count for chunk in chunks]
        
        return {
            'total_chunks': len(chunks),
            'avg_size': statistics.mean(sizes),
            'min_size': min(sizes),
            'max_size': max(sizes),
            'std_size': statistics.stdev(sizes) if len(sizes) > 1 else 0.0
        }
    
    def _calculate_quality_metrics(self, chunks: List[ChunkMetadata]) -> Dict[str, Any]:
        """Tính các metrics chất lượng."""
        coherence_scores = [
            chunk.semantic_coherence_score or 0.0 for chunk in chunks
        ]
        completeness_scores = [
            chunk.completeness_score or 0.0 for chunk in chunks
        ]
        language_confidences = [
            chunk.language_confidence for chunk in chunks
        ]
        
        return {
            'avg_coherence': statistics.mean(coherence_scores),
            'avg_completeness': statistics.mean(completeness_scores),
            'avg_language_confidence': statistics.mean(language_confidences)
        }
    
    def _calculate_structure_metrics(self, 
                                   chunks: List[ChunkMetadata],
                                   original_text: Optional[str]) -> Dict[str, Any]:
        """Tính các metrics về cấu trúc."""
        
        # Tỷ lệ chunks kết thúc bằng câu hoàn chỉnh
        complete_sentences = sum(
            1 for chunk in chunks 
            if chunk.content.strip().endswith(('.', '!', '?'))
        )
        complete_sentences_ratio = complete_sentences / len(chunks)
        
        # Paragraph preservation (nếu có original text)
        paragraph_preservation = 0.5  # Default
        if original_text:
            original_paragraphs = len([p for p in original_text.split('\n\n') if p.strip()])
            chunk_paragraphs = sum(
                chunk.vietnamese_features.get('paragraph_count', 0) 
                for chunk in chunks
            )
            if original_paragraphs > 0:
                paragraph_preservation = min(1.0, chunk_paragraphs / original_paragraphs)
        
        # Overlap efficiency
        overlaps = [
            chunk.chunk_overlap_prev + chunk.chunk_overlap_next 
            for chunk in chunks
        ]
        avg_overlap = statistics.mean(overlaps) if overlaps else 0
        total_content_length = sum(chunk.char_count for chunk in chunks)
        overlap_efficiency = 1.0 - (avg_overlap / total_content_length) if total_content_length > 0 else 1.0
        
        return {
            'complete_sentences_ratio': complete_sentences_ratio,
            'paragraph_preservation': paragraph_preservation,
            'overlap_efficiency': max(0.0, overlap_efficiency)
        }
    
    def _calculate_vietnamese_metrics(self, chunks: List[ChunkMetadata]) -> Dict[str, Any]:
        """Tính các metrics đặc trưng tiếng Việt."""
        
        # Tỷ lệ ký tự tiếng Việt
        vietnamese_ratios = []
        for chunk in chunks:
            features = chunk.vietnamese_features
            if 'vietnamese_chars_ratio' in features:
                vietnamese_ratios.append(features['vietnamese_chars_ratio'])
        
        vietnamese_chars_ratio = statistics.mean(vietnamese_ratios) if vietnamese_ratios else 0.0
        
        # Trung bình số từ mỗi câu
        words_per_sentence = []
        for chunk in chunks:
            features = chunk.vietnamese_features
            if 'avg_words_per_sentence' in features:
                words_per_sentence.append(features['avg_words_per_sentence'])
        
        avg_words_per_sentence = statistics.mean(words_per_sentence) if words_per_sentence else 0.0
        
        # Không sử dụng named entities nữa
        total_entities = 0  # Bỏ named entities
        
        # Đa dạng POS tags
        all_pos_tags = set()
        for chunk in chunks:
            all_pos_tags.update(chunk.pos_tags)
        
        pos_diversity = len(all_pos_tags) / 20.0  # Normalize (giả sử max 20 POS tags)
        pos_diversity = min(1.0, pos_diversity)
        
        return {
            'vietnamese_chars_ratio': vietnamese_chars_ratio,
            'avg_words_per_sentence': avg_words_per_sentence,
            'named_entities_count': total_entities,  # Luôn = 0
            'pos_diversity': pos_diversity
        }
    
    def _calculate_overall_score(self, 
                               basic_metrics: Dict[str, Any],
                               quality_metrics: Dict[str, Any],
                               structure_metrics: Dict[str, Any],
                               vietnamese_metrics: Dict[str, Any]) -> float:
        """Tính tổng điểm chất lượng."""
        
        # Score cho kích thước chunks (0.0 - 1.0)
        avg_size = basic_metrics['avg_size']
        size_diff = abs(avg_size - self.target_chunk_size) / self.target_chunk_size
        size_score = max(0.0, 1.0 - size_diff / self.size_tolerance)
        
        # Score cho consistency kích thước
        std_size = basic_metrics['std_size']
        consistency_score = max(0.0, 1.0 - std_size / avg_size) if avg_size > 0 else 0.0
        
        # Kết hợp các scores với trọng số
        overall_score = (
            quality_metrics['avg_coherence'] * 0.25 +           # 25%
            quality_metrics['avg_completeness'] * 0.20 +        # 20%
            structure_metrics['complete_sentences_ratio'] * 0.15 + # 15%
            vietnamese_metrics['vietnamese_chars_ratio'] * 0.10 +   # 10%
            quality_metrics['avg_language_confidence'] * 0.10 +     # 10%
            size_score * 0.10 +                                     # 10%
            consistency_score * 0.05 +                              # 5%
            structure_metrics['overlap_efficiency'] * 0.05          # 5%
        )
        
        return min(1.0, max(0.0, overall_score))
    
    def _generate_recommendations(self, 
                                chunks: List[ChunkMetadata],
                                basic_metrics: Dict[str, Any],
                                quality_metrics: Dict[str, Any],
                                structure_metrics: Dict[str, Any]) -> List[str]:
        """Tạo recommendations để cải thiện chunking."""
        recommendations = []
        
        # Kiểm tra coherence
        if quality_metrics['avg_coherence'] < self.min_acceptable_coherence:
            recommendations.append(
                f"Coherence score thấp ({quality_metrics['avg_coherence']:.2f}). "
                "Thử semantic chunking hoặc sentence-aware strategy."
            )
        
        # Kiểm tra completeness
        if quality_metrics['avg_completeness'] < self.min_acceptable_completeness:
            recommendations.append(
                f"Completeness score thấp ({quality_metrics['avg_completeness']:.2f}). "
                "Tăng overlap hoặc sử dụng sentence boundary preservation."
            )
        
        # Kiểm tra kích thước
        avg_size = basic_metrics['avg_size']
        size_diff_ratio = abs(avg_size - self.target_chunk_size) / self.target_chunk_size
        
        if size_diff_ratio > self.size_tolerance:
            if avg_size > self.target_chunk_size:
                recommendations.append(
                    f"Chunks quá lớn (trung bình {avg_size:.0f} chars). "
                    "Giảm chunk_size hoặc tăng threshold cho semantic splitting."
                )
            else:
                recommendations.append(
                    f"Chunks quá nhỏ (trung bình {avg_size:.0f} chars). "
                    "Tăng chunk_size hoặc giảm threshold cho semantic splitting."
                )
        
        # Kiểm tra consistency
        std_size = basic_metrics['std_size']
        if std_size > avg_size * 0.5:  # Nếu độ lệch chuẩn > 50% trung bình
            recommendations.append(
                f"Kích thước chunks không đồng đều (std: {std_size:.0f}). "
                "Thử recursive chunking hoặc điều chỉnh parameters."
            )
        
        # Kiểm tra sentence completion
        if structure_metrics['complete_sentences_ratio'] < 0.7:
            recommendations.append(
                f"Nhiều chunks không kết thúc hoàn chỉnh ({structure_metrics['complete_sentences_ratio']:.1%}). "
                "Bật sentence boundary preservation."
            )
        
        # Kiểm tra overlap efficiency
        if structure_metrics['overlap_efficiency'] < 0.8:
            recommendations.append(
                "Overlap không hiệu quả. Cân nhắc giảm overlap ratio."
            )
        
        # Kiểm tra language confidence
        if quality_metrics['avg_language_confidence'] < 0.8:
            recommendations.append(
                f"Độ tin cậy ngôn ngữ thấp ({quality_metrics['avg_language_confidence']:.2f}). "
                "Kiểm tra preprocessing hoặc sử dụng Vietnamese-specific models."
            )
        
        # Nếu không có vấn đề
        if not recommendations:
            recommendations.append("Chất lượng chunking tốt! Không cần điều chỉnh.")
        
        return recommendations
    
    def _empty_evaluation(self) -> ChunkingEvaluation:
        """Trả về evaluation rỗng khi không có chunks."""
        return ChunkingEvaluation(
            total_chunks=0,
            avg_chunk_size=0.0,
            min_chunk_size=0,
            max_chunk_size=0,
            std_chunk_size=0.0,
            avg_coherence_score=0.0,
            avg_completeness_score=0.0,
            avg_language_confidence=0.0,
            complete_sentences_ratio=0.0,
            paragraph_preservation_ratio=0.0,
            overlap_efficiency=0.0,
            vietnamese_chars_ratio=0.0,
            avg_words_per_sentence=0.0,
            named_entities_count=0,
            pos_diversity=0.0,
            overall_quality_score=0.0,
            strategy_name="none",
            processing_time=0.0,
            recommendations=["Không có chunks để đánh giá."]
        )
    
    def compare_strategies(self, 
                          evaluations: Dict[str, ChunkingEvaluation]) -> Dict[str, Any]:
        """
        So sánh nhiều strategies chunking.
        
        Args:
            evaluations: Dict mapping strategy_name -> evaluation
            
        Returns:
            Kết quả so sánh chi tiết
        """
        if not evaluations:
            return {"error": "Không có evaluations để so sánh"}
        
        # Tìm strategy tốt nhất theo từng metric
        best_by_metric = {}
        
        metrics = [
            'overall_quality_score',
            'avg_coherence_score', 
            'avg_completeness_score',
            'complete_sentences_ratio',
            'overlap_efficiency',
            'vietnamese_chars_ratio'
        ]
        
        for metric in metrics:
            best_strategy = max(
                evaluations.keys(),
                key=lambda s: getattr(evaluations[s], metric)
            )
            best_value = getattr(evaluations[best_strategy], metric)
            best_by_metric[metric] = {
                'strategy': best_strategy,
                'value': best_value
            }
        
        # Tìm strategy tốt nhất tổng thể
        best_overall = max(
            evaluations.keys(),
            key=lambda s: evaluations[s].overall_quality_score
        )
        
        # Tạo ranking
        ranking = sorted(
            evaluations.keys(),
            key=lambda s: evaluations[s].overall_quality_score,
            reverse=True
        )
        
        # Tính toán summary statistics
        all_scores = [eval.overall_quality_score for eval in evaluations.values()]
        summary_stats = {
            'avg_score': statistics.mean(all_scores),
            'best_score': max(all_scores),
            'worst_score': min(all_scores),
            'score_range': max(all_scores) - min(all_scores)
        }
        
        return {
            'best_overall_strategy': best_overall,
            'best_overall_score': evaluations[best_overall].overall_quality_score,
            'ranking': ranking,
            'best_by_metric': best_by_metric,
            'summary_statistics': summary_stats,
            'detailed_comparison': self._create_detailed_comparison(evaluations)
        }
    
    def _create_detailed_comparison(self, 
                                  evaluations: Dict[str, ChunkingEvaluation]) -> Dict[str, Dict[str, Any]]:
        """Tạo bảng so sánh chi tiết các strategies."""
        comparison = {}
        
        for strategy, evaluation in evaluations.items():
            comparison[strategy] = {
                'overall_score': evaluation.overall_quality_score,
                'coherence': evaluation.avg_coherence_score,
                'completeness': evaluation.avg_completeness_score,
                'chunk_count': evaluation.total_chunks,
                'avg_size': evaluation.avg_chunk_size,
                'size_consistency': 1.0 - (evaluation.std_chunk_size / evaluation.avg_chunk_size) if evaluation.avg_chunk_size > 0 else 0,
                'sentence_completion': evaluation.complete_sentences_ratio,
                'vietnamese_ratio': evaluation.vietnamese_chars_ratio,
                'processing_time': evaluation.processing_time,
                'recommendation_count': len(evaluation.recommendations)
            }
        
        return comparison
    
    def generate_evaluation_report(self, 
                                 evaluation: ChunkingEvaluation,
                                 detailed: bool = True) -> str:
        """
        Tạo báo cáo đánh giá dạng text.
        
        Args:
            evaluation: Kết quả đánh giá
            detailed: Có tạo báo cáo chi tiết không
            
        Returns:
            Báo cáo dạng string
        """
        report = []
        
        # Header
        report.append("=" * 60)
        report.append(f"BÁO CÁO ĐÁNH GIÁ CHUNKING - {evaluation.strategy_name.upper()}")
        report.append("=" * 60)
        
        # Tổng quan
        report.append(f"\n📊 TỔNG QUAN:")
        report.append(f"   • Tổng điểm chất lượng: {evaluation.overall_quality_score:.2f}/1.00")
        report.append(f"   • Số chunks: {evaluation.total_chunks}")
        report.append(f"   • Thời gian xử lý: {evaluation.processing_time:.2f}s")
        
        # Metrics cơ bản
        report.append(f"\n📏 METRICS KÍCH THƯỚC:")
        report.append(f"   • Kích thước trung bình: {evaluation.avg_chunk_size:.0f} chars")
        report.append(f"   • Khoảng: {evaluation.min_chunk_size} - {evaluation.max_chunk_size} chars")
        report.append(f"   • Độ lệch chuẩn: {evaluation.std_chunk_size:.0f}")
        
        # Metrics chất lượng
        report.append(f"\n✨ METRICS CHẤT LƯỢNG:")
        report.append(f"   • Coherence: {evaluation.avg_coherence_score:.2f}/1.00")
        report.append(f"   • Completeness: {evaluation.avg_completeness_score:.2f}/1.00")
        report.append(f"   • Độ tin cậy ngôn ngữ: {evaluation.avg_language_confidence:.2f}/1.00")
        
        # Metrics cấu trúc
        report.append(f"\n🏗️ METRICS CẤU TRÚC:")
        report.append(f"   • Câu hoàn chỉnh: {evaluation.complete_sentences_ratio:.1%}")
        report.append(f"   • Bảo toàn đoạn văn: {evaluation.paragraph_preservation_ratio:.1%}")
        report.append(f"   • Hiệu quả overlap: {evaluation.overlap_efficiency:.1%}")
        
        # Metrics tiếng Việt
        report.append(f"\n🇻🇳 METRICS TIẾNG VIỆT:")
        report.append(f"   • Tỷ lệ ký tự tiếng Việt: {evaluation.vietnamese_chars_ratio:.1%}")
        report.append(f"   • Từ/câu trung bình: {evaluation.avg_words_per_sentence:.1f}")
        report.append(f"   • Số thực thể: {evaluation.named_entities_count}")
        report.append(f"   • Đa dạng POS: {evaluation.pos_diversity:.2f}")
        
        if detailed:
            # Recommendations
            report.append(f"\n💡 KHUYẾN NGHỊ:")
            for i, rec in enumerate(evaluation.recommendations, 1):
                report.append(f"   {i}. {rec}")
            
            # Đánh giá chi tiết
            report.append(f"\n📋 ĐÁNH GIÁ CHI TIẾT:")
            
            # Quality assessment
            if evaluation.avg_coherence_score >= 0.8:
                report.append("   ✅ Coherence rất tốt")
            elif evaluation.avg_coherence_score >= 0.6:
                report.append("   ⚠️ Coherence chấp nhận được")
            else:
                report.append("   ❌ Coherence cần cải thiện")
            
            if evaluation.avg_completeness_score >= 0.8:
                report.append("   ✅ Completeness rất tốt")
            elif evaluation.avg_completeness_score >= 0.7:
                report.append("   ⚠️ Completeness chấp nhận được")
            else:
                report.append("   ❌ Completeness cần cải thiện")
            
            if evaluation.complete_sentences_ratio >= 0.8:
                report.append("   ✅ Cấu trúc câu được bảo toàn tốt")
            else:
                report.append("   ⚠️ Nhiều chunks bị cắt giữa câu")
            
            if evaluation.vietnamese_chars_ratio >= 0.7:
                report.append("   ✅ Văn bản tiếng Việt chất lượng cao")
            else:
                report.append("   ⚠️ Kiểm tra chất lượng văn bản tiếng Việt")
        
        report.append("\n" + "=" * 60)
        
        return "\n".join(report)
    
    def benchmark_strategies(self, 
                           text: str,
                           strategies: List[str] = None) -> Dict[str, Any]:
        """
        Benchmark nhiều strategies trên cùng một văn bản.
        
        Args:
            text: Văn bản test
            strategies: Danh sách tên strategies cần test
            
        Returns:
            Kết quả benchmark
        """
        if strategies is None:
            strategies = ['fixed_size', 'sentence_aware', 'recursive', 'semantic']
        
        # Import chunkers (lazy import để tránh circular dependency)
        from .chunkers import VietnameseTextChunker, HybridVietnameseChunker
        from .chunking_strategies import (
            FixedSizeStrategy, SentenceAwareStrategy, 
            RecursiveStrategy, SemanticStrategy
        )
        
        strategy_map = {
            'fixed_size': FixedSizeStrategy(chunk_size=1000, overlap=200),
            'sentence_aware': SentenceAwareStrategy(target_size=1000),
            'recursive': RecursiveStrategy(chunk_size=1000, chunk_overlap=200),
            'semantic': SemanticStrategy(similarity_threshold=0.75)
        }
        
        results = {}
        evaluations = {}
        
        for strategy_name in strategies:
            if strategy_name not in strategy_map:
                self.logger.warning(f"Unknown strategy: {strategy_name}")
                continue
            
            try:
                start_time = time.time()
                
                # Chunk text
                strategy = strategy_map[strategy_name]
                chunker = VietnameseTextChunker(strategy)
                chunks = chunker.chunk_text(text)
                
                # Evaluate
                evaluation = self.evaluate_chunks(chunks, text)
                
                processing_time = time.time() - start_time
                
                results[strategy_name] = {
                    'chunks': chunks,
                    'evaluation': evaluation,
                    'processing_time': processing_time
                }
                evaluations[strategy_name] = evaluation
                
                self.logger.info(f"Benchmarked {strategy_name}: {len(chunks)} chunks, score: {evaluation.overall_quality_score:.2f}")
                
            except Exception as e:
                self.logger.error(f"Benchmark failed for {strategy_name}: {e}")
                continue
        
        # Compare results
        comparison = self.compare_strategies(evaluations)
        
        return {
            'individual_results': results,
            'comparison': comparison,
            'best_strategy': comparison.get('best_overall_strategy'),
            'benchmark_summary': {
                'total_strategies_tested': len(results),
                'best_score': comparison.get('best_overall_score', 0),
                'avg_score': comparison.get('summary_statistics', {}).get('avg_score', 0)
            }
        }