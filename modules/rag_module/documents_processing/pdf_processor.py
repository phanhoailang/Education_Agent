import time
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import json
import os
from dataclasses import dataclass

# Core processing libraries
try:
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.config.parser import ConfigParser
    from marker.output import text_from_rendered
    MARKER_AVAILABLE = True
except ImportError:
    MARKER_AVAILABLE = False
    logging.warning("Marker not available. Install with: pip install marker-pdf")

try:
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    from docling.pipeline.simple_pipeline import SimplePipeline
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    logging.warning("Docling not available. Install with: pip install docling")

# OCR and image processing
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    from PIL import Image
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

# Base classes
from .base import (
    DocumentProcessor, ProcessingConfig, ProcessingResult, 
    DocumentMetadata, DocumentFormat, ProcessingMode,
    FormulaExtractor, TableExtractor, ImageExtractor
)


@dataclass
class ChunkInfo:
    """Information about a chunk"""
    start_page: int
    end_page: int
    chunk_id: int
    total_chunks: int
    file_path: str
    temp_file_path: Optional[str] = None


class ChunkManager:
    """Manages file chunking and processing"""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.chunk_size_mb = getattr(config, 'chunk_size_mb', 50)  # Default 50MB per chunk
        self.chunk_overlap_pages = getattr(config, 'chunk_overlap_pages', 2)  # Overlap pages
        self.auto_chunk_threshold_mb = getattr(config, 'auto_chunk_threshold_mb', 100)  # Auto chunk if > 100MB
        self.temp_dir = Path(getattr(config, 'temp_dir', './temp_chunks'))
        self.temp_dir.mkdir(exist_ok=True)
    
    def should_chunk(self, file_path: Union[str, Path]) -> bool:
        """Check if file should be chunked based on size"""
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        return file_size_mb > self.auto_chunk_threshold_mb
    
    def get_pdf_info(self, file_path: Union[str, Path]) -> Tuple[int, float]:
        """Get PDF page count and file size"""
        if not PYMUPDF_AVAILABLE:
            return 0, 0
        
        try:
            doc = fitz.open(str(file_path))
            page_count = len(doc)
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            doc.close()
            return page_count, file_size_mb
        except Exception as e:
            logging.error(f"Error getting PDF info: {e}")
            return 0, 0
    
    def create_chunks(self, file_path: Union[str, Path]) -> List[ChunkInfo]:
        """Create chunks from PDF file"""
        if not PYMUPDF_AVAILABLE:
            logging.warning("PyMuPDF not available for chunking")
            return []
        
        try:
            doc = fitz.open(str(file_path))
            total_pages = len(doc)
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            
            # Calculate pages per chunk based on file size
            pages_per_chunk = max(10, int(total_pages * self.chunk_size_mb / file_size_mb))
            
            chunks = []
            chunk_id = 0
            
            for start_page in range(0, total_pages, pages_per_chunk - self.chunk_overlap_pages):
                end_page = min(start_page + pages_per_chunk - 1, total_pages - 1)
                
                # Create temporary PDF for this chunk
                temp_filename = f"chunk_{chunk_id}_{start_page}_{end_page}.pdf"
                temp_path = self.temp_dir / temp_filename
                
                # Extract pages to new PDF
                new_doc = fitz.open()
                for page_num in range(start_page, end_page + 1):
                    new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                
                new_doc.save(str(temp_path))
                new_doc.close()
                
                chunk_info = ChunkInfo(
                    start_page=start_page,
                    end_page=end_page,
                    chunk_id=chunk_id,
                    total_chunks=0,  # Will be set later
                    file_path=str(file_path),
                    temp_file_path=str(temp_path)
                )
                chunks.append(chunk_info)
                chunk_id += 1
                
                # If we've reached the end, break
                if end_page >= total_pages - 1:
                    break
            
            # Set total chunks for all chunks
            for chunk in chunks:
                chunk.total_chunks = len(chunks)
            
            doc.close()
            logging.info(f"Created {len(chunks)} chunks from {file_path}")
            return chunks
            
        except Exception as e:
            logging.error(f"Error creating chunks: {e}")
            return []
    
    def cleanup_chunks(self, chunks: List[ChunkInfo]):
        """Clean up temporary chunk files"""
        for chunk in chunks:
            if chunk.temp_file_path and os.path.exists(chunk.temp_file_path):
                try:
                    os.remove(chunk.temp_file_path)
                except Exception as e:
                    logging.warning(f"Could not remove temp file {chunk.temp_file_path}: {e}")
    
    def merge_chunk_results(self, chunk_results: List[Dict[str, Any]], chunks: List[ChunkInfo]) -> Dict[str, Any]:
        """Merge results from multiple chunks"""
        merged_content = []
        merged_metadata = {}
        merged_images = []
        merged_tables = []
        
        successful_chunks = 0
        total_processing_time = 0
        
        for i, (result, chunk) in enumerate(zip(chunk_results, chunks)):
            if result.get("success", False):
                successful_chunks += 1
                
                # Add content with chunk header
                content = result.get("content", "")
                if content.strip():
                    chunk_header = f"\n\n## Chunk {chunk.chunk_id + 1}/{chunk.total_chunks} (Pages {chunk.start_page + 1}-{chunk.end_page + 1})\n\n"
                    merged_content.append(chunk_header + content)
                
                # Merge images (adjust page numbers)
                chunk_images = result.get("images", [])
                for img in chunk_images:
                    if isinstance(img, dict) and "page" in img:
                        img["page"] = img["page"] + chunk.start_page
                        img["chunk_id"] = chunk.chunk_id
                    merged_images.append(img)
                
                # Merge tables (adjust page numbers)
                chunk_tables = result.get("tables", [])
                for table in chunk_tables:
                    if isinstance(table, dict) and "page" in table:
                        table["page"] = table["page"] + chunk.start_page
                        table["chunk_id"] = chunk.chunk_id
                    merged_tables.append(table)
                
                # Accumulate metadata
                chunk_metadata = result.get("metadata", {})
                if i == 0:  # Use first chunk's metadata as base
                    merged_metadata = chunk_metadata.copy()
                else:
                    # Merge numeric values
                    if "elements" in chunk_metadata:
                        if "elements" not in merged_metadata:
                            merged_metadata["elements"] = {}
                        for key, value in chunk_metadata["elements"].items():
                            if isinstance(value, (int, float)):
                                merged_metadata["elements"][key] = merged_metadata["elements"].get(key, 0) + value
        
        # Update final metadata
        merged_metadata["chunks_processed"] = successful_chunks
        merged_metadata["total_chunks"] = len(chunks)
        merged_metadata["chunked_processing"] = True
        
        return {
            "content": "\n".join(merged_content),
            "metadata": merged_metadata,
            "images": merged_images,
            "tables": merged_tables,
            "success": successful_chunks > 0,
            "processor": chunk_results[0].get("processor", "unknown") if chunk_results else "unknown",
            "chunks_info": {
                "total": len(chunks),
                "successful": successful_chunks,
                "failed": len(chunks) - successful_chunks
            }
        }


