from loaia.bootstrap import (
    APPROVE_PENDING_COMMAND,
    OPEN_SIDEBAR_COMMAND,
    PREVIEW_SELECTION_COMMAND,
    PROTOCOL_SCHEME,
    ExtensionBootstrap,
    bootstrap,
)


class AIProtocolHandler:
    SUPPORTED_COMMANDS = {
        OPEN_SIDEBAR_COMMAND,
        PREVIEW_SELECTION_COMMAND,
        APPROVE_PENDING_COMMAND,
    }

    def __init__(self, runtime: ExtensionBootstrap | None = None) -> None:
        self.runtime = runtime or bootstrap()
        self._frame: object | None = None

    def set_frame(self, frame: object | None) -> None:
        self._frame = frame

    def handles(self, url: object) -> bool:
        protocol = getattr(url, "Protocol", "")
        path = getattr(url, "Path", "") or self._path_from_complete(getattr(url, "Complete", ""))
        return protocol == PROTOCOL_SCHEME and path in self.SUPPORTED_COMMANDS

    def dispatch(self, url: object, arguments: object) -> str:
        command = getattr(url, "Path", "") or self._path_from_complete(
            getattr(url, "Complete", "")
        )

        if not self.handles(url) or command not in self.SUPPORTED_COMMANDS:
            raise ValueError("Protocol handler received an unsupported URL")

        if command == OPEN_SIDEBAR_COMMAND:
            return self.open_sidebar(frame=self._frame)

        if command == PREVIEW_SELECTION_COMMAND:
            prompt = self._argument_value(arguments, "Prompt", "UserMessage")
            return self.preview_selection(frame=self._frame, prompt=prompt)

        return self.approve_pending(frame=self._frame)

    def open_sidebar(self, frame: object | None = None) -> str:
        panel = self.runtime.open_sidebar(frame=frame)
        return f"{panel.title} sidebar opened"

    def preview_selection(self, frame: object | None = None, prompt: str | None = None) -> str:
        return self.runtime.preview_selection(frame=frame, prompt=prompt)

    def approve_pending(self, frame: object | None = None) -> str:
        return self.runtime.approve_pending(frame=frame)

    @staticmethod
    def _path_from_complete(complete: str) -> str:
        if not complete.startswith(PROTOCOL_SCHEME):
            return ""

        return complete.removeprefix(PROTOCOL_SCHEME)

    @staticmethod
    def _argument_value(arguments: object, *names: str) -> str | None:
        if not isinstance(arguments, (list, tuple)):
            return None

        accepted_names = set(names)
        for argument in arguments:
            name = getattr(argument, "Name", None)
            value = getattr(argument, "Value", None)
            if name in accepted_names and isinstance(value, str):
                return value

        return None
