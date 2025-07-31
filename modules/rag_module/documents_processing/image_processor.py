import time
import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from concurrent.futures import ThreadPoolExecutor
from utils.auto_cleanup import auto_cleanup

# Image processing
try:
    from PIL import Image
    import cv2
    import numpy as np
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logging.warning("PIL/CV2 not available for image processing")

# OCR Libraries
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logging.warning("Tesseract not available")

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    logging.warning("EasyOCR not available")

# PDF generation
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logging.warning("ReportLab not available. Install with: pip install reportlab")

# Base classes
from .base import (
    DocumentProcessor, ProcessingConfig, ProcessingResult, 
    DocumentMetadata, DocumentFormat, ProcessingMode,
    ImageExtractor, ProcessorFactory
)


class ImageExtractorImpl(ImageExtractor):
    """Implementation of ImageExtractor for extracting images from documents"""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
    
    def extract_images(self, content: Any) -> List[Dict[str, Any]]:
        """Extract images from content"""
        # For image processor, this would extract embedded images or process the main image
        return []
    
    def classify_image(self, image_data: Any) -> Dict[str, Any]:
        """Classify image type and content"""
        if not PIL_AVAILABLE:
            return {"type": "unknown", "confidence": 0.0}
        
        try:
            if isinstance(image_data, (str, Path)):
                image = Image.open(image_data)
            else:
                image = image_data
            
            # Basic image classification
            classification = {
                "type": "document" if image.mode in ["1", "L"] else "photo",
                "mode": image.mode,
                "size": image.size,
                "format": image.format,
                "confidence": 0.8
            }
            
            # Check if it might be a scanned document
            if image.mode == "L" or (image.mode == "RGB" and self._is_document_like(image)):
                classification["type"] = "document"
                classification["confidence"] = 0.9
            
            return classification
            
        except Exception as e:
            logging.error(f"Image classification failed: {e}")
            return {"type": "unknown", "confidence": 0.0, "error": str(e)}
    
    def _is_document_like(self, image: Image.Image) -> bool:
        """Check if image looks like a document"""
        # Simple heuristic: documents tend to have more white/light pixels
        try:
            # Convert to grayscale
            gray = image.convert('L')
            # Get histogram
            hist = gray.histogram()
            # Check if there's a lot of white/light pixels (above 200)
            light_pixels = sum(hist[200:])
            total_pixels = sum(hist)
            return (light_pixels / total_pixels) > 0.3
        except:
            return False


class OCREngine:
    """Base class for OCR engines"""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
    
    def extract_text(self, image_path: Union[str, Path]) -> Dict[str, Any]:
        """Extract text from image"""
        raise NotImplementedError


class TesseractOCREngine(OCREngine):
    """Tesseract OCR engine implementation"""
    
    def __init__(self, config: ProcessingConfig):
        super().__init__(config)
        self.languages = '+'.join(config.language_hints) if config.language_hints else 'eng'
    
    def extract_text(self, image_path: Union[str, Path]) -> Dict[str, Any]:
        """Extract text using Tesseract"""
        if not TESSERACT_AVAILABLE or not PIL_AVAILABLE:
            return {
                "text": "",
                "confidence": 0.0,
                "success": False,
                "error": "Tesseract or PIL not available",
                "engine": "tesseract"
            }
        
        try:
            image = Image.open(image_path)
            
            # Preprocessing based on processing mode
            if self.config.mode == ProcessingMode.ACCURATE:
                image = self._enhance_image(image)
            
            # OCR extraction
            text = pytesseract.image_to_string(image, lang=self.languages)
            
            # Try to get confidence data
            confidence = 0.7  # Default
            try:
                data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
                confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
                if confidences:
                    confidence = sum(confidences) / len(confidences) / 100
            except:
                pass
            
            return {
                "text": text.strip(),
                "confidence": confidence,
                "success": True,
                "engine": "tesseract"
            }
            
        except Exception as e:
            logging.error(f"Tesseract OCR failed: {e}")
            return {
                "text": "",
                "confidence": 0.0,
                "success": False,
                "error": str(e),
                "engine": "tesseract"
            }
    
    def _enhance_image(self, image: Image.Image) -> Image.Image:
        """Enhance image for better OCR"""
        if not PIL_AVAILABLE:
            return image
        
        try:
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Convert to numpy array for OpenCV processing
            img_array = np.array(image)
            
            # Apply basic enhancement
            if cv2 is not None:
                # Convert to grayscale
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                
                # Apply denoising
                denoised = cv2.fastNlMeansDenoising(gray)
                
                # Apply adaptive threshold
                thresh = cv2.adaptiveThreshold(
                    denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
                )
                
                # Convert back to PIL
                return Image.fromarray(thresh)
            
            return image
            
        except Exception as e:
            logging.warning(f"Image enhancement failed: {e}")
            return image


