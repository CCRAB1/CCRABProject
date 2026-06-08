# test_purpleair_client.py
from unittest.mock import MagicMock, patch

import pytest
from PurpleAPIWrapper import PurpleAirAPIError, PurpleAirClient

API_KEY = "test_key"


@pytest.fixture
def client():
    return PurpleAirClient(api_key=API_KEY, timeout=1.0)


def make_mock_response(status_code=200, json_data=None, text="OK"):
    """Helper to create a mock requests.Response object."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.ok = 200 <= status_code < 300
    if json_data is not None:
        mock_resp.json.return_value = json_data
    else:
        mock_resp.json.side_effect = ValueError("No JSON")
    mock_resp.text = text
    return mock_resp


# -------- Organization tests --------


@patch("requests.request")
def test_get_organization_success(mock_request, client):
    mock_request.return_value = make_mock_response(
        200, {"organization": {"id": 1, "name": "Test Org"}}
    )
    data = client.get_organization()
    assert data["organization"]["name"] == "Test Org"
    mock_request.assert_called_once()


@patch("requests.request")
def test_update_organization_success(mock_request, client):
    mock_request.return_value = make_mock_response(200, {"ok": True})
    data = client.update_organization(name="New Name")
    assert data["ok"] is True
    args, kwargs = mock_request.call_args
    assert kwargs["json"] == {"name": "New Name"}


# -------- Sensor tests --------


@patch("requests.request")
def test_get_sensor_with_fields(mock_request, client):
    mock_request.return_value = make_mock_response(
        200, {"sensor": {"sensor_index": 123, "pm2.5_atm": 10.2}}
    )
    result = client.get_sensor(123, fields=["pm2.5_atm"])
    assert result["sensor"]["pm2.5_atm"] == 10.2
    args, kwargs = mock_request.call_args
    assert kwargs["params"]["fields"] == "pm2.5_atm"


@patch("requests.request")
def test_get_sensor_history_error(mock_request, client):
    mock_request.return_value = make_mock_response(500, text="Internal error")
    with pytest.raises(PurpleAirAPIError):
        client.get_sensor_history(123, 1000, 2000)


# -------- Group tests --------


@patch("requests.request")
def test_create_group(mock_request, client):
    mock_request.return_value = make_mock_response(200, {"group_id": 42})
    data = client.create_group("My Group")
    assert data["group_id"] == 42
    args, kwargs = mock_request.call_args
    assert kwargs["json"] == {"name": "My Group"}


@patch("requests.request")
def test_add_and_remove_member(mock_request, client):
    # add member
    mock_request.return_value = make_mock_response(200, {"ok": True})
    add_result = client.add_member_to_group(1, 999)
    assert add_result["ok"]

    # remove member
    mock_request.return_value = make_mock_response(200, {"ok": True})
    remove_result = client.remove_member_from_group(1, 1234)
    assert remove_result["ok"]


@patch("requests.request")
def test_get_members_data_with_fields(mock_request, client):
    mock_request.return_value = make_mock_response(200, {"data": [{"pm2.5_atm": 12.3}]})
    result = client.get_members_data(1, fields=["pm2.5_atm"])
    assert result["data"][0]["pm2.5_atm"] == 12.3
    args, kwargs = mock_request.call_args
    assert kwargs["params"]["fields"] == "pm2.5_atm"


# -------- Error handling --------


@patch("requests.request")
def test_non_json_response_raises(client, mock_request):
    mock_request.return_value = make_mock_response(200, json_data=None)
    with pytest.raises(PurpleAirAPIError):
        client.get_groups()


@patch("requests.request")
def test_http_error_raises(client, mock_request):
    mock_request.return_value = make_mock_response(404, text="Not Found")
    with pytest.raises(PurpleAirAPIError):
        client.get_group_detail(999)
