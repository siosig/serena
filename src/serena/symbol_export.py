import json
import os
from dataclasses import asdict, dataclass

from serena.symbol import LanguageServerSymbol
from solidlsp.ls import DocumentSymbols
from solidlsp.ls_types import SymbolKind


@dataclass(frozen=True, kw_only=True)
class ExportedSymbol:
    """
    A symbol in the form in which it is exported for consumption by other tools.
    """

    name: str
    """the name path of the symbol, e.g. `Class/method`"""
    kind: str
    """the name of the symbol's kind (a `SymbolKind` member name), e.g. `Method`"""
    path: str
    """the path of the file containing the symbol, relative to the project root and using forward slashes"""
    start_line: int
    """the 1-based first line of the symbol's body"""
    end_line: int
    """the 1-based last line of the symbol's body"""


class SymbolExport:
    """
    Collects the symbols of source files and renders them as a JSON document.
    Only symbols that are useful as navigation targets are exported: the data-like symbols
    (variables, constants, fields, ...) as well as file and package symbols are left out.
    """

    SCHEMA_VERSION = 1
    _EXCLUDED_KINDS = frozenset({SymbolKind.File, SymbolKind.Package})

    def __init__(self) -> None:
        self._symbols: list[ExportedSymbol] = []

    def add_file(self, relative_path: str, document_symbols: DocumentSymbols) -> None:
        """
        :param relative_path: the path of the file, relative to the project root
        :param document_symbols: the symbols of the file
        """
        path = relative_path.replace(os.sep, "/")
        for symbol_info in document_symbols.iter_symbols():
            symbol = LanguageServerSymbol(symbol_info)

            # leave out symbols that are not useful as navigation targets
            if symbol.is_low_level() or symbol.symbol_kind in self._EXCLUDED_KINDS:
                continue
            start_line, end_line = symbol.get_body_line_numbers()
            if start_line is None or end_line is None or not symbol.name:
                continue

            # convert the 0-based lines of the language server to 1-based lines
            self._symbols.append(
                ExportedSymbol(
                    name=symbol.get_name_path(),
                    kind=symbol.symbol_kind_name,
                    path=path,
                    start_line=start_line + 1,
                    end_line=end_line + 1,
                )
            )

    def to_json(self) -> str:
        return json.dumps(
            {"schema_version": self.SCHEMA_VERSION, "symbols": [asdict(s) for s in self._symbols]},
            ensure_ascii=False,
        )
