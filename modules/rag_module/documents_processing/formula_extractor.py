import re
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
import base64
import io
from concurrent.futures import ThreadPoolExecutor

# Image processing
try:
    from PIL import Image
    import cv2
    import numpy as np
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logging.warning("PIL/CV2 not available for image processing")

# pix2tex for LaTeX OCR
try:
    from pix2tex.cli import LatexOCR
    PIX2TEX_AVAILABLE = True
except ImportError:
    PIX2TEX_AVAILABLE = False
    logging.warning("pix2tex not available. Install with: pip install pix2tex[gui]")

# EasyOCR for general text
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    logging.warning("EasyOCR not available. Install with: pip install easyocr")

# Base classes
from .base import FormulaExtractor, ProcessingConfig, ProcessingMode


class Pix2TexExtractor:
    """Formula extractor using pix2tex (ViT-based LaTeX OCR)"""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.model = None
        self._initialize()
    
    def _initialize(self):
        """Initialize pix2tex model"""
        if not PIX2TEX_AVAILABLE:
            raise RuntimeError("pix2tex not available")
        
        try:
            self.model = LatexOCR()
            logging.info("pix2tex model loaded successfully")
        except Exception as e:
            logging.error(f"Failed to load pix2tex: {e}")
            raise
    
    def extract_latex(self, image: Union[Image.Image, np.ndarray, str]) -> str:
        """Extract LaTeX from formula image"""
        try:
            if isinstance(image, str):
                # Base64 or file path
                if image.startswith('data:'):
                    # Base64 data URL
                    image_data = base64.b64decode(image.split(',')[1])
                    image = Image.open(io.BytesIO(image_data))
                else:
                    # File path
                    image = Image.open(image)
            elif isinstance(image, np.ndarray):
                # Convert numpy array to PIL Image
                image = Image.fromarray(image)
            
            # Ensure RGB format
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Extract LaTeX using pix2tex
            latex_code = self.model(image)
            
            return latex_code.strip() if latex_code else ""
            
        except Exception as e:
            logging.error(f"pix2tex extraction failed: {e}")
            return ""
    
    def batch_extract(self, images: List[Any]) -> List[str]:
        """Extract LaTeX from multiple images"""
        results = []
        for image in images:
            latex = self.extract_latex(image)
            results.append(latex)
        return results


class EasyOCRExtractor:
    """Fallback OCR using EasyOCR"""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.reader = None
        self._initialize()
    
    def _initialize(self):
        """Initialize EasyOCR"""
        if not EASYOCR_AVAILABLE:
            raise RuntimeError("EasyOCR not available")
        
        try:
            languages = self.config.language_hints or ['en']
            self.reader = easyocr.Reader(languages, gpu=self.config.use_gpu)
            logging.info("EasyOCR initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize EasyOCR: {e}")
            raise
    
    def extract_text(self, image: Union[Image.Image, np.ndarray, str]) -> str:
        """Extract text from image"""
        try:
            if isinstance(image, Image.Image):
                image = np.array(image)
            elif isinstance(image, str):
                image = cv2.imread(image)
            
            results = self.reader.readtext(image)
            
            # Combine text results
            text_parts = []
            for (bbox, text, confidence) in results:
                if confidence > 0.5:  # Filter low confidence results
                    text_parts.append(text)
            
            return " ".join(text_parts)
            
        except Exception as e:
            logging.error(f"EasyOCR extraction failed: {e}")
            return ""


