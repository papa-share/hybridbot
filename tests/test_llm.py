from chatbot.llm import _skip_model, _vision_pool, build_model_labels, model_from_label


def test_skip_embed_ocr():
    assert _skip_model("nomic-embed-text:latest")
    assert _skip_model("glm-ocr:q8_0")
    assert not _skip_model("qwen3-vl:235b-cloud")


def test_model_from_label():
    assert model_from_label("[cloud] nemotron-3-super:cloud") == "nemotron-3-super:cloud"
    assert model_from_label("granite4:latest") == "granite4:latest"


def test_vision_pool_cloud_first():
    catalog = {
        "chat_local": [],
        "chat_cloud": [],
        "vision_local": ["gemma4:e2b"],
        "vision_cloud": ["devstral-small-2:24b-cloud", "gemma4:31b-cloud"],
    }
    assert _vision_pool(catalog) == [
        "devstral-small-2:24b-cloud",
        "gemma4:31b-cloud",
        "gemma4:e2b",
    ]


def test_build_model_labels():
    catalog = {
        "chat_local": ["granite4:latest"],
        "chat_cloud": ["nemotron-3-super:cloud"],
        "vision_local": ["gemma4:e2b"],
        "vision_cloud": ["qwen3-vl:235b-cloud"],
    }
    labels = build_model_labels(catalog)
    assert labels == [
        "[local] granite4:latest",
        "[vision local] gemma4:e2b",
        "[cloud] nemotron-3-super:cloud",
        "[vision cloud] qwen3-vl:235b-cloud",
    ]
