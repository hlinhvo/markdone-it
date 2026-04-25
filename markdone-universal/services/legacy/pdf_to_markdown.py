#!/usr/bin/env python3
"""
PDF to Vault Markdown Converter
Converts PDF files (from PowerPoint or Word) to clean Markdown format.
"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging

import click
import fitz  # PyMuPDF
from tqdm import tqdm
from loguru import logger

from pdf_extractor import PDFExtractor
from markdown_formatter import MarkdownFormatter
from content_cleaner import ContentCleaner


class PDFToMarkdownConverter:
    """Main converter class for PDF to Markdown conversion."""
    
    def __init__(
        self,
        source_type: str = "auto",
        preserve_images: bool = True,
        add_frontmatter: bool = True,
        verbose: bool = False
    ):
        """
        Initialize the converter.
        
        Args:
            source_type: Type of PDF source ('ppt', 'word', or 'auto')
            preserve_images: Whether to extract and reference images
            add_frontmatter: Whether to add YAML frontmatter
            verbose: Enable verbose logging
        """
        self.source_type = source_type
        self.preserve_images = preserve_images
        self.add_frontmatter = add_frontmatter
        
        # Configure logging
        if verbose:
            logger.remove()
            logger.add(sys.stderr, level="DEBUG")
        else:
            logger.remove()
            logger.add(sys.stderr, level="INFO")
        
        self.extractor = PDFExtractor()
        self.formatter = MarkdownFormatter()
        self.cleaner = ContentCleaner()
    
    def detect_source_type(self, pdf_path: Path) -> str:
        """
        Detect whether PDF originated from PowerPoint or Word.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Detected source type ('ppt' or 'word')
        """
        logger.debug(f"Detecting source type for {pdf_path}")
        
        try:
            doc = fitz.open(pdf_path)
            # Sample first few pages
            sample_pages = min(3, len(doc))
            text_samples = []
            
            for i in range(sample_pages):
                page = doc.load_page(i)
                text = page.get_text("text") or ""
                text_samples.append(text)
            
            doc.close()
            combined_text = "\n".join(text_samples)
            
            # PowerPoint indicators
            ppt_indicators = [
                r"Slide \d+",
                r"Notes:",
                r"Speaker Notes",
                r"\d+/\d+",  # Slide numbers
            ]
            
            # Word indicators
            word_indicators = [
                r"Page \d+ of \d+",
                r"^Chapter \d+",
                r"^Section \d+",
            ]
            
            ppt_score = sum(1 for pattern in ppt_indicators
                           if re.search(pattern, combined_text, re.IGNORECASE))
            word_score = sum(1 for pattern in word_indicators
                            if re.search(pattern, combined_text, re.IGNORECASE))
            
            detected = "ppt" if ppt_score > word_score else "word"
            logger.info(f"Detected source type: {detected}")
            return detected
                
        except Exception as e:
            logger.warning(f"Could not detect source type: {e}. Defaulting to 'word'")
            return "word"
    
    def convert_file(
        self,
        input_path: Path,
        output_path: Optional[Path] = None
    ) -> Tuple[bool, str]:
        """
        Convert a single PDF file to Markdown.
        
        Args:
            input_path: Path to input PDF file
            output_path: Path to output Markdown file (optional)
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            logger.info(f"Converting {input_path}")
            
            # Validate input
            if not input_path.exists():
                return False, f"File not found: {input_path}"
            
            if not input_path.suffix.lower() == '.pdf':
                return False, f"Not a PDF file: {input_path}"
            
            # Determine output path
            if output_path is None:
                output_path = input_path.with_suffix('.md')
            
            # Detect source type if auto
            source_type = self.source_type
            if source_type == "auto":
                source_type = self.detect_source_type(input_path)
            
            # Extract content from PDF
            logger.debug("Extracting content from PDF")
            extracted_data = self.extractor.extract(input_path, source_type)
            
            if not extracted_data:
                return False, "Failed to extract content from PDF"
            
            # Clean the extracted content
            logger.debug("Cleaning extracted content")
            cleaned_data = self.cleaner.clean(extracted_data, source_type)
            
            # Format as Markdown
            logger.debug("Formatting as Markdown")
            markdown_content = self.formatter.format(
                cleaned_data,
                source_type=source_type,
                add_frontmatter=self.add_frontmatter,
                source_file=input_path.name
            )
            
            # Write output
            logger.debug(f"Writing output to {output_path}")
            output_path.write_text(markdown_content, encoding='utf-8')
            
            logger.info(f"Successfully converted to {output_path}")
            return True, f"Converted successfully: {output_path}"
            
        except Exception as e:
            error_msg = f"Error converting {input_path}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def convert_directory(
        self,
        input_dir: Path,
        output_dir: Optional[Path] = None,
        recursive: bool = False
    ) -> Dict[str, List[str]]:
        """
        Convert all PDF files in a directory.
        
        Args:
            input_dir: Input directory containing PDF files
            output_dir: Output directory for Markdown files
            recursive: Whether to process subdirectories
            
        Returns:
            Dictionary with 'success' and 'failed' lists of file paths
        """
        logger.info(f"Processing directory: {input_dir}")
        
        if not input_dir.exists() or not input_dir.is_dir():
            logger.error(f"Invalid directory: {input_dir}")
            return {"success": [], "failed": [str(input_dir)]}
        
        # Find all PDF files
        pattern = "**/*.pdf" if recursive else "*.pdf"
        pdf_files = list(input_dir.glob(pattern))
        
        if not pdf_files:
            logger.warning(f"No PDF files found in {input_dir}")
            return {"success": [], "failed": []}
        
        logger.info(f"Found {len(pdf_files)} PDF file(s)")
        
        # Prepare output directory
        if output_dir is None:
            output_dir = input_dir
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
        
        results = {"success": [], "failed": []}
        
        # Process each file with progress bar
        with tqdm(total=len(pdf_files), desc="Converting PDFs") as pbar:
            for pdf_file in pdf_files:
                # Maintain directory structure if recursive
                if recursive and output_dir != input_dir:
                    rel_path = pdf_file.relative_to(input_dir)
                    output_path = output_dir / rel_path.with_suffix('.md')
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                else:
                    output_path = output_dir / pdf_file.with_suffix('.md').name
                
                success, message = self.convert_file(pdf_file, output_path)
                
                if success:
                    results["success"].append(str(pdf_file))
                else:
                    results["failed"].append(str(pdf_file))
                    logger.error(message)
                
                pbar.update(1)
        
        return results


