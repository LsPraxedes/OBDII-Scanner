#!/usr/bin/env python3
"""
Rotina de formatacao e quebra de linhas para arquivos LaTeX (.tex).

Objetivo:
    Reduzir a quantidade de texto por linha (limite padrao de 88 caracteres)
    para facilitar a leitura, revisao e edicao manual no VS Code, mantendo
    100% de compatibilidade sintatica e tipografica com o compilador LaTeX
    (pdflatex / latexmk / abnTeX2).

Uso:
    python docs/latex/format_latex.py [caminho_do_arquivo.tex ...]
    (Se nenhum arquivo for informado, formata docs/latex/TCC_II/main.tex e siglas.tex)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

MAX_LINE_LENGTH = 88


def _protect_tokens(line: str) -> list[str]:
    """
    Divide uma linha em tokens atomicos que nao devem ser quebrados ao meio
    (ex: matematicas inline $...$, comandos curtos com chaves, etc.),
    separados por espacos.
    """
    tokens: list[str] = []
    current: list[str] = []
    in_math = False
    brace_depth = 0
    i = 0
    n = len(line)

    while i < n:
        ch = line[i]

        # Caractere escapado (ex: \$, \{, \}, \&, \%)
        if ch == "\\" and i + 1 < n:
            current.append(ch)
            current.append(line[i + 1])
            i += 2
            continue

        if ch == "$":
            in_math = not in_math
            current.append(ch)
            i += 1
            continue

        if not in_math:
            if ch == "{":
                brace_depth += 1
                current.append(ch)
                i += 1
                continue
            elif ch == "}":
                brace_depth = max(0, brace_depth - 1)
                current.append(ch)
                i += 1
                continue

        # Quebra em espaco apenas se nao estivermos dentro de $...$
        # e se o bloco entre chaves nao for um comando curto (ex: \cite{...}, \text{ s})
        if ch in (" ", "\t") and not in_math and brace_depth == 0:
            if current:
                tokens.append("".join(current))
                current = []
            # Avanca espacos multiplos
            while i < n and line[i] in (" ", "\t"):
                i += 1
            continue

        current.append(ch)
        i += 1

    if current:
        tokens.append("".join(current))

    return tokens


def _wrap_plain_segment(
    text: str,
    first_indent: str,
    cont_indent: str,
    max_len: int = MAX_LINE_LENGTH,
) -> list[str]:
    """
    Quebra um segmento de texto LaTeX respeitando o limite de caracteres.
    Caso um token possua chaves longas (ex: \textbf{...}, \footnote{...}, \caption{...}),
    permite quebrar nos espacos internos.
    """
    stripped = text.strip()
    if not stripped:
        return [first_indent.rstrip()]

    if len(first_indent) + len(stripped) <= max_len:
        return [f"{first_indent}{stripped}"]

    # Primeiro tentamos com tokens protegidos ($...$ e {...} fechados)
    tokens = _protect_tokens(stripped)

    # Se algum token individual for muito grande (ex: \textbf{texto longo...}),
    # subdividimos esse token pelos espacos fora de $...$
    expanded_tokens: list[str] = []
    for tok in tokens:
        if len(tok) > max_len - len(cont_indent) - 10:
            # Subdivide preservando apenas $...$ e \text{...} curtos
            sub_tokens = _split_keeping_math(tok)
            expanded_tokens.extend(sub_tokens)
        else:
            expanded_tokens.append(tok)

    lines: list[str] = []
    current_indent = first_indent
    current_words: list[str] = []
    current_len = len(current_indent)

    for word in expanded_tokens:
        sep_len = 1 if current_words else 0
        if current_words and (current_len + sep_len + len(word) > max_len):
            lines.append(current_indent + " ".join(current_words))
            current_indent = cont_indent
            current_words = [word]
            current_len = len(current_indent) + len(word)
        else:
            current_words.append(word)
            current_len += sep_len + len(word)

    if current_words:
        lines.append(current_indent + " ".join(current_words))

    return lines


def _split_keeping_math(text: str) -> list[str]:
    """
    Divide um trecho por espacos, mantendo blocos matematicos $...$ unidos.
    """
    tokens: list[str] = []
    current: list[str] = []
    in_math = False
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            current.append(ch)
            current.append(text[i + 1])
            i += 2
            continue
        if ch == "$":
            in_math = not in_math
            current.append(ch)
            i += 1
            continue
        if ch in (" ", "\t") and not in_math:
            if current:
                tokens.append("".join(current))
                current = []
            while i < n and text[i] in (" ", "\t"):
                i += 1
            continue
        current.append(ch)
        i += 1

    if current:
        tokens.append("".join(current))
    return tokens


def _split_table_cells(line: str) -> list[str]:
    """
    Divide uma linha de tabela pelos separadores de coluna '&' nao escapados ('\\&').
    """
    cells: list[str] = []
    current: list[str] = []
    i = 0
    n = len(line)
    while i < n:
        if line[i] == "\\" and i + 1 < n:
            current.append(line[i])
            current.append(line[i + 1])
            i += 2
            continue
        if line[i] == "&":
            cells.append("".join(current).strip())
            current = []
            i += 1
            continue
        current.append(line[i])
        i += 1
    cells.append("".join(current).strip())
    return cells


def _wrap_table_row(
    line: str,
    base_indent: str,
    max_len: int = MAX_LINE_LENGTH,
) -> list[str]:
    """
    Formata e quebra uma linha de tabela (contendo '&') em linhas <= max_len.
    Prioriza quebras antes do separador '&' (como no exemplo da linha 588)
    e, se uma celula individual for longa (ex: Quadros descritivos), quebra
    o texto interno da celula em espacos.
    """
    stripped = line.strip()
    if len(base_indent) + len(stripped) <= max_len:
        return [f"{base_indent}{stripped}"]

    cells = _split_table_cells(stripped)
    if len(cells) <= 1:
        return _wrap_plain_segment(stripped, base_indent, base_indent + "    ", max_len)

    cont_indent = base_indent + "    "

    # Monta segmentos na forma:
    # cell[0], "& " + cell[1], "& " + cell[2], ...
    segments: list[str] = []
    for idx, cell in enumerate(cells):
        if idx == 0:
            segments.append(cell)
        else:
            segments.append(f"& {cell}" if cell else "&")

    out_lines: list[str] = []
    curr_line = ""
    curr_indent = base_indent

    for seg in segments:
        if not curr_line:
            candidate = f"{curr_indent}{seg}"
            if len(candidate) <= max_len:
                curr_line = candidate
            else:
                # A propria celula excede max_len -> quebra internamente por palavras
                wrapped_cell = _wrap_plain_segment(seg, curr_indent, cont_indent, max_len)
                out_lines.extend(wrapped_cell[:-1])
                curr_line = wrapped_cell[-1]
                curr_indent = cont_indent
        else:
            candidate = f"{curr_line} {seg}"
            if len(candidate) <= max_len:
                curr_line = candidate
            else:
                out_lines.append(curr_line)
                curr_indent = cont_indent
                candidate_new = f"{curr_indent}{seg}"
                if len(candidate_new) <= max_len:
                    curr_line = candidate_new
                else:
                    wrapped_cell = _wrap_plain_segment(
                        seg, curr_indent, cont_indent, max_len
                    )
                    out_lines.extend(wrapped_cell[:-1])
                    curr_line = wrapped_cell[-1]

    if curr_line:
        out_lines.append(curr_line)

    return out_lines


def _split_inline_comment(line: str) -> tuple[str, str]:
    """
    Separa a parte de codigo/texto de um comentario inline (%) nao escapado (\\%).
    """
    i = 0
    n = len(line)
    while i < n:
        if line[i] == "\\" and i + 1 < n:
            i += 2
            continue
        if line[i] == "%":
            return line[:i], line[i:]
        i += 1
    return line, ""


def format_latex_content(content: str, max_len: int = MAX_LINE_LENGTH) -> str:
    """
    Processa o conteudo completo de um arquivo .tex, quebrando linhas longas
    em no maximo `max_len` caracteres sem alterar a semantica do LaTeX.
    """
    raw_lines = content.splitlines()
    formatted_lines: list[str] = []
    in_tabular = False

    for raw_line in raw_lines:
        stripped = raw_line.strip()

        # Linha em branco
        if not stripped:
            formatted_lines.append("")
            continue

        # Detecta entrada/saida de ambientes tabular
        if re.search(r"\\begin\{(tabular|longtable|supertabular)\}", stripped):
            in_tabular = True
        if re.search(r"\\end\{(tabular|longtable|supertabular)\}", stripped):
            in_tabular = False

        # Captura a indentacao original
        indent_match = re.match(r"^(\s*)", raw_line)
        base_indent = indent_match.group(1) if indent_match else ""

        # Linha puramente de comentario (%)
        if stripped.startswith("%"):
            formatted_lines.append(raw_line.rstrip())
            continue

        # Se a linha ja cabe no limite, mantem intacta
        if len(raw_line.rstrip()) <= max_len:
            formatted_lines.append(raw_line.rstrip())
            continue

        # Separa eventual comentario no final da linha
        code_part, comment_part = _split_inline_comment(raw_line)

        # Caso 1: Linha de tabela (dentro de tabular ou contendo '&' nao escapado)
        if in_tabular and "&" in code_part:
            wrapped = _wrap_table_row(code_part, base_indent, max_len)
            if comment_part:
                if len(wrapped[-1]) + 1 + len(comment_part) <= max_len:
                    wrapped[-1] = f"{wrapped[-1]} {comment_part}"
                else:
                    wrapped.append(f"{base_indent}{comment_part}")
            formatted_lines.extend(wrapped)
            continue

        # Caso 2: Item de lista (\item ...) -> mantem indentacao nas linhas seguintes
        if stripped.startswith(r"\item"):
            cont_indent = base_indent + "    " if base_indent else "    "
            wrapped = _wrap_plain_segment(code_part, base_indent, cont_indent, max_len)
        else:
            wrapped = _wrap_plain_segment(code_part, base_indent, base_indent, max_len)

        if comment_part:
            if len(wrapped[-1]) + 1 + len(comment_part) <= max_len:
                wrapped[-1] = f"{wrapped[-1]} {comment_part}"
            else:
                wrapped.append(f"{base_indent}{comment_part}")

        formatted_lines.extend(wrapped)

    return "\n".join(formatted_lines) + "\n"


def format_file(path: Path, max_len: int = MAX_LINE_LENGTH) -> tuple[int, int]:
    """
    Formata um arquivo .tex in-place e retorna (num_linhas_antes, num_linhas_depois).
    """
    original = path.read_text(encoding="utf-8")
    before_count = len(original.splitlines())
    formatted = format_latex_content(original, max_len=max_len)
    after_count = len(formatted.splitlines())
    path.write_text(formatted, encoding="utf-8")
    return before_count, after_count


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    if len(sys.argv) > 1:
        targets = [Path(arg).resolve() for arg in sys.argv[1:]]
    else:
        targets = [
            repo_root / "docs" / "latex" / "TCC_II" / "main.tex",
            repo_root / "docs" / "latex" / "TCC_II" / "siglas.tex",
        ]

    for target in targets:
        if not target.exists():
            print(f"[ERRO] Arquivo nao encontrado: {target}", file=sys.stderr)
            return 1
        before, after = format_file(target, max_len=MAX_LINE_LENGTH)
        print(
            f"[OK] {target.name}: {before} linhas -> {after} linhas "
            f"(limite <= {MAX_LINE_LENGTH} caracteres/linha)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
