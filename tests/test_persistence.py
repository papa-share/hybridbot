from chatbot.persistence import _step_dict_from_row, default_chat_prefs


def test_default_chat_prefs():
    prefs = default_chat_prefs("[cloud] gpt-oss:120b-cloud")
    assert prefs["model"] == "[cloud] gpt-oss:120b-cloud"
    assert prefs["temperature"] == 0.4
    assert prefs["max_tokens"] == 1024


def test_step_dict_from_row_favorite():
    row = {
        "step_id": "id-1",
        "step_name": "User",
        "step_type": "user_message",
        "step_threadid": "thread-1",
        "step_parentid": None,
        "step_streaming": False,
        "step_metadata": {"favorite": True},
        "step_showinput": "false",
        "step_output": "Bonjour",
    }
    step = _step_dict_from_row(row)
    assert step is not None
    assert step["output"] == "Bonjour"


def test_step_dict_from_row_not_favorite():
    row = {
        "step_id": "id-1",
        "step_name": "User",
        "step_type": "user_message",
        "step_threadid": "thread-1",
        "step_parentid": None,
        "step_metadata": {"favorite": False},
        "step_showinput": "false",
        "step_output": "Bonjour",
    }
    assert _step_dict_from_row(row) is None
