from chainlit.element import Task, TaskList, TaskStatus


def format_source_link(index: int, title: str, url: str) -> str:
    clean = (title or "Sans titre").replace("\n", " ")
    return f"{index}. [{clean}]({url})"


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

    async def _push(self) -> None:
        if not self._sent:
            await self.task_list.send()
            self._sent = True
        else:
            await self.task_list.update()

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
            title = data.get("title") or "Sans titre"
            url = data.get("url") or ""
            self._exa.status = TaskStatus.DONE
            self.task_list.status = f"Sources ({idx}/{total})"
            if url:
                self._sources.append(
                    Task(
                        title=format_source_link(idx, title, url),
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
        elif kind == "model":
            model = data.get("name", "")
            self._llm.status = TaskStatus.RUNNING
            self._llm.title = f"Modèle : {model}"
            self.task_list.status = "Préparation"
        elif kind == "retry":
            model = data.get("name", "")
            self._llm.title = f"Essai : {model}"
            self._llm.status = TaskStatus.RUNNING
            self.task_list.status = "Bascule modèle"
        elif kind == "generating":
            self._llm.status = TaskStatus.RUNNING
            self.task_list.status = "Génération"
        elif kind == "done":
            self._llm.status = TaskStatus.DONE
            self.task_list.status = "Terminé"
        elif kind == "error":
            self._exa.status = TaskStatus.FAILED
            self.task_list.status = "Erreur"

        await self._push()