class ImagePreprocessor:
    """Image preprocessing for better OCR results"""
    
    @staticmethod
    def preprocess_for_formula_ocr(image: Union[Image.Image, np.ndarray]) -> Image.Image:
        """Preprocess image for better formula recognition"""
        if not PIL_AVAILABLE:
            return image
        
        try:
            if isinstance(image, Image.Image):
                image = np.array(image)
            
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                gray = image
            
            # Resize to optimal resolution (~300 DPI)
            height, width = gray.shape
            if height < 100 or width < 100:
                scale_factor = max(300 / height, 300 / width)
                new_height = int(height * scale_factor)
                new_width = int(width * scale_factor)
                gray = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            
            # Enhance contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            # Denoise
            denoised = cv2.medianBlur(enhanced, 3)
            
            # Threshold for binary image
            _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Convert back to PIL Image
            return Image.fromarray(binary)
            
        except Exception as e:
            logging.warning(f"Image preprocessing failed: {e}")
            return image if isinstance(image, Image.Image) else Image.fromarray(image)
    
    @staticmethod
    def detect_formula_regions(image: Union[Image.Image, np.ndarray]) -> List[Tuple[int, int, int, int]]:
        """Detect potential formula regions in image"""
        if not PIL_AVAILABLE:
            return []
        
        try:
            if isinstance(image, Image.Image):
                image = np.array(image)
            
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                gray = image
            
            # Find contours of potential formulas
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Filter contours by size and aspect ratio
            formula_regions = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                
                # Filter by size (not too small or too large)
                if w > 20 and h > 10 and w < gray.shape[1] * 0.8 and h < gray.shape[0] * 0.5:
                    # Check aspect ratio (formulas are often wider than tall)
                    aspect_ratio = w / h
                    if 0.5 <= aspect_ratio <= 10:
                        formula_regions.append((x, y, w, h))
            
            return formula_regions
            
        except Exception as e:
            logging.warning(f"Formula region detection failed: {e}")
            return []


