from modules.rag_module.data_embedding.embedding_processor import VietnameseEmbeddingProcessor

# Tạo processor
processor = VietnameseEmbeddingProcessor()

# Xử lý file
chunks_file = "/home/ductrien/internship/EduMateAgent/chunking_output/tai-lieu-triet-hoc-chuong-1-triet-hoc-mac-lenin-dai-hoc_result_hybrid_20250717_061955_chunks.json"

result = processor.run(chunks_file, save_results=True)