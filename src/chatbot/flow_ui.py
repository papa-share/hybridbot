from chainlit.element import Task, TaskList, TaskStatus

LLM_FLOW_EVENTS = frozenset({"model", "retry", "generating", "done", "error"})


def safe_title(value: str | None, *, default: str = "") -> str:
    text = (value or default).replace("\n", " ")
    return text or default


async def push_task_list(task_list: TaskList, sent: bool) -> bool:
    if not sent:
        await task_list.send()
        return True
    await task_list.update()
    return sent


def apply_llm_flow(kind: str, data: dict, llm_task: Task, task_list: TaskList) -> bool:
    if kind not in LLM_FLOW_EVENTS:
        return False
    if kind == "model":
        llm_task.status = TaskStatus.RUNNING
        llm_task.title = "Génération"
        task_list.status = "Préparation"
    elif kind == "retry":
        llm_task.status = TaskStatus.RUNNING
        llm_task.title = "Nouvel essai"
        task_list.status = "Relance"
    elif kind == "generating":
        llm_task.status = TaskStatus.RUNNING
        task_list.status = "Génération"
    elif kind == "done":
        llm_task.status = TaskStatus.DONE
        task_list.status = "Terminé"
    elif kind == "error":
        llm_task.status = TaskStatus.FAILED
        task_list.status = data.get("message") or "Erreur"
    return True
