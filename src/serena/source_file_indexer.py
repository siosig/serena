from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from time import monotonic

from sensai.util import logging
from tqdm import tqdm

from serena.ls_manager import LanguageServerManager
from serena.project import Project
from solidlsp.ls import DocumentSymbols
from solidlsp.ls_config import LanguageServerIdLike

log = logging.getLogger(__name__)


@dataclass
class IndexingOutcome:
    """
    The result of indexing a collection of source files.
    """

    language_file_counts: dict[LanguageServerIdLike, int] = field(default_factory=dict)
    """the number of successfully indexed files per language server"""
    failures: list[tuple[str, Exception]] = field(default_factory=list)
    """the relative paths of the files that could not be indexed, each with the exception that occurred"""


class SourceFileIndexer:
    """
    Requests the document symbols of source files from the language servers of a manager,
    which fills the symbol caches of the language servers.
    The caches are saved periodically and once indexing is complete.
    """

    CACHE_SAVE_INTERVAL_SECONDS = 30

    def __init__(self, ls_manager: LanguageServerManager) -> None:
        self._ls_manager = ls_manager

    def index(
        self,
        files: Sequence[Project.ProjectFile],
        on_document_symbols: Callable[[str, DocumentSymbols], None] | None = None,
    ) -> IndexingOutcome:
        """
        :param files: the files to index
        :param on_document_symbols: a callback receiving the relative path and the document symbols of each file
            that was indexed successfully
        :return: the outcome, in which a file that failed to index is recorded while indexing continues
        """
        outcome = IndexingOutcome()

        # request the symbols of each file, saving the caches at regular intervals
        last_save_time = monotonic()
        for project_file in tqdm(files, desc="Indexing"):
            rel_path = project_file.rel_path
            try:
                ls = self._ls_manager.get_language_server(rel_path)
                document_symbols = ls.request_document_symbols(rel_path)
                outcome.language_file_counts[ls.ls_id] = outcome.language_file_counts.get(ls.ls_id, 0) + 1
                if on_document_symbols is not None:
                    on_document_symbols(rel_path, document_symbols)
            except Exception as e:
                log.error(f"Failed to index {rel_path}, continuing.")
                outcome.failures.append((rel_path, e))
            now = monotonic()
            if now - last_save_time >= self.CACHE_SAVE_INTERVAL_SECONDS:
                self._ls_manager.save_all_caches()
                last_save_time = now

        # persist the caches
        self._ls_manager.save_all_caches()
        return outcome
