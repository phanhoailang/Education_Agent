# EduMate Document Processing System

A comprehensive, high-performance document processing system designed for educational AI applications. Supports multiple document formats with advanced OCR, formula extraction, and parallel processing capabilities.

## 🚀 Features

### Supported Formats
- **PDF Documents**: High-accuracy processing with Marker, Docling, and PyMuPDF
- **Office Documents**: DOCX, PPTX, XLSX with advanced table and image extraction
- **Images**: PNG, JPEG, TIFF with multi-engine OCR (Tesseract, EasyOCR, PaddleOCR)
- **Audio Files**: WAV, MP3 with automatic speech recognition (Whisper)
- **Mathematical Formulas**: LaTeX extraction using pix2tex and Surya OCR

### Key Capabilities
- 🔥 **High Performance**: GPU acceleration and parallel processing
- 🎯 **High Accuracy**: Multiple OCR engines with fallback mechanisms
- 📐 **Formula Extraction**: Advanced mathematical formula recognition and LaTeX conversion
- 🗃️ **Smart Caching**: Intelligent caching system for improved performance
- 🔄 **Async Support**: Full asynchronous processing capabilities
- 📊 **Comprehensive Reporting**: Detailed processing statistics and reports
- 🛠️ **Modular Design**: Easy to extend and customize

## 📦 Installation

### Basic Installation
```bash
pip install -r requirements.txt
```

### GPU Support (Recommended)
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install -r requirements.txt
```

### Optional Dependencies
```bash
# For enhanced features
pip install unstructured llamaparse

# For development
pip install -e .[dev]
```

## 🚀 Quick Start

### Basic Usage
```python
from EduMate.modules.rag_module.documents_processing import EduMateDocumentProcessor

# Create processor (balanced speed and accuracy)
processor = EduMateDocumentProcessor.create_balanced()

# Process single file
result = processor.process_file("document.pdf")
if result.success:
    print("Content:", result.content[:500] + "...")
    print("Formulas found:", len(result.formulas))
    print("Tables found:", len(result.tables))

# Process multiple files
results = processor.process_files([
    "paper1.pdf", 
    "presentation.pptx", 
    "spreadsheet.xlsx"
])

# Process entire directory
results = processor.process_directory(
    "./documents", 
    recursive=True
)
```

### Advanced Configuration
```python
# Custom processor configuration
processor = EduMateDocumentProcessor.create_custom(
    mode=ProcessingMode.ACCURATE,
    use_gpu=True,
    extract_formulas=True,
    extract_tables=True,
    parallel_processing=True,
    max_workers=8,
    language_hints=["en", "vi"]
)

# Process with progress tracking
def progress_callback(current, total, file_path, result):
    print(f"Progress: {current}/{total} - {file_path.name}")
    if not result.success:
        print(f"  Error: {result.error_message}")

results = processor.batch_process_with_progress(
    file_paths, 
    callback=progress_callback
)
```

### Formula Extraction
```python
# Extract formulas from images or documents
formulas = processor.extract_formulas("math_page.png")

for formula in formulas:
    print(f"LaTeX: {formula['latex']}")
    print(f"Confidence: {formula['confidence']:.2f}")
    print(f"Extractor: {formula['extractor']}")
```

### Async Processing
```python
import asyncio

async def process_async():
    # Process files asynchronously
    results = await processor.process_files_async([
        "doc1.pdf", "doc2.docx", "doc3.pptx"
    ])
    
    for result in results:
        if result.success:
            print(f"Processed successfully: {len(result.content)} chars")

asyncio.run(process_async())
```

## 🔧 Processing Modes

### Fast Mode
- Optimized for speed
- Basic text extraction
- Minimal formula processing
- Suitable for large-scale processing

```python
processor = EduMateDocumentProcessor.create_fast()
```

### Balanced Mode (Recommended)
- Good balance of speed and accuracy
- Full feature extraction
- Suitable for most use cases

```python
processor = EduMateDocumentProcessor.create_balanced()
```

### Accurate Mode
- Maximum accuracy
- Advanced processing with LLM enhancement
- Suitable for critical documents

```python
processor = EduMateDocumentProcessor.create_accurate()
```

## 📊 Processing Reports

```python
# Process directory and generate comprehensive report
results = processor.process_directory("./documents")

# Create detailed report
report = processor.create_processing_report(
    results, 
    output_dir="./processing_report"
)