class FallbackImageProcessor:
    """Fallback processor when no OCR engines are available"""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
    
class EasyOCREngine(OCREngine):
    """EasyOCR engine implementation"""
    
    def __init__(self, config: ProcessingConfig):
        super().__init__(config)
        self.reader = None
        self._initialize()
    
    def _initialize(self):
        """Initialize EasyOCR reader"""
        if not EASYOCR_AVAILABLE:
            raise RuntimeError("EasyOCR not available")
        
        try:
            languages = self.config.language_hints or ['en']
            # Map to valid EasyOCR languages
            valid_languages = ['en', 'ch_sim', 'ch_tra', 'ja', 'ko', 'fr', 'de', 'es', 'pt', 'ru']
            languages = [lang for lang in languages if lang in valid_languages]
            if not languages:
                languages = ['en']
            
            self.reader = easyocr.Reader(languages, gpu=self.config.use_gpu)
            logging.info("EasyOCR initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize EasyOCR: {e}")
            raise
    
    def extract_text(self, image_path: Union[str, Path]) -> Dict[str, Any]:
        """Extract text using EasyOCR"""
        if not self.reader:
            return {
                "text": "",
                "confidence": 0.0,
                "success": False,
                "error": "EasyOCR not initialized",
                "engine": "easyocr"
            }
        
        try:
            results = self.reader.readtext(str(image_path))
            
            # Combine results
            text_parts = []
            confidences = []
            
            for result in results:
                if len(result) >= 3:
                    bbox, text, confidence = result
                    if confidence > 0.1:  # Low threshold to capture more text
                        text_parts.append(text)
                        confidences.append(confidence)
            
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            return {
                "text": " ".join(text_parts),
                "confidence": avg_confidence,
                "success": True,
                "engine": "easyocr"
            }
            
        except Exception as e:
            logging.error(f"EasyOCR failed: {e}")
            return {
                "text": "",
                "confidence": 0.0,
                "success": False,
                "error": str(e),
                "engine": "easyocr"
            }
    """EasyOCR engine implementation"""
    
    def __init__(self, config: ProcessingConfig):
        super().__init__(config)
        self.reader = None
        self._initialize()
    
    def _initialize(self):
        """Initialize EasyOCR reader"""
        if not EASYOCR_AVAILABLE:
            raise RuntimeError("EasyOCR not available")
        
        try:
            languages = self.config.language_hints or ['en']
            # Map to valid EasyOCR languages
            valid_languages = ['en', 'ch_sim', 'ch_tra', 'ja', 'ko', 'fr', 'de', 'es', 'pt', 'ru']
            languages = [lang for lang in languages if lang in valid_languages]
            if not languages:
                languages = ['en']
            
            self.reader = easyocr.Reader(languages, gpu=self.config.use_gpu)
            logging.info("EasyOCR initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize EasyOCR: {e}")
            raise
    
    def extract_text(self, image_path: Union[str, Path]) -> Dict[str, Any]:
        """Extract text using EasyOCR"""
        if not self.reader:
            return {
                "text": "",
                "confidence": 0.0,
                "success": False,
                "error": "EasyOCR not initialized",
                "engine": "easyocr"
            }
        
        try:
            results = self.reader.readtext(str(image_path))
            
            # Combine results
            text_parts = []
            confidences = []
            
            for result in results:
                if len(result) >= 3:
                    bbox, text, confidence = result
                    if confidence > 0.1:  # Low threshold to capture more text
                        text_parts.append(text)
                        confidences.append(confidence)
            
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            return {
                "text": " ".join(text_parts),
                "confidence": avg_confidence,
                "success": True,
                "engine": "easyocr"
            }
            
        except Exception as e:
            logging.error(f"EasyOCR failed: {e}")
            return {
                "text": "",
                "confidence": 0.0,
                "success": False,
                "error": str(e),
                "engine": "easyocr"
            }


