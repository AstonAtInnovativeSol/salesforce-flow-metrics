#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Add Back Buttons to All HTML Reports
Automatically adds sleek back button navigation to all HTML dashboard/report files.
"""

import re
from pathlib import Path
from typing import List

# Back button CSS
BACK_BUTTON_CSS = """
        .back-btn {
            position: absolute;
            left: 24px;
            top: 50%;
            transform: translateY(-50%);
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 8px 16px;
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--ink);
            text-decoration: none;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.2s ease;
            z-index: 10;
        }
        
        .back-btn:hover {
            background: var(--brand);
            color: white;
            border-color: var(--brand);
            transform: translateY(-50%) translateX(-2px);
            box-shadow: 0 2px 8px rgba(75, 123, 236, 0.3);
        }
        
        .back-btn svg {
            width: 16px;
            height: 16px;
        }
"""

# Back button HTML
BACK_BUTTON_HTML = """        <a href="index.html" class="back-btn">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M19 12H5M12 19l-7-7 7-7"/>
            </svg>
            Back to Dashboard
        </a>
"""

def find_html_files(directory: Path) -> List[Path]:
    """Find all HTML files that need back buttons"""
    html_files = []
    
    # Find all HTML files except index.html
    for html_file in directory.glob("*.html"):
        if html_file.name != "index.html":
            html_files.append(html_file)
    
    return sorted(html_files)

def has_back_button(html_content: str) -> bool:
    """Check if HTML already has a back button"""
    return "back-btn" in html_content or "Back to Dashboard" in html_content

def ensure_header_relative(html_content: str) -> str:
    """Ensure header has position: relative for absolute positioning"""
    # Check if .hdr or header already has position: relative
    if re.search(r'\.hdr\s*\{[^}]*position:\s*relative', html_content, re.DOTALL):
        return html_content
    
    # Check if there's a .hdr style block
    hdr_pattern = r'(\.hdr\s*\{[^}]*?)(position:\s*[^;]+;)?([^}]*?\})'
    match = re.search(hdr_pattern, html_content, re.DOTALL)
    
    if match:
        # Add position: relative if not present
        if not match.group(2) or 'relative' not in match.group(2):
            # Insert position: relative after opening brace
            replacement = match.group(1) + 'position: relative;\n            ' + (match.group(3) or '')
            html_content = html_content[:match.start()] + replacement + html_content[match.end():]
    
    return html_content

def add_back_button_css(html_content: str) -> str:
    """Add back button CSS to style section"""
    if "back-btn" in html_content:
        return html_content  # CSS already exists
    
    # Find the closing </style> tag
    style_end = html_content.rfind("</style>")
    if style_end == -1:
        print("  ⚠ No </style> tag found, skipping CSS addition")
        return html_content
    
    # Insert CSS before </style>
    html_content = html_content[:style_end] + BACK_BUTTON_CSS + html_content[style_end:]
    return html_content

def add_back_button_html(html_content: str) -> str:
    """Add back button HTML to header"""
    if "Back to Dashboard" in html_content:
        return html_content  # HTML already exists
    
    # Find header opening tag - look for common patterns
    header_patterns = [
        r'(<div\s+class=["\']hdr["\'][^>]*>)',
        r'(<header[^>]*>)',
        r'(<div\s+class=["\']header["\'][^>]*>)',
    ]
    
    for pattern in header_patterns:
        match = re.search(pattern, html_content, re.IGNORECASE)
        if match:
            # Insert back button HTML right after header opening tag
            insert_pos = match.end()
            html_content = html_content[:insert_pos] + "\n" + BACK_BUTTON_HTML + html_content[insert_pos:]
            return html_content
    
    print("  ⚠ No header div found, trying alternative approach")
    # Alternative: look for body tag and add after it
    body_match = re.search(r'(<body[^>]*>)', html_content, re.IGNORECASE)
    if body_match:
        insert_pos = body_match.end()
        html_content = html_content[:insert_pos] + "\n" + BACK_BUTTON_HTML + html_content[insert_pos:]
        return html_content
    
    print("  ❌ Could not find header or body tag to insert back button")
    return html_content

def process_html_file(html_file: Path) -> bool:
    """Process a single HTML file to add back button"""
    print(f"\nProcessing: {html_file.name}")
    
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if already has back button
        if has_back_button(content):
            print(f"  ✓ Already has back button, skipping")
            return False
        
        # Ensure header has position: relative
        content = ensure_header_relative(content)
        
        # Add CSS
        content = add_back_button_css(content)
        
        # Add HTML
        content = add_back_button_html(content)
        
        # Write back
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"  ✓ Added back button successfully")
        return True
        
    except Exception as e:
        print(f"  ❌ Error processing {html_file.name}: {e}")
        return False

def main():
    """Main execution"""
    print("=" * 80)
    print("Add Back Buttons to All HTML Reports")
    print("=" * 80)
    
    # Get script directory
    script_dir = Path(__file__).parent
    
    # Find all HTML files
    html_files = find_html_files(script_dir)
    
    print(f"\nFound {len(html_files)} HTML files to process:")
    for f in html_files:
        print(f"  - {f.name}")
    
    # Process each file
    updated_count = 0
    for html_file in html_files:
        if process_html_file(html_file):
            updated_count += 1
    
    print(f"\n{'=' * 80}")
    print(f"✓ Complete! Updated {updated_count} out of {len(html_files)} files")
    
    if updated_count < len(html_files):
        print(f"  ({len(html_files) - updated_count} files already had back buttons or couldn't be updated)")

if __name__ == "__main__":
    main()

