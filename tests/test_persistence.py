from chatbot.persistence import default_chat_prefs, model_index


def test_default_chat_prefs():
    prefs = default_chat_prefs("[cloud] gpt-oss:120b-cloud")
    assert prefs["model"] == "[cloud] gpt-oss:120b-cloud"
    assert prefs["temperature"] == 0.4
    assert prefs["max_tokens"] == 1024


def test_model_index():
    models = ["a", "b", "c"]
    assert model_index(models, "b", 0) == 1
    assert model_index(models, "missing", 2) == 2
