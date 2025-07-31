# modules/rag_module/query_pipeline.py
import logging
from modules.agents.SubtopicGeneratorAgent import SubtopicGeneratorAgent
from modules.agents.CoverageEvaluatorAgent import CoverageEvaluatorAgent
from modules.rag_module.query_db.VectorSearcher import VectorSearcher
from modules.rag_module.datatypes.CoverageAssessment import CoverageAssessment
from modules.rag_module.datatypes.CoverageLevel import CoverageLevel

class QueryEvaluationPipeline:
    def __init__(self, llm, vector_searcher: VectorSearcher):
        self.subtopic_agent = SubtopicGeneratorAgent(llm)
        self.coverage_agent = CoverageEvaluatorAgent(llm)
        self.vector_searcher = vector_searcher
        self.logger = logging.getLogger(__name__)

    def print_report(self, request: str, subtopics: list[str], chunks: list, assessment: CoverageAssessment):
        print("\n" + "="*60)
        print("BÁO CÁO ĐÁNH GIÁ NỘI DUNG")
        print("="*60)
        print(f"\n📋 YÊU CẦU NGƯỜI DÙNG:\n{request}")

        print(f"\n📌 CÁC CHỦ ĐỀ CẦN CÓ ({len(subtopics)}):")
        for topic in subtopics:
            print(f"• {topic}")

        print(f"\n🔍 KẾT QUẢ TÌM KIẾM:")
        print(f"• Tổng số chunk tìm thấy: {len(chunks)}")
        print(f"• Nguồn tài liệu: {len(set(c.source_file for c in chunks))} file")
        avg_score = sum(c.score for c in chunks) / len(chunks) if chunks else 0
        print(f"• Điểm relevance trung bình: {avg_score:.3f}")

        print(f"\n📊 ĐÁNH GIÁ ĐỘ PHỦ:")
        print(f"• Mức độ: {assessment.level.value.upper()}")
        print(f"• Điểm số: {assessment.score:.2f}/1.0")
        print(f"• Chủ đề đã có: {len(assessment.covered_topics)}")
        print(f"• Chủ đề thiếu: {len(assessment.missing_topics)}")

        print(f"\n✅ CÁC CHỦ ĐỀ ĐÃ CÓ:")
        if assessment.covered_topics:
            for topic in assessment.covered_topics:
                print(f"• {topic}")
        else:
            print("(Chưa có chủ đề nào được đánh giá là đầy đủ)")

        print(f"\n❌ CÁC CHỦ ĐỀ THIẾU:")
        if assessment.missing_topics:
            for topic in assessment.missing_topics:
                print(f"• {topic}")
        else:
            print("(Không có chủ đề nào thiếu)")

    def run(self, user_request: str) -> CoverageAssessment:
        self.logger.info(f"Processing request: {user_request}")

        subtopics = self.subtopic_agent.run(user_request)
        self.logger.info(f"Extracted {len(subtopics)} subtopics")

        if not subtopics:
            self.logger.warning("No subtopics extracted")
            assessment = CoverageAssessment(
                level=CoverageLevel.INSUFFICIENT,
                score=0.0,
                missing_topics=[],
                covered_topics=[],
            )
            print("❌ Không thể xử lý yêu cầu.")
            return assessment

        # Vector search
        all_chunks = []
        for sub in subtopics:
            results = self.vector_searcher.search(sub)
            all_chunks.extend(results)
            self.logger.info(f"Found {len(results)} chunks for: {sub}")

        # Deduplication
        unique_chunks = self.vector_searcher.deduplicate(all_chunks)
        self.logger.info(f"After deduplication: {len(unique_chunks)} unique chunks")

        # Coverage evaluation
        assessment = self.coverage_agent.run(user_request, subtopics, unique_chunks)
        self.logger.info(f"Coverage assessment: {assessment.level.value} ({assessment.score:.2f})")

        # Print report
        self.print_report(user_request, subtopics, unique_chunks, assessment)
        return assessment
