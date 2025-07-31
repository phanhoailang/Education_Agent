from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass
from enum import Enum
import asyncio
from pathlib import Path


class DocumentFormat(Enum):
    """Supported document formats"""
    PDF = "pdf"
    DOCX = "docx" 
    PPTX = "pptx"
    XLSX = "xlsx"
    HTML = "html"
    MARKDOWN = "md"
    TXT = "txt"
    IMAGE = "image"  # PNG, JPEG, TIFF


class ProcessingMode(Enum):
    """Document processing modes"""
    FAST = "fast"           # Quick processing, basic extraction
    BALANCED = "balanced"   # Balanced speed and accuracy
    ACCURATE = "accurate"   # Maximum accuracy, slower processing
    OCR_HEAVY = "ocr_heavy" # For scanned documents


@dataclass
class ProcessingConfig:
    """Configuration for document processing"""
    mode: ProcessingMode = ProcessingMode.BALANCED
    use_gpu: bool = True
    enable_ocr: bool = True
    extract_images: bool = True
    extract_tables: bool = True
    extract_formulas: bool = True
    parallel_processing: bool = True
    max_workers: int = 4
    chunk_size: int = 1000
    output_format: str = "markdown"
    preserve_layout: bool = True
    language_hints: List[str] = None
    use_llm_enhancement: bool = False
    llm_model: Optional[str] = None


@dataclass
class DocumentMetadata:
    """Document metadata container"""
    title: Optional[str] = None
    author: Optional[str] = None
    creation_date: Optional[str] = None
    modification_date: Optional[str] = None
    language: Optional[str] = None
    page_count: Optional[int] = None
    file_size: Optional[int] = None
    format: Optional[DocumentFormat] = None
    processing_time: Optional[float] = None
    confidence_score: Optional[float] = None
    extracted_elements: Dict[str, int] = None


@dataclass
class ProcessingResult:
    """Result container for processed documents"""
    content: str
    metadata: DocumentMetadata
    images: List[Dict[str, Any]] = None
    tables: List[Dict[str, Any]] = None
    formulas: List[Dict[str, Any]] = None
    chunks: List[Dict[str, Any]] = None
    raw_data: Optional[Dict[str, Any]] = None
    success: bool = True
    error_message: Optional[str] = None


class DocumentProcessor(ABC):
    """Abstract base class for document processors"""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
        self._initialize_processor()
    
    @abstractmethod
    def _initialize_processor(self) -> None:
        """Initialize the processor with required models/libraries"""
        pass
    
    @abstractmethod
    def can_process(self, file_path: Union[str, Path]) -> bool:
        """Check if this processor can handle the given file"""
        pass
    
    @abstractmethod
    def process(self, file_path: Union[str, Path]) -> ProcessingResult:
        """Process a single document"""
        pass
    
    @abstractmethod
    async def process_async(self, file_path: Union[str, Path]) -> ProcessingResult:
        """Process a single document asynchronously"""
        pass
    
    def process_batch(self, file_paths: List[Union[str, Path]]) -> List[ProcessingResult]:
        """Process multiple documents"""
        if self.config.parallel_processing:
            return asyncio.run(self._process_batch_async(file_paths))
        else:
            return [self.process(path) for path in file_paths]
    
    async def _process_batch_async(self, file_paths: List[Union[str, Path]]) -> List[ProcessingResult]:
        """Process multiple documents asynchronously"""
        semaphore = asyncio.Semaphore(self.config.max_workers)
        
        async def process_with_semaphore(path):
            async with semaphore:
                return await self.process_async(path)
        
        tasks = [process_with_semaphore(path) for path in file_paths]
        return await asyncio.gather(*tasks, return_exceptions=True)


class FormulaExtractor(ABC):
    """Abstract base class for formula extraction"""
    
    @abstractmethod
    def extract_formulas(self, content: Any) -> List[Dict[str, Any]]:
        """Extract mathematical formulas from content"""
        pass
    
    @abstractmethod
    def formula_to_latex(self, formula_image: Any) -> str:
        """Convert formula image to LaTeX"""
        pass


