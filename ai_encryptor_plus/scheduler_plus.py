import heapq, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Tuple
from .cost_model import CostModel

class Task:
    __slots__ = ("prio","path","size","suffix")
    def __init__(self, prio, path, size, suffix):
        self.prio = prio
        self.path = path
        self.size = size
        self.suffix = suffix
    def __lt__(self, other): return self.prio < other.prio

class SchedulerPlus:
    def __init__(self, max_workers=4):
        self.cm = CostModel()
        self.max_workers = max_workers

    def plan(self, files: List[Path]) -> List[Task]:
        # Files ko priority ke saath schedule karta hai
        # Return: Task objects ka list (priority order mein)

        # 1) tiny batch → FIFO
        if len(files) <= 2:
            return [Task(0, p, p.stat().st_size, p.suffix.lower()) for p in files]

        total_size = sum(p.stat().st_size for p in files)

        # 2) total workload too small → FIFO
        if total_size < 4 * 1024 * 1024:    # 4 MB
            return [Task(0, p, p.stat().st_size, p.suffix.lower()) for p in files]

        # 3) files all small → FIFO
        if all(p.stat().st_size < 256 * 1024 for p in files):  # < 256 KB
            return [Task(0, p, p.stat().st_size, p.suffix.lower()) for p in files]

        # AI model se priority predict karta hai
        pq = []
        for p in files:
            size = p.stat().st_size
            suffix = p.suffix.lower()
            prio = self.cm.predict_seconds(chunk_size=size, suffix=suffix, sample=None)
            heapq.heappush(pq, Task(prio, p, size, suffix))
        plan = []
        while pq:
            plan.append(heapq.heappop(pq))
        return plan

    def observe(self, p: Path, elapsed: float):
        # File process karne mein actual time nikalta hai
        # CostModel ko update karta hai
        size = p.stat().st_size
        self.cm.observe(chunk_size=size, suffix=p.suffix.lower(), actual_s=elapsed, sample=None)