class ImageToPDFConverter:
    """Convert images to PDF for processing with PDF processors"""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
    
    def convert(self, image_path: Union[str, Path]) -> Optional[Path]:
        """Convert image to PDF"""
        image_path = Path(image_path)
        
        if not self._is_supported_image(image_path):
            return None
        
        temp_dir = Path(tempfile.gettempdir())
        pdf_path = temp_dir / f"{image_path.stem}_temp.pdf"

        auto_cleanup(pdf_path, timeout=1800)
        
        # Try multiple conversion methods
        conversion_methods = [
            self._convert_with_reportlab,
            self._convert_with_img2pdf,
            self._convert_with_pillow
        ]
        
        for method in conversion_methods:
            try:
                if method(image_path, pdf_path):
                    logging.info(f"Successfully converted {image_path} to PDF using {method.__name__}")
                    return pdf_path
            except Exception as e:
                logging.debug(f"Conversion method {method.__name__} failed: {e}")
                continue
        
        logging.warning("All image to PDF conversion methods failed")
        return None
    
    def _is_supported_image(self, file_path: Path) -> bool:
        """Check if image format is supported"""
        supported = {'.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.gif'}
        return file_path.suffix.lower() in supported
    
    def _convert_with_reportlab(self, image_path: Path, pdf_path: Path) -> bool:
        """Convert using ReportLab"""
        if not REPORTLAB_AVAILABLE or not PIL_AVAILABLE:
            return False
        
        try:
            # Load image and get dimensions
            image = Image.open(image_path)
            img_width, img_height = image.size
            
            # Calculate scale to fit A4
            page_width, page_height = A4
            margin = 72  # 1 inch margin
            available_width = page_width - 2 * margin
            available_height = page_height - 2 * margin - 100  # Extra space for title
            
            # Scale image to fit page
            scale_x = available_width / img_width
            scale_y = available_height / img_height
            scale = min(scale_x, scale_y, 0.8)  # Max 80% of available space
            
            new_width = img_width * scale
            new_height = img_height * scale
            
            # Create PDF
            from reportlab.pdfgen import canvas as pdf_canvas
            
            c = pdf_canvas.Canvas(str(pdf_path), pagesize=A4)
            
            # Add title
            c.setFont("Helvetica-Bold", 16)
            c.drawString(margin, page_height - margin, f"Image: {image_path.name}")
            
            # Convert image for ReportLab
            if image.mode == 'RGBA':
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Save temp image
            temp_img_path = pdf_path.parent / f"temp_rl_{image_path.name}"
            image.save(temp_img_path, 'JPEG', quality=85)
            
            # Calculate position to center image
            x_pos = margin + (available_width - new_width) / 2
            y_pos = margin + (available_height - new_height) / 2
            
            # Draw image
            c.drawImage(str(temp_img_path), x_pos, y_pos, width=new_width, height=new_height)
            
            # Save PDF
            c.save()
            
            # Clean up temp image
            try:
                temp_img_path.unlink()
            except:
                pass
            
            return pdf_path.exists() and pdf_path.stat().st_size > 0
            
        except Exception as e:
            logging.debug(f"ReportLab image conversion failed: {e}")
            return False
    
    def _convert_with_img2pdf(self, image_path: Path, pdf_path: Path) -> bool:
        """Convert using img2pdf library"""
        try:
            import img2pdf
            
            # Load image
            image = Image.open(image_path)
            
            # Convert RGBA to RGB if needed
            if image.mode == 'RGBA':
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])
                image = background
            
            # Save as temp JPEG if needed
            if image.mode != 'RGB':
                temp_img = pdf_path.parent / f"temp_{image_path.stem}.jpg"
                image.convert('RGB').save(temp_img, 'JPEG')
                image_path = temp_img
            
            # Convert to PDF
            with open(pdf_path, "wb") as f:
                f.write(img2pdf.convert(str(image_path)))
            
            # Clean up temp file
            if 'temp_img' in locals():
                try:
                    temp_img.unlink()
                except:
                    pass
            
            return pdf_path.exists()
            
        except ImportError:
            logging.debug("img2pdf not available")
            return False
        except Exception as e:
            logging.debug(f"img2pdf conversion failed: {e}")
            return False
    
    def _convert_with_pillow(self, image_path: Path, pdf_path: Path) -> bool:
        """Convert using PIL (fallback)"""
        if not PIL_AVAILABLE:
            return False
        
        try:
            image = Image.open(image_path)
            
            # Convert to RGB if needed
            if image.mode == 'RGBA':
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Save as PDF
            image.save(pdf_path, 'PDF', resolution=100.0)
            return pdf_path.exists()
            
        except Exception as e:
            logging.debug(f"PIL PDF conversion failed: {e}")
            return False


