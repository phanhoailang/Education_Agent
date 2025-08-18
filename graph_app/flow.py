import sys
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
from modules.lesson_plan.LessonPlanPipeline import LessonPlanPipeline
from modules.quiz_plan.QuizPipeline import QuizPipeline

load_dotenv()

# ========================= Helpers =========================
def clean_objectid(obj):
    if isinstance(obj, dict):
        return {k: clean_objectid(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_objectid(i) for i in obj]
    elif isinstance(obj, ObjectId):
        return str(obj)
    else:
        return obj


# ========================= State =========================
class FlowState(TypedDict):
    form_data: dict
    user_prompt: str
    subtopics: list
    db_chunks: list
    uploaded_chunks: list
    search_chunks: list
    all_chunks: list
    embedded_chunks: list
    filtered_chunks: list
    lesson_plan: dict
    quiz: dict
    output_path: str
    __skip__: bool
    __plan_done__: bool
    __quiz_done__: bool


# ========================= Nodes =========================
class PromptGenerator:
    def __init__(self, llm: GPTClient):
        self.agent = ChatAgent(llm)

    def __call__(self, state: FlowState):
        result = self.agent.run(mode="generate_prompt", form_data=state["form_data"])
        print("\n🧠 Prompt gốc sinh từ form:")
        print(result)
        return {"user_prompt": result}


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

                # 1) Document processing
                doc_result = self.document_processor.process_file(file_path_obj)
                if not doc_result.success:
                    print(f"Document processing failed: {doc_result.error_message}")
                    continue

                # 2) Chunking (trên file .md tạm)
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as temp_file:
                    temp_file.write(doc_result.content)
                    temp_md_path = temp_file.name

                chunking_result = self.chunking_processor.run(
                    Path(temp_md_path),
                    strategy=None,
                    save_json=False,
                    print_report=False
                )
                chunks_data = chunking_result['result']['chunking_results']['chunks_data']

                # 3) Standardize
                for i, chunk_data in enumerate(chunks_data):
                    all_standardized_chunks.append({
                        "chunk_id": f"{Path(file_path).stem}_chunk_{i+1:02d}",
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

                try:
                    os.unlink(temp_md_path)
                except Exception:
                    pass

            except Exception as e:
                print(f"⚠️ Failed to process {file_path}: {e}")
                continue

        if not all_standardized_chunks:
            print("\n❌ Không có file nào được xử lý thành công")
            return {"__skip__": True, "search_chunks": [], "db_chunks": [], "all_chunks": []}

        print(f"\n🎉 Tổng cộng đã xử lý: {len(all_standardized_chunks)} chunks từ {len(files)} files")
        return {
            "search_chunks": [],
            "db_chunks": [],
            "uploaded_chunks": all_standardized_chunks,
            "__skip__": False,
            "source_files": files,
            "processing_method": "new_intelligent",
        }


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

        chunks = self.retriever.retrieve(prompt, subtopics)
        db_chunks = [c for c in chunks if c.get("retrieved_from") == "db"]
        search_chunks = [c for c in chunks if c.get("retrieved_from") == "search"]
        all_chunks = db_chunks + search_chunks

        print(f"\n📦 Tổng cộng: {len(all_chunks)} chunks (DB: {len(db_chunks)}, Search: {len(search_chunks)})")
        return {"db_chunks": db_chunks, "search_chunks": search_chunks, "all_chunks": all_chunks}


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


def embed_and_store_chunks(chunks, source_files):
    print("\n📄 Chunks:")
    print(json.dumps(chunks[:3], ensure_ascii=False, indent=2))
    if len(chunks) > 3:
        print(f"... (còn {len(chunks) - 3} chunks nữa)\n")

    chunks_with_metadata = []
    for chunk in chunks:
        if "metadata" not in chunk:
            chunk["metadata"] = {}
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
    except Exception:
        pass

    db = MongoDBClient()
    db.insert_many("lectures", embedded_chunks)
    print(f"\n✅ Đã lưu {len(embedded_chunks)} chunks vào MongoDB")

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


class FilterChunks:
    def __init__(self):
        self.engine = SemanticChunkFilter()

    def __call__(self, state: FlowState):
        uploaded_chunks = state.get("uploaded_chunks", [])
        all_chunks = state.get("all_chunks", [])
        subtopics = state.get("subtopics", [])

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

        filtered = self.engine.filter(chunks, subtopics)
        print(f"✅ Đã lọc còn {len(filtered)} chunks liên quan")
        return {"filtered_chunks": filtered}


class GenerateLessonPlan:
    def __init__(self, llm: GPTClient):
        self.pipeline = LessonPlanPipeline(llm)

    def __call__(self, state: FlowState):
        # Kiểm tra có cần tạo lesson plan không
        if not should_generate_lesson_plan(state):
            print("⏭️ Skip tạo Lesson Plan (user không tick)")
            return {"lesson_plan": {}, "__plan_done__": True}
        print("\n🎓 Bắt đầu tạo kế hoạch bài giảng...")
        prompt = state.get("user_prompt", "")
        filtered_chunks = state.get("filtered_chunks", [])
        if not prompt:
            return {"lesson_plan": {"error": "Không có prompt để tạo bài giảng"}, "__plan_done__": True}
        lesson_plan = self.pipeline.create_full_lesson_plan(prompt, filtered_chunks)
        print("✅ Hoàn thành tạo kế hoạch bài giảng!")
        if "output_path" in lesson_plan:
            print(f"📁 Đã lưu tại: {lesson_plan['output_path']}")
        return {"lesson_plan": lesson_plan, "__plan_done__": True}


class GenerateQuiz:
    def __init__(self, llm: GPTClient):
        self.pipeline = QuizPipeline(llm)

    def __call__(self, state: FlowState):
        # Kiểm tra có cần tạo quiz không
        if not should_generate_quiz(state):
            print("⏭️ Skip tạo Quiz (user không tick)")
            return {"quiz": {}, "__quiz_done__": True}
        
        print("\n📝 Bắt đầu tạo Quiz...")
        form = state.get("form_data", {}) or {}
        mode = form.get("quiz_source", "material")  # "material" | "plan"
        config = form.get("quiz_config", {})
        prompt = state.get("user_prompt", "")
        filtered_chunks = state.get("filtered_chunks", [])
        lesson_plan = state.get("lesson_plan", {})

        if mode == "plan" and not lesson_plan:
            print("⚠️ Không có lesson plan để sinh quiz. Fallback sang material.")
            mode = "material"

        # --- Gọi pipeline với fallback ---
        if mode == "plan":
            if hasattr(self.pipeline, "from_lesson_plan"):
                quiz = self.pipeline.from_lesson_plan(lesson_plan, prompt, config)
            else:
                # Fallback: fuse lesson plan vào prompt rồi tạo quiz từ chunks
                plan_md = (
                    lesson_plan.get("complete_markdown")
                    or lesson_plan.get("markdown", "")
                    or json.dumps(lesson_plan, ensure_ascii=False)
                )
                augmented_prompt = f"{prompt}\n\n[LESSON_PLAN]\n{plan_md}"
                quiz = self.pipeline.create_full_quiz(augmented_prompt, filtered_chunks)
        else:
            if hasattr(self.pipeline, "from_materials"):
                quiz = self.pipeline.from_materials(prompt, filtered_chunks, config)
            else:
                quiz = self.pipeline.create_full_quiz(prompt, filtered_chunks)

        print("✅ Hoàn thành tạo Quiz!")
        if isinstance(quiz, dict) and "output_path" in quiz:
            print(f"📁 Đã lưu quiz tại: {quiz['output_path']}")

        return {"quiz": quiz, "__quiz_done__": True}


# ========================= Routing funcs =========================
def should_call_agent(state: FlowState):
    """Sau process_file: nếu không có file => agent_retrieval, ngược lại embed uploaded."""
    return "agent_retrieval" if state.get("__skip__") else "embed_store_uploaded"


def first_after_filter(state: FlowState):
    """Sau filter_chunks: quyết định sinh plan hay quiz trước dựa trên checkbox."""
    form = state.get("form_data", {}) or {}
    
    # Lấy content_types từ form (từ checkbox)
    content_types = form.get("content_types", [])
    
    # DEBUG: In ra để kiểm tra
    print(f"🔍 [DEBUG] form keys: {list(form.keys())}")
    print(f"🔍 [DEBUG] content_types value: {content_types}")
    print(f"🔍 [DEBUG] content_types type: {type(content_types)}")
    
    # Ensure content_types is a list
    if not isinstance(content_types, list):
        if isinstance(content_types, str):
            content_types = [content_types]
        else:
            content_types = []
    
    # Convert thành set để dễ so sánh
    if isinstance(content_types, list):
        outputs = set(content_types)
    else:
        print(f"⚠️ [WARNING] content_types không phải list: {content_types}")
        outputs = set()
    
    print(f"🎯 [first_after_filter] User chọn: {outputs}")
    
    # Convert thành set để dễ so sánh
    outputs = set(content_types)
    print(f"🎯 [first_after_filter] User chọn: {outputs}")
    
    # Case 1: Chỉ tạo lesson plan
    if outputs == {"lesson_plan"}:
        print("✅ Chỉ tạo Kế hoạch giảng dạy")
        return "generate_lesson_plan"
    
    # Case 2: Chỉ tạo quiz  
    if outputs == {"quiz"}:
        print("✅ Chỉ tạo Quiz")
        return "generate_quiz"
    
    # Case 3: Tạo cả hai - luôn tạo plan trước để quiz có thể sử dụng
    if "lesson_plan" in outputs and "quiz" in outputs:
        print("✅ Tạo cả hai: Plan trước, Quiz sau")
        return "generate_lesson_plan"
    
    # Fallback: mặc định tạo lesson plan nếu có lesson_plan
    if "lesson_plan" in outputs:
        print(f"⚠️ Fallback tạo lesson plan từ {outputs}")
        return "generate_lesson_plan"
    elif "quiz" in outputs:
        print(f"⚠️ Fallback tạo quiz từ {outputs}")
        return "generate_quiz"
    else:
        print(f"❌ Không có lựa chọn hợp lệ từ {outputs}, mặc định tạo lesson plan")
        return "generate_lesson_plan"


def route_after_plan(state: FlowState):
    """Sau generate_lesson_plan: kiểm tra còn cần quiz không."""
    form = state.get("form_data", {}) or {}
    content_types = form.get("content_types", [])
    
    # Ensure it's a list
    if not isinstance(content_types, list):
        if isinstance(content_types, str):
            content_types = [content_types]
        else:
            content_types = []
    
    outputs = set(content_types)
    print(f"🔄 [route_after_plan] Đã hoàn thành Plan. User chọn: {outputs}")
    
    # Nếu user có tick quiz và chưa làm quiz
    if "quiz" in outputs and not state.get("__quiz_done__", False):
        print("➡️ Tiếp tục tạo Quiz")
        return "generate_quiz"
    
    print("🏁 Hoàn thành - chỉ cần Plan")
    return "END"


def route_after_quiz(state: FlowState):
    """Sau generate_quiz: kiểm tra còn cần plan không."""
    form = state.get("form_data", {}) or {}
    content_types = form.get("content_types", [])
    
    # Ensure it's a list
    if not isinstance(content_types, list):
        if isinstance(content_types, str):
            content_types = [content_types]
        else:
            content_types = []
    
    outputs = set(content_types)
    print(f"🔄 [route_after_quiz] Đã hoàn thành Quiz. User chọn: {outputs}")
    
    # Nếu user có tick plan và chưa làm plan  
    if "lesson_plan" in outputs and not state.get("__plan_done__", False):
        print("➡️ Tiếp tục tạo Lesson Plan")
        return "generate_lesson_plan"
    
    print("🏁 Hoàn thành - chỉ cần Quiz")
    return "END"

##Skip Logic
def should_generate_lesson_plan(state: FlowState):
    """Kiểm tra có cần tạo lesson plan không."""
    form = state.get("form_data", {}) or {}
    content_types = form.get("content_types", [])
    
    if not isinstance(content_types, list):
        if isinstance(content_types, str):
            content_types = [content_types]
        else:
            content_types = []
    
    should_generate = "lesson_plan" in content_types
    print(f"🤔 [should_generate_lesson_plan] {should_generate} (from {content_types})")
    return should_generate

def should_generate_quiz(state: FlowState):
    """Kiểm tra có cần tạo quiz không."""  
    form = state.get("form_data", {}) or {}
    content_types = form.get("content_types", [])
    
    if not isinstance(content_types, list):
        if isinstance(content_types, str):
            content_types = [content_types]
        else:
            content_types = []
    
    should_generate = "quiz" in content_types
    print(f"🤔 [should_generate_quiz] {should_generate} (from {content_types})")
    return should_generate

# ========================= LLMs =========================
llm = GPTClient(
    api_key=os.environ.get("AZURE_API_KEY"),
    endpoint=os.environ.get("AZURE_ENDPOINT"),
    model=os.environ.get("AZURE_MODEL"),
    api_version=os.environ.get("AZURE_API_VERSION")
)

# Có thể dùng Gemini nếu muốn
gemini_llm = GeminiClient(
    api_key=os.environ.get("GEMINI_API_KEY"),
    model="gemini-2.5-flash"
)


# ========================= Build Graph =========================
builder = StateGraph(FlowState)

builder.add_node("generate_prompt", PromptGenerator(llm))
builder.add_node("generate_subtopics", SubtopicGenerator(llm))
builder.add_node("process_file", FileProcessor())
builder.add_node("agent_retrieval", AgentBasedRetrieval())
builder.add_node("embed_store_uploaded", EmbedAndStoreUploaded())
builder.add_node("embed_store_searched", EmbedAndStoreSearched())
builder.add_node("filter_chunks", FilterChunks())
builder.add_node("generate_lesson_plan", GenerateLessonPlan(llm))
builder.add_node("generate_quiz", GenerateQuiz(llm))

builder.set_entry_point("generate_prompt")

# Linear edges
builder.add_edge("generate_prompt", "generate_subtopics")
builder.add_edge("generate_subtopics", "process_file")

# Branch after process_file
builder.add_conditional_edges(
    "process_file", should_call_agent,
    {"embed_store_uploaded": "embed_store_uploaded", "agent_retrieval": "agent_retrieval"}
)

# Continue embedding / retrieval to filter
builder.add_edge("agent_retrieval", "embed_store_searched")
builder.add_edge("embed_store_uploaded", "filter_chunks")
builder.add_edge("embed_store_searched", "filter_chunks")

# Decide which product first
builder.add_conditional_edges(
    "filter_chunks", first_after_filter,
    {"generate_lesson_plan": "generate_lesson_plan", "generate_quiz": "generate_quiz"}
)

# After plan -> maybe quiz / end
builder.add_conditional_edges(
    "generate_lesson_plan", route_after_plan,
    {"generate_quiz": "generate_quiz", "END": END}
)

# After quiz -> maybe plan / end
builder.add_conditional_edges(
    "generate_quiz", route_after_quiz,
    {"generate_lesson_plan": "generate_lesson_plan", "END": END}
)

# ========================= Compile & Run =========================
graph = builder.compile()

def run_flow(form_data: dict):
    result = graph.invoke({"form_data": form_data})
    return result


# ========================= Viz =========================
try:
    graph.get_graph().draw_png("langgraph_flow.png")
    print("Đã tạo sơ đồ flow tại: langgraph_flow.png")
except Exception as e:
    print(f"Không thể tạo sơ đồ trực tiếp (lỗi: {e}). Đảm bảo đã cài 'pygraphviz'/'pydot' và 'graphviz'.")
    print("\nĐang thử xuất cấu trúc đồ thị sang JSON.")
    try:
        graph_json = graph.get_graph().to_json()
        output_json_path = "langgraph_flow.json"
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(graph_json, f, ensure_ascii=False, indent=2)
        print(f"✅ Xuất cấu trúc đồ thị: {output_json_path}")
    except Exception as json_e:
        print(f"Không thể xuất đồ thị sang JSON: {json_e}")
        try:
            print(graph.get_graph().get_graph().to_string())
        except Exception as dot_e:
            print(f"Không thể lấy DOT string: {dot_e}")
