[app]

# (str) Title of your application
title = WaveBrute

# (str) Package name
package.name = wavebrute

# (str) Package domain (needed for android)
package.domain = org.wavebrute

# (str) Source code directory (where your main.py or main.pyx lives)
source.dir = .

# (list) Source files to include (regex works too)
source.include_exts = py,png,jpg,kv,atlas,svg,ttf,otf

# (list) Source files to exclude
source.exclude_patterns = tests/**,docs/**,.github/**,CHANGELOG.md,CONTRIBUTING.md,README.md,SECURITY.md

# (str) Application version
version = 0.1.0

# (str) Application main file (the one that starts the Kivy app)
main = main.py

# (list) Application requirements
requirements = python3,kivy==2.1.0,scapy,jinja2,click,setuptools

# (str) Orientation of the application
orientation = portrait,landscape

# (bool) Indicate if the application will be fullscreen
fullscreen = 0

# (list) Permissions
android.permissions = INTERNET,ACCESS_NETWORK_STATE,CHANGE_NETWORK_STATE,ACCESS_WIFI_STATE,CHANGE_WIFI_STATE,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# (int) Target Android API level
android.api = 33

# (int) Minimum Android API level
android.minapi = 24

# (bool) Whether to build in release mode
# android.release = False

# (str) Path to a custom keystore
# android.keystore = wavebrute.keystore

# (str) Keystore password
# android.keystore_password = wavebrute123

# (str) Alias of the key in the keystore
# android.keyalias = wavebrute

# (str) Key password
# android.keyalias_password = wavebrute123

# (str) Android entry point
android.entrypoint = org.kivy.android.PythonActivity

# (list) Android additional jars
# NOTE: left commented out (not set to empty) - buildozer has a bug where
# a present-but-empty value here resolves to the project's source
# directory itself and tries to copy it as a .jar, crashing the final
# apk packaging step.
#android.add_jars =

# (list) Android additional aars
#android.add_aars =

# (str) Android NDK version
android.ndk = 25b

# (str) Android SDK version
android.sdk = 33

# (bool) If True, enables the SDL2 bootstrap (recommended for Kivy)
android.bootstrap = sdl2

# (str) python-for-android branch/tag to use.
# Pinned to an older release because current python-for-android (master)
# targets Python 3.14, and Kivy 2.1.0's setup.py still imports the stdlib
# 'cgi' module, which was removed in Python 3.13. This release's python3
# recipe builds Python 3.11.5 instead, which still has 'cgi'.
p4a.branch = v2024.01.21

# (str) Python version used by the app
# NOTE: this key is no longer read by current buildozer/python-for-android
# (the actual target Python version comes from the pinned p4a release's
# python3 recipe, set via p4a.branch above). Left here for documentation.
python.version = 3.10

# (str) List of python modules to include
python.modules = kivy,wavebrute

# (bool) Enable AndroidX support
android.use_androidx = True

[buildozer]

# (str) Log level of buildozer
log_level = 2

# (str) Path to build directory
bin_dir = bin

# (str) Path to temporary build directory
build_dir = .buildozer

# (bool) Automatically update buildozer and dependencies
update = False
