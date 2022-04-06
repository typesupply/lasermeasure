from mojo import roboFont

version = roboFont.version
versionMajor, versionMinor = version.split(".", 1)
versionMinor = versionMinor.split(".")[0]
versionMajor = "".join([i for i in versionMajor if i in "0123456789"])
versionMinor = "".join([i for i in versionMinor if i in "0123456789"])
versionMajor = int(versionMajor)
versionMinor = int(versionMinor)