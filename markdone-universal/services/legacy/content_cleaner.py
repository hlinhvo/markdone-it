"""
Content Cleaner
Removes artifacts, formatting marks, and unnecessary elements from extracted PDF content.
"""

import re
from typing import Dict, List, Any
from loguru import logger


class ContentCleaner:
    """Clean and normalize extracted PDF content."""
    
    def __init__(self):
        """Initialize the content cleaner."""
        # Common artifacts to remove
        self.common_artifacts = [
            r'\f',  # Form feed
            r'\x0c',  # Page break
            r'[\u200b-\u200f\u202a-\u202e]',  # Zero-width and direction marks
            r'\ufeff',  # BOM
        ]
        
        # PowerPoint-specific artifacts
        self.ppt_artifacts = [
            r'Slide\s+\d+\s+of\s+\d+',
            r'^\d+/\d+$',  # Slide numbers like "1/10"
            r'^Page\s+\d+$',
            r'Click to add (?:title|text|notes)',
            r'(?:Transition|Animation):\s*\w+',
            r'Layout:\s*\w+',
        ]
        
        # Word-specific artifacts
        self.word_artifacts = [
            r'Page\s+\d+\s+of\s+\d+',
            r'^-\s*\d+\s*-$',  # Page numbers like "- 5 -"
            r'^\d+$',  # Standalone page numbers
            r'(?:Header|Footer):\s*.+',
        ]
        
        # Common header/footer patterns
        self.header_footer_patterns = [
            r'^(?:Confidential|Internal|Draft|Private)(?:\s+[-–—]\s+.+)?$',
            r'^\d{1,2}/\d{1,2}/\d{2,4}$',  # Dates
            r'^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+.+$',
            r'©\s*\d{4}',  # Copyright
        ]
    
    def clean(self, extracted_data: Dict[str, Any], source_type: str) -> Dict[str, Any]:
        """
        Clean extracted content based on source type.
        
        Args:
            extracted_data: Extracted content dictionary
            source_type: Type of source ('ppt' or 'word')
            
        Returns:
            Cleaned content dictionary
        """
        if source_type == "ppt" or extracted_data.get('type') == 'powerpoint':
            return self._clean_powerpoint(extracted_data)
        else:
            return self._clean_word(extracted_data)
    
    def _clean_powerpoint(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean PowerPoint-originated content.
        
        Args:
            data: Extracted PowerPoint data
            
        Returns:
            Cleaned data
        """
        logger.debug("Cleaning PowerPoint content")
        
        cleaned_slides = []
        
        for slide in data.get('slides', []):
            cleaned_slide = {
                'number': slide['number'],
                'content': self._clean_text(slide.get('content', ''), 'ppt'),
                'notes': self._clean_text(slide.get('notes', ''), 'ppt'),
                'images': slide.get('images', []),
                'tables': slide.get('tables', [])
            }
            
            # Clean tables if present
            if 'tables' in cleaned_slide and cleaned_slide['tables']:
                cleaned_slide['tables'] = [
                    self._clean_table(table) for table in cleaned_slide['tables']
                ]
            
            cleaned_slides.append(cleaned_slide)
        
        data['slides'] = cleaned_slides
        return data
    
    def _clean_word(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean Word-originated content.
        
        Args:
            data: Extracted Word document data
            
        Returns:
            Cleaned data
        """
        logger.debug("Cleaning Word document content")
        
        cleaned_pages = []
        
        for page in data.get('pages', []):
            cleaned_page = {
                'number': page['number'],
                'content': self._clean_text(page.get('content', ''), 'word'),
                'images': page.get('images', []),
                'tables': page.get('tables', [])
            }
            
            # Clean tables if present
            if 'tables' in cleaned_page and cleaned_page['tables']:
                cleaned_page['tables'] = [
                    self._clean_table(table) for table in cleaned_page['tables']
                ]
            
            cleaned_pages.append(cleaned_page)
        
        data['pages'] = cleaned_pages
        return data
    
    def _clean_text(self, text: str, source_type: str) -> str:
        """
        Clean text content by removing artifacts and normalizing.
        
        Args:
            text: Text to clean
            source_type: Source type ('ppt' or 'word')
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove common artifacts
        for pattern in self.common_artifacts:
            text = re.sub(pattern, '', text)
        
        # Remove source-specific artifacts
        artifacts = self.ppt_artifacts if source_type == 'ppt' else self.word_artifacts
        for pattern in artifacts:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)
        
        # Remove header/footer patterns
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines (will be normalized later)
            if not line:
                cleaned_lines.append('')
                continue
            
            # Check if line matches header/footer pattern
            is_artifact = False
            for pattern in self.header_footer_patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    is_artifact = True
                    break
            
            if not is_artifact:
                cleaned_lines.append(line)
        
        # Join lines and normalize whitespace
        text = '\n'.join(cleaned_lines)
        
        # Remove excessive blank lines (more than 2 consecutive)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        # Fix common OCR/extraction errors
        text = self._fix_common_errors(text)
        
        return text
    
    def _fix_common_errors(self, text: str) -> str:
        """
        Fix common OCR and extraction errors.
        
        Args:
            text: Text to fix
            
        Returns:
            Fixed text
        """
        # Fix broken words (e.g., "hel lo" -> "hello")
        # Be conservative to avoid breaking intentional spacing
        text = re.sub(r'(\w)\s+(\w)(?=\s|$)', r'\1\2', text)
        
        # Fix bullet points
        text = re.sub(r'[•●○◦▪▫■□]', '- ', text)
        text = re.sub(r'^\s*[►▸▹]', '  - ', text, flags=re.MULTILINE)
        
        # Fix smart quotes and dashes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        text = text.replace('—', '--').replace('–', '-')
        text = text.replace('…', '...')
        
        # Fix multiple spaces
        text = re.sub(r' {2,}', ' ', text)
        
        # Fix spacing around punctuation
        text = re.sub(r'\s+([.,;:!?])', r'\1', text)
        text = re.sub(r'([.,;:!?])(\w)', r'\1 \2', text)
        
        return text
    
    def _clean_table(self, table: List[List[str]]) -> List[List[str]]:
        """
        Clean table data.
        
        Args:
            table: Table as list of rows (each row is list of cells)
            
        Returns:
            Cleaned table
        """
        cleaned_table = []
        
        for row in table:
            cleaned_row = []
            for cell in row:
                if cell is None:
                    cleaned_row.append('')
                else:
                    # Clean cell content
                    cleaned_cell = str(cell).strip()
                    cleaned_cell = re.sub(r'\s+', ' ', cleaned_cell)
                    cleaned_row.append(cleaned_cell)
            
            # Only include non-empty rows
            if any(cell for cell in cleaned_row):
                cleaned_table.append(cleaned_row)
        
        return cleaned_table
    
    def remove_duplicate_content(self, text: str) -> str:
        """
        Remove duplicate consecutive lines or paragraphs.
        
        Args:
            text: Text to deduplicate
            
        Returns:
            Deduplicated text
        """
        lines = text.split('\n')
        deduplicated = []
        prev_line = None
        
        for line in lines:
            # Keep line if it's different from previous or if it's empty
            if line != prev_line or not line.strip():
                deduplicated.append(line)
            prev_line = line
        
        return '\n'.join(deduplicated)
    
    def normalize_spacing(self, text: str) -> str:
        """
        Normalize spacing in text.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
        """
        # Ensure single space after sentence-ending punctuation
        text = re.sub(r'([.!?])\s+', r'\1 ', text)
        
        # Ensure blank line between paragraphs
        paragraphs = re.split(r'\n\s*\n', text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        return '\n\n'.join(paragraphs)

# Made with Bob
