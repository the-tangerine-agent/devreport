#!/usr/bin/env python3
"""
DevReport — Professional Project Status Reports from Your Codebase

Scans a project directory and generates a comprehensive, professional report
including: file structure, lines of code by language, dependency analysis,
TODO/FIXME extraction, git history summary, and project health score.

Usage:
    python3 devreport.py /path/to/project
    python3 devreport.py /path/to/project --format html --output report.html
    python3 devreport.py /path/to/project --format md --output report.md
    python3 devreport.py /path/to/project --client "Acme Corp" --title "Sprint 3 Report"
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

__version__ = "1.0.0"

# Language detection by extension
LANG_MAP = {
    '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript', '.tsx': 'TypeScript (JSX)',
    '.jsx': 'JavaScript (JSX)', '.html': 'HTML', '.css': 'CSS', '.scss': 'SCSS',
    '.sass': 'Sass', '.less': 'Less', '.java': 'Java', '.kt': 'Kotlin',
    '.swift': 'Swift', '.go': 'Go', '.rs': 'Rust', '.rb': 'Ruby',
    '.php': 'PHP', '.c': 'C', '.cpp': 'C++', '.h': 'C/C++ Header',
    '.cs': 'C#', '.r': 'R', '.m': 'Objective-C', '.scala': 'Scala',
    '.sh': 'Shell', '.bash': 'Bash', '.zsh': 'Zsh', '.fish': 'Fish',
    '.sql': 'SQL', '.graphql': 'GraphQL', '.proto': 'Protocol Buffers',
    '.yaml': 'YAML', '.yml': 'YAML', '.toml': 'TOML', '.ini': 'INI',
    '.json': 'JSON', '.xml': 'XML', '.md': 'Markdown', '.rst': 'reStructuredText',
    '.txt': 'Text', '.vue': 'Vue', '.svelte': 'Svelte', '.dart': 'Dart',
    '.lua': 'Lua', '.ex': 'Elixir', '.exs': 'Elixir', '.erl': 'Erlang',
    '.hs': 'Haskell', '.ml': 'OCaml', '.clj': 'Clojure', '.elm': 'Elm',
    '.tf': 'Terraform', '.dockerfile': 'Dockerfile',
}

# Directories to skip
SKIP_DIRS = {
    'node_modules', '.git', '__pycache__', '.venv', 'venv', 'env',
    '.tox', '.mypy_cache', '.pytest_cache', 'dist', 'build', '.next',
    '.nuxt', 'target', 'bin', 'obj', '.idea', '.vscode', '.DS_Store',
    'vendor', 'bower_components', '.cache', 'coverage', '.nyc_output',
}

# Dependency file patterns
DEP_FILES = {
    'package.json': 'Node.js (npm)',
    'package-lock.json': 'Node.js (npm lock)',
    'yarn.lock': 'Node.js (Yarn)',
    'pnpm-lock.yaml': 'Node.js (pnpm)',
    'requirements.txt': 'Python (pip)',
    'Pipfile': 'Python (Pipenv)',
    'Pipfile.lock': 'Python (Pipenv lock)',
    'pyproject.toml': 'Python (pyproject)',
    'setup.py': 'Python (setuptools)',
    'Gemfile': 'Ruby (Bundler)',
    'Gemfile.lock': 'Ruby (Bundler lock)',
    'go.mod': 'Go (modules)',
    'go.sum': 'Go (modules checksum)',
    'Cargo.toml': 'Rust (Cargo)',
    'Cargo.lock': 'Rust (Cargo lock)',
    'composer.json': 'PHP (Composer)',
    'pom.xml': 'Java (Maven)',
    'build.gradle': 'Java/Kotlin (Gradle)',
    'build.gradle.kts': 'Kotlin (Gradle KTS)',
    'Podfile': 'iOS (CocoaPods)',
    'pubspec.yaml': 'Dart/Flutter (pub)',
    'mix.exs': 'Elixir (Mix)',
}

# CI/CD patterns
CI_FILES = {
    '.github/workflows': 'GitHub Actions',
    '.gitlab-ci.yml': 'GitLab CI',
    'Jenkinsfile': 'Jenkins',
    '.travis.yml': 'Travis CI',
    '.circleci': 'CircleCI',
    'bitbucket-pipelines.yml': 'Bitbucket Pipelines',
    'azure-pipelines.yml': 'Azure DevOps',
    '.drone.yml': 'Drone CI',
}


def scan_project(project_path):
    """Scan a project directory and collect all metrics."""
    project = Path(project_path).resolve()
    if not project.is_dir():
        print(f"Error: '{project_path}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    data = {
        'project_name': project.name,
        'project_path': str(project),
        'scan_time': datetime.now().isoformat(),
        'files': [],
        'languages': Counter(),
        'loc_by_lang': Counter(),
        'total_files': 0,
        'total_loc': 0,
        'total_blank': 0,
        'total_comment': 0,
        'todos': [],
        'fixmes': [],
        'dependencies': {},
        'dep_managers': [],
        'ci_systems': [],
        'has_readme': False,
        'has_license': False,
        'has_tests': False,
        'has_docker': False,
        'has_ci': False,
        'has_gitignore': False,
        'file_tree': [],
        'largest_files': [],
        'git_info': None,
    }

    all_files = []

    for root, dirs, files in os.walk(project):
        # Skip ignored directories
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel_root = os.path.relpath(root, project)

        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, project)

            # Check special files
            lower = fname.lower()
            if lower.startswith('readme'):
                data['has_readme'] = True
            if lower in ('license', 'license.md', 'license.txt', 'licence'):
                data['has_license'] = True
            if lower == '.gitignore':
                data['has_gitignore'] = True
            if lower in ('dockerfile', 'docker-compose.yml', 'docker-compose.yaml'):
                data['has_docker'] = True

            # Check for tests
            if 'test' in rel_path.lower() or 'spec' in rel_path.lower():
                data['has_tests'] = True

            # Check CI
            for ci_pattern, ci_name in CI_FILES.items():
                if ci_pattern in rel_path:
                    if ci_name not in data['ci_systems']:
                        data['ci_systems'].append(ci_name)
                    data['has_ci'] = True

            # Check dependency files
            if fname in DEP_FILES:
                data['dep_managers'].append(DEP_FILES[fname])
                _parse_deps(fpath, fname, data)

            # Get file extension
            ext = os.path.splitext(fname)[1].lower()
            lang = LANG_MAP.get(ext)

            # Special cases
            if fname == 'Dockerfile':
                lang = 'Dockerfile'
            if fname == 'Makefile':
                lang = 'Makefile'

            try:
                size = os.path.getsize(fpath)
            except OSError:
                continue

            file_info = {
                'path': rel_path,
                'size': size,
                'language': lang,
            }

            if lang and size < 2_000_000:  # Skip binary/huge files
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()

                    loc = 0
                    blank = 0
                    comments = 0
                    for i, line in enumerate(lines, 1):
                        stripped = line.strip()
                        if not stripped:
                            blank += 1
                        elif _is_comment(stripped, lang):
                            comments += 1
                        else:
                            loc += 1

                        # Extract TODOs and FIXMEs
                        upper = stripped.upper()
                        if 'TODO' in upper:
                            data['todos'].append({
                                'file': rel_path,
                                'line': i,
                                'text': stripped[:200],
                            })
                        if 'FIXME' in upper or 'HACK' in upper or 'XXX' in upper:
                            data['fixmes'].append({
                                'file': rel_path,
                                'line': i,
                                'text': stripped[:200],
                            })

                    file_info['loc'] = loc
                    file_info['blank'] = blank
                    file_info['comments'] = comments
                    data['languages'][lang] += 1
                    data['loc_by_lang'][lang] += loc
                    data['total_loc'] += loc
                    data['total_blank'] += blank
                    data['total_comment'] += comments

                except Exception:
                    pass

            all_files.append(file_info)
            data['total_files'] += 1

    data['files'] = all_files
    data['largest_files'] = sorted(all_files, key=lambda f: f.get('loc', 0), reverse=True)[:10]
    data['file_tree'] = _build_tree(project, max_depth=3)

    # Git analysis
    data['git_info'] = _analyze_git(project)

    # Calculate health score
    data['health_score'] = _calculate_health(data)

    return data


def _is_comment(line, lang):
    """Check if a line is a comment based on language."""
    if lang in ('Python', 'Ruby', 'Shell', 'Bash', 'Zsh', 'Fish', 'R', 'Elixir', 'YAML', 'TOML', 'INI'):
        return line.startswith('#')
    if lang in ('JavaScript', 'TypeScript', 'Java', 'C', 'C++', 'C#', 'Go', 'Rust',
                'Kotlin', 'Swift', 'Scala', 'Dart', 'PHP', 'JavaScript (JSX)', 'TypeScript (JSX)'):
        return line.startswith('//') or line.startswith('/*') or line.startswith('*')
    if lang == 'HTML':
        return line.startswith('<!--')
    if lang == 'CSS' or lang == 'SCSS' or lang == 'Less':
        return line.startswith('/*') or line.startswith('*') or line.startswith('//')
    if lang in ('Haskell', 'Elm'):
        return line.startswith('--')
    if lang == 'Lua':
        return line.startswith('--')
    if lang in ('Clojure', 'Lisp'):
        return line.startswith(';')
    if lang == 'SQL':
        return line.startswith('--')
    return False


def _parse_deps(fpath, fname, data):
    """Parse dependency files to extract dependency lists."""
    try:
        if fname == 'package.json':
            with open(fpath, 'r') as f:
                pkg = json.load(f)
            deps = list(pkg.get('dependencies', {}).keys())
            dev_deps = list(pkg.get('devDependencies', {}).keys())
            data['dependencies']['npm'] = {
                'production': deps,
                'development': dev_deps,
                'total': len(deps) + len(dev_deps),
            }
        elif fname == 'requirements.txt':
            with open(fpath, 'r') as f:
                lines = [l.strip().split('==')[0].split('>=')[0].split('<=')[0].split('~=')[0]
                         for l in f if l.strip() and not l.startswith('#') and not l.startswith('-')]
            data['dependencies']['pip'] = {
                'packages': lines,
                'total': len(lines),
            }
        elif fname == 'pyproject.toml':
            with open(fpath, 'r') as f:
                content = f.read()
            # Simple TOML parsing for dependencies
            deps = re.findall(r'"([^"]+)"', content)
            # This is rough — just count unique package-like strings
            data['dependencies']['pyproject'] = {'note': 'pyproject.toml detected'}
        elif fname == 'go.mod':
            with open(fpath, 'r') as f:
                lines = [l.strip().split()[0] for l in f
                         if l.strip() and not l.startswith('module')
                         and not l.startswith('go ') and not l.startswith(')') and not l.startswith('(')
                         and not l.startswith('//') and not l.startswith('require')]
            data['dependencies']['go'] = {
                'modules': [l for l in lines if '/' in l],
                'total': len([l for l in lines if '/' in l]),
            }
        elif fname == 'Cargo.toml':
            with open(fpath, 'r') as f:
                content = f.read()
            in_deps = False
            crates = []
            for line in content.split('\n'):
                if '[dependencies]' in line:
                    in_deps = True
                    continue
                if in_deps and line.startswith('['):
                    break
                if in_deps and '=' in line and line.strip():
                    crates.append(line.split('=')[0].strip())
            data['dependencies']['cargo'] = {
                'crates': crates,
                'total': len(crates),
            }
    except Exception:
        pass


def _build_tree(project, max_depth=3):
    """Build a simplified file tree representation."""
    tree = []
    project = Path(project)

    def walk(path, prefix="", depth=0):
        if depth > max_depth:
            return
        entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        dirs = [e for e in entries if e.is_dir() and e.name not in SKIP_DIRS]
        files = [e for e in entries if e.is_file()]

        # Show first 15 files at each level
        for f in files[:15]:
            tree.append(f"{prefix}{f.name}")
        if len(files) > 15:
            tree.append(f"{prefix}... and {len(files) - 15} more files")

        for d in dirs:
            tree.append(f"{prefix}{d.name}/")
            walk(d, prefix + "  ", depth + 1)

    walk(project)
    return tree


def _analyze_git(project):
    """Analyze git history if available."""
    git_dir = Path(project) / '.git'
    if not git_dir.exists():
        return None

    info = {}
    try:
        # Total commits
        result = subprocess.run(
            ['git', 'log', '--oneline', '--all'],
            capture_output=True, text=True, cwd=project, timeout=10
        )
        commits = result.stdout.strip().split('\n') if result.stdout.strip() else []
        info['total_commits'] = len(commits)

        # Recent commits (last 10)
        result = subprocess.run(
            ['git', 'log', '--pretty=format:%h|%an|%ar|%s', '-10'],
            capture_output=True, text=True, cwd=project, timeout=10
        )
        recent = []
        for line in result.stdout.strip().split('\n'):
            if '|' in line:
                parts = line.split('|', 3)
                if len(parts) == 4:
                    recent.append({
                        'hash': parts[0],
                        'author': parts[1],
                        'date': parts[2],
                        'message': parts[3],
                    })
        info['recent_commits'] = recent

        # Contributors
        result = subprocess.run(
            ['git', 'shortlog', '-sn', '--all'],
            capture_output=True, text=True, cwd=project, timeout=10
        )
        contributors = []
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if line:
                match = re.match(r'(\d+)\s+(.+)', line)
                if match:
                    contributors.append({
                        'name': match.group(2),
                        'commits': int(match.group(1)),
                    })
        info['contributors'] = contributors

        # Branch info
        result = subprocess.run(
            ['git', 'branch', '-a'],
            capture_output=True, text=True, cwd=project, timeout=10
        )
        branches = [b.strip().lstrip('* ') for b in result.stdout.strip().split('\n') if b.strip()]
        info['branches'] = branches
        info['branch_count'] = len(branches)

        # Current branch
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True, text=True, cwd=project, timeout=10
        )
        info['current_branch'] = result.stdout.strip()

        # Commits in last 30 days
        result = subprocess.run(
            ['git', 'log', '--oneline', '--since=30 days ago'],
            capture_output=True, text=True, cwd=project, timeout=10
        )
        recent_lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
        info['commits_last_30d'] = len(recent_lines)

        # Commits in last 7 days
        result = subprocess.run(
            ['git', 'log', '--oneline', '--since=7 days ago'],
            capture_output=True, text=True, cwd=project, timeout=10
        )
        recent_lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
        info['commits_last_7d'] = len(recent_lines)

    except Exception:
        pass

    return info


def _calculate_health(data):
    """Calculate a project health score (0-100)."""
    score = 0
    details = []

    # README (15 points)
    if data['has_readme']:
        score += 15
        details.append(('README', 15, 'Present'))
    else:
        details.append(('README', 0, 'Missing'))

    # License (10 points)
    if data['has_license']:
        score += 10
        details.append(('License', 10, 'Present'))
    else:
        details.append(('License', 0, 'Missing'))

    # .gitignore (5 points)
    if data['has_gitignore']:
        score += 5
        details.append(('.gitignore', 5, 'Present'))
    else:
        details.append(('.gitignore', 0, 'Missing'))

    # Tests (20 points)
    if data['has_tests']:
        score += 20
        details.append(('Tests', 20, 'Found'))
    else:
        details.append(('Tests', 0, 'Not found'))

    # CI/CD (10 points)
    if data['has_ci']:
        score += 10
        details.append(('CI/CD', 10, ', '.join(data['ci_systems'])))
    else:
        details.append(('CI/CD', 0, 'Not configured'))

    # Code comments ratio (10 points)
    total_code = data['total_loc'] + data['total_comment']
    if total_code > 0:
        comment_ratio = data['total_comment'] / total_code
        if comment_ratio >= 0.1:
            score += 10
            details.append(('Comments', 10, f'{comment_ratio:.0%} ratio'))
        elif comment_ratio >= 0.05:
            score += 5
            details.append(('Comments', 5, f'{comment_ratio:.0%} ratio (could be better)'))
        else:
            details.append(('Comments', 0, f'{comment_ratio:.0%} ratio (too low)'))

    # Low TODO/FIXME count (10 points)
    fixme_count = len(data['fixmes'])
    if fixme_count == 0:
        score += 10
        details.append(('Tech debt markers', 10, 'None found'))
    elif fixme_count <= 5:
        score += 5
        details.append(('Tech debt markers', 5, f'{fixme_count} found'))
    else:
        details.append(('Tech debt markers', 0, f'{fixme_count} found'))

    # Git history (10 points)
    if data['git_info']:
        if data['git_info'].get('total_commits', 0) > 10:
            score += 10
            details.append(('Git history', 10, f"{data['git_info']['total_commits']} commits"))
        elif data['git_info'].get('total_commits', 0) > 0:
            score += 5
            details.append(('Git history', 5, f"{data['git_info']['total_commits']} commits"))
    else:
        details.append(('Git history', 0, 'No git repo'))

    # Docker support (5 points)
    if data['has_docker']:
        score += 5
        details.append(('Docker', 5, 'Present'))
    else:
        details.append(('Docker', 0, 'Not found'))

    # Dependency management (5 points)
    if data['dep_managers']:
        score += 5
        details.append(('Dependencies', 5, ', '.join(set(data['dep_managers']))))
    else:
        details.append(('Dependencies', 0, 'No dependency files'))

    return {'score': score, 'max': 100, 'details': details}


# ─── Report Generators ─────────────────────────────────────────────────────────

def generate_markdown(data, client=None, title=None):
    """Generate a Markdown report."""
    now = datetime.now().strftime('%B %d, %Y')
    project = data['project_name']
    report_title = title or f"{project} — Project Report"

    lines = []
    lines.append(f"# {report_title}")
    lines.append("")
    if client:
        lines.append(f"**Prepared for:** {client}")
    lines.append(f"**Generated:** {now}")
    lines.append(f"**Tool:** DevReport v{__version__}")
    lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")
    health = data['health_score']
    lines.append(f"- **Project Health Score:** {health['score']}/{health['max']}")
    lines.append(f"- **Total Files:** {data['total_files']:,}")
    lines.append(f"- **Lines of Code:** {data['total_loc']:,}")
    lines.append(f"- **Languages:** {len(data['languages'])}")
    if data['git_info']:
        lines.append(f"- **Total Commits:** {data['git_info'].get('total_commits', 'N/A')}")
        lines.append(f"- **Contributors:** {len(data['git_info'].get('contributors', []))}")
        lines.append(f"- **Activity (last 30 days):** {data['git_info'].get('commits_last_30d', 0)} commits")
    lines.append("")

    # Health Score Breakdown
    lines.append("## Project Health")
    lines.append("")
    grade = _score_to_grade(health['score'])
    lines.append(f"**Overall Grade: {grade}** ({health['score']}/100)")
    lines.append("")
    lines.append("| Category | Score | Status |")
    lines.append("|----------|-------|--------|")
    for category, points, status in health['details']:
        icon = "✅" if points > 0 else "❌"
        lines.append(f"| {category} | {points} | {icon} {status} |")
    lines.append("")

    # Languages
    lines.append("## Languages & Code")
    lines.append("")
    lines.append("| Language | Files | Lines of Code | % of Total |")
    lines.append("|----------|-------|---------------|------------|")
    for lang, loc in data['loc_by_lang'].most_common(15):
        pct = (loc / data['total_loc'] * 100) if data['total_loc'] > 0 else 0
        files = data['languages'][lang]
        lines.append(f"| {lang} | {files} | {loc:,} | {pct:.1f}% |")
    lines.append("")
    lines.append(f"**Total:** {data['total_loc']:,} lines of code, {data['total_blank']:,} blank lines, {data['total_comment']:,} comment lines")
    lines.append("")

    # Largest Files
    lines.append("## Largest Files (by LOC)")
    lines.append("")
    lines.append("| File | Language | Lines |")
    lines.append("|------|----------|-------|")
    for f in data['largest_files'][:10]:
        if f.get('loc', 0) > 0:
            lines.append(f"| `{f['path']}` | {f.get('language', '—')} | {f['loc']:,} |")
    lines.append("")

    # Dependencies
    if data['dependencies']:
        lines.append("## Dependencies")
        lines.append("")
        for manager, deps in data['dependencies'].items():
            if isinstance(deps, dict):
                if 'production' in deps:
                    lines.append(f"### {manager}")
                    lines.append(f"- **Production:** {len(deps['production'])} packages")
                    lines.append(f"- **Development:** {len(deps.get('development', []))} packages")
                    if deps['production']:
                        lines.append(f"- Key: `{'`, `'.join(deps['production'][:10])}`")
                elif 'packages' in deps:
                    lines.append(f"### {manager}")
                    lines.append(f"- **Packages:** {len(deps['packages'])}")
                    if deps['packages']:
                        lines.append(f"- Key: `{'`, `'.join(deps['packages'][:10])}`")
                elif 'modules' in deps:
                    lines.append(f"### {manager}")
                    lines.append(f"- **Modules:** {len(deps['modules'])}")
                elif 'crates' in deps:
                    lines.append(f"### {manager}")
                    lines.append(f"- **Crates:** {len(deps['crates'])}")
        lines.append("")

    # Git History
    if data['git_info']:
        lines.append("## Git History")
        lines.append("")
        gi = data['git_info']
        lines.append(f"- **Current branch:** `{gi.get('current_branch', '—')}`")
        lines.append(f"- **Total branches:** {gi.get('branch_count', 0)}")
        lines.append(f"- **Total commits:** {gi.get('total_commits', 0)}")
        lines.append(f"- **Last 7 days:** {gi.get('commits_last_7d', 0)} commits")
        lines.append(f"- **Last 30 days:** {gi.get('commits_last_30d', 0)} commits")
        lines.append("")

        if gi.get('contributors'):
            lines.append("### Contributors")
            lines.append("")
            lines.append("| Name | Commits |")
            lines.append("|------|---------|")
            for c in gi['contributors'][:10]:
                lines.append(f"| {c['name']} | {c['commits']} |")
            lines.append("")

        if gi.get('recent_commits'):
            lines.append("### Recent Commits")
            lines.append("")
            for c in gi['recent_commits']:
                lines.append(f"- `{c['hash']}` {c['message']} — *{c['author']}*, {c['date']}")
            lines.append("")

    # TODOs and FIXMEs
    if data['todos'] or data['fixmes']:
        lines.append("## Action Items")
        lines.append("")
        if data['todos']:
            lines.append(f"### TODOs ({len(data['todos'])})")
            lines.append("")
            for t in data['todos'][:20]:
                lines.append(f"- `{t['file']}:{t['line']}` — {t['text']}")
            if len(data['todos']) > 20:
                lines.append(f"- *...and {len(data['todos']) - 20} more*")
            lines.append("")

        if data['fixmes']:
            lines.append(f"### FIXMEs / Tech Debt ({len(data['fixmes'])})")
            lines.append("")
            for t in data['fixmes'][:20]:
                lines.append(f"- `{t['file']}:{t['line']}` — {t['text']}")
            if len(data['fixmes']) > 20:
                lines.append(f"- *...and {len(data['fixmes']) - 20} more*")
            lines.append("")

    # File Structure
    lines.append("## Project Structure")
    lines.append("")
    lines.append("```")
    for entry in data['file_tree'][:50]:
        lines.append(entry)
    if len(data['file_tree']) > 50:
        lines.append(f"... ({len(data['file_tree']) - 50} more entries)")
    lines.append("```")
    lines.append("")

    # Footer
    lines.append("---")
    lines.append(f"*Generated by [DevReport](https://github.com/genesis-ai-admin/devreport) v{__version__}*")

    return "\n".join(lines)


def generate_html(data, client=None, title=None):
    """Generate an HTML report with professional styling."""
    now = datetime.now().strftime('%B %d, %Y')
    project = data['project_name']
    report_title = title or f"{project} — Project Report"
    health = data['health_score']
    grade = _score_to_grade(health['score'])
    score = health['score']

    # Color based on score
    if score >= 80:
        score_color = '#22c55e'
        grade_bg = '#dcfce7'
    elif score >= 60:
        score_color = '#f59e0b'
        grade_bg = '#fef3c7'
    elif score >= 40:
        score_color = '#f97316'
        grade_bg = '#ffedd5'
    else:
        score_color = '#ef4444'
        grade_bg = '#fee2e2'

    # Build language chart data
    lang_rows = ""
    max_loc = max(data['loc_by_lang'].values()) if data['loc_by_lang'] else 1
    colors = ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#818cf8',
              '#60a5fa', '#38bdf8', '#22d3ee', '#2dd4bf', '#34d399',
              '#4ade80', '#a3e635', '#facc15', '#fb923c', '#f87171']
    for i, (lang, loc) in enumerate(data['loc_by_lang'].most_common(10)):
        pct = (loc / data['total_loc'] * 100) if data['total_loc'] > 0 else 0
        bar_width = (loc / max_loc * 100)
        color = colors[i % len(colors)]
        lang_rows += f"""
        <tr>
            <td style="font-weight:500">{lang}</td>
            <td style="text-align:right">{data['languages'][lang]}</td>
            <td style="text-align:right">{loc:,}</td>
            <td style="width:40%">
                <div style="background:{color}20;border-radius:4px;overflow:hidden">
                    <div style="width:{bar_width}%;background:{color};height:20px;border-radius:4px;min-width:2px"></div>
                </div>
            </td>
            <td style="text-align:right;color:#64748b">{pct:.1f}%</td>
        </tr>"""

    # Health details
    health_rows = ""
    for category, points, status in health['details']:
        icon = "✓" if points > 0 else "✗"
        icon_color = "#22c55e" if points > 0 else "#ef4444"
        health_rows += f"""
        <tr>
            <td><span style="color:{icon_color};font-weight:bold">{icon}</span> {category}</td>
            <td style="text-align:center">{points}</td>
            <td style="color:#64748b">{status}</td>
        </tr>"""

    # Largest files
    largest_rows = ""
    for f in data['largest_files'][:10]:
        if f.get('loc', 0) > 0:
            largest_rows += f"""
            <tr>
                <td><code>{f['path']}</code></td>
                <td>{f.get('language', '—')}</td>
                <td style="text-align:right">{f['loc']:,}</td>
            </tr>"""

    # Git section
    git_html = ""
    if data['git_info']:
        gi = data['git_info']
        commits_html = ""
        for c in gi.get('recent_commits', []):
            commits_html += f"""
            <div style="display:flex;gap:12px;padding:8px 0;border-bottom:1px solid #f1f5f9">
                <code style="color:#6366f1;flex-shrink:0">{c['hash']}</code>
                <span style="flex:1">{c['message']}</span>
                <span style="color:#94a3b8;flex-shrink:0;font-size:0.85em">{c['author']}, {c['date']}</span>
            </div>"""

        contributors_html = ""
        for c in gi.get('contributors', [])[:8]:
            contributors_html += f"""
            <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f1f5f9">
                <span>{c['name']}</span>
                <span style="color:#64748b">{c['commits']} commits</span>
            </div>"""

        git_html = f"""
        <section>
            <h2>Git History</h2>
            <div class="grid-2">
                <div class="card">
                    <h3>Activity</h3>
                    <div class="stat-row"><span>Current branch</span><code>{gi.get('current_branch', '—')}</code></div>
                    <div class="stat-row"><span>Total commits</span><strong>{gi.get('total_commits', 0)}</strong></div>
                    <div class="stat-row"><span>Last 7 days</span><strong>{gi.get('commits_last_7d', 0)}</strong></div>
                    <div class="stat-row"><span>Last 30 days</span><strong>{gi.get('commits_last_30d', 0)}</strong></div>
                    <div class="stat-row"><span>Branches</span><strong>{gi.get('branch_count', 0)}</strong></div>
                </div>
                <div class="card">
                    <h3>Contributors</h3>
                    {contributors_html or '<p style="color:#94a3b8">No contributors found</p>'}
                </div>
            </div>
            <div class="card" style="margin-top:16px">
                <h3>Recent Commits</h3>
                {commits_html or '<p style="color:#94a3b8">No commits found</p>'}
            </div>
        </section>"""

    # TODOs section
    todos_html = ""
    if data['todos'] or data['fixmes']:
        todo_items = ""
        for t in data['todos'][:15]:
            todo_items += f'<div class="todo-item"><code>{t["file"]}:{t["line"]}</code><span>{t["text"][:120]}</span></div>'
        fixme_items = ""
        for t in data['fixmes'][:15]:
            fixme_items += f'<div class="todo-item fixme"><code>{t["file"]}:{t["line"]}</code><span>{t["text"][:120]}</span></div>'

        todos_html = f"""
        <section>
            <h2>Action Items</h2>
            <div class="grid-2">
                <div class="card">
                    <h3>TODOs <span class="badge">{len(data['todos'])}</span></h3>
                    {todo_items or '<p style="color:#94a3b8">None found</p>'}
                    {'<p style="color:#94a3b8;font-size:0.85em">...and ' + str(len(data["todos"]) - 15) + ' more</p>' if len(data['todos']) > 15 else ''}
                </div>
                <div class="card">
                    <h3>FIXMEs / Tech Debt <span class="badge warn">{len(data['fixmes'])}</span></h3>
                    {fixme_items or '<p style="color:#94a3b8">None found</p>'}
                    {'<p style="color:#94a3b8;font-size:0.85em">...and ' + str(len(data["fixmes"]) - 15) + ' more</p>' if len(data['fixmes']) > 15 else ''}
                </div>
            </div>
        </section>"""

    # Dependencies section
    deps_html = ""
    if data['dependencies']:
        dep_cards = ""
        for manager, deps in data['dependencies'].items():
            if isinstance(deps, dict):
                if 'production' in deps:
                    dep_cards += f"""
                    <div class="card">
                        <h3>{manager}</h3>
                        <div class="stat-row"><span>Production</span><strong>{len(deps['production'])}</strong></div>
                        <div class="stat-row"><span>Development</span><strong>{len(deps.get('development', []))}</strong></div>
                        <p style="color:#64748b;font-size:0.85em;margin-top:8px">{'`, `'.join(deps['production'][:8])}</p>
                    </div>"""
                elif 'packages' in deps:
                    dep_cards += f"""
                    <div class="card">
                        <h3>{manager}</h3>
                        <div class="stat-row"><span>Packages</span><strong>{deps['total']}</strong></div>
                        <p style="color:#64748b;font-size:0.85em;margin-top:8px">{'`, `'.join(deps['packages'][:8])}</p>
                    </div>"""
        if dep_cards:
            deps_html = f"""
            <section>
                <h2>Dependencies</h2>
                <div class="grid-2">{dep_cards}</div>
            </section>"""

    # File tree
    tree_text = "\n".join(data['file_tree'][:40])
    if len(data['file_tree']) > 40:
        tree_text += f"\n... ({len(data['file_tree']) - 40} more entries)"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report_title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f8fafc;
            color: #1e293b;
            line-height: 1.6;
        }}
        .container {{ max-width: 1000px; margin: 0 auto; padding: 40px 24px; }}
        header {{
            background: linear-gradient(135deg, #1e1b4b, #312e81);
            color: white;
            padding: 48px 40px;
            border-radius: 16px;
            margin-bottom: 32px;
        }}
        header h1 {{ font-size: 2em; margin-bottom: 8px; }}
        header .meta {{ opacity: 0.8; font-size: 0.95em; }}
        header .meta span {{ margin-right: 24px; }}
        section {{ margin-bottom: 32px; }}
        h2 {{
            font-size: 1.4em;
            color: #1e293b;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 2px solid #e2e8f0;
        }}
        h3 {{ font-size: 1.1em; color: #475569; margin-bottom: 12px; }}
        .card {{
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            border: 1px solid #e2e8f0;
        }}
        .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
        .grid-4 {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }}
        .stat-card {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            border: 1px solid #e2e8f0;
        }}
        .stat-card .number {{ font-size: 2em; font-weight: 700; color: #6366f1; }}
        .stat-card .label {{ color: #64748b; font-size: 0.85em; margin-top: 4px; }}
        .stat-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #f1f5f9;
        }}
        .score-card {{
            background: {grade_bg};
            border-radius: 16px;
            padding: 32px;
            text-align: center;
            margin-bottom: 16px;
        }}
        .score-card .grade {{ font-size: 3em; font-weight: 800; color: {score_color}; }}
        .score-card .score-num {{ font-size: 1.2em; color: #64748b; margin-top: 4px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #f1f5f9; }}
        th {{ font-weight: 600; color: #64748b; font-size: 0.85em; text-transform: uppercase; letter-spacing: 0.5px; }}
        code {{
            background: #f1f5f9;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.85em;
            color: #6366f1;
        }}
        pre {{
            background: #1e293b;
            color: #e2e8f0;
            padding: 20px;
            border-radius: 8px;
            overflow-x: auto;
            font-size: 0.85em;
            line-height: 1.5;
        }}
        .badge {{
            background: #6366f1;
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.8em;
            font-weight: 600;
        }}
        .badge.warn {{ background: #f59e0b; }}
        .todo-item {{
            padding: 8px 0;
            border-bottom: 1px solid #f1f5f9;
            font-size: 0.9em;
        }}
        .todo-item code {{ margin-right: 8px; }}
        .todo-item.fixme code {{ color: #f59e0b; }}
        footer {{
            text-align: center;
            color: #94a3b8;
            font-size: 0.85em;
            margin-top: 48px;
            padding-top: 24px;
            border-top: 1px solid #e2e8f0;
        }}
        @media (max-width: 768px) {{
            .grid-2 {{ grid-template-columns: 1fr; }}
            .grid-4 {{ grid-template-columns: repeat(2, 1fr); }}
            header {{ padding: 32px 24px; }}
        }}
        @media print {{
            body {{ background: white; }}
            .card {{ box-shadow: none; border: 1px solid #e2e8f0; }}
            header {{ background: #1e1b4b !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{report_title}</h1>
            <div class="meta">
                {f'<span>Prepared for: <strong>{client}</strong></span>' if client else ''}
                <span>Generated: {now}</span>
                <span>DevReport v{__version__}</span>
            </div>
        </header>

        <section>
            <div class="grid-4">
                <div class="stat-card">
                    <div class="number">{data['total_files']:,}</div>
                    <div class="label">Total Files</div>
                </div>
                <div class="stat-card">
                    <div class="number">{data['total_loc']:,}</div>
                    <div class="label">Lines of Code</div>
                </div>
                <div class="stat-card">
                    <div class="number">{len(data['languages'])}</div>
                    <div class="label">Languages</div>
                </div>
                <div class="stat-card">
                    <div class="number">{data['git_info'].get('total_commits', 0) if data['git_info'] else 0}</div>
                    <div class="label">Commits</div>
                </div>
            </div>
        </section>

        <section>
            <h2>Project Health</h2>
            <div class="grid-2">
                <div class="score-card">
                    <div class="grade">{grade}</div>
                    <div class="score-num">{score}/100</div>
                </div>
                <div class="card">
                    <table>
                        <thead><tr><th>Category</th><th>Score</th><th>Status</th></tr></thead>
                        <tbody>{health_rows}</tbody>
                    </table>
                </div>
            </div>
        </section>

        <section>
            <h2>Languages & Code</h2>
            <div class="card">
                <table>
                    <thead><tr><th>Language</th><th>Files</th><th>LOC</th><th>Distribution</th><th>%</th></tr></thead>
                    <tbody>{lang_rows}</tbody>
                </table>
            </div>
        </section>

        <section>
            <h2>Largest Files</h2>
            <div class="card">
                <table>
                    <thead><tr><th>File</th><th>Language</th><th>Lines</th></tr></thead>
                    <tbody>{largest_rows}</tbody>
                </table>
            </div>
        </section>

        {deps_html}
        {git_html}
        {todos_html}

        <section>
            <h2>Project Structure</h2>
            <pre>{tree_text}</pre>
        </section>

        <footer>
            Generated by <strong>DevReport</strong> v{__version__} &mdash; Professional Project Reports for Developers
        </footer>
    </div>
</body>
</html>"""
    return html