class TableExtractor(ABC):
    """Abstract base class for table extraction"""
    
    @abstractmethod
    def extract_tables(self, content: Any) -> List[Dict[str, Any]]:
        """Extract tables from content"""
        pass
    
    @abstractmethod
    def table_to_markdown(self, table_data: Any) -> str:
        """Convert table data to markdown format"""
        pass


class ImageExtractor(ABC):
    """Abstract base class for image extraction"""
    
    @abstractmethod
    def extract_images(self, content: Any) -> List[Dict[str, Any]]:
        """Extract images from content"""
        pass
    
    @abstractmethod
    def classify_image(self, image_data: Any) -> Dict[str, Any]:
        """Classify image type and content"""
        pass


class ProcessorFactory:
    """Factory class for creating appropriate document processors"""
    
    _processors = {}
    
    @classmethod
    def register_processor(cls, format_type: DocumentFormat, processor_class):
        """Register a processor for a specific document format"""
        cls._processors[format_type] = processor_class
    
    @classmethod
    def create_processor(cls, file_path: Union[str, Path], config: ProcessingConfig) -> DocumentProcessor:
        """Create appropriate processor for the given file"""
        file_path = Path(file_path)
        
        # Determine format from extension
        extension = file_path.suffix.lower().lstrip('.')
        
        # Map extensions to formats
        format_mapping = {
            'pdf': DocumentFormat.PDF,
            'docx': DocumentFormat.DOCX,
            'pptx': DocumentFormat.PPTX,
            'xlsx': DocumentFormat.XLSX,
            'html': DocumentFormat.HTML,
            'htm': DocumentFormat.HTML,
            'md': DocumentFormat.MARKDOWN,
            'markdown': DocumentFormat.MARKDOWN,
            'txt': DocumentFormat.TXT,
            'png': DocumentFormat.IMAGE,
            'jpg': DocumentFormat.IMAGE,
            'jpeg': DocumentFormat.IMAGE,
            'tiff': DocumentFormat.IMAGE,
        }
        
        document_format = format_mapping.get(extension)
        if not document_format:
            raise ValueError(f"Unsupported file format: {extension}")
        
        processor_class = cls._processors.get(document_format)
        if not processor_class:
            raise ValueError(f"No processor available for format: {document_format}")
        
        return processor_class(config)
    
    @classmethod
    def get_supported_formats(cls) -> List[DocumentFormat]:
        """Get list of supported document formats"""
        return list(cls._processors.keys())


class ProcessingPipeline:
    """Main processing pipeline orchestrator"""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.results_cache = {}
    
    def process_document(self, file_path: Union[str, Path]) -> ProcessingResult:
        """Process a single document through the pipeline"""
        try:
            processor = ProcessorFactory.create_processor(file_path, self.config)
            return processor.process(file_path)
        except Exception as e:
            return ProcessingResult(
                content="",
                metadata=DocumentMetadata(),
                success=False,
                error_message=str(e)
            )
    
    def process_documents(self, file_paths: List[Union[str, Path]]) -> List[ProcessingResult]:
        """Process multiple documents through the pipeline"""
        results = []
        
        # Group files by format for batch processing
        format_groups = {}
        for path in file_paths:
            try:
                processor = ProcessorFactory.create_processor(path, self.config)
                format_key = type(processor).__name__
                if format_key not in format_groups:
                    format_groups[format_key] = {'processor': processor, 'files': []}
                format_groups[format_key]['files'].append(path)
            except Exception as e:
                results.append(ProcessingResult(
                    content="",
                    metadata=DocumentMetadata(),
                    success=False,
                    error_message=str(e)
                ))
        
        # Process each format group
        for format_key, group in format_groups.items():
            try:
                batch_results = group['processor'].process_batch(group['files'])
                results.extend(batch_results)
            except Exception as e:
                for _ in group['files']:
                    results.append(ProcessingResult(
                        content="",
                        metadata=DocumentMetadata(),
                        success=False,
                        error_message=str(e)
                    ))
        
        return results
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return {
            'supported_formats': ProcessorFactory.get_supported_formats(),
            'config': self.config,
            'cache_size': len(self.results_cache)
        }