class AdvancedFormulaExtractor(FormulaExtractor):
    """Advanced formula extractor with multiple backends"""
    
    def __init__(self, config: ProcessingConfig):
        self.config = config
        self.extractors = []
        self.preprocessor = ImagePreprocessor()
        self._initialize_extractors()
    
    def _initialize_extractors(self):
        """Initialize available formula extractors"""
        
        # Priority 1: pix2tex (best for clean formula images)
        if PIX2TEX_AVAILABLE:
            try:
                self.extractors.append(('pix2tex', Pix2TexExtractor(self.config)))
                logging.info("pix2tex extractor added")
            except Exception as e:
                logging.warning(f"Failed to initialize pix2tex: {e}")
        
        # Priority 2: EasyOCR (fallback)
        if EASYOCR_AVAILABLE:
            try:
                self.extractors.append(('easyocr', EasyOCRExtractor(self.config)))
                logging.info("EasyOCR extractor added")
            except Exception as e:
                logging.warning(f"Failed to initialize EasyOCR: {e}")
        
        if not self.extractors:
            logging.warning("No formula extractors available")
    
    def extract_formulas(self, content: Any) -> List[Dict[str, Any]]:
        """Extract formulas from various content types"""
        if isinstance(content, (str, Path)):
            # File path to image
            return self._extract_from_image_file(content)
        elif isinstance(content, (Image.Image, np.ndarray)):
            # Direct image
            return self._extract_from_image(content)
        elif isinstance(content, list):
            # List of images
            return self._extract_from_image_list(content)
        elif isinstance(content, dict) and 'images' in content:
            # Document result with images
            return self._extract_from_document_images(content['images'])
        else:
            logging.warning(f"Unsupported content type for formula extraction: {type(content)}")
            return []
    
    def _extract_from_image_file(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """Extract formulas from image file"""
        try:
            image = Image.open(file_path)
            return self._extract_from_image(image)
        except Exception as e:
            logging.error(f"Failed to load image {file_path}: {e}")
            return []
    
    def _extract_from_image(self, image: Union[Image.Image, np.ndarray]) -> List[Dict[str, Any]]:
        """Extract formulas from single image"""
        results = []
        
        # Preprocess image
        processed_image = self.preprocessor.preprocess_for_formula_ocr(image)
        
        # Detect potential formula regions
        formula_regions = self.preprocessor.detect_formula_regions(processed_image)
        
        if not formula_regions:
            # No specific regions detected, process entire image
            formula_regions = [(0, 0, processed_image.width, processed_image.height)]
        
        # Extract formulas from each region
        for i, (x, y, w, h) in enumerate(formula_regions):
            try:
                # Crop region
                region_image = processed_image.crop((x, y, x + w, y + h))
                
                # Try extractors in priority order
                latex_code = ""
                confidence = 0.0
                extractor_used = "none"
                
                for extractor_name, extractor in self.extractors:
                    try:
                        if extractor_name == 'pix2tex':
                            latex_code = extractor.extract_latex(region_image)
                            if latex_code and len(latex_code) > 3:
                                confidence = 0.9
                                extractor_used = extractor_name
                                break
                        elif extractor_name == 'easyocr':
                            text = extractor.extract_text(region_image)
                            if text and self._contains_math_symbols(text):
                                latex_code = text
                                confidence = 0.5
                                extractor_used = extractor_name
                                break
                    except Exception as e:
                        logging.warning(f"Extractor {extractor_name} failed: {e}")
                        continue
                
                if latex_code:
                    results.append({
                        "latex": latex_code,
                        "bbox": (x, y, w, h),
                        "confidence": confidence,
                        "extractor": extractor_used,
                        "region_index": i
                    })
                    
            except Exception as e:
                logging.warning(f"Failed to process formula region {i}: {e}")
                continue
        
        return results
    
    def _extract_from_image_list(self, images: List[Any]) -> List[Dict[str, Any]]:
        """Extract formulas from list of images"""
        all_results = []
        
        for i, image in enumerate(images):
            try:
                formulas = self._extract_from_image(image)
                # Add image index to results
                for formula in formulas:
                    formula['image_index'] = i
                all_results.extend(formulas)
            except Exception as e:
                logging.warning(f"Failed to process image {i}: {e}")
                continue
        
        return all_results
    
    def _extract_from_document_images(self, document_images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract formulas from document images"""
        all_results = []
        
        for i, image_info in enumerate(document_images):
            try:
                # Handle different image data formats
                if 'data' in image_info:
                    # Binary image data
                    image = Image.open(io.BytesIO(image_info['data']))
                elif 'path' in image_info:
                    # Image file path
                    image = Image.open(image_info['path'])
                elif 'base64' in image_info:
                    # Base64 encoded image
                    image_data = base64.b64decode(image_info['base64'])
                    image = Image.open(io.BytesIO(image_data))
                else:
                    logging.warning(f"Unknown image format in document image {i}")
                    continue
                
                formulas = self._extract_from_image(image)
                
                # Add document context to results
                for formula in formulas:
                    formula['document_image_index'] = i
                    formula['page'] = image_info.get('page', 0)
                    formula['source_format'] = image_info.get('format', 'unknown')
                
                all_results.extend(formulas)
                
            except Exception as e:
                logging.warning(f"Failed to process document image {i}: {e}")
                continue
        
        return all_results
    
    def formula_to_latex(self, formula_image: Any) -> str:
        formulas = self._extract_from_image(formula_image)
        if formulas:
            return formulas[0]['latex']
        return ""
    
    def _contains_math_symbols(self, text: str) -> bool:
        math_symbols = ['∫', '∑', '∏', '√', '±', '≤', '≥', '≠', '≈', '≡', 'α', 'β', 'γ', 'δ', 'ε']
        return any(symbol in text for symbol in math_symbols) or bool(re.search(r'[0-9]+[\^_]', text))

    def get_extractor_status(self) -> Dict[str, Any]:
        return {
            "available_extractors": [name for name, _ in self.extractors],
            "pix2tex_available": PIX2TEX_AVAILABLE,
            "easyocr_available": EASYOCR_AVAILABLE,
            "total_extractors": len(self.extractors)
        }
    
    async def extract_formulas_async(self, content: Any) -> List[Dict[str, Any]]:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, self.extract_formulas, content)