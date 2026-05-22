from loaia.bootstrap import (
    APPROVE_PENDING_COMMAND,
    OPEN_SIDEBAR_COMMAND,
    PREVIEW_SELECTION_COMMAND,
    PROTOCOL_SCHEME,
    SAVE_SETTINGS_COMMAND,
    ExtensionBootstrap,
    bootstrap,
)


class AIProtocolHandler:
    SUPPORTED_COMMANDS = {
        OPEN_SIDEBAR_COMMAND,
        PREVIEW_SELECTION_COMMAND,
        APPROVE_PENDING_COMMAND,
        SAVE_SETTINGS_COMMAND,
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
            pipe_address = self._argument_value(arguments, "PipeAddress")
            return self.preview_selection(
                frame=self._frame,
                prompt=prompt,
                pipe_address=pipe_address,
            )

        if command == SAVE_SETTINGS_COMMAND:
            provider = self._argument_value(arguments, "Provider")
            model = self._argument_value(arguments, "Model")
            return self.save_settings(
                frame=self._frame,
                provider=provider,
                model=model,
            )

        return self.approve_pending(frame=self._frame)

    def open_sidebar(self, frame: object | None = None) -> str:
        panel = self.runtime.open_sidebar(frame=frame)
        return f"{panel.title} sidebar opened"

    def preview_selection(
        self,
        frame: object | None = None,
        prompt: str | None = None,
        pipe_address: str | None = None,
    ) -> str:
        return self.runtime.preview_selection(
            frame=frame,
            prompt=prompt,
            pipe_address=pipe_address,
        )

    def approve_pending(self, frame: object | None = None) -> str:
        return self.runtime.approve_pending(frame=frame)

    def save_settings(
        self,
        frame: object | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> str:
        return self.runtime.save_settings(
            frame=frame,
            provider=provider,
            model=model,
        )

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
