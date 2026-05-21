try:
    import unohelper
    from com.sun.star.frame import XDispatch, XDispatchProvider
    from com.sun.star.lang import XInitialization, XServiceInfo
    from com.sun.star.ui import XUIElementFactory
except ImportError:
    class _UnoBase:
        pass


    class _ImplementationHelper:
        def __init__(self) -> None:
            self.implementations: list[tuple[object, str, tuple[str, ...]]] = []

        def addImplementation(
            self,
            constructor: object,
            implementation_name: str,
            service_names: tuple[str, ...],
        ) -> None:
            self.implementations.append((constructor, implementation_name, service_names))


    class _UnoHelperModule:
        Base = _UnoBase
        ImplementationHelper = _ImplementationHelper


    unohelper = _UnoHelperModule()

    class XDispatch:
        pass


    class XDispatchProvider:
        pass


    class XInitialization:
        pass


    class XServiceInfo:
        pass


    class XUIElementFactory:
        pass

from loaia.bootstrap import SIDEBAR_RESOURCE_URL, ExtensionBootstrap, bootstrap
from loaia.protocol_handler import AIProtocolHandler


class ServiceInfoMixin:
    implementationName = ""
    serviceNames: tuple[str, ...] = ()

    def getImplementationName(self) -> str:
        return self.implementationName

    def supportsService(self, service_name: str) -> bool:
        return service_name in self.serviceNames

    def getSupportedServiceNames(self) -> tuple[str, ...]:
        return self.serviceNames


class LoaiaProtocolDispatch(unohelper.Base, ServiceInfoMixin, XDispatch):
    implementationName = "org.gungwang.libreoffice.ai.agent.ProtocolDispatch"
    serviceNames = ()

    def __init__(
        self,
        context: object | None = None,
        runtime: ExtensionBootstrap | None = None,
    ) -> None:
        self.context = context
        self.runtime = runtime or bootstrap()
        self._handler = AIProtocolHandler(runtime=self.runtime)

    def set_frame(self, frame: object | None) -> None:
        self._handler.set_frame(frame)

    def handles(self, url: object) -> bool:
        return self._handler.handles(url)

    def dispatch(self, url: object, arguments: object) -> None:
        self._handler.dispatch(url, arguments)

    def addStatusListener(self, control: object, url: object) -> None:
        del control, url

    def removeStatusListener(self, control: object, url: object) -> None:
        del control, url


class LoaiaProtocolHandlerProvider(
    unohelper.Base,
    ServiceInfoMixin,
    XServiceInfo,
    XInitialization,
    XDispatchProvider,
):
    implementationName = "org.gungwang.libreoffice.ai.agent.ProtocolHandler"
    serviceNames = ("com.sun.star.frame.ProtocolHandler",)

    def __init__(
        self,
        context: object | None = None,
        runtime: ExtensionBootstrap | None = None,
    ) -> None:
        self.context = context
        self.runtime = runtime or bootstrap()
        self._dispatch = LoaiaProtocolDispatch(context=context, runtime=self.runtime)

    def initialize(self, arguments: tuple[object, ...] | list[object]) -> None:
        if arguments:
            self._dispatch.set_frame(arguments[0])

    def queryDispatch(
        self,
        url: object,
        target_frame_name: str,
        search_flags: int,
    ) -> object | None:
        del target_frame_name, search_flags

        if self._dispatch.handles(url):
            return self._dispatch

        return None

    def queryDispatches(
        self,
        requests: list[object] | tuple[object, ...],
    ) -> tuple[object | None, ...]:
        return tuple(
            self.queryDispatch(request.FeatureURL, request.FrameName, request.SearchFlags)
            for request in requests
        )


class LoaiaSidebarPanelFactory(
    unohelper.Base,
    ServiceInfoMixin,
    XServiceInfo,
    XUIElementFactory,
):
    implementationName = "org.gungwang.libreoffice.ai.agent.SidebarFactory"
    serviceNames = ("com.sun.star.ui.UIElementFactory",)

    def __init__(
        self,
        context: object | None = None,
        runtime: ExtensionBootstrap | None = None,
    ) -> None:
        self.context = context
        self.runtime = runtime or bootstrap()

    def createUIElement(
        self,
        resource_url: str,
        arguments: list[object] | tuple[object, ...],
    ) -> object:
        if resource_url != SIDEBAR_RESOURCE_URL:
            raise ValueError(f"Unsupported sidebar resource URL: {resource_url}")

        values_by_name = {
            argument.Name: argument.Value
            for argument in arguments
            if hasattr(argument, "Name") and hasattr(argument, "Value")
        }

        return self.runtime.create_sidebar_ui_element(
            resource_url=resource_url,
            frame=values_by_name.get("Frame"),
            parent_window=values_by_name.get("ParentWindow"),
        )


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    LoaiaProtocolHandlerProvider,
    LoaiaProtocolHandlerProvider.implementationName,
    LoaiaProtocolHandlerProvider.serviceNames,
)
g_ImplementationHelper.addImplementation(
    LoaiaSidebarPanelFactory,
    LoaiaSidebarPanelFactory.implementationName,
    LoaiaSidebarPanelFactory.serviceNames,
)