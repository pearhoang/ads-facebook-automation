from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


def _cipher(key: bytes) -> Fernet:
    try:
        return Fernet(key)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("SECRET_ENCRYPTION_KEY phải là Fernet key hợp lệ.") from exc


def encrypt_password(key: bytes, password: str) -> str:
    if not password:
        raise ValueError("SSH password không được để trống.")
    return _cipher(key).encrypt(password.encode("utf-8")).decode("ascii")


def decrypt_password(key: bytes, ciphertext: str | None) -> str | None:
    if not ciphertext:
        return None
    try:
        return _cipher(key).decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Không giải mã được SSH password bằng key hiện tại.") from exc
