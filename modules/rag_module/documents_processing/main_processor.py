import logging
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Union
import json
import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

# Import all processors
from .base import (
    ProcessingPipeline, ProcessingConfig, ProcessingResult, 
    DocumentMetadata, ProcessingMode,
    ProcessorFactory
)

# Import specific processors to register them
from .pdf_processor import PDFProcessor
from .office_processor import DOCXProcessor, PPTXProcessor, XLSXProcessor
from .image_processor import ImageProcessor
from .formula_extractor import AdvancedFormulaExtractor


class DocumentProcessingSystem:
    """Main document processing system with caching and optimization"""
    
    def __init__(self, config: ProcessingConfig = None):
        self.config = config or ProcessingConfig()
        self.pipeline = ProcessingPipeline(self.config)
        self.cache = {}
        self.stats = {
            "processed_files": 0,
            "cache_hits": 0,
            "total_processing_time": 0.0,
            "errors": 0,
            "format_stats": {}
        }
        
        # Initialize logging
        self._setup_logging()
        
        # Validate configuration
        self._validate_config()
        
        logging.info("DocumentProcessingSystem initialized successfully")
    
    def _setup_logging(self):
        """Setup logging configuration"""
        log_level = logging.INFO
        if self.config.mode == ProcessingMode.FAST:
            log_level = logging.WARNING
        elif self.config.mode == ProcessingMode.ACCURATE:
            log_level = logging.DEBUG
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def _validate_config(self):
        """Validate processing configuration"""
        if not isinstance(self.config.max_workers, int) or self.config.max_workers < 1:
            self.config.max_workers = 4
            logging.warning("Invalid max_workers, set to default: 4")
        
        if not isinstance(self.config.chunk_size, int) or self.config.chunk_size < 100:
            self.config.chunk_size = 1000
            logging.warning("Invalid chunk_size, set to default: 1000")
    
    def process_file(self, file_path: Union[str, Path], use_cache: bool = True) -> ProcessingResult:
        """Process a single file with caching"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            return ProcessingResult(
                content="",
                metadata=DocumentMetadata(),
                success=False,
                error_message=f"File not found: {file_path}"
            )
        
        # Check cache
        cache_key = self._get_cache_key(file_path)
        if use_cache and cache_key in self.cache:
            self.stats["cache_hits"] += 1
            logging.info(f"Cache hit for {file_path.name}")
            return self.cache[cache_key]
        
        # Process file
        start_time = time.time()
        try:
            result = self.pipeline.process_document(file_path)
            
            # Update statistics
            processing_time = time.time() - start_time
            self._update_stats(file_path, processing_time, result.success)
            
            # Cache result if successful
            if use_cache and result.success:
                self.cache[cache_key] = result
            
            logging.info(f"Processed {file_path.name} in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            self.stats["errors"] += 1
            logging.error(f"Failed to process {file_path}: {e}")
            return ProcessingResult(
                content="",
                metadata=DocumentMetadata(),
                success=False,
                error_message=str(e)
            )
    
    def process_files(self, file_paths: List[Union[str, Path]], 
                     use_cache: bool = True, 
                     parallel: bool = None) -> List[ProcessingResult]:
        """Process multiple files"""
        if parallel is None:
            parallel = self.config.parallel_processing
        
        file_paths = [Path(p) for p in file_paths]
        
        if not parallel or len(file_paths) <= 1:
            # Sequential processing
            return [self.process_file(path, use_cache) for path in file_paths]
        else:
            # Parallel processing
            return self._process_files_parallel(file_paths, use_cache)
    
    def _process_files_parallel(self, file_paths: List[Path], use_cache: bool) -> List[ProcessingResult]:
        """Process files in parallel"""
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = [
                executor.submit(self.process_file, path, use_cache) 
                for path in file_paths
            ]
            return [future.result() for future in futures]
    
    async def process_file_async(self, file_path: Union[str, Path], use_cache: bool = True) -> ProcessingResult:
        """Process file asynchronously"""
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, self.process_file, file_path, use_cache)
    
    async def process_files_async(self, file_paths: List[Union[str, Path]], 
                                 use_cache: bool = True) -> List[ProcessingResult]:
        """Process multiple files asynchronously"""
        tasks = [
            self.process_file_async(path, use_cache) 
            for path in file_paths
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    def process_directory(self, directory_path: Union[str, Path], 
                         recursive: bool = True,
                         file_patterns: List[str] = None,
                         use_cache: bool = True) -> Dict[str, ProcessingResult]:
        """Process all supported files in a directory"""
        directory_path = Path(directory_path)
        
        if not directory_path.exists() or not directory_path.is_dir():
            raise ValueError(f"Invalid directory: {directory_path}")
        
        # Default file patterns for supported formats
        if file_patterns is None:
            file_patterns = [
                "*.pdf", "*.docx", "*.pptx", "*.xlsx",
                "*.png", "*.jpg", "*.jpeg", "*.tiff",
                "*.wav", "*.mp3", "*.html", "*.md"
            ]
        
        # Find all matching files
        files = []
        for pattern in file_patterns:
            if recursive:
                files.extend(directory_path.rglob(pattern))
            else:
                files.extend(directory_path.glob(pattern))
        
        # Remove duplicates and sort
        files = sorted(set(files))
        
        logging.info(f"Found {len(files)} files to process in {directory_path}")
        
        # Process files
        results = self.process_files(files, use_cache)
        
        # Return as dictionary with relative paths as keys
        return {
            str(file.relative_to(directory_path)): result 
            for file, result in zip(files, results)
        }
    
    def extract_formulas_from_content(self, content: Any) -> List[Dict[str, Any]]:
        """Extract mathematical formulas from various content types"""
        try:
            formula_extractor = AdvancedFormulaExtractor(self.config)
            return formula_extractor.extract_formulas(content)
        except Exception as e:
            logging.error(f"Formula extraction failed: {e}")
            return []
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported file formats"""
        formats = ProcessorFactory.get_supported_formats()
        return [fmt.value for fmt in formats]
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return {
            **self.stats,
            "config": asdict(self.config),
            "supported_formats": self.get_supported_formats(),
            "cache_size": len(self.cache),
            "avg_processing_time": (
                self.stats["total_processing_time"] / max(1, self.stats["processed_files"])
            )
        }
    
    def clear_cache(self):
        """Clear processing cache"""
        self.cache.clear()
        logging.info("Processing cache cleared")
    
    def save_results_to_json(self, results: Union[ProcessingResult, List[ProcessingResult], Dict[str, ProcessingResult]], 
                            output_path: Union[str, Path]):
        """Save processing results to JSON file"""
        output_path = Path(output_path)
        
        # Convert results to serializable format
        if isinstance(results, ProcessingResult):
            data = self._result_to_dict(results)
        elif isinstance(results, list):
            data = [self._result_to_dict(result) for result in results]
        elif isinstance(results, dict):
            data = {key: self._result_to_dict(result) for key, result in results.items()}
        else:
            raise ValueError("Invalid results type")
        
        # Save to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        
        logging.info(f"Results saved to {output_path}")
    
    def save_results_to_markdown(self, results: Union[ProcessingResult, List[ProcessingResult], Dict[str, ProcessingResult]], 
                               output_path: Union[str, Path]):
        """Save processing results to Markdown file"""
        output_path = Path(output_path)
        
        content_parts = []
        
        if isinstance(results, ProcessingResult):
            content_parts.append(self._result_to_markdown(results, "Document"))
        elif isinstance(results, list):
            for i, result in enumerate(results, 1):
                content_parts.append(self._result_to_markdown(result, f"Document {i}"))
        elif isinstance(results, dict):
            for filename, result in results.items():
                content_parts.append(self._result_to_markdown(result, filename))
        
        # Save to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n\n".join(content_parts))
        
        logging.info(f"Results saved to {output_path}")
    
    def _get_cache_key(self, file_path: Path) -> str:
        """Generate cache key for file"""
        # Use file path, size, and modification time for cache key
        stat = file_path.stat()
        key_data = f"{file_path}_{stat.st_size}_{stat.st_mtime}_{asdict(self.config)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _update_stats(self, file_path: Path, processing_time: float, success: bool):
        """Update processing statistics"""
        self.stats["processed_files"] += 1
        self.stats["total_processing_time"] += processing_time
        
        if not success:
            self.stats["errors"] += 1
        
        # Update format statistics
        file_format = file_path.suffix.lower()
        if file_format not in self.stats["format_stats"]:
            self.stats["format_stats"][file_format] = {"count": 0, "success": 0, "total_time": 0.0}
        
        self.stats["format_stats"][file_format]["count"] += 1
        self.stats["format_stats"][file_format]["total_time"] += processing_time
        if success:
            self.stats["format_stats"][file_format]["success"] += 1
    
    def _result_to_dict(self, result: ProcessingResult) -> Dict[str, Any]:
        """Convert ProcessingResult to dictionary"""
        return {
            "content": result.content,
            "metadata": asdict(result.metadata),
            "images": result.images or [],
            "tables": result.tables or [],
            "formulas": result.formulas or [],
            "chunks": result.chunks or [],
            "success": result.success,
            "error_message": result.error_message
        }
    
    def _result_to_markdown(self, result: ProcessingResult, title: str) -> str:
        """Convert ProcessingResult to markdown format"""
        parts = []
        # parts.append(f"## {title}")
        
        # if result.success:
        #     parts.append(f"**Status:** ✅ Success")
        #     if result.metadata.processing_time:
        #         parts.append(f"**Processing Time:** {result.metadata.processing_time:.2f}s")
        #     if result.metadata.confidence_score:
        #         parts.append(f"**Confidence:** {result.metadata.confidence_score:.2f}")
        # else:
        #     parts.append(f"**Status:** ❌ Failed")
        #     if result.error_message:
        #         parts.append(f"**Error:** {result.error_message}")
        
        # # Add metadata
        # if result.metadata.format:
        #     parts.append(f"**Format:** {result.metadata.format.value.upper()}")
        # if result.metadata.page_count:
        #     parts.append(f"**Pages:** {result.metadata.page_count}")
        
        # # Add extracted elements summary
        # if result.metadata.extracted_elements:
        #     elements = result.metadata.extracted_elements
        #     element_summary = ", ".join([f"{k}: {v}" for k, v in elements.items()])
        #     parts.append(f"**Extracted Elements:** {element_summary}")
        
        # Add content
        if result.content:
            parts.append(result.content)
        
        return "\n\n".join(parts)


