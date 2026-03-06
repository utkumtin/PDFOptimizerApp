from setuptools import setup

APP = ["main.py"]
DATA_FILES = [
    ("resources", ["resources/style.qss", "resources/icon.icns", "resources/trash.svg"]),
]
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "resources/icon.icns",
    "plist": {
        "CFBundleName": "PDF Optimizer",
        "CFBundleDisplayName": "PDF Optimizer",
        "CFBundleGetInfoString": "Advanced PDF Optimization Tool",
        "CFBundleIdentifier": "com.pdfoptimizer.app",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "NSHighResolutionCapable": True,
    },
    "packages": ["PySide6"],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
