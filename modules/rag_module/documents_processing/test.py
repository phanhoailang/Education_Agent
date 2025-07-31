from pathlib import Path
from modules.rag_module.documents_processing.main_processor import EduMateDocumentProcessor

# Đường dẫn file hoặc thư mục cần xử lý
path = Path("/home/ductrien/Downloads/TestDocs/sample_math_slides.pptx")

# Tạo thư mục output nếu chưa có
output_dir = Path("./processing_output")
output_dir.mkdir(parents=True, exist_ok=True)

# Khởi tạo processor
processor = EduMateDocumentProcessor.create_balanced()

# In định dạng được hỗ trợ
print(f"📚 Supported formats: {processor.get_supported_formats()}")

# Xử lý file hoặc thư mục
if path.is_file():
    result = processor.process_file(path)

    print(f"\n✅ Processing completed!")
    print(f"📝 Content length: {len(result.content)} characters")
    print(f"📐 Formulas found: {len(result.formulas) if result.formulas else 0}")
    print(f"📊 Tables found: {len(result.tables) if result.tables else 0}")
    print(f"🖼️ Images found: {len(result.images) if result.images else 0}")

    # 1. Xuất ra JSON
    json_file = output_dir / f"{path.stem}_result.json"
    # json_file = output_dir / f"_result.json"
    processor.save_results(result, json_file, format="json")
    print(f"📄 JSON saved to: {json_file}")

    # 2. Xuất ra Markdown
    md_file = output_dir / f"{path.stem}_result.md"
    # md_file = output_dir / f"_result.md"
    processor.save_results(result, md_file, format="markdown")
    print(f"📝 Markdown saved to: {md_file}")

elif path.is_dir():
    results = processor.process_directory(path)

    successful = sum(1 for r in results.values() if r.success)
    total = len(results)

    print(f"\n📁 Processed {total} files, {successful} successful")

    # Tạo báo cáo tổng hợp
    report_path = output_dir / "processing_report"
    report = processor.create_processing_report(results, report_path)
    print(f"📊 Report saved with {report['summary']['success_rate']:.1%} success rate")

else:
    print(f"Invalid path: {path}")
