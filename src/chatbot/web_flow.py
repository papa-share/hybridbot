from chainlit.element import Task, TaskList, TaskStatus

from chatbot.flow_ui import apply_llm_flow, push_task_list


class WebFlowUI:
    def __init__(self) -> None:
        self._sent = False
        self._exa = Task(title="Recherche Exa", status=TaskStatus.RUNNING)
        self._llm = Task(title="Réponse", status=TaskStatus.READY)
        self._sources: list[Task] = []
        self.task_list = TaskList(
            tasks=[self._exa, self._llm],
            status="Recherche en cours",
        )

    def _sync_tasks(self) -> None:
        self.task_list.tasks = [self._exa, *self._sources, self._llm]

    async def handle(self, kind: str, data: dict) -> None:
        if kind == "searching":
            query = data.get("query", "")
            self._exa.title = f"Exa : {query}"
            self._exa.status = TaskStatus.RUNNING
            self.task_list.status = "Interrogation Exa"
        elif kind == "source":
            idx = data["index"]
            total = data["total"]
            title = (data.get("title") or "Sans titre").replace("\n", " ")
            url = data.get("url") or ""
            self._exa.status = TaskStatus.DONE
            self.task_list.status = f"Sources ({idx}/{total})"
            if url:
                self._sources.append(
                    Task(
                        title=f"{idx}. [{title}]({url})",
                        status=TaskStatus.DONE,
                    )
                )
                self._sync_tasks()
        elif kind == "sources_done":
            count = data.get("count", len(self._sources))
            self._exa.status = TaskStatus.DONE
            self.task_list.status = f"{count} source(s)"
        elif kind == "empty":
            self._exa.status = TaskStatus.DONE
            self._llm.status = TaskStatus.FAILED
            self._llm.title = "Aucune source"
            self.task_list.status = "Aucun résultat"
        elif apply_llm_flow(kind, data, self._llm, self.task_list):
            if kind == "error":
                self._exa.status = TaskStatus.FAILED

        self._sent = await push_task_list(self.task_list, self._sent)