@click.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option(
    '--output', '-o',
    type=click.Path(),
    help='Output file or directory path'
)
@click.option(
    '--source-type', '-s',
    type=click.Choice(['auto', 'ppt', 'word'], case_sensitive=False),
    default='auto',
    help='Source type of PDF (auto-detect by default)'
)
@click.option(
    '--recursive', '-r',
    is_flag=True,
    help='Process subdirectories recursively'
)
@click.option(
    '--no-images',
    is_flag=True,
    help='Do not extract or reference images'
)
@click.option(
    '--no-frontmatter',
    is_flag=True,
    help='Do not add YAML frontmatter'
)
@click.option(
    '--dry-run',
    is_flag=True,
    help='Show what would be converted without actually converting'
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='Enable verbose logging'
)
def main(
    input_path: str,
    output: Optional[str],
    source_type: str,
    recursive: bool,
    no_images: bool,
    no_frontmatter: bool,
    dry_run: bool,
    verbose: bool
):
    """
    Convert PDF files to Vault-compatible Markdown format.
    
    INPUT_PATH can be a single PDF file or a directory containing PDF files.
    
    Examples:
    
        # Convert single file
        python pdf_to_markdown.py document.pdf
        
        # Convert with specific output
        python pdf_to_markdown.py document.pdf -o output.md
        
        # Convert directory
        python pdf_to_markdown.py ./pdfs/ -o ./markdown/
        
        # Convert directory recursively
        python pdf_to_markdown.py ./pdfs/ -r -o ./markdown/
        
        # Specify source type
        python pdf_to_markdown.py slides.pdf -s ppt
    """
    input_path_obj = Path(input_path)
    output_path_obj = Path(output) if output else None
    
    # Initialize converter
    converter = PDFToMarkdownConverter(
        source_type=source_type.lower(),
        preserve_images=not no_images,
        add_frontmatter=not no_frontmatter,
        verbose=verbose
    )
    
    # Dry run mode
    if dry_run:
        logger.info("DRY RUN MODE - No files will be converted")
        if input_path_obj.is_file():
            logger.info(f"Would convert: {input_path_obj}")
        else:
            pattern = "**/*.pdf" if recursive else "*.pdf"
            pdf_files = list(input_path_obj.glob(pattern))
            logger.info(f"Would convert {len(pdf_files)} file(s):")
            for pdf_file in pdf_files:
                logger.info(f"  - {pdf_file}")
        return
    
    # Process single file or directory
    if input_path_obj.is_file():
        success, message = converter.convert_file(input_path_obj, output_path_obj)
        if success:
            click.echo(click.style(f"✓ {message}", fg='green'))
        else:
            click.echo(click.style(f"✗ {message}", fg='red'))
            sys.exit(1)
    else:
        results = converter.convert_directory(
            input_path_obj,
            output_path_obj,
            recursive=recursive
        )
        
        # Print summary
        total = len(results['success']) + len(results['failed'])
        click.echo(f"\n{'='*60}")
        click.echo(f"Conversion Summary")
        click.echo(f"{'='*60}")
        click.echo(f"Total files: {total}")
        click.echo(click.style(f"Successful: {len(results['success'])}", fg='green'))
        click.echo(click.style(f"Failed: {len(results['failed'])}", fg='red'))
        
        if results['failed']:
            click.echo("\nFailed files:")
            for failed_file in results['failed']:
                click.echo(f"  - {failed_file}")
            sys.exit(1)


if __name__ == '__main__':
    main()

# Made with Bob