class ImageProcessor(DocumentProcessor):
    """Main image processor that inherits from DocumentProcessor"""
    
    def __init__(self, config: ProcessingConfig):
        # Initialize attributes first
        self.ocr_engines = []
        self.pdf_converter = None
        self.image_extractor = None
        # Then call parent __init__ which will call _initialize_processor
        super().__init__(config)
    
    def _initialize_processor(self) -> None:
        """Initialize the processor with required models/libraries"""
        # Initialize OCR engines
        if EASYOCR_AVAILABLE:
            try:
                self.ocr_engines.append(EasyOCREngine(self.config))
                logging.info("EasyOCR engine initialized")
            except Exception as e:
                logging.warning(f"Failed to initialize EasyOCR: {e}")
        
        if TESSERACT_AVAILABLE:
            try:
                self.ocr_engines.append(TesseractOCREngine(self.config))
                logging.info("Tesseract engine initialized")
            except Exception as e:
                logging.warning(f"Failed to initialize Tesseract: {e}")
        
        # Add fallback processor if no OCR engines available
        if not self.ocr_engines:
            logging.warning("No OCR engines available, using fallback processor")
            self.ocr_engines.append(FallbackImageProcessor(self.config))
        
        # Initialize PDF converter
        self.pdf_converter = ImageToPDFConverter(self.config)
        
        # Initialize image extractor
        self.image_extractor = ImageExtractorImpl(self.config)
    
    def can_process(self, file_path: Union[str, Path]) -> bool:
        """Check if this processor can handle the given file"""
        supported_extensions = {'.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.gif'}
        return Path(file_path).suffix.lower() in supported_extensions
    
    def process(self, file_path: Union[str, Path]) -> ProcessingResult:
        """Process a single document"""
        start_time = time.time()
        file_path = Path(file_path)
        
        if not self.can_process(file_path):
            return ProcessingResult(
                content="",
                metadata=DocumentMetadata(),
                success=False,
                error_message=f"Unsupported file format: {file_path.suffix}"
            )
        
        if not file_path.exists():
            return ProcessingResult(
                content="",
                metadata=DocumentMetadata(),
                success=False,
                error_message=f"File not found: {file_path}"
            )
        
        try:
            # Try PDF conversion first (leverage existing PDF processors)
            if self.config.mode != ProcessingMode.FAST:
                pdf_result = self._try_pdf_conversion(file_path)
                if pdf_result and pdf_result.success:
                    pdf_result.metadata.processing_time = time.time() - start_time
                    return pdf_result
            
            # Fallback to direct OCR processing
            return self._process_with_ocr(file_path, start_time)
            
        except Exception as e:
            logging.error(f"Image processing failed: {e}")
            return ProcessingResult(
                content="",
                metadata=DocumentMetadata(
                    format=DocumentFormat.IMAGE,
                    processing_time=time.time() - start_time
                ),
                success=False,
                error_message=str(e)
            )
    
    def _try_pdf_conversion(self, file_path: Path) -> Optional[ProcessingResult]:
        """Try to convert image to PDF and process with PDF processor"""
        try:
            pdf_path = self.pdf_converter.convert(file_path)
            if pdf_path and pdf_path.exists():
                # Try to import and use PDF processor
                try:
                    from .pdf_processor import PDFProcessor
                    pdf_processor = PDFProcessor(self.config)
                    result = pdf_processor.process(pdf_path)
                    
                    # Clean up temp PDF
                    try:
                        pdf_path.unlink()
                    except:
                        pass
                    
                    if result.success:
                        # Update metadata to reflect image origin
                        result.metadata.format = DocumentFormat.IMAGE
                        result.metadata.title = result.metadata.title or file_path.stem
                        if result.metadata.extracted_elements:
                            result.metadata.extracted_elements["conversion_method"] = "image-to-pdf"
                        
                        return result
                        
                except ImportError as e:
                    logging.debug(f"PDF processor not available: {e}")
                    # Clean up temp PDF
                    try:
                        pdf_path.unlink()
                    except:
                        pass
                    
        except Exception as e:
            logging.debug(f"PDF conversion approach failed: {e}")
        
        return None
    
    def _process_with_ocr(self, file_path: Path, start_time: float) -> ProcessingResult:
        """Process image directly with OCR"""
        if not self.ocr_engines:
            return ProcessingResult(
                content="No OCR engines available. Please install pytesseract or easyocr.",
                metadata=DocumentMetadata(
                    format=DocumentFormat.IMAGE,
                    processing_time=time.time() - start_time,
                    title=file_path.stem
                ),
                success=False,
                error_message="No OCR engines available"
            )
        
        best_result = None
        best_confidence = 0.0
        
        # Try each OCR engine
        for engine in self.ocr_engines:
            try:
                ocr_result = engine.extract_text(file_path)
                
                if ocr_result["success"] and ocr_result["confidence"] > best_confidence:
                    best_result = ocr_result
                    best_confidence = ocr_result["confidence"]
                    
                    # If we get good confidence, use it
                    if best_confidence > 0.8:
                        break
                        
            except Exception as e:
                logging.warning(f"OCR engine {type(engine).__name__} failed: {e}")
                continue
        
        if not best_result or not best_result["success"]:
            return ProcessingResult(
                content="Failed to extract text from image.",
                metadata=DocumentMetadata(
                    format=DocumentFormat.IMAGE,
                    processing_time=time.time() - start_time,
                    title=file_path.stem
                ),
                success=False,
                error_message="All OCR engines failed"
            )
        
        # Format content
        content = best_result["text"].strip()
        if content:
            content = f"## Extracted Text from Image\n\n{content}"
        else:
            content = "No text content extracted from image."
        
        # Get image info
        image_info = self._get_image_info(file_path)
        
        # Create metadata
        metadata = DocumentMetadata(
            title=file_path.stem,
            format=DocumentFormat.IMAGE,
            processing_time=time.time() - start_time,
            confidence_score=best_confidence,
            file_size=file_path.stat().st_size,
            extracted_elements={
                "text_extracted": 1 if content.strip() else 0,
                "ocr_engine_used": 1,
                "image_info_extracted": 1
            }
        )
        
        return ProcessingResult(
            content=content,
            metadata=metadata,
            success=True
        )
    
    def _get_image_info(self, image_path: Path) -> Dict[str, Any]:
        """Get basic image information"""
        try:
            if PIL_AVAILABLE:
                image = Image.open(image_path)
                info = {
                    "width": image.width,
                    "height": image.height,
                    "mode": image.mode,
                    "format": image.format,
                    "size_bytes": image_path.stat().st_size
                }
                
                # Add classification
                if self.image_extractor:
                    classification = self.image_extractor.classify_image(image)
                    info.update(classification)
                
                return info
        except Exception as e:
            logging.debug(f"Failed to get image info: {e}")
        
        return {"size_bytes": image_path.stat().st_size if image_path.exists() else 0}
    
    async def process_async(self, file_path: Union[str, Path]) -> ProcessingResult:
        """Process a single document asynchronously"""
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            return await loop.run_in_executor(executor, self.process, file_path)


# Register the processor
ProcessorFactory.register_processor(DocumentFormat.IMAGE, ImageProcessor)