class MarkerProcessor:
    """Wrapper for Marker PDF processing"""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.converter = None
        self.chunk_manager = ChunkManager(config)
        self._initialize()
    
    def _initialize(self):
        """Initialize Marker converter"""
        if not MARKER_AVAILABLE:
            raise RuntimeError("Marker not available")
        
        try:
            # Configure Marker based on processing mode
            marker_config = {
                "output_format": "markdown",
                "use_llm": self.config.use_llm_enhancement,
                "format_lines": True,  # Better math and formatting
                "disable_image_extraction": not self.config.extract_images,
                "force_ocr": self.config.mode == ProcessingMode.OCR_HEAVY,
            }
            
            if self.config.use_gpu:
                marker_config["device"] = "cuda" if self.config.use_gpu else "cpu"
            
            config_parser = ConfigParser(marker_config)
            
            self.converter = PdfConverter(
                config=config_parser.generate_config_dict(),
                artifact_dict=create_model_dict(),
                processor_list=config_parser.get_processors(),
                renderer=config_parser.get_renderer()
            )
            
            logging.info("Marker processor initialized successfully")
            
        except Exception as e:
            logging.error(f"Failed to initialize Marker: {e}")
            raise
    
    def _process_single_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Process a single file with Marker"""
        try:
            rendered = self.converter(str(file_path))
            
            # Extract text properly from rendered
            if hasattr(rendered, 'text'):
                text = rendered.text
            elif hasattr(rendered, 'markdown'):
                text = rendered.markdown
            else:
                text = str(rendered)
            
            # Handle metadata properly
            metadata = {}
            images = []
            
            if hasattr(rendered, 'metadata'):
                metadata = rendered.metadata
            
            if hasattr(rendered, 'images'):
                images = rendered.images or []
            
            return {
                "content": text or "",
                "metadata": metadata,
                "images": images,
                "success": True,
                "processor": "marker"
            }
            
        except Exception as e:
            logging.error(f"Marker processing failed for {file_path}: {e}")
            return {
                "content": "",
                "metadata": {},
                "images": [],
                "success": False,
                "error": str(e),
                "processor": "marker"
            }
    
    def process(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Process PDF with Marker, with auto-chunking for large files"""
        
        # Check if file should be chunked
        if self.chunk_manager.should_chunk(file_path):
            logging.info(f"File {file_path} is large, processing with chunking...")
            return self._process_with_chunking(file_path)
        else:
            logging.info(f"File {file_path} is small enough, processing normally...")
            return self._process_single_file(file_path)
    
    def _process_with_chunking(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Process large PDF with chunking"""
        try:
            # Create chunks
            chunks = self.chunk_manager.create_chunks(file_path)
            if not chunks:
                logging.warning("Could not create chunks, falling back to normal processing")
                return self._process_single_file(file_path)
            
            # Process chunks
            chunk_results = []
            for i, chunk in enumerate(chunks):
                logging.info(f"Processing chunk {i+1}/{len(chunks)} (pages {chunk.start_page+1}-{chunk.end_page+1})")
                
                if chunk.temp_file_path:
                    result = self._process_single_file(chunk.temp_file_path)
                    chunk_results.append(result)
                else:
                    chunk_results.append({
                        "content": "",
                        "metadata": {},
                        "images": [],
                        "success": False,
                        "error": "No temp file path",
                        "processor": "marker"
                    })
            
            # Merge results
            merged_result = self.chunk_manager.merge_chunk_results(chunk_results, chunks)
            
            # Cleanup temporary files
            self.chunk_manager.cleanup_chunks(chunks)
            
            return merged_result
            
        except Exception as e:
            logging.error(f"Chunked processing failed: {e}")
            return {
                "content": "",
                "metadata": {},
                "images": [],
                "success": False,
                "error": str(e),
                "processor": "marker"
            }


class DoclingProcessor:
    """Wrapper for Docling PDF processing"""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.converter = None
        self.chunk_manager = ChunkManager(config)
        self._initialize()
    
    def _initialize(self):
        """Initialize Docling converter"""
        if not DOCLING_AVAILABLE:
            raise RuntimeError("Docling not available")
        
        try:
            # Tạo DocumentConverter trực tiếp mà không cần pipeline
            self.converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: {
                        "page_boundaries": True,
                        "extract_images": self.config.extract_images,
                        "extract_tables": self.config.extract_tables,
                        "ocr_enabled": self.config.enable_ocr,
                    }
                }
            )
            
            logging.info("Docling processor initialized successfully")
            
        except Exception as e:
            logging.error(f"Failed to initialize Docling: {e}")
            raise
    
    def _process_single_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Process a single file with Docling"""
        try:
            result = self.converter.convert(str(file_path))
            
            # Export to markdown
            markdown_content = result.document.export_to_markdown()
            
            # Extract metadata
            metadata = {
                "title": getattr(result.document, 'title', None),
                "page_count": len(result.document.pages) if hasattr(result.document, 'pages') else None,
                "elements": {}
            }
            
            # Count extracted elements
            if hasattr(result.document, 'tables'):
                metadata["elements"]["tables"] = len(result.document.tables)
            if hasattr(result.document, 'figures'):
                metadata["elements"]["figures"] = len(result.document.figures)
            
            return {
                "content": markdown_content,
                "metadata": metadata,
                "images": getattr(result.document, 'figures', []),
                "tables": getattr(result.document, 'tables', []),
                "success": True,
                "processor": "docling"
            }
            
        except Exception as e:
            logging.error(f"Docling processing failed for {file_path}: {e}")
            return {
                "content": "",
                "metadata": {},
                "images": [],
                "tables": [],
                "success": False,
                "error": str(e),
                "processor": "docling"
            }
    
    def process(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Process PDF with Docling, with auto-chunking for large files"""
        
        # Check if file should be chunked
        if self.chunk_manager.should_chunk(file_path):
            logging.info(f"File {file_path} is large, processing with chunking...")
            return self._process_with_chunking(file_path)
        else:
            logging.info(f"File {file_path} is small enough, processing normally...")
            return self._process_single_file(file_path)
    
    def _process_with_chunking(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Process large PDF with chunking"""
        try:
            # Create chunks
            chunks = self.chunk_manager.create_chunks(file_path)
            if not chunks:
                logging.warning("Could not create chunks, falling back to normal processing")
                return self._process_single_file(file_path)
            
            # Process chunks
            chunk_results = []
            for i, chunk in enumerate(chunks):
                logging.info(f"Processing chunk {i+1}/{len(chunks)} (pages {chunk.start_page+1}-{chunk.end_page+1})")
                
                if chunk.temp_file_path:
                    result = self._process_single_file(chunk.temp_file_path)
                    chunk_results.append(result)
                else:
                    chunk_results.append({
                        "content": "",
                        "metadata": {},
                        "images": [],
                        "tables": [],
                        "success": False,
                        "error": "No temp file path",
                        "processor": "docling"
                    })
            
            # Merge results
            merged_result = self.chunk_manager.merge_chunk_results(chunk_results, chunks)
            
            # Cleanup temporary files
            self.chunk_manager.cleanup_chunks(chunks)
            
            return merged_result
            
        except Exception as e:
            logging.error(f"Chunked processing failed: {e}")
            return {
                "content": "",
                "metadata": {},
                "images": [],
                "tables": [],
                "success": False,
                "error": str(e),
                "processor": "docling"
            }


class PyMuPDFProcessor:
    """Fallback processor using PyMuPDF"""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.chunk_manager = ChunkManager(config)
    
    def _process_single_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Process a single file with PyMuPDF"""
        if not PYMUPDF_AVAILABLE:
            return {
                "content": "",
                "metadata": {},
                "images": [],
                "success": False,
                "error": "PyMuPDF not available",
                "processor": "pymupdf"
            }
        
        try:
            doc = fitz.open(str(file_path))
            
            content_parts = []
            images = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Extract text
                text = page.get_text()
                if text.strip():
                    content_parts.append(f"\n\n## Page {page_num + 1}\n\n{text}")
                
                # Extract images if requested
                if self.config.extract_images:
                    image_list = page.get_images()
                    for img_index, img in enumerate(image_list):
                        try:
                            xref = img[0]
                            pix = fitz.Pixmap(doc, xref)
                            if pix.n - pix.alpha < 4:  # GRAY or RGB
                                img_data = pix.tobytes("png")
                                images.append({
                                    "page": page_num + 1,
                                    "index": img_index,
                                    "data": img_data,
                                    "format": "png"
                                })
                            pix = None
                        except:
                            continue
            
            doc.close()
            
            metadata = {
                "page_count": len(doc),
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "elements": {
                    "images": len(images)
                }
            }
            
            return {
                "content": "\n".join(content_parts),
                "metadata": metadata,
                "images": images,
                "success": True,
                "processor": "pymupdf"
            }
            
        except Exception as e:
            logging.error(f"PyMuPDF processing failed for {file_path}: {e}")
            return {
                "content": "",
                "metadata": {},
                "images": [],
                "success": False,
                "error": str(e),
                "processor": "pymupdf"
            }
        finally:
            if 'doc' in locals() and doc is not None:
                try:
                    doc.close()
                except:
                    pass
    
    def process(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Process PDF with PyMuPDF, with auto-chunking for large files"""
        
        # Check if file should be chunked
        if self.chunk_manager.should_chunk(file_path):
            logging.info(f"File {file_path} is large, processing with chunking...")
            return self._process_with_chunking(file_path)
        else:
            logging.info(f"File {file_path} is small enough, processing normally...")
            return self._process_single_file(file_path)
    
    def _process_with_chunking(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Process large PDF with chunking"""
        try:
            # Create chunks
            chunks = self.chunk_manager.create_chunks(file_path)
            if not chunks:
                logging.warning("Could not create chunks, falling back to normal processing")
                return self._process_single_file(file_path)
            
            # Process chunks
            chunk_results = []
            for i, chunk in enumerate(chunks):
                logging.info(f"Processing chunk {i+1}/{len(chunks)} (pages {chunk.start_page+1}-{chunk.end_page+1})")
                
                if chunk.temp_file_path:
                    result = self._process_single_file(chunk.temp_file_path)
                    chunk_results.append(result)
                else:
                    chunk_results.append({
                        "content": "",
                        "metadata": {},
                        "images": [],
                        "success": False,
                        "error": "No temp file path",
                        "processor": "pymupdf"
                    })
            
            # Merge results
            merged_result = self.chunk_manager.merge_chunk_results(chunk_results, chunks)
            
            # Cleanup temporary files
            self.chunk_manager.cleanup_chunks(chunks)
            
            return merged_result
            
        except Exception as e:
            logging.error(f"Chunked processing failed: {e}")
            return {
                "content": "",
                "metadata": {},
                "images": [],
                "success": False,
                "error": str(e),
                "processor": "pymupdf"
            }


class PDFProcessor(DocumentProcessor):
    """Advanced PDF processor with multiple backends"""
    
    def __init__(self, config: ProcessingConfig):
        self.processors = []
        self._current_processor = None
        super().__init__(config)
    
    def _initialize_processor(self) -> None:
        """Initialize available PDF processors in priority order"""
        
        # Priority 1: Marker (best for academic papers and complex layouts)
        if MARKER_AVAILABLE and self.config.mode in [ProcessingMode.ACCURATE, ProcessingMode.BALANCED]:
            try:
                self.processors.append(MarkerProcessor(self.config))
                logging.info("Marker processor added")
            except Exception as e:
                logging.warning(f"Failed to initialize Marker: {e}")
        
        # Priority 2: Docling (excellent for general documents)
        if DOCLING_AVAILABLE:
            try:
                self.processors.append(DoclingProcessor(self.config))
                logging.info("Docling processor added")
            except Exception as e:
                logging.warning(f"Failed to initialize Docling: {e}")
        
        # Priority 3: PyMuPDF (fallback)
        if PYMUPDF_AVAILABLE:
            self.processors.append(PyMuPDFProcessor(self.config))
            logging.info("PyMuPDF processor added as fallback")
        
        if not self.processors:
            raise RuntimeError("No PDF processors available. Install marker-pdf, docling, or PyMuPDF")
    
    def can_process(self, file_path: Union[str, Path]) -> bool:
        """Check if this processor can handle PDF files"""
        return Path(file_path).suffix.lower() == '.pdf'
    
    def process(self, file_path: Union[str, Path]) -> ProcessingResult:
        """Process PDF using the best available processor"""
        start_time = time.time()
        
        if not self.can_process(file_path):
            return ProcessingResult(
                content="",
                metadata=DocumentMetadata(),
                success=False,
                error_message="Not a PDF file"
            )
        
        # Try processors in priority order
        last_error = None
        for processor in self.processors:
            try:
                result = processor.process(file_path)
                
                if isinstance(result, dict) and result.get("success", False):
                    processing_time = time.time() - start_time
                    
                    result_metadata = result.get("metadata", {})
                    
                    metadata = DocumentMetadata(
                        title=result_metadata.get("title"),
                        page_count=result_metadata.get("page_count"),
                        format=DocumentFormat.PDF,
                        processing_time=processing_time,
                        extracted_elements=result_metadata.get("elements", {})
                    )
                    
                    # Add chunking info to metadata if available
                    if "chunks_processed" in result_metadata:
                        metadata.chunked_processing = result_metadata.get("chunked_processing", False)
                        metadata.chunks_info = result.get("chunks_info", {})
                    
                    return ProcessingResult(
                        content=result.get("content", ""),
                        metadata=metadata,
                        images=result.get("images", []),
                        tables=result.get("tables", []),
                        success=True
                    )
                else:
                    # Xử lý khi result là dict
                    if isinstance(result, dict):
                        last_error = result.get("error", "Unknown error")
                    else:
                        last_error = "Invalid result format"
                    continue
            except Exception as e:
                last_error = str(e)
                logging.warning(f"Processor {type(processor).__name__} failed: {e}")
                continue
        
        # All processors failed
        return ProcessingResult(
            content="",
            metadata=DocumentMetadata(format=DocumentFormat.PDF),
            success=False,
            error_message=f"All PDF processors failed. Last error: {last_error}"
        )
    
    async def process_async(self, file_path: Union[str, Path]) -> ProcessingResult:
        """Process PDF asynchronously"""
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, self.process, file_path)
    
    def process_batch_parallel(self, file_paths: List[Union[str, Path]]) -> List[ProcessingResult]:
        """Process multiple PDFs in parallel using multiprocessing"""
        if not self.config.parallel_processing:
            return [self.process(path) for path in file_paths]
        
        # For large batches, use process pool
        if len(file_paths) > 10:
            with ProcessPoolExecutor(max_workers=self.config.max_workers) as executor:
                futures = [executor.submit(self._process_single, path) for path in file_paths]
                return [future.result() for future in futures]
        else:
            # For smaller batches, use thread pool
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                futures = [executor.submit(self.process, path) for path in file_paths]
                return [future.result() for future in futures]
    
    def _process_single(self, file_path: Union[str, Path]) -> ProcessingResult:
        """Single file processing for multiprocessing"""
        # Reinitialize processor in new process
        processor = PDFProcessor(self.config)
        return processor.process(file_path)
    
    def get_processor_status(self) -> Dict[str, Any]:
        """Get status of available processors"""
        return {
            "available_processors": [type(p).__name__ for p in self.processors],
            "marker_available": MARKER_AVAILABLE,
            "docling_available": DOCLING_AVAILABLE,
            "pymupdf_available": PYMUPDF_AVAILABLE,
            "total_processors": len(self.processors)
        }


# Register the PDF processor
from .base import ProcessorFactory
ProcessorFactory.register_processor(DocumentFormat.PDF, PDFProcessor)