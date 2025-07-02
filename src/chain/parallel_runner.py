from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_core.runnables import Runnable, RunnableLambda


class ParallelRunner[Input, Output](RunnableLambda[Sequence[Input], Sequence[Output]]):
    def __init__(
        self,
        worker: Runnable[Input, Output] | Callable[[Input], Output],
        max_workers: int | None = None,
    ) -> None:
        super().__init__(self._run)
        self.worker = worker.invoke if isinstance(worker, Runnable) else worker
        self.max_workers = max_workers

    def _run(self, inputs: Sequence[Input]) -> Sequence[Output]:
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_input = {executor.submit(self.worker, inp): inp for inp in inputs}
            return [future.result() for future in as_completed(future_to_input)]
