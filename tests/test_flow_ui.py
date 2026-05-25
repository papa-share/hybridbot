from chainlit.element import TaskStatus

from chatbot.flow_ui import apply_llm_flow


class _FakeTask:
    def __init__(self) -> None:
        self.title = "Réponse"
        self.status = TaskStatus.READY


class _FakeTaskList:
    def __init__(self) -> None:
        self.status = "init"


def test_apply_llm_flow_generating():
    llm_task = _FakeTask()
    task_list = _FakeTaskList()

    assert apply_llm_flow("generating", {}, llm_task, task_list) is True
    assert llm_task.status == TaskStatus.RUNNING
    assert task_list.status == "Génération"


def test_apply_llm_flow_unknown_event():
    llm_task = _FakeTask()
    task_list = _FakeTaskList()

    assert apply_llm_flow("unknown", {}, llm_task, task_list) is False
    assert llm_task.status == TaskStatus.READY


def test_apply_llm_flow_error_uses_message():
    llm_task = _FakeTask()
    task_list = _FakeTaskList()

    assert apply_llm_flow("error", {"message": "Exa HS"}, llm_task, task_list) is True
    assert llm_task.status == TaskStatus.FAILED
    assert task_list.status == "Exa HS"
