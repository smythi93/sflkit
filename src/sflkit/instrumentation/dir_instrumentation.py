import os
import queue
import re
import shutil
from pathlib import Path
from typing import List, Optional, Iterable, Tuple

from sflkit.instrumentation import Instrumentation
from sflkit.instrumentation.file_instrumentation import FileInstrumentation
from sflkit.language.visitor import ASTVisitor
from sflkit.logger import LOGGER


class DirInstrumentation(Instrumentation):
    def __init__(
        self,
        visitor: ASTVisitor,
        mapping_path: Optional[Path] = None,
        test_visitor: ASTVisitor = None,
    ):
        super().__init__(visitor, mapping_path)
        self.file_instrumentation = FileInstrumentation(visitor, mapping_path)
        if test_visitor:
            self.test_file_instrumentation = FileInstrumentation(
                test_visitor, mapping_path
            )
        else:
            self.test_file_instrumentation = None

    @staticmethod
    def check_included(element: str, includes: Optional[Iterable[str]]):
        return not includes or any(re.match(include, element) for include in includes)

    def check_tests(self, element: str, tests: Optional[Iterable[str]]):
        return (
            tests
            and self.test_file_instrumentation
            and any(re.match(test, element) for test in tests)
        )

    def handle_element(
        self,
        element: str,
        file_queue: queue.Queue[Tuple[str, bool]],
        src: os.PathLike,
        dst: os.PathLike,
        suffixes: List[str],
        check: bool,
    ):
        if os.path.isdir(os.path.join(src, element)):
            LOGGER.debug(f"I found a subdir at {element}.")
            os.makedirs(os.path.join(dst, element), exist_ok=True)
            for f in os.listdir(os.path.join(src, element)):
                file_queue.put((os.path.join(element, f), check, False))
        elif (
            not check
            and any(element.endswith(f".{suffix}") for suffix in suffixes)
            and not os.path.islink(os.path.join(src, element))
        ):
            LOGGER.debug(f"I found a file I can instrument at {element}.")
            self.file_instrumentation.instrument(
                os.path.join(src, element),
                os.path.join(dst, element),
                file=element,
            )
        else:
            LOGGER.debug(f"I found a file I will not instrument at {element}.")
            shutil.copy(
                os.path.join(src, element),
                os.path.join(dst, element),
                follow_symlinks=False,
            )

    def handle_test_element(
        self,
        element: str,
        file_queue: queue.Queue[Tuple[str, bool, bool]],
        src: os.PathLike,
        dst: os.PathLike,
        suffixes: List[str],
        check: bool,
    ):
        if os.path.isdir(os.path.join(src, element)):
            LOGGER.debug(f"I found a test subdir at {element}.")
            os.makedirs(os.path.join(dst, element), exist_ok=True)
            for f in os.listdir(os.path.join(src, element)):
                file_queue.put((os.path.join(element, f), check, True))
        elif (
            not check
            and any(element.endswith(f".{suffix}") for suffix in suffixes)
            and not os.path.islink(os.path.join(src, element))
        ):
            LOGGER.debug(f"I found a test file I can instrument at {element}.")
            self.test_file_instrumentation.instrument(
                os.path.join(src, element),
                os.path.join(dst, element),
                file=element,
            )
        else:
            LOGGER.debug(f"I found a test file I will not instrument at {element}.")
            shutil.copy(
                os.path.join(src, element),
                os.path.join(dst, element),
                follow_symlinks=False,
            )

    def instrument(
        self,
        src: os.PathLike,
        dst: os.PathLike,
        suffixes: List[str] = None,
        file: str = "",
        includes: Optional[Iterable[str]] = None,
        excludes: Optional[Iterable[str]] = None,
        tests: Optional[Iterable[str]] = None,
        test_files: Optional[Iterable[str]] = None,
    ):
        if suffixes is None:
            raise ValueError("DirInstrumentation requires suffixes")
        if excludes is None:
            excludes = list()
        if not os.path.exists(src):
            raise ValueError(f"Path {src} does not exist")
        if os.path.exists(dst):
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            else:
                os.remove(dst)
        if os.path.isfile(src):
            LOGGER.debug(f"I found a file I can instrument at {src}.")
            self.file_instrumentation.instrument(
                src, dst, suffixes=suffixes, file=os.path.split(src)[-1]
            )
        else:
            os.makedirs(dst, exist_ok=True)
            file_queue = queue.Queue()
            file_queue.put(("", True, False))
            while not file_queue.empty():
                element, check, test = file_queue.get()
                if check and self.check_included(element, includes):
                    self.handle_element(element, file_queue, src, dst, suffixes, False)
                elif test or self.check_tests(element, tests):
                    self.handle_test_element(
                        element, file_queue, src, dst, suffixes, False
                    )
                elif element != "" and any(
                    re.match(exclude, element) for exclude in excludes
                ):
                    if os.path.isdir(os.path.join(src, element)):
                        shutil.copytree(
                            os.path.join(src, element),
                            os.path.join(dst, element),
                            symlinks=True,
                        )
                    else:
                        shutil.copy(
                            os.path.join(src, element),
                            os.path.join(dst, element),
                            follow_symlinks=False,
                        )
                    continue
                else:
                    self.handle_element(element, file_queue, src, dst, suffixes, check)
            if test_files and self.test_file_instrumentation:
                for test_file in test_files:
                    if os.path.exists(os.path.join(src, test_file)):
                        self.test_file_instrumentation.instrument(
                            os.path.join(src, test_file),
                            os.path.join(dst, test_file),
                            file=test_file,
                        )
        self.events = self.file_instrumentation.events
        if self.test_file_instrumentation:
            self.events += self.test_file_instrumentation.events
        LOGGER.info(f"I found {len(self.events)} events in {src}.")
