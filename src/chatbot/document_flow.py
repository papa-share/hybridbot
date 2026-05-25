from chainlit.element import Task, TaskList, TaskStatus

from chatbot.flow_ui import apply_llm_flow, push_task_list, safe_title


class DocumentFlowUI:
    def __init__(self) -> None:
        self._sent = False
        self._file = Task(title="PDF", status=TaskStatus.READY)
        self._extract = Task(title="Extraction", status=TaskStatus.READY)
        self._llm = Task(title="Réponse", status=TaskStatus.READY)
        self.task_list = TaskList(
            tasks=[self._file, self._extract, self._llm],
            status="Document",
        )

    async def handle(self, kind: str, data: dict) -> None:
        if kind == "extract_start":
            self._file.title = safe_title(data.get("name"), default="PDF")
            self._file.status = TaskStatus.RUNNING
            self._extract.status = TaskStatus.READY
            self.task_list.status = "PDF détecté"
        elif kind == "extracting":
            self._file.status = TaskStatus.DONE
            self._extract.title = data.get("message") or "Extraction en cours"
            self._extract.status = TaskStatus.RUNNING
            self.task_list.status = "Extraction"
        elif kind == "extract_done":
            self._extract.status = TaskStatus.DONE
            self._extract.title = "Extraction terminée"
            self.task_list.status = "Texte extrait"
        elif apply_llm_flow(kind, data, self._llm, self.task_list):
            if kind == "error":
                self._file.status = TaskStatus.FAILED
                self._extract.status = TaskStatus.FAILED

        self._sent = await push_task_list(self.task_list, self._sent)