# Convenience functions
def create_fast_processor() -> DocumentProcessingSystem:
    """Create processor optimized for speed"""
    config = ProcessingConfig(
        mode=ProcessingMode.FAST,
        parallel_processing=True,
        max_workers=8,
        extract_images=True,
        extract_tables=True,
        extract_formulas=True,
        use_llm_enhancement=False
    )
    return DocumentProcessingSystem(config)


def create_accurate_processor() -> DocumentProcessingSystem:
    """Create processor optimized for accuracy"""
    config = ProcessingConfig(
        mode=ProcessingMode.ACCURATE,
        parallel_processing=True,
        max_workers=4,
        extract_images=True,
        extract_tables=True,
        extract_formulas=True,
        use_llm_enhancement=True,
        preserve_layout=True
    )
    return DocumentProcessingSystem(config)


def create_balanced_processor() -> DocumentProcessingSystem:
    """Create processor with balanced speed and accuracy"""
    config = ProcessingConfig(
        mode=ProcessingMode.BALANCED,
        parallel_processing=True,
        max_workers=6,
        extract_images=True,
        extract_tables=True,
        extract_formulas=True,
        use_llm_enhancement=False
    )
    return DocumentProcessingSystem(config)


def create_custom_processor(
    mode: ProcessingMode = ProcessingMode.BALANCED,
    use_gpu: bool = True,
    extract_images: bool = True,
    extract_tables: bool = True,
    extract_formulas: bool = True,
    parallel_processing: bool = True,
    max_workers: int = 4,
    use_llm_enhancement: bool = False,
    language_hints: List[str] = None
) -> DocumentProcessingSystem:
    """Create processor with custom configuration"""
    config = ProcessingConfig(
        mode=mode,
        use_gpu=use_gpu,
        extract_images=extract_images,
        extract_tables=extract_tables,
        extract_formulas=extract_formulas,
        parallel_processing=parallel_processing,
        max_workers=max_workers,
        use_llm_enhancement=use_llm_enhancement,
        language_hints=language_hints
    )
    return DocumentProcessingSystem(config)


