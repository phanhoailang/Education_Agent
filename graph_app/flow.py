import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

import os
import json
import datetime
from pathlib import Path
from langgraph.graph import StateGraph, END
from typing import TypedDict
from bson import ObjectId
from dotenv import load_dotenv

from utils.GPTClient import GPTClient
from utils.GeminiClient import GeminiClient
from modules.agents.ChatAgent import ChatAgent
from modules.agents.SubtopicGeneratorAgent import SubtopicGeneratorAgent
from modules.rag_module.SemanticChunkFilter import SemanticChunkFilter
from modules.rag_module.documents_processing.main_processor import EduMateDocumentProcessor
from modules.rag_module.data_chunking.processor import IntelligentVietnameseChunkingProcessor
from modules.rag_module.data_embedding.embedding_processor import VietnameseEmbeddingProcessor
from modules.rag_module.query_db.MongoDBClient import MongoDBClient
from modules.rag_module.DeepRetrieval import OptimizedDeepRetrieval, DeepRetrieval
from modules.rag_module.SemanticChunkFilter import SemanticChunkFilter
from modules.lesson_plan.LessonPlanPipeline import LessonPlanPipeline

load_dotenv()

# ✅ Hàm lọc ObjectId
def clean_objectid(obj):
    if isinstance(obj, dict):
        return {k: clean_objectid(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_objectid(i) for i in obj]
    elif isinstance(obj, ObjectId):
        return str(obj)
    else:
        return obj

# ✅ 1. Khai báo trạng thái
class FlowState(TypedDict):
    form_data: dict
    user_prompt: str
    subtopics: list
    db_chunks: list
    uploaded_chunks: list
    search_chunks: list
    all_chunks: list
    embedded_chunks: list
    filtered_chunks: list  # ✅ THÊM
    lesson_plan: dict      # ✅ THÊM
    output_path: str
    __skip__: bool

# ✅ 2. Step: Sinh prompt từ form
class PromptGenerator:
    def __init__(self, llm: GPTClient):
        self.agent = ChatAgent(llm)

    def __call__(self, state: FlowState):
        result = self.agent.run(mode="generate_prompt", form_data=state["form_data"])
        print("\n🧠 Prompt gốc sinh từ form:")
        print(result)

        return {
            "user_prompt": result
        }
    
# ✅ 3. Step: Sinh các subtopics từ prompt
class SubtopicGenerator:
    def __init__(self, llm: GPTClient):
        self.agent = SubtopicGeneratorAgent(llm)

    def __call__(self, state: FlowState):
        prompt = state["user_prompt"]
        subtopics = self.agent.run(prompt)

        print(f"\n📌 Đã sinh {len(subtopics)} subtopics:")
        for i, topic in enumerate(subtopics, 1):
            print(f"   {i}. {topic}")

        return {"subtopics": subtopics}

# ✅ 4. Step: Xử lý file người dùng
class FileProcessor:
    def __init__(self):
        self.document_processor = EduMateDocumentProcessor.create_balanced()
        self.chunking_processor = IntelligentVietnameseChunkingProcessor(
            output_dir="temp_langgraph_chunking",
            min_quality=0.65
        )
        
    def __call__(self, state: FlowState):
        form = state["form_data"]
        files = form.get("files", [])
        if not files:
            print("\nKhông có file đính kèm. Sẽ gọi agent truy vấn sau...")
            return {"__skip__": True, "search_chunks": [], "db_chunks": [], "all_chunks": []}

        all_standardized_chunks = []

        for file_path in files:
            print(f"\n📂 Đang xử lý file: {file_path}")

            try:
                file_path_obj = Path(file_path)
                
                # Step 1: Document processing
                doc_result = self.document_processor.process_file(file_path_obj)
                
                if not doc_result.success:
                    print(f"Document processing failed: {doc_result.error_message}")
                    continue  # Bỏ qua file này và chuyển sang file tiếp theo

                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as temp_file:
                    temp_file.write(doc_result.content)
                    temp_md_path = temp_file.name
                
                # Step 2: Intelligent chunking
                chunking_result = self.chunking_processor.run(
                    Path(temp_md_path),
                    strategy=None,
                    save_json=False,
                    print_report=False
                )
                
                chunks_data = chunking_result['result']['chunking_results']['chunks_data']
                
                # Step 3: Convert to standardized format
                for i, chunk_data in enumerate(chunks_data):
                    all_standardized_chunks.append({
                        "chunk_id": f"{Path(file_path).stem}_chunk_{i+1:02d}",  # Thêm tên file vào chunk_id
                        "content": chunk_data["content"],
                        "token_count": chunk_data.get("word_count", 0),
                        "method": chunk_data.get("chunking_strategy", "intelligent"),
                        "source_file": file_path,
                        "retrieved_from": "upload",
                        "char_count": chunk_data.get("char_count", 0),
                        "keywords": chunk_data.get("keywords", []),
                        "coherence_score": chunk_data.get("semantic_coherence_score", 0.0),
                        "completeness_score": chunk_data.get("completeness_score", 0.0),
                        "language_confidence": chunk_data.get("language_confidence", 0.0)
                    })
                
                print(f"✅ Processed {file_path}: {len(chunks_data)} chunks created")
                
                # Cleanup temp file
                try:
                    import os
                    os.unlink(temp_md_path)
                except:
                    pass
                    
            except Exception as e:
                print(f"⚠️ Failed to process {file_path}: {e}")
                continue  # Tiếp tục với file tiếp theo
        
        if not all_standardized_chunks:
            print("\n❌ Không có file nào được xử lý thành công")
            return {"__skip__": True, "search_chunks": [], "db_chunks": [], "all_chunks": []}
            
        print(f"\n🎉 Tổng cộng đã xử lý: {len(all_standardized_chunks)} chunks từ {len(files)} files")
        
        return {
            "search_chunks": [],
            "db_chunks": [],
            "uploaded_chunks": all_standardized_chunks,
            "__skip__": False,
            "source_files": files,  # Trả về danh sách tất cả files
            "processing_method": "new_intelligent"
        }

# ✅ 5. Nếu không có file → truy vấn DB + search ngoài
class AgentBasedRetrieval:
    def __init__(self):
        self.retriever = OptimizedDeepRetrieval()

    def __call__(self, state: FlowState):
        print("🧠 [agent_retrieval] ĐÃ ĐƯỢC GỌI")
        prompt = state.get("user_prompt", "")
        subtopics = state.get("subtopics", [])
        if not prompt or not subtopics:
            print("\nThiếu prompt hoặc subtopics.")
            return {}

        if hasattr(self, 'retriever'):
            chunks = self.retriever.retrieve(prompt, subtopics)
        else:
            chunks = DeepRetrieval(prompt, subtopics)

        db_chunks = [c for c in chunks if c.get("retrieved_from") == "db"]
        search_chunks = [c for c in chunks if c.get("retrieved_from") == "search"]
        all_chunks = db_chunks + search_chunks

        print(f"\n📦 Tổng cộng: {len(all_chunks)} chunks (DB: {len(db_chunks)}, Search: {len(search_chunks)})")

        return {
            "db_chunks": db_chunks,
            "search_chunks": search_chunks,
            "all_chunks": all_chunks
        }

# ✅ 6. Embedding + lưu CSDL (chỉ cho chunks search hoặc upload)
class EmbedAndStoreUploaded:
    def __call__(self, state: FlowState):
        chunks = state.get("uploaded_chunks", [])
        if not chunks:
            print("\n Không có chunks để embedding (uploaded).")
            return {}

        file_path = state.get("source_file", "upload")
        source_name = os.path.basename(file_path)

        return embed_and_store_chunks(chunks, source_name)


class EmbedAndStoreSearched:
    def __call__(self, state: FlowState):
        chunks = state.get("search_chunks", [])
        if not chunks:
            print("\n❌ Không có chunks để embedding (searched).")
            return {}

        return embed_and_store_chunks(chunks, "web_search")

# ✅ Hỗ trợ: chia sẻ logic embedding & lưu
def embed_and_store_chunks(chunks, source_files):
    print("\n📄 Chunks:")
    print(json.dumps(chunks[:3], ensure_ascii=False, indent=2))
    if len(chunks) > 3:
        print(f"... (còn {len(chunks) - 3} chunks nữa)\n")

    chunks_with_metadata = []
    for chunk in chunks:
        if "metadata" not in chunk:
            chunk["metadata"] = {}
        
        # Thêm source file info vào metadata
        chunk["metadata"]["source_file"] = chunk.get("source_file", "unknown")
        chunk["metadata"]["all_source_files"] = source_files if isinstance(source_files, list) else [source_files]
        chunk["metadata"]["collection"] = "lectures"
        
        chunks_with_metadata.append(chunk)

    os.makedirs("temp_embedding", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_path = os.path.join("temp_embedding", f"temp_chunks_{timestamp}.json")

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(chunks_with_metadata, f, ensure_ascii=False, indent=2)

    embedder = VietnameseEmbeddingProcessor()
    result = embedder.run(temp_path, save_results=False)
    embedded_chunks = result["chunks"]

    try:
        os.remove(temp_path)
    except:
        pass

    db = MongoDBClient()
    db.insert_many("lectures", embedded_chunks)
    print(f"\n✅ Đã lưu {len(embedded_chunks)} chunks vào MongoDB")

    os.makedirs("output_chunks", exist_ok=True)
    os.makedirs("output_chunks", exist_ok=True)
    out_path = os.path.join("output_chunks", f"chunks_{timestamp}.json")

    cleaned = clean_objectid(embedded_chunks)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    print(f"\n📦 Đã lưu vào: {out_path}")
    return {
        "embedded_chunks": embedded_chunks, 
        "output_path": out_path,
    }

# ✅ 7. Lọc semantic
class FilterChunks:
    def __init__(self):
        self.engine = SemanticChunkFilter()
        
    def __call__(self, state: FlowState):
        uploaded_chunks = state.get("uploaded_chunks", [])
        all_chunks = state.get("all_chunks", [])
        subtopics = state.get("subtopics", [])

        # Ưu tiên lọc uploaded nếu có
        if uploaded_chunks:
            chunks = uploaded_chunks
            print(f"\n📂 Lọc {len(chunks)} uploaded chunks theo {len(subtopics)} subtopics...")
        else:
            chunks = all_chunks
            print(f"\n🌐 Lọc {len(chunks)} (db + search) chunks theo {len(subtopics)} subtopics...")

        if not chunks or not subtopics:
            print("\n⚠️ Không có chunks hoặc subtopics để lọc")
            return {"filtered_chunks": chunks}

        if len(chunks) <= 5:
            print(f"\nℹ️ Chỉ có {len(chunks)} chunks — bỏ qua bước lọc semantic.")
            return {"filtered_chunks": chunks}

        engine = SemanticChunkFilter()
        filtered = engine.filter(chunks, subtopics)

        print(f"✅ Đã lọc còn {len(filtered)} chunks liên quan")
        return {"filtered_chunks": filtered}
    
# ✅ 7. Sinh sườn bài giảng
class GenerateLessonPlan:
    def __init__(self, llm: GPTClient):
    # def __init__(self, llm: GeminiClient):
        self.pipeline = LessonPlanPipeline(llm)
        
    def __call__(self, state: FlowState):
        print("\n🎓 Bắt đầu tạo kế hoạch bài giảng...")
        
        prompt = state.get("user_prompt", "")
        filtered_chunks = state.get("filtered_chunks", [])
        
        if not prompt:
            return {"lesson_plan": {"error": "Không có prompt để tạo bài giảng"}}
        
        # Tạo kế hoạch bài giảng đầy đủ
        lesson_plan = self.pipeline.create_full_lesson_plan(prompt, filtered_chunks)
        
        print(f"✅ Hoàn thành tạo kế hoạch bài giảng!")
        if "output_path" in lesson_plan:
            print(f"📁 Đã lưu tại: {lesson_plan['output_path']}")
        
        return {"lesson_plan": lesson_plan}

# ✅ Điều kiện rẽ nhánh

def should_call_agent(state: FlowState):
    return "agent_retrieval" if state.get("__skip__") else "embed_store_uploaded"

llm = GPTClient(
    api_key=os.environ.get("AZURE_API_KEY"),
    endpoint=os.environ.get("AZURE_ENDPOINT"),
    model=os.environ.get("AZURE_MODEL"),
    api_version=os.environ.get("AZURE_API_VERSION")
)

gemini_llm = GeminiClient(
    api_key=os.environ.get("GEMINI_API_KEY"),
    model="gemini-2.5-flash"
)

# ✅ Build LangGraph
builder = StateGraph(FlowState)
builder.add_node("generate_prompt", PromptGenerator(llm))
builder.add_node("generate_subtopics", SubtopicGenerator(llm))
builder.add_node("process_file", FileProcessor())
builder.add_node("agent_retrieval", AgentBasedRetrieval())
builder.add_node("embed_store_uploaded", EmbedAndStoreUploaded())
builder.add_node("embed_store_searched", EmbedAndStoreSearched())
builder.add_node("filter_chunks", FilterChunks())
builder.add_node("generate_lesson_plan", GenerateLessonPlan(llm))
# builder.add_node("generate_lesson_plan", GenerateLessonPlan(gemini_llm))

builder.set_entry_point("generate_prompt")
builder.add_edge("generate_prompt", "generate_subtopics")
builder.add_edge("generate_subtopics", "process_file")
builder.add_conditional_edges("process_file", should_call_agent, {
    "embed_store_uploaded": "embed_store_uploaded",
    "agent_retrieval": "agent_retrieval"
})
builder.add_edge("agent_retrieval", "embed_store_searched")
builder.add_edge("embed_store_uploaded", "filter_chunks")
builder.add_edge("embed_store_searched", "filter_chunks")
builder.add_edge("filter_chunks", "generate_lesson_plan")  # ✅ SỬA
builder.add_edge("generate_lesson_plan", END)              # ✅ THÊM


graph = builder.compile()

def run_flow(form_data: dict):
    result = graph.invoke({"form_data": form_data})
    return result


try:
    graph.get_graph().draw_png("langgraph_flow.png")
    print("Đã tạo sơ đồ flow tại: langgraph_flow.png")
except Exception as e:
    print(f"Không thể tạo sơ đồ trực tiếp (lỗi: {e}). Đảm bảo bạn đã cài đặt 'pygraphviz' hoặc 'pydot' và 'graphviz'.")
    print("\nĐang thử xuất cấu trúc đồ thị sang định dạng JSON để bạn có thể trực quan hóa thủ công.")
    try:
        graph_json = graph.get_graph().to_json()
        output_json_path = "langgraph_flow.json"
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(graph_json, f, ensure_ascii=False, indent=2)
        print(f"✅ Đã xuất cấu trúc đồ thị thành công sang: {output_json_path}")
        print("   Bạn có thể dùng các công cụ trực tuyến như 'Mermaid Live Editor' (https://mermaid.live/)")
        print("   hoặc 'GraphvizOnline' (https://dreampuf.github.io/GraphvizOnline/) để dán nội dung JSON và xem.")
    except Exception as json_e:
        print(f"Không thể xuất đồ thị sang JSON: {json_e}")
        print("\nDưới đây là định dạng DOT của đồ thị (có thể không đầy đủ nếu có lỗi):")
        # Fallback cuối cùng là in ra DOT nếu mọi thứ khác thất bại
        try:
            print(graph.get_graph().get_graph().to_string())
        except Exception as dot_e:
            print(f"Không thể lấy chuỗi DOT: {dot_e}")