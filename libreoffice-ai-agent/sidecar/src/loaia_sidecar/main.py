from loaia_sidecar.server import LoaiaSidecarServer


def main() -> None:
    server = LoaiaSidecarServer()
    server.run()


if __name__ == "__main__":
    main()