# Main interface class for easy import
class EduMateDocumentProcessor:
    def __init__(self, processor: DocumentProcessingSystem):
        self._processor = processor
    
    @classmethod
    def create_fast(cls) -> 'EduMateDocumentProcessor':
        """Create fast processing instance"""
        return cls(create_fast_processor())
    
    @classmethod
    def create_accurate(cls) -> 'EduMateDocumentProcessor':
        """Create accurate processing instance"""
        return cls(create_accurate_processor())
    
    @classmethod
    def create_balanced(cls) -> 'EduMateDocumentProcessor':
        """Create balanced processing instance"""
        return cls(create_balanced_processor())
    
    @classmethod
    def create_custom(cls, **kwargs) -> 'EduMateDocumentProcessor':
        """Create custom processing instance"""
        return cls(create_custom_processor(**kwargs))
    
    def process_file(self, file_path: Union[str, Path], use_cache: bool = True) -> ProcessingResult:
        """Process a single file"""
        return self._processor.process_file(file_path, use_cache)
    
    def process_files(self, file_paths: List[Union[str, Path]], 
                     use_cache: bool = True,
                     parallel: bool = None) -> List[ProcessingResult]:
        """Process multiple files"""
        return self._processor.process_files(file_paths, use_cache, parallel)
    
    def process_directory(self, directory_path: Union[str, Path],
                         recursive: bool = True,
                         file_patterns: List[str] = None,
                         use_cache: bool = True) -> Dict[str, ProcessingResult]:
        """Process all supported files in directory"""
        return self._processor.process_directory(directory_path, recursive, file_patterns, use_cache)
    
    def extract_formulas(self, content: Any) -> List[Dict[str, Any]]:
        """Extract mathematical formulas"""
        return self._processor.extract_formulas_from_content(content)
    
    async def process_file_async(self, file_path: Union[str, Path], use_cache: bool = True) -> ProcessingResult:
        """Process file asynchronously"""
        return await self._processor.process_file_async(file_path, use_cache)
    
    async def process_files_async(self, file_paths: List[Union[str, Path]], 
                                 use_cache: bool = True) -> List[ProcessingResult]:
        """Process files asynchronously"""
        return await self._processor.process_files_async(file_paths, use_cache)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return self._processor.get_processing_stats()
    
    def get_supported_formats(self) -> List[str]:
        """Get supported file formats"""
        return self._processor.get_supported_formats()
    
    def clear_cache(self):
        """Clear processing cache"""
        self._processor.clear_cache()
    
    def save_results(self, results: Any, output_path: Union[str, Path], format: str = "json"):
        """Save results to file"""
        if format.lower() == "json":
            self._processor.save_results_to_json(results, output_path)
        elif format.lower() == "markdown":
            self._processor.save_results_to_markdown(results, output_path)
        else:
            raise ValueError("Supported formats: 'json', 'markdown'")
    
    def batch_process_with_progress(self, file_paths: List[Union[str, Path]], 
                                   callback: callable = None) -> List[ProcessingResult]:
        """Process files with progress callback"""
        results = []
        total = len(file_paths)
        
        for i, file_path in enumerate(file_paths):
            result = self.process_file(file_path)
            results.append(result)
            
            if callback:
                callback(i + 1, total, file_path, result)
        
        return results
    
    def create_processing_report(self, results: Dict[str, ProcessingResult], 
                               output_dir: Union[str, Path] = None) -> Dict[str, Any]:
        """Create comprehensive processing report"""
        output_dir = Path(output_dir) if output_dir else Path.cwd()
        output_dir.mkdir(exist_ok=True)
        
        # Generate report data
        total_files = len(results)
        successful = sum(1 for r in results.values() if r.success)
        failed = total_files - successful
        
        # Format statistics
        format_stats = {}
        for filename, result in results.items():
            ext = Path(filename).suffix.lower()
            if ext not in format_stats:
                format_stats[ext] = {"total": 0, "success": 0, "failed": 0}
            format_stats[ext]["total"] += 1
            if result.success:
                format_stats[ext]["success"] += 1
            else:
                format_stats[ext]["failed"] += 1
        
        # Processing time analysis
        processing_times = [
            r.metadata.processing_time for r in results.values() 
            if r.metadata.processing_time
        ]
        avg_time = sum(processing_times) / len(processing_times) if processing_times else 0
        
        # Extracted elements summary
        total_images = sum(len(r.images) for r in results.values() if r.images)
        total_tables = sum(len(r.tables) for r in results.values() if r.tables)
        total_formulas = sum(len(r.formulas) for r in results.values() if r.formulas)
        
        report = {
            "summary": {
                "total_files": total_files,
                "successful": successful,
                "failed": failed,
                "success_rate": successful / total_files if total_files > 0 else 0,
                "average_processing_time": avg_time,
                "total_extracted_elements": {
                    "images": total_images,
                    "tables": total_tables,
                    "formulas": total_formulas
                }
            },
            "format_statistics": format_stats,
            "failed_files": [
                {"filename": filename, "error": result.error_message}
                for filename, result in results.items() if not result.success
            ],
            "processing_stats": self.get_stats(),
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Save detailed results
        self.save_results(results, output_dir / "detailed_results.json", "json")
        self.save_results(results, output_dir / "results_summary.md", "markdown")
        
        # Save report
        with open(output_dir / "processing_report.json", 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logging.info(f"Processing report saved to {output_dir}")
        return report


# Example usage and testing
def main():
    """Example usage of the document processing system"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python main_processor.py <file_or_directory>")
        return
    
    path = Path(sys.argv[1])
    
    # Create processor
    processor = EduMateDocumentProcessor.create_balanced()
    
    print(f"Supported formats: {processor.get_supported_formats()}")
    
    if path.is_file():
        # Process single file
        print(f"Processing file: {path}")
        result = processor.process_file(path)
        
        if result.success:
            print(f"✅ Success! Extracted {len(result.content)} characters")
            if result.formulas:
                print(f"📐 Found {len(result.formulas) if result.formulas else 0} formulas")
            if result.tables:
                print(f"📊 Found {len(result.tables) if result.tables else 0} tables")
            if result.images:
                print(f"🖼️ Found {len(result.images) if result.images else 0} images")
        else:
            print(f"❌ Failed: {result.error_message}")
    
    elif path.is_dir():
        # Process directory
        print(f"Processing directory: {path}")
        results = processor.process_directory(path)
        
        successful = sum(1 for r in results.values() if r.success)
        total = len(results)
        
        print(f"Processed {total} files, {successful} successful")
        
        # Create report
        report = processor.create_processing_report(results, path / "processing_report")
        print(f"Report saved with {report['summary']['success_rate']:.1%} success rate")
    
    else:
        print(f"Invalid path: {path}")
    
    # Print statistics
    stats = processor.get_stats()
    print(f"\nProcessing Statistics:")
    print(f"- Total files processed: {stats['processed_files']}")
    print(f"- Cache hits: {stats['cache_hits']}")
    print(f"- Errors: {stats['errors']}")
    print(f"- Average processing time: {stats['avg_processing_time']:.2f}s")


if __name__ == "__main__":
    main()