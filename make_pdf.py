#!/usr/bin/env python3
"""Konwersja SPRAWOZDANIE.md -> HTML -> PDF (przez Chrome headless).

Nie wymaga zewnętrznych bibliotek Pythona ani dostępu do sieci.
"""
import html
import os
import re
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
MD_FILE = os.path.join(BASE, "SPRAWOZDANIE.md")
HTML_FILE = os.path.join(BASE, "SPRAWOZDANIE.html")
PDF_FILE = os.path.join(BASE, "SPRAWOZDANIE.pdf")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+?)`", r"<code>\1</code>", text)
    return text


def convert(md: str) -> str:
    lines = md.split("\n")
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        # fenced code block
        if line.strip().startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(html.escape(lines[i]))
                i += 1
            i += 1  # skip closing fence
            out.append("<pre><code>" + "\n".join(buf) + "</code></pre>")
            continue

        # horizontal rule
        if line.strip() == "---":
            out.append("<hr/>")
            i += 1
            continue

        # image
        m = re.match(r"!\[(.*?)\]\((.*?)\)", line.strip())
        if m:
            alt, src = m.group(1), m.group(2)
            out.append(
                f'<figure><img src="{html.escape(src)}" alt="{html.escape(alt)}"/>'
                f"<figcaption>{html.escape(alt)}</figcaption></figure>"
            )
            i += 1
            continue

        # table (block of lines starting with |)
        if line.strip().startswith("|"):
            tbl = []
            while i < n and lines[i].strip().startswith("|"):
                tbl.append(lines[i].strip())
                i += 1

            def cells(row):
                parts = row.strip().strip("|").split("|")
                return [p.strip() for p in parts]

            header = cells(tbl[0])
            body = tbl[2:] if len(tbl) > 1 else []
            html_tbl = ["<table>", "<thead><tr>"]
            for c in header:
                html_tbl.append(f"<th>{inline(c)}</th>")
            html_tbl.append("</tr></thead><tbody>")
            for row in body:
                html_tbl.append("<tr>")
                for c in cells(row):
                    html_tbl.append(f"<td>{inline(c)}</td>")
                html_tbl.append("</tr>")
            html_tbl.append("</tbody></table>")
            out.append("\n".join(html_tbl))
            continue

        # headings
        m = re.match(r"(#{1,6})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # bullet list
        if re.match(r"\s*-\s+", line):
            items = []
            while i < n and re.match(r"\s*-\s+", lines[i]):
                # join wrapped continuation lines
                content = re.sub(r"\s*-\s+", "", lines[i], count=1)
                i += 1
                while i < n and lines[i].strip() and not re.match(
                    r"\s*-\s+", lines[i]
                ) and not lines[i].strip().startswith(("|", "#", "```")):
                    content += " " + lines[i].strip()
                    i += 1
                items.append(f"<li>{inline(content)}</li>")
            out.append("<ul>" + "".join(items) + "</ul>")
            continue

        # numbered list
        if re.match(r"\s*\d+\.\s+", line):
            items = []
            while i < n and re.match(r"\s*\d+\.\s+", lines[i]):
                content = re.sub(r"\s*\d+\.\s+", "", lines[i], count=1)
                i += 1
                while i < n and lines[i].strip() and not re.match(
                    r"\s*\d+\.\s+", lines[i]
                ) and not lines[i].strip().startswith(("|", "#", "```", "-")):
                    content += " " + lines[i].strip()
                    i += 1
                items.append(f"<li>{inline(content)}</li>")
            out.append("<ol>" + "".join(items) + "</ol>")
            continue

        # blank line
        if line.strip() == "":
            i += 1
            continue

        # paragraph (join following non-empty, non-special lines)
        para = [line.strip()]
        i += 1
        while i < n and lines[i].strip() and not re.match(
            r"(#{1,6}\s|\s*-\s|\s*\d+\.\s)", lines[i]
        ) and not lines[i].strip().startswith(("|", "```", "---", "![")):
            para.append(lines[i].strip())
            i += 1
        out.append("<p>" + inline(" ".join(para)) + "</p>")

    return "\n".join(out)


CSS = """
@page { size: A4; margin: 18mm 16mm; }
* { box-sizing: border-box; }
body {
  font-family: 'Arial Unicode MS', 'Helvetica Neue', Arial, sans-serif;
  font-size: 11pt; line-height: 1.55; color: #1a1a1a; max-width: 100%;
}
h1 { font-size: 20pt; color: #0d3b66; border-bottom: 3px solid #0d3b66;
     padding-bottom: 6px; margin-top: 0; }
h2 { font-size: 15pt; color: #0d3b66; margin-top: 22px;
     border-bottom: 1px solid #cdd9e5; padding-bottom: 4px; }
h3 { font-size: 12.5pt; color: #1b4f72; margin-top: 16px; }
p { margin: 8px 0; text-align: justify; }
ul, ol { margin: 8px 0 8px 4px; padding-left: 22px; }
li { margin: 3px 0; }
strong { color: #0d3b66; }
code { font-family: 'SF Mono', Menlo, Consolas, monospace; font-size: 9.5pt;
       background: #eef2f7; padding: 1px 5px; border-radius: 4px; color: #b5179e; }
pre { background: #0f1c2e; color: #e6edf3; padding: 12px 14px; border-radius: 8px;
      overflow-x: auto; font-size: 9pt; line-height: 1.4; }
pre code { background: none; color: #e6edf3; padding: 0; font-size: 9pt; }
hr { border: none; border-top: 1px solid #dce3ea; margin: 18px 0; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 10pt; }
th { background: #0d3b66; color: #fff; text-align: left; padding: 8px 10px; }
td { border: 1px solid #cdd9e5; padding: 7px 10px; vertical-align: top; }
tbody tr:nth-child(even) { background: #f3f7fb; }
figure { margin: 14px 0; text-align: center; page-break-inside: avoid; }
figure img { max-width: 92%; border: 1px solid #cdd9e5; border-radius: 8px;
             box-shadow: 0 2px 8px rgba(0,0,0,0.12); }
figcaption { font-size: 9pt; color: #5b6b7b; margin-top: 6px; font-style: italic; }
h2 { page-break-after: avoid; }
"""


def main():
    with open(MD_FILE, encoding="utf-8") as f:
        md = f.read()
    body = convert(md)
    doc = (
        "<!DOCTYPE html><html lang='pl'><head><meta charset='utf-8'>"
        f"<style>{CSS}</style></head><body>{body}</body></html>"
    )
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(doc)
    print("HTML zapisany:", HTML_FILE)

    cmd = [
        CHROME,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={PDF_FILE}",
        "file://" + HTML_FILE,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(PDF_FILE):
        size = os.path.getsize(PDF_FILE) // 1024
        print(f"PDF zapisany: {PDF_FILE} ({size} KB)")
    else:
        print("BŁĄD generowania PDF")
        print(res.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
