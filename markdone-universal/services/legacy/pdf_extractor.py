"""
PDF Content Extractor - High-Performance Edition
Handles extraction of text, images, and structure from PDF files using PyMuPDF (fitz).
Optimized for large files (30MB+) with memory-mapped I/O.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from io import BytesIO

import fitz  # PyMuPDF
from PIL import Image
from loguru import logger


class PDFExtractor:
    """Extract content from PDF files using PyMuPDF for high performance."""
    
    def __init__(self):
        """Initialize the PDF extractor."""
        self.image_counter = 0
    
    def extract(self, pdf_path: Path, source_type: str, progress_callback=None) -> Dict[str, Any]:
        """
        Extract content from PDF file using PyMuPDF (fitz).
        
        Args:
            pdf_path: Path to PDF file
            source_type: Type of source ('ppt' or 'word')
            progress_callback: Optional callback function(current, total) for progress updates
            
        Returns:
            Dictionary containing extracted content
        """
        try:
            # PyMuPDF uses mmap for large files, keeping RAM usage low
            doc = fitz.open(str(pdf_path))
            
            if source_type == "ppt":
                result = self._extract_powerpoint(doc, pdf_path, progress_callback)
            else:
                result = self._extract_word(doc, pdf_path, progress_callback)
            
            doc.close()
            return result
            
        except Exception as e:
            logger.error(f"Error extracting from {pdf_path}: {e}")
            return {}
    
    def _extract_powerpoint(self, doc: fitz.Document, pdf_path: Path, progress_callback=None) -> Dict[str, Any]:
        """
        Extract content from PowerPoint-originated PDF.
        
        Args:
            doc: PyMuPDF Document object
            pdf_path: Path to PDF file
            progress_callback: Optional callback function(current, total) for progress updates
            
        Returns:
            Dictionary with slides and notes
        """
        logger.debug("Extracting PowerPoint content")
        
        slides = []
        total_pages = len(doc)
        
        for page_num in range(total_pages):
            page = doc.load_page(page_num)
            
            # Report progress
            if progress_callback:
                progress_callback(page_num + 1, total_pages)
            
            slide_data = {
                'number': page_num + 1,
                'content': '',
                'notes': '',
                'images': []
            }
            
            # Extract text - PyMuPDF is faster than pdfplumber for large files
            text = page.get_text("text")
            
            # Try to separate slide content from notes
            # Common patterns: "Notes:", "Speaker Notes:", or horizontal separation
            notes_patterns = [
                r'(?:Speaker\s+)?Notes?:\s*(.+)',
                r'(?:^|\n)(?:Notes?|Comments?)[\s:]+(.+)',
            ]
            
            notes_content = ""
            slide_content = text
            
            for pattern in notes_patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if match:
                    notes_content = match.group(1).strip()
                    slide_content = text[:match.start()].strip()
                    break
            
            # If no notes pattern found, try to detect by position
            if not notes_content:
                lines = text.split('\n')
                for i, line in enumerate(lines):
                    if re.search(r'\b(?:notes?|comments?)\b', line, re.IGNORECASE):
                        slide_content = '\n'.join(lines[:i]).strip()
                        notes_content = '\n'.join(lines[i+1:]).strip()
                        break
            
            slide_data['content'] = slide_content
            slide_data['notes'] = notes_content
            
            # Extract images using PyMuPDF
            try:
                image_list = page.get_images()
                for img_idx, img in enumerate(image_list):
                    self.image_counter += 1
                    xref = img[0]
                    
                    # Get image bbox
                    img_rects = page.get_image_rects(xref)
                    if img_rects:
                        rect = img_rects[0]
                        img_data = {
                            'index': self.image_counter,
                            'page': page_num + 1,
                            'bbox': (rect.x0, rect.y0, rect.x1, rect.y1),
                            'width': rect.width,
                            'height': rect.height
                        }
                        slide_data['images'].append(img_data)
            except Exception as e:
                logger.warning(f"Could not extract images from page {page_num + 1}: {e}")
            
            # Extract tables using PyMuPDF
            try:
                tables = page.find_tables()
                if tables and tables.tables:
                    slide_data['tables'] = [table.extract() for table in tables.tables]
            except Exception as e:
                logger.warning(f"Could not extract tables from page {page_num + 1}: {e}")
            
            slides.append(slide_data)
        
        # Extract metadata
        metadata = doc.metadata or {}
        
        return {
            'type': 'powerpoint',
            'slides': slides,
            'total_pages': len(doc),
            'metadata': metadata
        }
    
    def _extract_word(self, doc: fitz.Document, pdf_path: Path, progress_callback=None) -> Dict[str, Any]:
        """
        Extract content from Word-originated PDF.
        
        Args:
            doc: PyMuPDF Document object
            pdf_path: Path to PDF file
            progress_callback: Optional callback function(current, total) for progress updates
            
        Returns:
            Dictionary with document content
        """
        logger.debug("Extracting Word document content")
        
        pages = []
        total_pages = len(doc)
        
        for page_num in range(total_pages):
            page = doc.load_page(page_num)
            
            # Report progress
            if progress_callback:
                progress_callback(page_num + 1, total_pages)
            
            page_data = {
                'number': page_num + 1,
                'content': '',
                'images': [],
                'tables': []
            }
            
            # Extract text - Higher speed than pdfplumber for 30MB+ files
            text = page.get_text("text")
            page_data['content'] = text
            
            # Extract images using PyMuPDF
            try:
                image_list = page.get_images()
                for img_idx, img in enumerate(image_list):
                    self.image_counter += 1
                    xref = img[0]
                    
                    # Get image bbox
                    img_rects = page.get_image_rects(xref)
                    if img_rects:
                        rect = img_rects[0]
                        img_data = {
                            'index': self.image_counter,
                            'page': page_num + 1,
                            'bbox': (rect.x0, rect.y0, rect.x1, rect.y1),
                            'width': rect.width,
                            'height': rect.height
                        }
                        page_data['images'].append(img_data)
            except Exception as e:
                logger.warning(f"Could not extract images from page {page_num + 1}: {e}")
            
            # Extract tables using PyMuPDF
            try:
                tables = page.find_tables()
                if tables and tables.tables:
                    page_data['tables'] = [table.extract() for table in tables.tables]
            except Exception as e:
                logger.warning(f"Could not extract tables from page {page_num + 1}: {e}")
            
            pages.append(page_data)
        
        # Try to detect document structure (headings, sections)
        full_text = '\n\n'.join(p['content'] for p in pages)
        structure = self._detect_document_structure(full_text)
        
        # Extract metadata
        metadata = doc.metadata or {}
        
        return {
            'type': 'word',
            'pages': pages,
            'total_pages': len(doc),
            'structure': structure,
            'metadata': metadata
        }
    
    def _detect_document_structure(self, text: str) -> Dict[str, Any]:
        """
        Detect document structure like headings and sections.
        
        Args:
            text: Full document text
            
        Returns:
            Dictionary with detected structure
        """
        structure = {
            'headings': [],
            'sections': []
        }
        
        lines = text.split('\n')
        
        # Patterns for detecting headings
        heading_patterns = [
            (r'^(Chapter|Section|Part)\s+\d+[:\.]?\s*(.+)', 1),  # Chapter/Section
            (r'^(\d+\.)+\s+(.+)', 2),  # Numbered headings (1.1, 1.1.1)
            (r'^([A-Z][A-Z\s]{3,})\s*$', 1),  # ALL CAPS headings
            (r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*$', 2),  # Title Case
        ]
        
        for line_num, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            for pattern, level in heading_patterns:
                match = re.match(pattern, line)
                if match:
                    structure['headings'].append({
                        'line': line_num,
                        'text': line,
                        'level': level
                    })
                    break
        
        return structure
    
    def extract_images_to_files(
        self,
        pdf_path: Path,
        output_dir: Path,
        image_format: str = 'png'
    ) -> List[Path]:
        """
        Extract images from PDF and save to files using PyMuPDF.
        
        Args:
            pdf_path: Path to PDF file
            output_dir: Directory to save images
            image_format: Image format (png, jpg)
            
        Returns:
            List of paths to extracted images
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        extracted_images = []
        
        try:
            doc = fitz.open(str(pdf_path))
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                try:
                    # Render page to pixmap (image) at 150 DPI
                    pix = page.get_pixmap(matrix=fitz.Matrix(150/72, 150/72))
                    
                    # Save page image
                    img_filename = f"{pdf_path.stem}_page_{page_num + 1}.{image_format}"
                    img_path = output_dir / img_filename
                    
                    if image_format.lower() == 'png':
                        pix.save(str(img_path))
                    else:
                        # Convert to PIL Image for other formats
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        img.save(str(img_path), format=image_format.upper())
                    
                    extracted_images.append(img_path)
                    
                except Exception as e:
                    logger.warning(f"Could not extract image from page {page_num + 1}: {e}")
            
            doc.close()
        
        except Exception as e:
            logger.error(f"Error extracting images from {pdf_path}: {e}")
        
        return extracted_images


# Made with Bob
