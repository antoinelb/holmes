from holmes.utils.config import hash_config


class TestHashConfig:
    def test_stable(self):
        config = {"a": 1, "b": [1, 2, {"c": "x"}]}
        assert hash_config(config) == hash_config(config)
        assert len(hash_config(config)) == 8

    def test_key_order_is_ignored(self):
        assert hash_config({"a": 1, "b": 2}) == hash_config({"b": 2, "a": 1})

    def test_hash_key_is_excluded(self):
        assert hash_config({"a": 1, "hash": "xyz"}) == hash_config({"a": 1})

    def test_nested_values_change_the_hash(self):
        assert hash_config({"a": [1, {"b": 2}]}) != hash_config(
            {"a": [1, {"b": 3}]}
        )