def _score_to_grade(score):
    if score >= 90: return 'A+'
    if score >= 80: return 'A'
    if score >= 70: return 'B'
    if score >= 60: return 'C'
    if score >= 50: return 'D'
    return 'F'


# ─── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog='devreport',
        description='Generate professional project status reports from your codebase.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  devreport .                                    Scan current directory, print to stdout
  devreport /path/to/project -o report.html      Generate HTML report
  devreport . --format md -o report.md           Generate Markdown report
  devreport . --client "Acme Corp" --title "Sprint 3"  Add client branding
  devreport . --json                             Output raw JSON data
        """
    )
    parser.add_argument('path', help='Project directory to scan')
    parser.add_argument('-o', '--output', help='Output file path (default: stdout)')
    parser.add_argument('-f', '--format', choices=['html', 'md', 'json', 'summary'],
                        default=None, help='Output format (auto-detected from -o extension)')
    parser.add_argument('--client', help='Client name for branded reports')
    parser.add_argument('--title', help='Custom report title')
    parser.add_argument('--json', action='store_true', help='Output raw scan data as JSON')
    parser.add_argument('--version', action='version', version=f'DevReport v{__version__}')

    args = parser.parse_args()

    # Auto-detect format from output extension
    fmt = args.format
    if args.json:
        fmt = 'json'
    if not fmt and args.output:
        ext = os.path.splitext(args.output)[1].lower()
        fmt = {'html': 'html', '.htm': 'html', '.md': 'md', '.json': 'json',
               '.markdown': 'md'}.get(ext, 'html')
    if not fmt:
        fmt = 'summary'

    # Scan
    print(f"Scanning {os.path.abspath(args.path)}...", file=sys.stderr)
    data = scan_project(args.path)
    print(f"Found {data['total_files']:,} files, {data['total_loc']:,} lines of code", file=sys.stderr)

    # Generate output
    if fmt == 'json':
        # Convert Counters to dicts for JSON serialization
        data['languages'] = dict(data['languages'])
        data['loc_by_lang'] = dict(data['loc_by_lang'])
        del data['files']  # Too verbose for JSON output
        output = json.dumps(data, indent=2, default=str)
    elif fmt == 'html':
        output = generate_html(data, client=args.client, title=args.title)
    elif fmt == 'md':
        output = generate_markdown(data, client=args.client, title=args.title)
    elif fmt == 'summary':
        output = _print_summary(data)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Report saved to {args.output}", file=sys.stderr)
    else:
        print(output)


def _print_summary(data):
    """Print a quick terminal summary."""
    health = data['health_score']
    grade = _score_to_grade(health['score'])

    lines = []
    lines.append(f"╔══════════════════════════════════════════════╗")
    lines.append(f"║  DevReport — {data['project_name']:<32} ║")
    lines.append(f"╚══════════════════════════════════════════════╝")
    lines.append("")
    lines.append(f"  Health: {grade} ({health['score']}/100)")
    lines.append(f"  Files:  {data['total_files']:,}")
    lines.append(f"  LOC:    {data['total_loc']:,} ({data['total_comment']:,} comments, {data['total_blank']:,} blank)")
    lines.append(f"  Langs:  {len(data['languages'])}")
    lines.append("")

    # Top languages
    lines.append("  Top Languages:")
    for lang, loc in data['loc_by_lang'].most_common(5):
        pct = (loc / data['total_loc'] * 100) if data['total_loc'] > 0 else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        lines.append(f"    {lang:<20} {bar} {loc:>6,} ({pct:.0f}%)")
    lines.append("")

    # Health details
    lines.append("  Health Breakdown:")
    for cat, pts, status in health['details']:
        icon = "✓" if pts > 0 else "✗"
        lines.append(f"    {icon} {cat:<20} {pts:>2} pts  {status}")
    lines.append("")

    # Git
    if data['git_info']:
        gi = data['git_info']
        lines.append(f"  Git: {gi.get('total_commits', 0)} commits, {len(gi.get('contributors', []))} contributors")
        lines.append(f"       {gi.get('commits_last_30d', 0)} commits in last 30d, {gi.get('commits_last_7d', 0)} in last 7d")
        lines.append("")

    # Action items
    if data['todos'] or data['fixmes']:
        lines.append(f"  Action Items: {len(data['todos'])} TODOs, {len(data['fixmes'])} FIXMEs")
        lines.append("")

    lines.append(f"  Use --format html or --format md for full reports")

    return "\n".join(lines)


if __name__ == '__main__':
    main()
