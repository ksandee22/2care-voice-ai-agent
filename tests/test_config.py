from backend.config import is_valid_openai_api_key


def test_placeholder_keys_invalid():
    assert is_valid_openai_api_key("your_key") is False
    assert is_valid_openai_api_key("your_openai_api_key_here") is False
    assert is_valid_openai_api_key("") is False


def test_real_key_shape():
    assert is_valid_openai_api_key("sk-" + "a" * 40) is True