print(f"Success rate: {report['summary']['success_rate']:.1%}")
print(f"Total formulas extracted: {report['summary']['total_extracted_elements']['formulas']}")
```

## 🛠️ Architecture

### Modular Design
```
EduMate/modules/rag_module/documents_processing/
├── base.py                 # Core interfaces and abstract classes
├── pdf_processor.py        # PDF processing with Marker/Docling
├── office_processor.py     # Office documents (DOCX/PPTX/XLSX)
├── image_processor.py      # Image and audio processing
├── formula_extractor.py    # Mathematical formula extraction
├── main_processor.py       # Main processing system
├── __init__.py            # Module interface
└── requirements.txt       # Dependencies
```

### Processing Pipeline
1. **Format Detection**: Automatic file format identification
2. **Processor Selection**: Choose optimal processor for each format
3. **Preprocessing**: Image enhancement, audio normalization
4. **Content Extraction**: Text, tables, images, formulas
5. **Post-processing**: Cleanup, formatting, validation
6. **Caching**: Store results for future use

## 🔧 Configuration Options

```python
from EduMate.modules.rag_module.documents_processing import ProcessingConfig, ProcessingMode

config = ProcessingConfig(
    mode=ProcessingMode.BALANCED,
    use_gpu=True,                    # Enable GPU acceleration
    enable_ocr=True,                 # Enable OCR for scanned documents
    extract_images=True,             # Extract images from documents
    extract_tables=True,             # Extract and format tables
    extract_formulas=True,           # Extract mathematical formulas
    parallel_processing=True,        # Enable parallel processing
    max_workers=4,                   # Number of worker processes
    chunk_size=1000,                 # Text chunk size for processing
    output_format="markdown",        # Output format
    preserve_layout=True,            # Preserve document layout
    language_hints=["en", "vi"],     # Language hints for OCR
    use_llm_enhancement=False,       # Use LLM for enhancement
)
```

## 📈 Performance Optimization

### GPU Acceleration
- Enable GPU for OCR and formula extraction
- Significantly faster processing for large batches
- Supports CUDA and MPS (Apple Silicon)

### Parallel Processing
- Multi-threaded document processing
- Configurable worker count
- Optimal for batch processing

### Caching
- Intelligent file-based caching
- Cache invalidation based on file changes
- Significant speedup for repeated processing

### Memory Management
- Efficient memory usage
- Large file handling
- Automatic cleanup

## 🧪 Testing and Validation

```python
# Check system dependencies
from EduMate.modules.rag_module.documents_processing import print_dependency_status
print_dependency_status()

# Validate processing with test files
processor = EduMateDocumentProcessor.create_balanced()

# Test different formats
test_files = [
    "test.pdf",      # PDF with text and formulas
    "test.docx",     # Word document with tables
    "test.pptx",     # PowerPoint with images
    "test.xlsx",     # Excel with formulas
    "test.png",      # Image with text
    "test.wav"       # Audio file
]

for file_path in test_files:
    if Path(file_path).exists():
        result = processor.process_file(file_path)
        print(f"{file_path}: {'✅' if result.success else '❌'}")
        if not result.success:
            print(f"  Error: {result.error_message}")

# Get processing statistics
stats = processor.get_stats()
print(f"Supported formats: {processor.get_supported_formats()}")
```

## 🐛 Troubleshooting

### Common Issues

#### 1. GPU Not Detected
```python
# Check GPU availability
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"GPU count: {torch.cuda.device_count()}")

# Force CPU if needed
processor = EduMateDocumentProcessor.create_custom(use_gpu=False)
```

#### 2. OCR Accuracy Issues
```python
# Try different OCR engines
config = ProcessingConfig(
    language_hints=["eng", "vie"],  # Specify languages
    enable_ocr=True,
    mode=ProcessingMode.ACCURATE
)

# Preprocess images for better OCR
from PIL import Image, ImageEnhance
image = Image.open("document.png")
enhancer = ImageEnhance.Contrast(image)
enhanced = enhancer.enhance(2.0)  # Increase contrast
```

#### 3. Memory Issues with Large Files
```python
# Reduce worker count for large files
config = ProcessingConfig(
    max_workers=2,  # Reduce from default 4
    parallel_processing=False  # Disable for very large files
)

# Process files individually
for file_path in large_files:
    result = processor.process_file(file_path)
    processor.clear_cache()  # Clear cache between files
```

#### 4. Formula Extraction Issues
```python
# Check formula extractor status
extractor = AdvancedFormulaExtractor(config)
status = extractor.get_extractor_status()
print(f"Available extractors: {status['available_extractors']}")

