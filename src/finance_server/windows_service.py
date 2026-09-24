from __future__ import annotations

import sys

import servicemanager
import win32event
import win32service
import win32serviceutil
import uvicorn

from finance_server.service_main import (
    API_HOST,
    API_PORT,
    create_service_app,
)


SERVICE_NAME = "JATechnologyFinanceServer"
SERVICE_DISPLAY_NAME = "J.A. Technology Finance Server"
SERVICE_DESCRIPTION = (
    "Servidor local da API do J.A. Technology Finance."
)


class FinanceServerWindowsService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY_NAME
    _svc_description_ = SERVICE_DESCRIPTION

    def __init__(self, args) -> None:
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(
            None,
            0,
            0,
            None,
        )
        self.server: uvicorn.Server | None = None
        self.stop_requested = False

    def SvcStop(self) -> None:
        self.stop_requested = True
        self.ReportServiceStatus(
            win32service.SERVICE_STOP_PENDING
        )

        if self.server is not None:
            self.server.should_exit = True

        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self) -> None:
        servicemanager.LogInfoMsg(
            f"{SERVICE_NAME}: iniciando."
        )

        try:
            app = create_service_app()

            config = uvicorn.Config(
                app=app,
                host=API_HOST,
                port=API_PORT,
                log_level="info",
                access_log=True,
            )

            server = uvicorn.Server(config)
            self.server = server
            if self.stop_requested:
                server.should_exit = True
            server.run()

        except Exception as error:
            servicemanager.LogErrorMsg(
                f"{SERVICE_NAME}: falha ao iniciar: {error}"
            )
            raise

        finally:
            self.server = None
            servicemanager.LogInfoMsg(
                f"{SERVICE_NAME}: encerrado."
            )


def main() -> None:
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(
            FinanceServerWindowsService
        )
        servicemanager.StartServiceCtrlDispatcher()
        return

    win32serviceutil.HandleCommandLine(
        FinanceServerWindowsService
    )


if __name__ == "__main__":
    main()
