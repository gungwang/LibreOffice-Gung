from loaia.bootstrap import OPEN_SIDEBAR_COMMAND, PROTOCOL_SCHEME, ExtensionBootstrap, bootstrap


class AIProtocolHandler:
    def __init__(self, runtime: ExtensionBootstrap | None = None) -> None:
        self.runtime = runtime or bootstrap()
        self._frame: object | None = None

    def set_frame(self, frame: object | None) -> None:
        self._frame = frame

    def handles(self, url: object) -> bool:
        protocol = getattr(url, "Protocol", "")
        path = getattr(url, "Path", "") or self._path_from_complete(getattr(url, "Complete", ""))
        return protocol == PROTOCOL_SCHEME and path == OPEN_SIDEBAR_COMMAND

    def dispatch(self, url: object, arguments: object) -> str:
        del arguments

        if not self.handles(url):
            raise ValueError("Protocol handler received an unsupported URL")

        return self.open_sidebar(frame=self._frame)

    def open_sidebar(self, frame: object | None = None) -> str:
        panel = self.runtime.open_sidebar(frame=frame)
        return f"{panel.title} sidebar opened"

    @staticmethod
    def _path_from_complete(complete: str) -> str:
        if not complete.startswith(PROTOCOL_SCHEME):
            return ""

        return complete.removeprefix(PROTOCOL_SCHEME)
