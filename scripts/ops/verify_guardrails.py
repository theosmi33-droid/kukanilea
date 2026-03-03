#!/usr/bin/env python3
import os
import sys
import re

# Guardrail 1: No external CDN URLs in app/templates and app/static/sim
def check_cdn_urls():
    patterns = [
        r'(https?://|//)cdn',
        r'(https?://|//)unpkg',
        r'(https?://|//)cdnjs',
        r'(https?://|//)jsdelivr'
    ]
    regex = re.compile('|'.join(patterns))
    paths = ['app/templates', 'app/static/sim']
    errors = []
    for path in paths:
        if not os.path.exists(path):
            continue
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith(('.html', '.js', '.css')):
                    full_path = os.path.join(root, file)
                    with open(full_path, 'r', encoding='utf-8') as f:
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                # Exclude common namespaces or specific strings if necessary
                                if 'xmlns="http://www.w3.org/2000/svg"' in line:
                                    continue
                                errors.append(f"CDN URL found in {full_path}:{line_num}: {line.strip()}")
    return errors

# Guardrail 2: hx-post/hx-put/hx-patch/hx-delete require confirm gate in templates
def check_htmx_confirm():
    # Matches tags with hx-post|put|patch|delete but missing hx-confirm
    hx_methods = ['hx-post', 'hx-put', 'hx-patch', 'hx-delete']
    errors = []
    path = 'app/templates'
    if not os.path.exists(path):
        return errors
        
    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith('.html'):
                full_path = os.path.join(root, file)
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Find all tags
                    # A tag starts with < and ends with >. It can be multiline.
                    # This regex is simplified but good enough for HTML tags.
                    tags = re.finditer(r'(<[^>]+>)', content, re.DOTALL)
                    for match in tags:
                        tag = match.group(0)
                        has_method = any(f'{m}=' in tag for m in hx_methods)
                        has_confirm = 'hx-confirm=' in tag
                        if has_method and not has_confirm:
                            line_num = content.count('\n', 0, match.start()) + 1
                            tag_preview = tag.splitlines()[0] if '\n' in tag else tag
                            errors.append(f"HTMX method without hx-confirm in {full_path}:{line_num}: {tag_preview}")
    return errors

if __name__ == "__main__":
    print("[GUARDRAIL] Verifying CDN and HTMX confirm gates...")
    cdn_errors = check_cdn_urls()
    htmx_errors = check_htmx_confirm()
    
    all_errors = cdn_errors + htmx_errors
    if all_errors:
        for err in all_errors:
            print(f"FAILED: {err}")
        sys.exit(1)
    else:
        print("OK: All guardrail checks passed.")
        sys.exit(0)
