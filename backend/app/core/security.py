def wipe_password(password: str) -> None:
    if not isinstance(password, str):
        return

    password = "0" * len(password)
    del password
