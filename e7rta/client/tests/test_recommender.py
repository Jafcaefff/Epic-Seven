from unittest.mock import Mock

import pytest

from e7rta.client.recommender import Recommender


def test_recommend_posts_contract_payload():
    response = Mock()
    response.json.return_value = {"recommendations": [{"code": "c1168", "name": "利纳柯"}]}
    session = Mock()
    session.post.return_value = response
    client = Recommender("http://localhost:8799/", session=session)

    result = client.recommend(["c5154"], top=999, timeout=1)

    assert result["recommendations"][0]["name"] == "利纳柯"
    session.post.assert_called_once_with(
        "http://localhost:8799/api/draft/quick",
        json={"enemy_picks": ["c5154"], "top": 100},
        timeout=1,
    )
    response.raise_for_status.assert_called_once()


def test_recommend_rejects_bad_code_before_network():
    session = Mock()
    with pytest.raises(ValueError):
        Recommender(session=session).recommend(["not-a-code"])
    session.post.assert_not_called()


def test_recommend_rejects_invalid_response():
    response = Mock()
    response.json.return_value = {"wrong": []}
    session = Mock()
    session.post.return_value = response
    with pytest.raises(ValueError):
        Recommender(session=session).recommend([])
