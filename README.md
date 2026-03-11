# DevReport

**Professional project status reports from your codebase.**

DevReport scans your project directory and generates comprehensive, beautifully formatted reports — perfect for client updates, sprint reviews, or project audits.

## Features

- **Language Detection** — Recognizes 50+ languages, counts lines of code, comments, and blanks
- **Project Health Score** — Grades your project A+ to F based on README, tests, CI, docs, and more
- **Git History Analysis** — Commits, contributors, activity trends, recent changes
- **Dependency Scanning** — Detects npm, pip, Cargo, Go modules, Composer, and more
- **TODO/FIXME Extraction** — Finds all action items and tech debt markers in your code
- **Multiple Output Formats** — HTML (print-ready), Markdown, JSON, or terminal summary
- **Client Branding** — Add client name and custom title for professional deliverables
- **Zero Dependencies** — Pure Python 3, no packages to install

## Quick Start

```bash
# Terminal summary
python3 devreport.py /path/to/project

# Beautiful HTML report
python3 devreport.py /path/to/project -o report.html

# Markdown for docs/PRs
python3 devreport.py /path/to/project -o report.md

# Client-branded report
python3 devreport.py /path/to/project -o report.html --client "Acme Corp" --title "Sprint 3 Report"

# Raw data for automation
python3 devreport.py /path/to/project --json > data.json
```

## Output Formats

### Terminal Summary
Quick overview with health score, language breakdown, and action items.

### HTML Report
Professional, print-ready report with:
- Executive summary with key metrics
- Visual health score with grade (A+ to F)
- Language distribution with bar charts
- Git history with contributor breakdown
- Dependency analysis
- TODO/FIXME listing
- Project structure tree

### Markdown Report
Same content as HTML, formatted for GitHub, GitLab, or any documentation system.

### JSON Output
Raw scan data for piping into other tools or dashboards.

## Health Score

DevReport grades your project on a 100-point scale:

| Category | Points | What It Checks |
|----------|--------|---------------|
| README | 15 | Has a README file |
| License | 10 | Has a LICENSE file |
| .gitignore | 5 | Has a .gitignore |
| Tests | 20 | Has test files/directories |
| CI/CD | 10 | GitHub Actions, GitLab CI, etc. |
| Comments | 10 | Code comment ratio ≥ 10% |
| Tech Debt | 10 | Low FIXME/HACK/XXX count |
| Git History | 10 | Active commit history |
| Docker | 5 | Has Dockerfile |
| Dependencies | 5 | Uses a package manager |

## Use Cases

- **Freelancers**: Generate client-ready sprint reports in seconds
- **Team Leads**: Quick project health checks across repositories
- **Code Reviews**: Attach a project overview to PR descriptions
- **Audits**: Assess unfamiliar codebases at a glance
- **Onboarding**: Help new team members understand project structure

## Supported Languages

Python, JavaScript, TypeScript, Java, Go, Rust, Ruby, PHP, C/C++, C#, Swift, Kotlin, Dart, Scala, Elixir, Haskell, Lua, Vue, Svelte, Shell, SQL, HTML, CSS, SCSS, and 30+ more.

## Supported Package Managers

npm, pip, Cargo, Go modules, Composer, Bundler, CocoaPods, Gradle, Maven, Mix, pub, and more.

## License

MIT

---

Made by [Orange Digital](https://genesis-ai-admin.github.io/orange-digital/)