# Manually preprocess formula images
from EduMate.modules.rag_module.documents_processing.formula_extractor import ImagePreprocessor
preprocessed = ImagePreprocessor.preprocess_for_formula_ocr(image)
```

### Performance Tuning

#### Optimal Settings for Different Use Cases

**Large Scale Processing (1000+ files)**
```python
processor = EduMateDocumentProcessor.create_custom(
    mode=ProcessingMode.FAST,
    parallel_processing=True,
    max_workers=8,
    extract_formulas=False,  # Skip if not needed
    use_cache=True
)
```

**High Accuracy Research Documents**
```python
processor = EduMateDocumentProcessor.create_custom(
    mode=ProcessingMode.ACCURATE,
    extract_formulas=True,
    extract_tables=True,
    use_llm_enhancement=True,
    language_hints=["en"]
)
```

**Real-time Processing**
```python
processor = EduMateDocumentProcessor.create_custom(
    mode=ProcessingMode.FAST,
    parallel_processing=False,
    extract_images=False,
    use_cache=True
)
```

## 📚 API Reference

### Main Classes

#### `EduMateDocumentProcessor`
Main interface for document processing.

**Methods:**
- `create_fast()` - Create fast processor
- `create_balanced()` - Create balanced processor  
- `create_accurate()` - Create accurate processor
- `create_custom(**kwargs)` - Create custom processor
- `process_file(file_path, use_cache=True)` - Process single file
- `process_files(file_paths, use_cache=True, parallel=None)` - Process multiple files
- `process_directory(directory_path, recursive=True, file_patterns=None, use_cache=True)` - Process directory
- `extract_formulas(content)` - Extract mathematical formulas
- `get_stats()` - Get processing statistics
- `clear_cache()` - Clear processing cache

#### `ProcessingResult`
Result container for processed documents.

**Attributes:**
- `content: str` - Extracted text content
- `metadata: DocumentMetadata` - Document metadata
- `images: List[Dict]` - Extracted images
- `tables: List[Dict]` - Extracted tables
- `formulas: List[Dict]` - Extracted formulas
- `chunks: List[Dict]` - Content chunks
- `success: bool` - Processing success status
- `error_message: str` - Error message if failed

#### `ProcessingConfig`
Configuration for document processing.

**Parameters:**
- `mode: ProcessingMode` - Processing mode (FAST, BALANCED, ACCURATE, OCR_HEAVY)
- `use_gpu: bool` - Enable GPU acceleration
- `enable_ocr: bool` - Enable OCR for scanned documents
- `extract_images: bool` - Extract images from documents
- `extract_tables: bool` - Extract and format tables
- `extract_formulas: bool` - Extract mathematical formulas
- `parallel_processing: bool` - Enable parallel processing
- `max_workers: int` - Number of worker processes
- `chunk_size: int` - Text chunk size
- `output_format: str` - Output format
- `preserve_layout: bool` - Preserve document layout
- `language_hints: List[str]` - Language hints for OCR
- `use_llm_enhancement: bool` - Use LLM for enhancement

## 🤝 Contributing

### Development Setup
```bash
# Clone repository
git clone https://github.com/edumate/document-processor.git
cd document-processor

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install development dependencies
pip install -e .[dev]

# Run tests
pytest tests/

# Format code
black .
flake8 .
```

### Adding New Processors

1. **Create processor class** inheriting from `DocumentProcessor`
2. **Implement required methods**: `can_process()`, `process()`, `process_async()`
3. **Register processor** with `ProcessorFactory`
4. **Add tests** for the new processor

Example:
```python
from .base import DocumentProcessor, ProcessingResult

class MyCustomProcessor(DocumentProcessor):
    def can_process(self, file_path):
        return Path(file_path).suffix.lower() == '.myformat'
    
    def process(self, file_path):
        # Implementation here
        return ProcessingResult(...)
    
    async def process_async(self, file_path):
        # Async implementation
        return await ...

# Register the processor
from .base import ProcessorFactory, DocumentFormat
ProcessorFactory.register_processor(DocumentFormat.CUSTOM, MyCustomProcessor)
```

## 📄 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

This system builds upon several excellent open-source projects:

- **Marker** - High-accuracy PDF to Markdown conversion
- **Docling** - IBM's advanced document processing toolkit
- **pix2tex** - Vision Transformer for LaTeX OCR
- **Surya** - Modern OCR with formula support
- **OpenAI Whisper** - Robust speech recognition
- **EasyOCR** - Multi-language OCR support
- **PaddleOCR** - Production-ready OCR toolkit

Special thanks to the developers and maintainers of these projects for making advanced document processing accessible to everyone.

## 🔗 Links

- [Documentation](https://edumate.github.io/document-processor)
- [Issue Tracker](https://github.com/edumate/document-processor/issues)
- [Changelog](https://github.com/edumate/document-processor/blob/main/CHANGELOG.md)
- [PyPI Package](https://pypi.org/project/edumate-document-processor/)

---

## 📞 Support

For questions, issues, or contributions:

- 📧 Email: contact@edumate.ai
- 💬 GitHub Issues: [Create an issue](https://github.com/edumate/document-processor/issues)
- 📖 Documentation: [Read the docs](https://edumate.github.io/document-processor)

---

**Made with ❤️ for the EduMate AI ecosystem**