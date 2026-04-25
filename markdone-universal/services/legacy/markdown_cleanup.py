#!/usr/bin/env python3
"""
Markdown Cleanup Utility
Post-processes Markdown files to refine formatting and fix common issues.
"""

import re
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

import click
from loguru import logger
import yaml


class MarkdownCleanup:
    """Post-process and clean Markdown files."""
    
    def __init__(
        self,
        remove_duplicate_lines: bool = True,
        standardize_headings: bool = True,
        fix_lists: bool = True,
        normalize_spacing: bool = True,
        add_metadata: bool = False,
        verbose: bool = False
    ):
        """
        Initialize the cleanup utility.
        
        Args:
            remove_duplicate_lines: Remove duplicate consecutive lines
            standardize_headings: Standardize heading styles
            fix_lists: Fix list formatting
            normalize_spacing: Normalize blank lines and spacing
            add_metadata: Add or update YAML frontmatter
            verbose: Enable verbose logging
        """
        self.remove_duplicate_lines = remove_duplicate_lines
        self.standardize_headings = standardize_headings
        self.fix_lists = fix_lists
        self.normalize_spacing = normalize_spacing
        self.add_metadata = add_metadata
        
        # Configure logging
        if verbose:
            logger.remove()
            logger.add(sys.stderr, level="DEBUG")
        else:
            logger.remove()
            logger.add(sys.stderr, level="INFO")
    
    def cleanup_file(self, file_path: Path, output_path: Optional[Path] = None) -> bool:
        """
        Clean up a single Markdown file.
        
        Args:
            file_path: Path to Markdown file
            output_path: Output path (overwrites input if None)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Cleaning up {file_path}")
            
            # Read file
            content = file_path.read_text(encoding='utf-8')
            
            # Apply cleanup operations
            cleaned_content = self.cleanup_content(content)
            
            # Write output
            output_path = output_path or file_path
            output_path.write_text(cleaned_content, encoding='utf-8')
            
            logger.info(f"Successfully cleaned {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error cleaning {file_path}: {e}")
            return False
    
    def cleanup_content(self, content: str) -> str:
        """
        Apply all cleanup operations to content.
        
        Args:
            content: Markdown content
            
        Returns:
            Cleaned content
        """
        # Separate frontmatter from content
        frontmatter, body = self._extract_frontmatter(content)
        
        # Apply cleanup operations to body
        if self.remove_duplicate_lines:
            body = self._remove_duplicate_lines(body)
        
        if self.standardize_headings:
            body = self._standardize_headings(body)
        
        if self.fix_lists:
            body = self._fix_lists(body)
        
        if self.normalize_spacing:
            body = self._normalize_spacing(body)
        
        # Additional cleanup
        body = self._fix_common_issues(body)
        
        # Update frontmatter if requested
        if self.add_metadata and frontmatter:
            frontmatter = self._update_frontmatter(frontmatter)
        
        # Recombine
        if frontmatter:
            return f"---\n{frontmatter}\n---\n\n{body}"
        else:
            return body
    
    def _extract_frontmatter(self, content: str) -> tuple[str, str]:
        """
        Extract YAML frontmatter from content.
        
        Args:
            content: Full content
            
        Returns:
            Tuple of (frontmatter, body)
        """
        # Check for frontmatter
        if content.startswith('---\n'):
            parts = content.split('---\n', 2)
            if len(parts) >= 3:
                return parts[1].strip(), parts[2].strip()
        
        return "", content
    
    def _remove_duplicate_lines(self, content: str) -> str:
        """
        Remove duplicate consecutive lines.
        
        Args:
            content: Content to clean
            
        Returns:
            Cleaned content
        """
        logger.debug("Removing duplicate lines")
        
        lines = content.split('\n')
        cleaned_lines = []
        prev_line = None
        
        for line in lines:
            # Keep line if different from previous or if it's a blank line
            if line != prev_line or not line.strip():
                cleaned_lines.append(line)
            else:
                logger.debug(f"Removed duplicate: {line[:50]}")
            
            prev_line = line
        
        return '\n'.join(cleaned_lines)
    
    def _standardize_headings(self, content: str) -> str:
        """
        Standardize heading styles.
        
        Args:
            content: Content to clean
            
        Returns:
            Cleaned content
        """
        logger.debug("Standardizing headings")
        
        lines = content.split('\n')
        cleaned_lines = []
        
        for i, line in enumerate(lines):
            # Fix heading spacing (ensure space after #)
            if line.startswith('#'):
                # Count leading #
                level = len(line) - len(line.lstrip('#'))
                rest = line.lstrip('#').strip()
                
                if rest:
                    # Ensure single space after #
                    cleaned_lines.append(f"{'#' * level} {rest}")
                else:
                    cleaned_lines.append(line)
            
            # Convert underline-style headings to ATX style
            elif i > 0 and line.strip() and all(c in '=-' for c in line.strip()):
                prev_line = lines[i-1].strip()
                if prev_line:
                    # Remove previous line and replace with ATX heading
                    if cleaned_lines and cleaned_lines[-1].strip() == prev_line:
                        cleaned_lines.pop()
                    
                    level = 1 if '=' in line else 2
                    cleaned_lines.append(f"{'#' * level} {prev_line}")
                else:
                    cleaned_lines.append(line)
            else:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _fix_lists(self, content: str) -> str:
        """
        Fix list formatting.
        
        Args:
            content: Content to clean
            
        Returns:
            Cleaned content
        """
        logger.debug("Fixing list formatting")
        
        lines = content.split('\n')
        cleaned_lines = []
        in_list = False
        
        for line in lines:
            stripped = line.strip()
            
            # Detect list items
            is_list_item = (
                stripped.startswith('- ') or
                stripped.startswith('* ') or
                stripped.startswith('+ ') or
                re.match(r'^\d+\.\s', stripped)
            )
            
            if is_list_item:
                # Standardize bullet points to '-'
                if stripped.startswith('* ') or stripped.startswith('+ '):
                    indent = len(line) - len(line.lstrip())
                    cleaned_lines.append(' ' * indent + '- ' + stripped[2:])
                else:
                    cleaned_lines.append(line)
                
                in_list = True
            else:
                # Add blank line before list if needed
                if is_list_item and not in_list and cleaned_lines and cleaned_lines[-1].strip():
                    cleaned_lines.append('')
                
                cleaned_lines.append(line)
                
                # Reset list flag if blank line
                if not stripped:
                    in_list = False
        
        return '\n'.join(cleaned_lines)
    
    def _normalize_spacing(self, content: str) -> str:
        """
        Normalize spacing and blank lines.
        
        Args:
            content: Content to clean
            
        Returns:
            Cleaned content
        """
        logger.debug("Normalizing spacing")
        
        # Remove trailing whitespace from lines
        lines = [line.rstrip() for line in content.split('\n')]
        
        # Normalize blank lines (max 2 consecutive)
        cleaned_lines = []
        blank_count = 0
        
        for line in lines:
            if not line.strip():
                blank_count += 1
                if blank_count <= 2:
                    cleaned_lines.append('')
            else:
                blank_count = 0
                cleaned_lines.append(line)
        
        # Remove leading/trailing blank lines
        while cleaned_lines and not cleaned_lines[0].strip():
            cleaned_lines.pop(0)
        
        while cleaned_lines and not cleaned_lines[-1].strip():
            cleaned_lines.pop()
        
        return '\n'.join(cleaned_lines)
    
    def _fix_common_issues(self, content: str) -> str:
        """
        Fix common Markdown issues.
        
        Args:
            content: Content to clean
            
        Returns:
            Cleaned content
        """
        logger.debug("Fixing common issues")
        
        # Fix spacing around emphasis
        content = re.sub(r'\*\s+(\w)', r'*\1', content)
        content = re.sub(r'(\w)\s+\*', r'\1*', content)
        content = re.sub(r'_\s+(\w)', r'_\1', content)
        content = re.sub(r'(\w)\s+_', r'\1_', content)
        
        # Fix spacing around code
        content = re.sub(r'`\s+(\S)', r'`\1', content)
        content = re.sub(r'(\S)\s+`', r'\1`', content)
        
        # Fix link formatting
        content = re.sub(r'\[\s+', r'[', content)
        content = re.sub(r'\s+\]', r']', content)
        content = re.sub(r'\]\s+\(', r'](', content)
        
        # Ensure blank line before/after code blocks
        content = re.sub(r'([^\n])\n```', r'\1\n\n```', content)
        content = re.sub(r'```\n([^\n])', r'```\n\n\1', content)
        
        # Ensure blank line before/after blockquotes
        content = re.sub(r'([^\n])\n>', r'\1\n\n>', content)
        content = re.sub(r'>\s*\n([^\n>])', r'>\n\n\1', content)
        
        return content
    
    def _update_frontmatter(self, frontmatter: str) -> str:
        """
        Update YAML frontmatter with additional metadata.
        
        Args:
            frontmatter: Existing frontmatter
            
        Returns:
            Updated frontmatter
        """
        try:
            data = yaml.safe_load(frontmatter) or {}
        except yaml.YAMLError:
            logger.warning("Could not parse frontmatter")
            return frontmatter
        
        # Add last modified date
        data['last_modified'] = datetime.now().strftime("%Y-%m-%d")
        
        # Ensure tags is a list
        if 'tags' in data and isinstance(data['tags'], str):
            data['tags'] = [tag.strip() for tag in data['tags'].split(',')]
        
        # Add cleaned tag
        if 'tags' in data:
            if 'cleaned' not in data['tags']:
                data['tags'].append('cleaned')
        else:
            data['tags'] = ['cleaned']
        
        return yaml.dump(data, default_flow_style=False, sort_keys=False)


@click.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option(
    '--output', '-o',
    type=click.Path(),
    help='Output file or directory path'
)
@click.option(
    '--recursive', '-r',
    is_flag=True,
    help='Process subdirectories recursively'
)
@click.option(
    '--no-duplicates',
    is_flag=True,
    default=True,
    help='Remove duplicate consecutive lines'
)
@click.option(
    '--no-headings',
    is_flag=True,
    help='Do not standardize headings'
)
@click.option(
    '--no-lists',
    is_flag=True,
    help='Do not fix list formatting'
)
@click.option(
    '--no-spacing',
    is_flag=True,
    help='Do not normalize spacing'
)
@click.option(
    '--add-metadata',
    is_flag=True,
    help='Add or update YAML frontmatter metadata'
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='Enable verbose logging'
)
def main(
    input_path: str,
    output: Optional[str],
    recursive: bool,
    no_duplicates: bool,
    no_headings: bool,
    no_lists: bool,
    no_spacing: bool,
    add_metadata: bool,
    verbose: bool
):
    """
    Clean up and refine Markdown files.
    
    INPUT_PATH can be a single Markdown file or a directory.
    
    Examples:
    
        # Clean single file
        python markdown_cleanup.py document.md
        
        # Clean with output
        python markdown_cleanup.py document.md -o cleaned.md
        
        # Clean directory
        python markdown_cleanup.py ./markdown/ -r
        
        # Add metadata
        python markdown_cleanup.py document.md --add-metadata
    """
    input_path_obj = Path(input_path)
    output_path_obj = Path(output) if output else None
    
    # Initialize cleanup utility
    cleanup = MarkdownCleanup(
        remove_duplicate_lines=no_duplicates,
        standardize_headings=not no_headings,
        fix_lists=not no_lists,
        normalize_spacing=not no_spacing,
        add_metadata=add_metadata,
        verbose=verbose
    )
    
    # Process single file or directory
    if input_path_obj.is_file():
        success = cleanup.cleanup_file(input_path_obj, output_path_obj)
        if success:
            click.echo(click.style(f"✓ Cleaned {input_path_obj}", fg='green'))
        else:
            click.echo(click.style(f"✗ Failed to clean {input_path_obj}", fg='red'))
            sys.exit(1)
    else:
        # Process directory
        pattern = "**/*.md" if recursive else "*.md"
        md_files = list(input_path_obj.glob(pattern))
        
        if not md_files:
            logger.warning(f"No Markdown files found in {input_path_obj}")
            return
        
        logger.info(f"Found {len(md_files)} Markdown file(s)")
        
        success_count = 0
        failed_count = 0
        
        for md_file in md_files:
            if output_path_obj:
                # Maintain directory structure
                rel_path = md_file.relative_to(input_path_obj)
                out_file = output_path_obj / rel_path
                out_file.parent.mkdir(parents=True, exist_ok=True)
            else:
                out_file = None
            
            if cleanup.cleanup_file(md_file, out_file):
                success_count += 1
            else:
                failed_count += 1
        
        # Print summary
        click.echo(f"\n{'='*60}")
        click.echo(f"Cleanup Summary")
        click.echo(f"{'='*60}")
        click.echo(f"Total files: {len(md_files)}")
        click.echo(click.style(f"Successful: {success_count}", fg='green'))
        click.echo(click.style(f"Failed: {failed_count}", fg='red'))
        
        if failed_count > 0:
            sys.exit(1)


if __name__ == '__main__':
    main()

# Made with Bob
