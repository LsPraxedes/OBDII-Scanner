
import json
from unittest.mock import MagicMock, patch
from backend.mqtt_client import on_message

@patch('backend.mqtt_client.SessionLocal')
def test_on_message_valid_payload(mock_session_local):
    """
    Testa o processamento de uma mensagem MQTT com JSON válido.
    """
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db

    mock_client = MagicMock()
    mock_msg = MagicMock()
    mock_msg.topic = "test/topic"
    
    # Payload válido
    payload = {"rpm": 2500, "temperature": 90, "speed": 80}
    mock_msg.payload = json.dumps(payload).encode('utf-8')

    on_message(mock_client, None, mock_msg)

    # Verifica se a sessão de banco de dados foi usada e o commit foi chamado
    assert mock_session_local.called
    assert mock_db.add.called
    assert mock_db.commit.called
    assert mock_db.close.called

@patch('backend.mqtt_client.SessionLocal')
def test_on_message_invalid_json(mock_session_local):
    """
    Testa o recebimento de um JSON malformado.
    """
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db

    mock_client = MagicMock()
    mock_msg = MagicMock()
    mock_msg.topic = "test/topic"
    
    # Payload malformado
    mock_msg.payload = b"not_a_json"

    on_message(mock_client, None, mock_msg)

    # Não deve ter chamado add nem commit
    assert not mock_db.add.called
    assert not mock_db.commit.called

@patch('backend.mqtt_client.SessionLocal')
def test_on_message_invalid_schema(mock_session_local):
    """
    Testa o recebimento de um JSON válido mas que viola o schema do Pydantic.
    """
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db

    mock_client = MagicMock()
    mock_msg = MagicMock()
    mock_msg.topic = "test/topic"
    
    # Payload violando tipo (rpm como string)
    payload = {"rpm": "string_invalida", "temperature": 90}
    mock_msg.payload = json.dumps(payload).encode('utf-8')

    on_message(mock_client, None, mock_msg)

    # Não deve ter chamado add nem commit
    assert not mock_db.add.called
    assert not mock_db.commit.called
