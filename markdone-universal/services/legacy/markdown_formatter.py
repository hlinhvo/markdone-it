"""
Markdown Formatter
Converts cleaned PDF content to Vault-compatible Markdown format.
"""

import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from loguru import logger


class MarkdownFormatter:
    """Format cleaned content as Vault-compatible Markdown."""
    
    def __init__(self):
        """Initialize the Markdown formatter."""
        pass
    
    def format(
        self,
        data: Dict[str, Any],
        source_type: str,
        add_frontmatter: bool = True,
        source_file: str = ""
    ) -> str:
        """
        Format cleaned data as Markdown.
        
        Args:
            data: Cleaned content data
            source_type: Source type ('ppt' or 'word')
            add_frontmatter: Whether to add YAML frontmatter
            source_file: Original source filename
            
        Returns:
            Formatted Markdown string
        """
        if source_type == "ppt" or data.get('type') == 'powerpoint':
            return self._format_powerpoint(data, add_frontmatter, source_file)
        else:
            return self._format_word(data, add_frontmatter, source_file)
    
    def _format_powerpoint(
        self,
        data: Dict[str, Any],
        add_frontmatter: bool,
        source_file: str
    ) -> str:
        """
        Format PowerPoint content as Markdown.
        
        Args:
            data: PowerPoint data
            add_frontmatter: Whether to add frontmatter
            source_file: Source filename
            
        Returns:
            Formatted Markdown
        """
        logger.debug("Formatting PowerPoint content as Markdown")
        
        sections = []
        
        # Add frontmatter
        if add_frontmatter:
            sections.append(self._create_frontmatter(
                source_file=source_file,
                source_type="PowerPoint",
                total_slides=data.get('total_pages', 0),
                metadata=data.get('metadata', {})
            ))
        
        # Add title
        title = self._extract_title(data.get('metadata', {}), source_file)
        sections.append(f"# {title}\n")
        
        # Format each slide
        for slide in data.get('slides', []):
            slide_md = self._format_slide(slide)
            if slide_md:
                sections.append(slide_md)
        
        return '\n\n'.join(sections)
    
    def _format_word(
        self,
        data: Dict[str, Any],
        add_frontmatter: bool,
        source_file: str
    ) -> str:
        """
        Format Word document content as Markdown.
        
        Args:
            data: Word document data
            add_frontmatter: Whether to add frontmatter
            source_file: Source filename
            
        Returns:
            Formatted Markdown
        """
        logger.debug("Formatting Word document content as Markdown")
        
        sections = []
        
        # Add frontmatter
        if add_frontmatter:
            sections.append(self._create_frontmatter(
                source_file=source_file,
                source_type="Word",
                total_pages=data.get('total_pages', 0),
                metadata=data.get('metadata', {})
            ))
        
        # Add title
        title = self._extract_title(data.get('metadata', {}), source_file)
        sections.append(f"# {title}\n")
        
        # Combine all pages into continuous content
        full_content = []
        
        for page in data.get('pages', []):
            content = page.get('content', '').strip()
            if content:
                # Apply heading detection and formatting
                content = self._format_headings(content, data.get('structure', {}))
                full_content.append(content)
            
            # Add tables
            if page.get('tables'):
                for table in page['tables']:
                    table_md = self._format_table(table)
                    if table_md:
                        full_content.append(table_md)
            
            # Add image references
            if page.get('images'):
                for img in page['images']:
                    img_ref = self._format_image_reference(img, source_file)
                    full_content.append(img_ref)
        
        # Join content with proper spacing
        content_text = '\n\n'.join(full_content)
        sections.append(content_text)
        
        return '\n\n'.join(sections)
    
    def _format_slide(self, slide: Dict[str, Any]) -> str:
        """
        Format a single slide as Markdown.
        
        Args:
            slide: Slide data
            
        Returns:
            Formatted slide Markdown
        """
        parts = []
        
        # Slide heading
        slide_num = slide.get('number', 0)
        parts.append(f"## Slide {slide_num}")
        
        # Slide content
        content = slide.get('content', '').strip()
        if content:
            # Try to detect if first line is a title
            lines = content.split('\n')
            if lines and len(lines[0]) < 100 and not lines[0].endswith('.'):
                # First line might be slide title
                parts.append(f"### {lines[0]}")
                if len(lines) > 1:
                    parts.append('\n'.join(lines[1:]))
            else:
                parts.append(content)
        
        # Add tables
        if slide.get('tables'):
            for table in slide['tables']:
                table_md = self._format_table(table)
                if table_md:
                    parts.append(table_md)
        
        # Add image references
        if slide.get('images'):
            for img in slide['images']:
                img_ref = self._format_image_reference(img, f"slide_{slide_num}")
                parts.append(img_ref)
        
        # Speaker notes
        notes = slide.get('notes', '').strip()
        if notes:
            parts.append("#### Speaker Notes")
            parts.append(f"> {notes.replace(chr(10), chr(10) + '> ')}")
        
        return '\n\n'.join(parts)
    
    def _format_headings(self, text: str, structure: Dict[str, Any]) -> str:
        """
        Format text with proper Markdown headings.
        
        Args:
            text: Text content
            structure: Document structure information
            
        Returns:
            Text with formatted headings
        """
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                formatted_lines.append('')
                continue
            
            # Check if line matches heading patterns
            heading_level = self._detect_heading_level(line)
            
            if heading_level:
                # Format as Markdown heading
                formatted_lines.append(f"{'#' * heading_level} {line}")
            else:
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)
    
    def _detect_heading_level(self, line: str) -> Optional[int]:
        """
        Detect if a line is a heading and return its level.
        
        Args:
            line: Text line
            
        Returns:
            Heading level (2-6) or None
        """
        # Already a heading
        if line.startswith('#'):
            return None
        
        # Chapter/Section patterns
        if re.match(r'^(Chapter|Section|Part)\s+\d+', line, re.IGNORECASE):
            return 2
        
        # Numbered headings
        if re.match(r'^\d+\.\s+[A-Z]', line):
            return 2
        if re.match(r'^\d+\.\d+\.\s+[A-Z]', line):
            return 3
        if re.match(r'^\d+\.\d+\.\d+\.\s+[A-Z]', line):
            return 4
        
        # ALL CAPS (short lines only)
        if line.isupper() and len(line) < 60 and len(line.split()) <= 8:
            return 2
        
        # Title Case (short lines, no ending punctuation)
        if (len(line) < 60 and 
            not line.endswith(('.', '!', '?', ',', ';', ':')) and
            re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$', line)):
            return 3
        
        return None
    
    def _format_table(self, table: List[List[str]]) -> str:
        """
        Format table as Markdown table.
        
        Args:
            table: Table data (list of rows)
            
        Returns:
            Markdown table string
        """
        if not table or not table[0]:
            return ""
        
        # Determine column widths
        col_widths = [0] * len(table[0])
        for row in table:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))
        
        lines = []
        
        # Header row
        header = table[0]
        header_line = '| ' + ' | '.join(
            str(cell).ljust(col_widths[i]) for i, cell in enumerate(header)
        ) + ' |'
        lines.append(header_line)
        
        # Separator
        separator = '| ' + ' | '.join('-' * width for width in col_widths) + ' |'
        lines.append(separator)
        
        # Data rows
        for row in table[1:]:
            row_line = '| ' + ' | '.join(
                str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)
            ) + ' |'
            lines.append(row_line)
        
        return '\n'.join(lines)
    
    def _format_image_reference(self, img: Dict[str, Any], context: str) -> str:
        """
        Format image reference for Markdown.
        
        Args:
            img: Image data
            context: Context (slide number or page)
            
        Returns:
            Markdown image reference
        """
        img_index = img.get('index', 0)
        img_name = f"image_{context}_{img_index}"
        
        # Create placeholder reference
        return f"![{img_name}]({img_name}.png)"
    
    def _create_frontmatter(
        self,
        source_file: str,
        source_type: str,
        total_slides: int = 0,
        total_pages: int = 0,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Create YAML frontmatter for Vault.
        
        Args:
            source_file: Source filename
            source_type: Type of source document
            total_slides: Total number of slides (for PowerPoint)
            total_pages: Total number of pages (for Word)
            metadata: PDF metadata
            
        Returns:
            YAML frontmatter string
        """
        metadata = metadata or {}
        
        frontmatter_lines = ['---']
        
        # Basic metadata
        frontmatter_lines.append(f'title: "{self._extract_title(metadata, source_file)}"')
        frontmatter_lines.append(f'source: "{source_file}"')
        frontmatter_lines.append(f'source_type: {source_type}')
        frontmatter_lines.append(f'created: {datetime.now().strftime("%Y-%m-%d")}')
        
        # Add count based on source type
        if total_slides:
            frontmatter_lines.append(f'total_slides: {total_slides}')
        if total_pages:
            frontmatter_lines.append(f'total_pages: {total_pages}')
        
        # Add PDF metadata if available
        if metadata.get('Author'):
            frontmatter_lines.append(f'author: "{metadata["Author"]}"')
        
        if metadata.get('Subject'):
            frontmatter_lines.append(f'subject: "{metadata["Subject"]}"')
        
        if metadata.get('Keywords'):
            keywords = metadata['Keywords'].split(',')
            keywords_str = ', '.join(k.strip() for k in keywords)
            frontmatter_lines.append(f'keywords: [{keywords_str}]')
        
        # Tags
        frontmatter_lines.append('tags:')
        frontmatter_lines.append(f'  - {source_type.lower()}')
        frontmatter_lines.append('  - imported')
        
        frontmatter_lines.append('---')
        
        return '\n'.join(frontmatter_lines)
    
    def _extract_title(self, metadata: Dict[str, Any], source_file: str) -> str:
        """
        Extract or generate document title.
        
        Args:
            metadata: PDF metadata
            source_file: Source filename
            
        Returns:
            Document title
        """
        # Try to get title from metadata
        if metadata.get('Title'):
            return metadata['Title']
        
        # Use filename without extension
        from pathlib import Path
        return Path(source_file).stem.replace('_', ' ').replace('-', ' ').title()

# Made with Bob
