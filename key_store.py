"""Use only macOS Keychain; never fall back to a plaintext backend."""
SERVICE = 'paper-calendar.gemini'
ACCOUNT = 'api-key'


def backend():
    import sys
    if sys.platform != 'darwin':
        raise RuntimeError('macOSキーチェーンが必要です')
    from keyring.backends.macOS import Keyring
    return Keyring()


def load_key():
    return backend().get_password(SERVICE, ACCOUNT) or ''


def save_key(value):
    from recognition import validate_api_settings
    value, _ = validate_api_settings(value, 'keychain')
    backend().set_password(SERVICE, ACCOUNT, value)


def delete_key():
    backend().delete_password(SERVICE, ACCOUNT)
